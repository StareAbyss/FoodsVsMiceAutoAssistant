"""失败样本匹配与白名单建议，不生成诊断表或修改资源。"""

import re
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
import cv2
import numpy as np
from .sync import valid_loot_image

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

def whitelist_suggestions(
    images: dict[tuple[str, str], Path], unknown: set[tuple[str, str]],
    failed_root: Path, mask_path: Path,
) -> list[dict[str, object]]:
    """复用既有完美符合阈值，只对未分类物品累计至少两次的完美证据提出建议。"""
    failed_files = sorted(failed_root.glob("*.png"))
    if not failed_files or not (unknown & images.keys()):
        return []
    mask = read_image(mask_path)
    candidates = []
    for (category, name), path in sorted(images.items()):
        if not valid_loot_image(path):
            continue
        image = read_image(path)
        if image.shape != mask.shape:
            continue
        indices = ((image[:, :, 3] == 255) & (mask[:, :, 3] == 0)).reshape(-1).nonzero()[0]
        if indices.size:
            candidates.append(Candidate(name, category, path, indices, image[:, :, :3].reshape(-1, 3)[indices],
                                        (category, name) not in unknown, False))
    if len(candidates) < 2:
        print("[战利品资源] 有效候选不足两个，无法计算匹配分差，本次不提出白名单建议。")
        return []
    evidence = defaultdict(list)
    for index, path in enumerate(failed_files, start=1):
        try:
            block = read_image(path)
        except ValueError:
            continue
        if block.shape != mask.shape:
            continue
        scores = best_scores(block, candidates, top=2)
        best, second = scores[:2]
        key = best.candidate.category, best.candidate.name
        if key in unknown and confidence_for(best, second) == "完美符合":
            evidence[key].append((path.name, parse_failed_count(path), best.exact_ratio))
        if index % 100 == 0:
            print(f"[战利品资源] 失败样本匹配 {index}/{len(failed_files)}", flush=True)
    return [
        {"类型": key[0], "名称": key[1], "完美样本数": len(rows),
         "完美样本累计次数": sum(row[1] for row in rows),
         "最高一致率": f"{max(row[2] for row in rows):.4f}",
         "失败样本": " | ".join(row[0] for row in rows), "候选图片": str(images[key]),
         "建议": "建议直接写入白名单，请人工确认"}
        for key, rows in sorted(evidence.items()) if sum(row[1] for row in rows) >= 2
    ]
