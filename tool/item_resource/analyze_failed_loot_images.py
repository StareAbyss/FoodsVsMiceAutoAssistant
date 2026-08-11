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
from dataclasses import dataclass, replace
from pathlib import Path

import cv2
import numpy as np

from item_resource_common import (
    DEFAULT_LOOT_BLACKLIST_CSV,
    DEFAULT_LOOT_ROOT,
    DEFAULT_OUTPUT_ROOT,
    category_for_path,
    collect_pngs,
    read_loot_blacklist,
)


DEFAULT_FAILED_ROOT = Path("logs") / "match_failed" / "loots"
DEFAULT_REPORT_ROOT = Path("resource_other") / "战利品识别失败分析"
DEFAULT_LOOT_MASK = Path("resource") / "image" / "item" / "物品-掩模-不绑定.png"
FAILED_NAME_RE = re.compile(r"^unknown_(\d+)_(\d+)$")


@dataclass(frozen=True)
class Candidate:
    """保存单个 CDN 候选资源及其与正式识别库的关系。"""

    name: str
    category: str
    path: Path
    feature_indices: np.ndarray
    feature_colors: np.ndarray
    in_formal_resources: bool
    blacklisted: bool


@dataclass(frozen=True)
class MatchScore:
    """保存一个候选资源对失败图块提供的像素证据。"""

    candidate: Candidate
    exact_ratio: float
    near_ratio: float
    mean_color_error: float
    exact_pixels: int
    feature_pixels: int
    mismatch_locality: float


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


def read_image(path: Path) -> np.ndarray:
    """
    读取含中文路径的 PNG，并统一转换为 BGRA。

    Args:
        path: PNG 文件路径。

    Returns:
        四通道 BGRA 图像。

    Raises:
        ValueError: 文件不是可读取图片，或通道数不受支持。
    """
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"无法读取图片: {path}")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    if image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    if image.shape[2] == 4:
        return image
    raise ValueError(f"不支持的图片通道数: {path} -> {image.shape}")


