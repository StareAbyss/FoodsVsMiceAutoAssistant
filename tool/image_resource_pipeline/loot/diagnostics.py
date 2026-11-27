"""
战利品识别失败样本离线分析工具。

业务处理规则不是单纯按数值高低自动删图，而是分为三种结论：

1. 完美符合：用于确认失败图块就是某个未纳入正式识别库的物品。人工核实后把
   干净 CDN 图片加入正式库，再清理对应失败日志。
2. 基本符合：通常是数量数字、卡片、子弹、火苗等局部遮挡。只生成待确认清单，
   必须由维护者明确确认后才能删除，不能把遮挡图当作正式模板。
3. 完全不置信：可能是活动道具、截图/分块异常、严重遮挡或候选范围外物品，保留
   给维护者人工检查，禁止自动删除。

“正式识别库已有”仍可能对应历史失败日志：失败样本不会在后续补资源时自动回填
或删除；运行中的 FAA 也可能尚未刷新内存资源。完整判断、处理和删除边界见同目录
`README.md`，修改匹配阈值、报告分类或清理流程前必须同步核对该规范。
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .paths import (DEFAULT_LOOT_BLACKLIST_CSV, DEFAULT_LOOT_ROOT, DEFAULT_OUTPUT_ROOT,
                    DEFAULT_FAILED_ROOT, DEFAULT_REPORT_ROOT, DEFAULT_LOOT_MASK)
from ..common.files import category_for_path, collect_pngs
from .sync import read_loot_blacklist
from .matching import (Candidate, read_image, parse_failed_count, best_scores, confidence_for, cause_for, drop_status_for)


FAILED_NAME_RE = re.compile(r"^unknown_(\d+)_(\d+)$")






def build_arg_parser() -> argparse.ArgumentParser:
    """构建离线分析工具的命令行参数。"""
    parser = argparse.ArgumentParser(description="把战利品识别失败图块与最新 CDN 分类资源进行离线匹配。")
    parser.add_argument("--failed-root", type=Path, default=DEFAULT_FAILED_ROOT, help="FAA 识别失败图块目录")
    parser.add_argument("--latest-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="最新 CDN 分类资源根目录")
    parser.add_argument("--loot-root", type=Path, default=DEFAULT_LOOT_ROOT, help="正式战利品识别资源根目录")
    parser.add_argument("--blacklist", type=Path, default=DEFAULT_LOOT_BLACKLIST_CSV, help="无法掉落道具黑名单")
    parser.add_argument("--loot-mask", type=Path, default=DEFAULT_LOOT_MASK, help="正式识别使用的不绑定物品掩模")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_ROOT, help="报告输出目录")
    parser.add_argument("--top", type=int, default=3, help="每个失败图块保留的候选数量")
    return parser






def build_candidates(
        latest_root: Path,
        loot_root: Path,
        blacklist_path: Path,
        loot_mask_path: Path,
) -> tuple[list[Candidate], list[dict[str, object]]]:
    """
    按正式识别逻辑的透明像素和界面掩模构建 CDN 候选特征。

    正式识别会忽略数量数字等固定界面区域，并只使用资源图片 alpha 完全不透明的
    像素。离线分析复用相同特征区，但允许一部分像素被卡片、子弹、火苗等覆盖。

    Args:
        latest_root: 已分类的最新 CDN 资源根目录。
        loot_root: FAA 正式战利品识别资源根目录。
        blacklist_path: 道具可掉落黑名单。
        loot_mask_path: 正式识别使用的不绑定物品掩模。

    Returns:
        可参与离线匹配的候选资源列表，以及因尺寸不兼容而跳过的资源明细。
    """
    latest_files = collect_pngs(latest_root)
    formal_files = collect_pngs(loot_root)
    blacklist = read_loot_blacklist(blacklist_path)
    loot_mask = read_image(loot_mask_path)

    candidates = []
    skipped_rows = []
    # 主流程清理白名单候选副本后，仍需用正式图参与分差比较，避免未知图被过度匹配。
    sources = {name: (path, loot_root) for name, path in formal_files.items()}
    sources.update({name: (path, latest_root) for name, path in latest_files.items()})
    for name, (path, source_root) in sorted(sources.items()):
        image = read_image(path)
        if image.shape != loot_mask.shape:
            skipped_rows.append({
                "类型": category_for_path(source_root, path),
                "名称": name,
                "图片尺寸": f"{image.shape[1]}x{image.shape[0]}",
                "需要尺寸": f"{loot_mask.shape[1]}x{loot_mask.shape[0]}",
                "原因": "尺寸与 44x44 战利品图块不兼容，未参与匹配",
                "路径": str(path),
            })
            continue

        feature_mask = (image[:, :, 3] == 255) & (loot_mask[:, :, 3] == 0)
        feature_indices = np.flatnonzero(feature_mask.reshape(-1))
        if feature_indices.size == 0:
            continue

        category = category_for_path(source_root, path)
        candidates.append(Candidate(
            name=name,
            category=category,
            path=path,
            feature_indices=feature_indices,
            feature_colors=image[:, :, :3].reshape(-1, 3)[feature_indices],
            in_formal_resources=name in formal_files,
            blacklisted=(category, name) in blacklist,
        ))
    return candidates, skipped_rows














def path_for_html(target: Path, report_root: Path) -> str:
    """生成 HTML 中可用的相对文件路径。"""
    import os

    return Path(os.path.relpath(target.resolve(), report_root.resolve())).as_posix()


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    """以 Excel 友好的 UTF-8 BOM 编码写入 CSV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_html(report_root: Path, detail_rows: list[dict[str, object]]) -> None:
    """生成带失败图和最佳候选并排预览的人工复核页面。"""
    cards = []
    for row in detail_rows:
        failed_src = html.escape(path_for_html(Path(str(row["失败图像路径"])), report_root))
        candidate_src = html.escape(path_for_html(Path(str(row["最佳候选路径"])), report_root))
        search_text = html.escape(" ".join(str(value) for value in row.values()))
        cards.append(f"""
        <article class="card" data-search="{search_text}">
          <div class="images"><figure><img src="{failed_src}"><figcaption>{html.escape(str(row['失败图像']))}</figcaption></figure>
          <figure><img src="{candidate_src}"><figcaption>{html.escape(str(row['最佳候选名称']))}</figcaption></figure></div>
          <p><b>{html.escape(str(row['置信度']))}</b> · 历史 {row['历史失败次数']} 次 · 完全一致 {row['完全一致像素率']} · 分差 {row['前两名分差']}</p>
          <p>{html.escape(str(row['可掉落筛查']))}</p><p>{html.escape(str(row['可能原因']))}</p>
          <details><summary>Top 3</summary><pre>{html.escape(str(row['Top3候选']))}</pre></details>
        </article>""")

    document = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>战利品识别失败分析</title>
