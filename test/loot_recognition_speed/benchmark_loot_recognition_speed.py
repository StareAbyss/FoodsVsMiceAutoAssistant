import argparse
import copy
import json
import statistics
import time
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from function.common.bg_img_match import mask_transform_color_to_black
from function.common.image_processing.same_size_match import one_item_match
from function.core.analyzer_of_loot_logs import EMPTY_ITEM_NAMES, LOOT_EMPTY_ITEM_NAMES, split_image_to_blocks
from function.globals import EXTRA, g_resources
from function.globals.get_paths import PATHS


DEFAULT_LOOTS_IMAGE_DIR = Path("logs") / "loots_image"


def read_image(path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), -1)


def read_ranking():
    ranking_path = Path(PATHS["config"]) / "item_ranking_dag_graph.json"
    with ranking_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data.get("ranking", [])


def split_item_name(filename):
    return filename[:-4] if filename.endswith(".png") else filename


def build_current_mask(template_crop, raw_mask_crop):
    if template_crop.shape[2] == 4:
        mask_from_template = template_crop[:, :, 3]
        _, mask_from_template = cv2.threshold(mask_from_template, 254, 255, cv2.THRESH_BINARY)
        template_bgr = template_crop[:, :, :3]
    else:
        mask_from_template = np.ones(template_crop.shape[:2], dtype=np.uint8) * 255
        template_bgr = template_crop[:, :, :3]

    if raw_mask_crop.shape[2] == 4:
        mask_alpha = raw_mask_crop[:, :, 3]
        _, mask_alpha = cv2.threshold(mask_alpha, 254, 255, cv2.THRESH_BINARY)
        final_mask = mask_transform_color_to_black(mask=raw_mask_crop[:, :, :3].copy(), quick_method=True)
        final_mask[mask_alpha != 255] = mask_from_template[mask_alpha != 255]
    else:
        final_mask = mask_transform_color_to_black(mask=raw_mask_crop.copy(), quick_method=True)

    return template_bgr, final_mask


def build_preprocessed_templates():
    loot_images = g_resources.get_item_loot_images()
    full_unlocked_mask = g_resources.RESOURCE_P["item"]["物品-掩模-不绑定.png"]
    full_locked_mask = g_resources.RESOURCE_P["item"]["物品-掩模-绑定.png"]
    raw_unlocked_mask = g_resources.RESOURCE_P["item"]["物品-掩模-不绑定.png"][2:-10:2, 2:-10:2, :]
    raw_locked_mask = g_resources.RESOURCE_P["item"]["物品-掩模-绑定.png"][2:-10:2, 2:-10:2, :]
    locked_icon = g_resources.RESOURCE_P["item"]["物品-绑定角标-战利品.png"]

    bind_region = (slice(30, 44), slice(0, 15))
    locked_mask_region = full_locked_mask[bind_region]
    bind_template_region = locked_icon[bind_region][:, :, :3]
    bind_required = ((locked_mask_region[:, :, :3] == 255).all(axis=2)) & (locked_mask_region[:, :, 3] == 255)

    templates = {}
    for filename, image in loot_images.items():
        item_name = split_item_name(filename)

        unlocked_crop = image[2:-10:2, 2:-10:2, :]
        unlocked_bgr, unlocked_mask = build_current_mask(unlocked_crop, raw_unlocked_mask)
        unlocked_exact_mask = unlocked_mask != 0

        locked_image = image.copy()
        overlay_alpha = locked_icon[:, :, 3] == 255
        locked_image[overlay_alpha] = locked_icon[overlay_alpha]
        locked_crop = locked_image[2:-10:2, 2:-10:2, :]
        locked_bgr, locked_mask = build_current_mask(locked_crop, raw_locked_mask)
        locked_exact_mask = locked_mask != 0

        image_bgr = image[:, :, :3]
        image_opaque = image[:, :, 3] == 255
        user_unlocked_feature = image_opaque & (full_unlocked_mask[:, :, 3] == 0)
        user_locked_feature = image_opaque & (full_locked_mask[:, :, 3] == 0)
        user_unlocked_mask_3 = np.repeat(user_unlocked_feature[:, :, None], 3, axis=2).astype(np.uint8)
        user_locked_mask_3 = np.repeat(user_locked_feature[:, :, None], 3, axis=2).astype(np.uint8)

        templates[item_name] = {
            "unlocked_bgr": unlocked_bgr,
            "unlocked_mask": unlocked_mask,
            "unlocked_exact_mask": unlocked_exact_mask,
            "unlocked_exact_bytes": unlocked_bgr[unlocked_exact_mask].tobytes(),
            "locked_bgr": locked_bgr,
            "locked_mask": locked_mask,
            "locked_exact_mask": locked_exact_mask,
            "locked_exact_bytes": locked_bgr[locked_exact_mask].tobytes(),
            "user_unlocked_mask_3": user_unlocked_mask_3,
            "user_unlocked_masked_bytes": (image_bgr * user_unlocked_mask_3).tobytes(),
            "user_locked_mask_3": user_locked_mask_3,
            "user_locked_masked_bytes": (image_bgr * user_locked_mask_3).tobytes(),
        }

    ordered_names = list(templates.keys())
    return {
        "templates": templates,
        "ordered_names": ordered_names,
        "bind_required": bind_required,
        "bind_template_region": bind_template_region,
    }