def parse_failed_count(path: Path) -> int:
    """从 `unknown_编号_次数.png` 文件名读取累计失败次数。"""
    match = FAILED_NAME_RE.fullmatch(path.stem)
    return int(match.group(2)) if match else 1


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
        blacklist_path: 无法掉落道具名单。
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
    for name, path in sorted(latest_files.items()):
        image = read_image(path)
        if image.shape != loot_mask.shape:
            skipped_rows.append({
                "类型": category_for_path(latest_root, path),
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

        category = category_for_path(latest_root, path)
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


def calculate_mismatch_locality(feature_indices: np.ndarray, exact: np.ndarray, shape: tuple[int, int]) -> float:
    """
    估算不一致像素是否集中在少量连通区域，以辅助判断局部遮挡。

    Args:
        feature_indices: 候选特征像素的一维位置。
        exact: 每个特征像素是否与失败图块完全一致。
        shape: 图块的高和宽。

    Returns:
        最大不一致连通块占全部不一致像素的比例；没有不一致时返回 1。
    """
    mismatch_count = int(np.count_nonzero(~exact))
    if mismatch_count == 0:
        return 1.0

    mismatch = np.zeros(shape[0] * shape[1], dtype=np.uint8)
    mismatch[feature_indices[~exact]] = 1
    _, _, stats, _ = cv2.connectedComponentsWithStats(mismatch.reshape(shape), connectivity=8)
    if len(stats) <= 1:
        return 0.0
    return float(stats[1:, cv2.CC_STAT_AREA].max() / mismatch_count)


def score_candidate(block: np.ndarray, candidate: Candidate) -> MatchScore:
    """计算失败图块与一个候选资源的完全一致率、近似率和色差。"""
    source_colors = block[:, :, :3].reshape(-1, 3)[candidate.feature_indices]
    color_diff = np.abs(source_colors.astype(np.int16) - candidate.feature_colors.astype(np.int16))
    max_diff = color_diff.max(axis=1)
    exact = max_diff == 0
    near = max_diff <= 8
    feature_pixels = int(candidate.feature_indices.size)
    return MatchScore(
        candidate=candidate,
        exact_ratio=float(exact.mean()),
        near_ratio=float(near.mean()),
        mean_color_error=float(color_diff.mean()),
        exact_pixels=int(exact.sum()),
        feature_pixels=feature_pixels,
        # 连通域计算相对昂贵，只在候选排序完成后对 Top-N 补算。
        mismatch_locality=0.0,
    )


def best_scores(block: np.ndarray, candidates: list[Candidate], top: int) -> list[MatchScore]:
    """返回按完全一致率、近似率和色差排序的前若干候选。"""
    scores = [score_candidate(block=block, candidate=candidate) for candidate in candidates]
    scores.sort(key=lambda score: (-score.exact_ratio, -score.near_ratio, score.mean_color_error))
    top_scores = []
    for score in scores[:top]:
        source_colors = block[:, :, :3].reshape(-1, 3)[score.candidate.feature_indices]
        exact = np.all(source_colors == score.candidate.feature_colors, axis=1)
        top_scores.append(replace(
            score,
            mismatch_locality=calculate_mismatch_locality(
                feature_indices=score.candidate.feature_indices,
                exact=exact,
                shape=block.shape[:2],
            ),
        ))
    return top_scores


def confidence_for(best: MatchScore, second: MatchScore | None) -> str:
    """
    按人工复核工作流把匹配结果分为完美符合、基本符合和完全不置信。

    完美符合用于确认尚未纳入正式库的新物品；基本符合只表示候选主体特征明确，
    但可能被数量数字或战斗特效遮挡，必须经过人工确认后才能清理失败日志。
    """
    gap = best.exact_ratio - (second.exact_ratio if second else 0.0)
    if best.exact_ratio >= 0.98 and best.exact_pixels >= 40 and gap >= 0.03:
        return "完美符合"
    if best.exact_ratio >= 0.82 and best.exact_pixels >= 60 and gap >= 0.08:
        return "基本符合"
    if best.exact_ratio >= 0.65 and best.exact_pixels >= 50 and gap >= 0.06:
        return "基本符合"
    return "完全不置信"


def cause_for(best: MatchScore, confidence: str) -> str:
    """结合资源是否已入库和不一致像素分布，解释最可能的失败原因。"""
    if confidence == "完全不置信":
        return "候选证据不足，可能是严重遮挡、动画干扰、空格子或 CDN 候选范围外物品"
    if confidence == "完美符合":
        if best.candidate.in_formal_resources:
            return "当前正式资源可直接吻合；失败发生时可能尚未收录或资源版本不同"
        return "最新 CDN 资源与失败图像直接吻合，原识别库缺少该模板"
    if best.mismatch_locality >= 0.55:
        return "保留了较强物品特征，但不一致像素集中，疑似数量数字、卡片、子弹、火苗或其他局部遮挡"
    return "保留了部分物品特征，疑似大范围特效遮挡、半透明叠加或图像版本差异"


def drop_status_for(candidate: Candidate, confidence: str) -> str:
    """结合失败战利品证据与黑名单给出可掉落筛查状态。"""
    reliable = confidence in {"完美符合", "基本符合"}
    if reliable and candidate.blacklisted:
        return "黑名单冲突：失败战利品样本显示实际出现，建议复核黑名单"
    if reliable and candidate.in_formal_resources:
        return "正式识别库已有，且失败战利品样本已证实出现"
    if reliable:
        return "失败战利品样本已证实出现，建议补入正式识别库"
    if candidate.blacklisted:
        return "黑名单排除，当前匹配证据不足以推翻"
    if candidate.in_formal_resources:
        return "正式识别库已有，但当前失败样本无法可靠归因"
    return "未被黑名单排除：仅为可能掉落，仍需实掉验证"


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