<style>body{{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:20px;background:#f5f6f8;color:#202124}}input{{width:min(720px,95%);padding:10px;margin-bottom:16px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}}.card{{background:white;border:1px solid #ddd;border-radius:10px;padding:12px}}.images{{display:flex;gap:18px}}figure{{margin:0;text-align:center}}img{{width:88px;height:88px;image-rendering:pixelated;background:#31506d;border-radius:6px}}figcaption{{max-width:180px;font-size:12px}}p{{margin:7px 0;font-size:13px}}pre{{white-space:pre-wrap}}</style></head>
<body><h1>战利品识别失败分析</h1><p>左侧为失败图块，右侧为最新 CDN 候选。结论用于离线筛查，不会自动修改正式识别资源或可掉落名单。</p>
<input id="filter" placeholder="筛选物品名、置信度、黑名单、遮挡……"><div class="grid">{''.join(cards)}</div>
<script>const input=document.querySelector('#filter');input.addEventListener('input',()=>{{const q=input.value.toLowerCase();document.querySelectorAll('.card').forEach(x=>x.hidden=!x.dataset.search.toLowerCase().includes(q));}});</script></body></html>"""
    (report_root / "人工复核.html").write_text(document, encoding="utf-8")


def write_summary(report_root: Path, detail_rows: list[dict[str, object]], aggregate_rows: list[dict[str, object]]) -> None:
    """写入简要 Markdown，方便不打开 CSV 时快速查看结果规模。"""
    confidence_counts = Counter(str(row["置信度"]) for row in detail_rows)
    total_history = sum(int(row["历史失败次数"]) for row in detail_rows)
    reliable_rows = [row for row in detail_rows if row["置信度"] in {"完美符合", "基本符合"}]
    new_rows = [
        row for row in reliable_rows
        if row["置信度"] == "完美符合"
        and row["正式识别资源已有"] == "否"
        and row["黑名单"] == "否"
    ]
    blacklist_rows = [row for row in reliable_rows if row["黑名单"] == "是"]
    obstructed_rows = [row for row in detail_rows if row["置信度"] == "基本符合"]
    high_priority = [
        row for row in aggregate_rows
        if row["最高置信度"] in {"完美符合", "基本符合"}
    ][:30]
    lines = [
        "# 战利品识别失败分析摘要",
        "",
        f"- 失败图块：{len(detail_rows)} 个，累计出现 {total_history} 次。",
        f"- 匹配分级：{dict(confidence_counts)}。",
        f"- 建议补入识别库：{len(set(row['最佳候选名称'] for row in new_rows))} 项，"
        f"由 {len(new_rows)} 个失败图块、累计 {sum(int(row['历史失败次数']) for row in new_rows)} 次记录支持。",
        f"- 黑名单冲突：{len(set(row['最佳候选名称'] for row in blacklist_rows))} 项，"
        f"累计 {sum(int(row['历史失败次数']) for row in blacklist_rows)} 次记录支持重新核实。",
        f"- 基本符合、待确认清理：{len(obstructed_rows)} 个疑似数量数字或特效遮挡样本。",
        f"- 完全不置信、保留人工检查：{confidence_counts.get('完全不置信', 0)} 个样本。",
        "- `CDN 中存在` 不等于 `游戏中能够掉落`；黑名单外的新候选仍需实际掉落验证。",
        "- 完整结果见 `逐图匹配明细.csv`，按物品累计结果见 `候选物品汇总.csv`，图片对照见 `人工复核.html`。",
        "",
        "## 优先复核候选（按累计失败次数）",
        "",
        "|候选物品|类型|可靠样本数|累计失败次数|最高置信度|可掉落筛查|",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in high_priority:
        lines.append(
            f"|{row['候选物品']}|{row['类型']}|{row['可靠匹配样本数']}|{row['累计失败次数']}|"
            f"{row['最高置信度']}|{row['可掉落筛查']}|"
        )
    (report_root / "分析摘要.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    """执行只读匹配并生成 CSV、Markdown 和 HTML 报告。"""
    args = build_arg_parser().parse_args()
    if args.top < 2:
        raise ValueError("--top 至少为 2，置信度需要使用前两名分差")

    candidates, skipped_rows = build_candidates(
        latest_root=args.latest_root,
        loot_root=args.loot_root,
        blacklist_path=args.blacklist,
        loot_mask_path=args.loot_mask,
    )
    def failed_sort_key(path: Path) -> tuple[int, int | str]:
        """优先按 FAA 失败样本编号排序，兼容目录中的人工命名 PNG。"""
        match = FAILED_NAME_RE.fullmatch(path.stem)
        return (0, int(match.group(1))) if match else (1, path.name)

    failed_paths = sorted(args.failed_root.glob("*.png"), key=failed_sort_key)
    args.output.mkdir(parents=True, exist_ok=True)

    detail_rows = []
    for index, failed_path in enumerate(failed_paths, start=1):
        block = read_image(failed_path)
        scores = best_scores(block=block, candidates=candidates, top=args.top)
        if len(scores) < 2:
            raise ValueError("有效候选少于 2 个，无法计算匹配分差")
        best, second = scores[0], scores[1]
        confidence = confidence_for(best=best, second=second)
        gap = best.exact_ratio - second.exact_ratio
        detail_rows.append({
            "失败图像": failed_path.name,
            "历史失败次数": parse_failed_count(failed_path),
            "最佳候选名称": best.candidate.name,
            "类型": best.candidate.category,
            "置信度": confidence,
            "完全一致像素率": f"{best.exact_ratio:.4f}",
            "近似像素率": f"{best.near_ratio:.4f}",
            "完全一致像素数": best.exact_pixels,
            "候选特征像素数": best.feature_pixels,
            "平均颜色误差": f"{best.mean_color_error:.2f}",
            "前两名分差": f"{gap:.4f}",
            "不一致像素集中度": f"{best.mismatch_locality:.4f}",
            "正式识别资源已有": "是" if best.candidate.in_formal_resources else "否",
            "黑名单": "是" if best.candidate.blacklisted else "否",
            "可掉落筛查": drop_status_for(best.candidate, confidence),
            "可能原因": cause_for(best=best, confidence=confidence),
            "次优候选": second.candidate.name,
            "次优完全一致像素率": f"{second.exact_ratio:.4f}",
            "Top3候选": " | ".join(f"{score.candidate.name}:{score.exact_ratio:.4f}" for score in scores),
            "失败图像路径": str(failed_path),
            "最佳候选路径": str(best.candidate.path),
        })
        if index % 100 == 0:
            print(f"已分析 {index}/{len(failed_paths)}", flush=True)

    confidence_rank = {"完美符合": 2, "基本符合": 1, "完全不置信": 0}
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in detail_rows:
        grouped[(str(row["类型"]), str(row["最佳候选名称"]))].append(row)

    aggregate_rows = []
    for (category, name), rows in grouped.items():
        reliable_rows = [row for row in rows if row["置信度"] != "完全不置信"]
        best_row = max(rows, key=lambda row: float(row["完全一致像素率"]))
        aggregate_rows.append({
            "候选物品": name,
            "类型": category,
            "匹配样本数": len(rows),
            "可靠匹配样本数": len(reliable_rows),
            "累计失败次数": sum(int(row["历史失败次数"]) for row in reliable_rows),
            "最高置信度": max((str(row["置信度"]) for row in rows), key=lambda value: confidence_rank[value]),
            "最佳完全一致像素率": best_row["完全一致像素率"],
            "正式识别资源已有": best_row["正式识别资源已有"],
            "黑名单": best_row["黑名单"],
            "可掉落筛查": best_row["可掉落筛查"],
            "代表失败图像": best_row["失败图像"],
            "候选资源路径": best_row["最佳候选路径"],
        })
    aggregate_rows.sort(key=lambda row: (-int(row["累计失败次数"]), -int(row["可靠匹配样本数"]), str(row["候选物品"])))

    detail_fields = list(detail_rows[0].keys()) if detail_rows else []
    aggregate_fields = list(aggregate_rows[0].keys()) if aggregate_rows else []
    write_csv(args.output / "逐图匹配明细.csv", detail_rows, detail_fields)
    write_csv(args.output / "候选物品汇总.csv", aggregate_rows, aggregate_fields)

    suggested_rows = [
        row for row in aggregate_rows
        if int(row["可靠匹配样本数"]) > 0
        and row["最高置信度"] == "完美符合"
        and row["正式识别资源已有"] == "否"
        and row["黑名单"] == "否"
    ]
    blacklist_review_rows = [
        row for row in aggregate_rows
        if int(row["可靠匹配样本数"]) > 0 and row["黑名单"] == "是"
    ]
    interference_rows = [
        row for row in detail_rows
        if row["置信度"] == "基本符合"
    ]
    untrusted_rows = [row for row in detail_rows if row["置信度"] == "完全不置信"]
    reliably_matched_new_names = {str(row["候选物品"]) for row in suggested_rows}
    unverified_rows = [
        {
            "类型": candidate.category,
            "名称": candidate.name,
            "状态": "最新资源存在且未被黑名单排除，但当前失败样本没有可靠匹配",
            "候选资源路径": str(candidate.path),
        }
        for candidate in candidates
        if not candidate.in_formal_resources
        and not candidate.blacklisted
        and candidate.name not in reliably_matched_new_names
    ]
    write_csv(args.output / "建议补入正式识别资源.csv", suggested_rows, aggregate_fields)
    write_csv(args.output / "黑名单冲突复核.csv", blacklist_review_rows, aggregate_fields)
    write_csv(args.output / "基本符合_待确认清理.csv", interference_rows, detail_fields)
    write_csv(args.output / "完全不置信_保留人工检查.csv", untrusted_rows, detail_fields)
    write_csv(args.output / "仍待实掉验证候选.csv", unverified_rows, ["类型", "名称", "状态", "候选资源路径"])
    write_csv(args.output / "尺寸不兼容候选.csv", skipped_rows, ["类型", "名称", "图片尺寸", "需要尺寸", "原因", "路径"])
    write_html(args.output, detail_rows)
    write_summary(args.output, detail_rows, aggregate_rows)

    print(f"失败图块: {len(failed_paths)}")
    print(f"最新候选: {len(candidates)}")
    print(f"尺寸不兼容候选: {len(skipped_rows)}")
    print(f"建议补入正式识别资源: {len(suggested_rows)}")
    print(f"黑名单冲突复核: {len(blacklist_review_rows)}")
    print(f"基本符合、待确认清理: {len(interference_rows)}")
    print(f"完全不置信、保留人工检查: {len(untrusted_rows)}")
    print(f"仍待实掉验证候选: {len(unverified_rows)}")
    print(f"报告目录: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