def is_bind_exact(block, prepared):
    source = block[30:44, 0:15, :3]
    required = prepared["bind_required"]
    return np.array_equal(source[required], prepared["bind_template_region"][required])


def match_one_original_no_save(block, list_iter=None, last_name=None, may_locked=True):
    loot_images = g_resources.get_item_loot_images()
    item_is_bind = False
    if may_locked:
        item_is_bind, _ = one_item_match(img_block=block, img_tar=None, mode="match_is_bind")

    if item_is_bind:
        for item_name, item_img in loot_images.items():
            item_name = item_name.replace(".png", "")
            if item_name in EMPTY_ITEM_NAMES and item_name not in LOOT_EMPTY_ITEM_NAMES:
                continue
            is_it, _ = one_item_match(img_block=block, img_tar=item_img, mode="match_template_with_mask_locked")
            if is_it:
                return item_name, list_iter, True

    if last_name is not None:
        if last_name in EMPTY_ITEM_NAMES and last_name not in LOOT_EMPTY_ITEM_NAMES:
            return "璇嗗埆澶辫触", list_iter, False
        item_img = loot_images[last_name + ".png"]
        is_it, _ = one_item_match(img_block=block, img_tar=item_img, mode="match_template_with_mask_tradable")
        if is_it:
            return last_name, list_iter, False

    if list_iter:
        for item_name in list_iter:
            if item_name in EMPTY_ITEM_NAMES and item_name not in LOOT_EMPTY_ITEM_NAMES:
                continue
            item_img = loot_images[item_name + ".png"]
            is_it, _ = one_item_match(img_block=block, img_tar=item_img, mode="match_template_with_mask_tradable")
            if is_it:
                return item_name, list_iter, False

    for item_name, item_img in loot_images.items():
        item_name = item_name.replace(".png", "")
        if item_name in EMPTY_ITEM_NAMES and item_name not in LOOT_EMPTY_ITEM_NAMES:
            continue
        is_it, _ = one_item_match(img_block=block, img_tar=item_img, mode="match_template_with_mask_tradable")
        if is_it:
            return item_name, list_iter, False

    return "识别失败", list_iter, False


def match_board_original_no_save(image, ranking):
    block_list = split_image_to_blocks(image=image, mode="loots")
    ranking_iter = iter(copy.deepcopy(ranking))
    last_name = None
    best_match_items = []

    for block in block_list:
        best_match_item, ranking_iter, _ = match_one_original_no_save(
            block=block,
            list_iter=ranking_iter,
            last_name=last_name,
            may_locked=False,
        )
        if best_match_item in LOOT_EMPTY_ITEM_NAMES:
            break
        if best_match_item:
            best_match_items.append(best_match_item)
        if best_match_item != "识别失败":
            last_name = best_match_item
        else:
            ranking_iter = iter(copy.deepcopy(ranking))

    return best_match_items


def match_template_preprocessed(block, candidate_names, prepared, locked=False):
    source = block[2:-10:2, 2:-10:2, :3]
    bgr_key = "locked_bgr" if locked else "unlocked_bgr"
    mask_key = "locked_mask" if locked else "unlocked_mask"
    for item_name in candidate_names:
        if item_name in EMPTY_ITEM_NAMES and item_name not in LOOT_EMPTY_ITEM_NAMES:
            continue
        candidate = prepared["templates"].get(item_name)
        if candidate is None:
            continue
        result = cv2.matchTemplate(
            source,
            candidate[bgr_key],
            cv2.TM_SQDIFF_NORMED,
            mask=candidate[mask_key],
        )
        min_val, _, _, _ = cv2.minMaxLoc(result)
        if 1 - min_val > 0.98:
            return item_name
    return None


def match_exact_preprocessed(block, candidate_names, prepared, locked=False):
    source = block[:, :, :3]
    mask_key = "user_locked_mask_3" if locked else "user_unlocked_mask_3"
    bytes_key = "user_locked_masked_bytes" if locked else "user_unlocked_masked_bytes"
    for item_name in candidate_names:
        if item_name in EMPTY_ITEM_NAMES and item_name not in LOOT_EMPTY_ITEM_NAMES:
            continue
        candidate = prepared["templates"].get(item_name)
        if candidate is None:
            continue
        if (source * candidate[mask_key]).tobytes() == candidate[bytes_key]:
            return item_name
    return None


