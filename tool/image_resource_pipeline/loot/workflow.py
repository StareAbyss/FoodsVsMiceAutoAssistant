"""战利品获取、三名单处理、失败证据分析与同步的整轮编排。"""

import tempfile
import time
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from function.common.loot_policy import read_drop_list
from ..common.files import atomic_copy, write_csv
from .classification import parse_target_items
from .sync import scan_images, sort_loot_list, sync_whitelist_images, cleanup_images
from .matching import whitelist_suggestions

def run_pipeline(args, excel_path: Path, fetch) -> int:
    """
    下载、分析并落实人工名单，黑白名单只排序，不自动增删条目。

    下载或图片校验失败时保留原白名单模板；冲突项目暂停同步和清理。
    所有候选先写独立目录，分析完成后才更新正式模板和执行精确文件清理。

    Args:
        args: 下载入口的参数，包含各目录、三名单与下载设置。
        excel_path: 本轮固定的资源快照。
        fetch: 下载单个物品的函数，测试可注入本地数据源。

    Returns:
        0-正常完成；1-存在冲突、下载失败或不兼容图片。
    """
    white, black = read_drop_list(args.whitelist), read_drop_list(args.blacklist)
    if len({args.whitelist.resolve(), args.blacklist.resolve(), args.unclassified.resolve()}) != 3:
        raise ValueError("黑名单、白名单和未分类名单必须是三个不同的文件")
    conflicts = white & black
    formal_root, candidate_root = args.loot_root.resolve(), args.output.resolve()
    if formal_root == candidate_root or formal_root.is_relative_to(candidate_root) or candidate_root.is_relative_to(formal_root):
        raise ValueError("候选与正式库目录必须互相独立")
    formal, cached = scan_images(formal_root), scan_images(candidate_root)
    grouped = {}
    for item in parse_target_items(excel_path):
        item = replace(item, name=Path(item.filename).stem)
        key = item.item_type, item.name
        previous = grouped.get(key)
        grouped[key] = replace(item, urls=tuple(dict.fromkeys((previous.urls if previous else ()) + item.urls)))
    # 历史正式资源与未处理候选也属于维护范围，不因最新表缺少条目而丢失。
    scope = set(grouped) | set(formal) | set(cached)
    unknown = scope - white - black
    white_names = defaultdict(set)
    for category, name in white:
        white_names[name].add(category)
    if any(len(categories) > 1 for categories in white_names.values()):
        raise ValueError("白名单存在跨类型同名图片，运行时无法区分，请先消除重名")
    for key in conflicts:
        print(f"[战利品资源] 黑白名单冲突，暂停该物品同步与清理：{key[0]}/{key[1]}")
    if args.dry_run:
        print(f"[战利品资源] 预览：范围 {len(scope)}，白名单 {len(white)}，黑名单 {len(black)}，未分类 {len(unknown)}。")
        return int(bool(conflicts))
    sort_loot_list(args.whitelist)
    sort_loot_list(args.blacklist)
    candidate_root.mkdir(parents=True, exist_ok=True)
    write_csv(args.unclassified, [{"类型": cat, "名称": name} for cat, name in sorted(unknown)], ["类型", "名称"])
    downloads, errors, warnings = [], [], []
    fresh = {key: path for key, path in cached.items() if key in white and key not in grouped and key not in conflicts}
    # 整轮暂存目录离开时自动移除，不会把半张下载图写入正式库。
    with tempfile.TemporaryDirectory(prefix="download-", dir=candidate_root) as directory:
        staging = Path(directory)
        for index, (key, item) in enumerate(sorted(grouped.items()), start=1):
            if key in conflicts:
                continue
            source = cached.get(key)
            if args.offline:
                source = source or (formal.get(key) if key in white else None)
                status = "使用缓存" if source else ("无路径" if not item.urls else "无缓存")
                detail = ""
            elif source and key not in white and not args.force:
                status, detail = "使用缓存", ""
            else:
                status, detail = fetch(item, staging, args.timeout, True, args.downloader)
                if status == "已下载":
                    incoming = staging / item.item_type / item.filename
                    source = candidate_root / item.item_type / item.filename
                    atomic_copy(incoming, source)
                time.sleep(args.sleep)
            downloads.append({"类型": key[0], "名称": key[1], "状态": status, "详情": detail})
            if index % 25 == 0:
                print(f"[战利品资源] 获取候选 {index}/{len(grouped)}", flush=True)
            if status in {"失败", "无路径", "无缓存"}:
                if key not in black or status == "失败":
                    messages = warnings if status in {"无路径", "无缓存"} and key not in white else errors
                    messages.append(f"{key[0]}/{key[1]}：{status}")
                continue
            if source:
                fresh[key] = source
    cached = scan_images(candidate_root)
    # 从正式库退回未分类时，保留干净图片供人工核验；不把白名单旧缓存当成下载成功。
    for key in unknown & set(formal):
        if key not in cached:
            target = candidate_root / key[0] / (key[1] + ".png")
            atomic_copy(formal[key], target)
            cached[key] = target
    analysis_images = {key: path for key, path in (formal | cached).items() if key not in black and key not in conflicts}
    suggestions = whitelist_suggestions(analysis_images, unknown, args.failed_root, args.loot_mask)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.report_dir / "白名单建议.csv", suggestions,
              ["类型", "名称", "完美样本数", "完美样本累计次数", "最高一致率", "失败样本", "候选图片", "建议"])
    (added, updated, unchanged), sync_errors = sync_whitelist_images(fresh, white, conflicts, formal_root)
    errors.extend(sync_errors)
    removed_formal, removed_candidates = cleanup_images(formal, cached, white, unknown, conflicts)
    summary = [f"# 战利品资源同步\n", f"模式：{'离线核验' if args.offline else '联网获取'}；数据源：{excel_path}",
               f"新增 {added}，更新 {updated}，未变化 {unchanged}；清理正式图 {removed_formal}，候选副本 {removed_candidates}。",
               f"未分类 {len(unknown)}，白名单建议 {len(suggestions)}，冲突 {len(conflicts)}，错误 {len(errors)}，缺图待核验 {len(warnings)}。"]
    if unknown:
        image_count = sum(key in cached and cached[key].is_file() for key in unknown)
        summary.append(f"请立即手动分类 {args.unclassified}；未分类图片目录：{candidate_root}（已有图 {image_count}/{len(unknown)}）。")
    for row in suggestions:
        summary.append(f"建议加入白名单：{row['类型']}/{row['名称']}，完美匹配累计 {row['完美样本累计次数']} 次。")
    summary.extend(errors)
    summary.extend(warnings)
    (args.report_dir / "运行摘要.md").write_text("\n\n".join(summary) + "\n", encoding="utf-8")
    if args.manifest:
        write_csv(args.manifest, downloads, ["类型", "名称", "状态", "详情"])
    for line in summary[1:]:
        print(line)
    return int(bool(errors or conflicts))