def match_exact_then_template(block, candidate_names, prepared, locked=False):
    exact_result = match_exact_preprocessed(block, candidate_names, prepared, locked=locked)
    if exact_result is not None:
        return exact_result
    return match_template_preprocessed(block, candidate_names, prepared, locked=locked)


def match_one_with_order(block, ranking_iter, last_name, ranking, prepared, matcher, may_locked=False):
    item_is_bind = may_locked and is_bind_exact(block, prepared)
    if item_is_bind:
        item_name = matcher(block, prepared["ordered_names"], prepared, locked=True)
        return item_name or "识别失败", ranking_iter, True

    if last_name is not None:
        item_name = matcher(block, [last_name], prepared, locked=False)
        if item_name is not None:
            return item_name, ranking_iter, False

    if ranking_iter is not None:
        remaining_ranking = []
        for item_name in ranking_iter:
            remaining_ranking.append(item_name)
            matched = matcher(block, [item_name], prepared, locked=False)
            if matched is not None:
                return matched, ranking_iter, False
        ranking_iter = iter([])

    item_name = matcher(block, prepared["ordered_names"], prepared, locked=False)
    if item_name is not None:
        return item_name, ranking_iter, False

    return "识别失败", ranking_iter, False


def match_board_optimized(image, ranking, prepared, matcher):
    """
    使用完整战利品识别流程的顺序语义，测试预处理识别方案的整板速度。

    规范说明：
    战利品结算不是“每格独立随机出现”的无序集合。游戏会把掉落物按稳定顺序展示，
    当前项目通过 `item_ranking_dag_graph.json` 记录历史观测到的物品先后关系，
    并把这个有向无环图的最长链作为下一轮识别时的优先候选序列。识别整板图片时，
    每个格子先尝试上一个格子的识别结果，再沿 DAG ranking 从上一次停留处继续向后
    查找，最后才回退到全量资源遍历。这是当前战利品识别速度的主要来源，任何新的
    图片对比实现都必须保留这个顺序语义，否则单个物品的微基准不能代表真实战斗结算。

    本测试函数保留完整函数的核心顺序：
    1. 按 `split_image_to_blocks(..., mode="loots")` 把 245x490 的整板截图切为
       50 个 44x44 图标块。
    2. 对每个图标块先尝试 `last_name`，用于连续相同掉落的快速短路。
    3. 继续使用 DAG ranking 迭代器，命中后迭代器不回退，使下一格从更靠后的候选
       开始搜索。
    4. ranking 未命中时才扫描全部战利品模板。
    5. 识别到 `None-*` 空模板后停止本板后续空格识别。

    预处理方案分为两类 matcher：
    - `match_template_preprocessed`：保留 OpenCV `matchTemplate` 和原掩模语义，但把
      每个资源的裁剪图、最终 mask、绑定角标叠加图提前算好，避免每次候选比较重复
      处理 alpha、mask 和数组切片。
    - `match_exact_preprocessed`：验证新的精确数组短路思路。绑定判断先取左下角
      `物品-掩模-绑定.png` 中“白色且不透明”的像素，这些像素代表绑定角标必须
      出现的区域，再与 `物品-绑定角标-战利品.png` 的对应像素做数组相等。
      物品判断不再沿用 OpenCV 模板匹配的掩模语义，而是对每个候选资源预先生成
      44x44 全尺寸特征掩模：候选资源自身 alpha=255 的像素视为物品有效像素，
      同时把当前模式对应掩模中 alpha 不透明的位置全部排除，因为这些位置可能是
      绑定角标或掉落数量数字占位。最终得到 0/1 三通道掩模后，对待识别图块和
      候选资源分别执行数组乘法，只比较乘掩模后的 BGR 数组是否完全一致。
      这个方案速度理论上更高，但它要求截图像素与资源像素完全一致；若游戏渲染、
      缩放、抗锯齿、压缩或透明区处理产生 1 个像素差异，就会漏识别。因此它当前
      只作为基准和正确性对比，不能在未通过真实截图回归前替换正式识别逻辑。

    Args:
        image: 完整战利品截图，通常为 245x490x4 的 numpy.ndarray。
        ranking: 从 item_ranking_dag_graph.json 读取的 DAG ranking 列表。
        prepared: `build_preprocessed_templates` 生成的模板缓存。
        matcher: 具体候选比较函数。

    Returns:
        list[str]: 按截图顺序识别出的物品名称，识别失败时保留 "识别失败"。
    """
    block_list = split_image_to_blocks(image=image, mode="loots")
    ranking_iter = iter(copy.deepcopy(ranking))
    last_name = None
    best_match_items = []

    for block in block_list:
        best_match_item, ranking_iter, _ = match_one_with_order(
            block=block,
            ranking_iter=ranking_iter,
            last_name=last_name,
            ranking=ranking,
            prepared=prepared,
            matcher=matcher,
            may_locked=False,
        )
        if best_match_item in LOOT_EMPTY_ITEM_NAMES:
            break
        if best_match_item:
            best_match_items.append(best_match_item)
        if best_match_item != "识别失败":
            last_name = best_match_item
        else:
            ranking_iter = iter(copy.deepcopy(ranking))

    return best_match_items


def benchmark(label, images, fn, repeat=1):
    times = []
    counts = []
    results = []
    total_start = time.perf_counter()
    for _ in range(repeat):
        for image_path, image in images:
            start = time.perf_counter()
            result = fn(image_path, image)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            counts.append(len(result))
            results.append(result)
    total = time.perf_counter() - total_start
    boards = len(images) * repeat
    return {
        "label": label,
        "boards": boards,
        "items": sum(counts),
        "total_s": total,
        "boards_per_s": boards / total if total else 0,
        "items_per_s": sum(counts) / total if total else 0,
        "avg_ms": statistics.mean(times) * 1000,
        "p50_ms": statistics.median(times) * 1000,
        "p95_ms": sorted(times)[max(0, int(len(times) * 0.95) - 1)] * 1000,
        "results": results,
    }


def compare_results(reference, target):
    mismatches = []
    for index, (ref_items, target_items) in enumerate(zip(reference, target)):
        if ref_items != target_items:
            mismatches.append((index, ref_items, target_items))
    return mismatches


def format_mismatch(index, ref_items, target_items):
    shared_prefix = 0
    for ref_item, target_item in zip(ref_items, target_items):
        if ref_item != target_item:
            break
        shared_prefix += 1

    ref_tail = ref_items[shared_prefix:shared_prefix + 5]
    target_tail = target_items[shared_prefix:shared_prefix + 5]
    return (
        f"  mismatch#{index}: same_prefix={shared_prefix} "
        f"ref_len={len(ref_items)} target_len={len(target_items)} "
        f"ref_next={ref_tail} target_next={target_tail}"
    )


def main():
    parser = argparse.ArgumentParser(description="测试战利品整板识别速度和预处理识别方案正确性。")
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_LOOTS_IMAGE_DIR)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    EXTRA.EXTRA_LOG_MATCH = False

    image_paths = sorted(args.image_dir.glob("*.png"))
    if args.limit > 0:
        image_paths = image_paths[:args.limit]
    images = [(path, read_image(path)) for path in image_paths]
    images = [(path, image) for path, image in images if image is not None and image.shape[:2] == (245, 490)]

    ranking = read_ranking()
    prepared = build_preprocessed_templates()

    original = benchmark(
        "original_recognition_no_save",
        images,
        lambda path, image: match_board_original_no_save(image, ranking),
        repeat=args.repeat,
    )

    template_preprocessed = benchmark(
        "preprocessed_match_template",
        images,
        lambda path, image: match_board_optimized(image, ranking, prepared, match_template_preprocessed),
        repeat=args.repeat,
    )
    exact_preprocessed = benchmark(
        "preprocessed_exact_equal",
        images,
        lambda path, image: match_board_optimized(image, ranking, prepared, match_exact_preprocessed),
        repeat=args.repeat,
    )
    exact_then_template = benchmark(
        "preprocessed_exact_then_template",
        images,
        lambda path, image: match_board_optimized(image, ranking, prepared, match_exact_then_template),
        repeat=args.repeat,
    )

    results = [original, template_preprocessed, exact_preprocessed, exact_then_template]
    print(f"images={len(images)} repeat={args.repeat} ranking={len(ranking)} loot_templates={len(prepared['ordered_names'])}")
    for result in results:
        print(
            f"{result['label']}: boards={result['boards']} items={result['items']} "
            f"total_s={result['total_s']:.6f} boards_per_s={result['boards_per_s']:.2f} "
            f"items_per_s={result['items_per_s']:.2f} avg_ms={result['avg_ms']:.3f} "
            f"p50_ms={result['p50_ms']:.3f} p95_ms={result['p95_ms']:.3f}"
        )

    for result in [template_preprocessed, exact_preprocessed, exact_then_template]:
        mismatches = compare_results(original["results"], result["results"])
        print(f"{result['label']}_mismatches={len(mismatches)}")
        for index, ref_items, target_items in mismatches[:5]:
            print(format_mismatch(index, ref_items, target_items))


if __name__ == "__main__":
    main()
