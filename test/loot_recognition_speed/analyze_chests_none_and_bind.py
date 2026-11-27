from collections import Counter, defaultdict
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from function.core.analyzer_of_loot_logs import CHEST_EMPTY_ITEM_NAMES, _get_loot_match_cache, match_what_item_is, split_image_to_blocks
from function.common.image_processing.same_size_match import one_item_match
from test.loot_recognition_speed.benchmark_loot_recognition_speed import read_image


CHESTS_IMAGE_DIR = ROOT_DIR / "logs" / "chests_image"
OUT_DIR = ROOT_DIR / "test" / "loot_recognition_speed"


def _font(size):
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    font_path = next((path for path in candidates if path.exists()), None)
    return ImageFont.truetype(str(font_path), size) if font_path else ImageFont.load_default()


def render_bgra(img, scale=5):
    bgr = img[:, :, :3].astype(np.float32)
    alpha = img[:, :, 3:4].astype(np.float32) / 255.0
    h, w = img.shape[:2]
    yy, xx = np.indices((h, w))
    checker = np.where(((xx // 4 + yy // 4) % 2)[:, :, None] == 0, 230, 190).astype(np.float32)
    composed = (bgr * alpha + checker * (1.0 - alpha)).astype(np.uint8)
    rgb = cv2.cvtColor(composed, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb).resize((w * scale, h * scale), Image.Resampling.NEAREST)


def save_contact_sheet(records, output_path, title, max_items=30):
    shown = records[:max_items]
    cols = 6
    scale = 5
    cell_img = 44 * scale
    label_h = 64
    gap = 18
    title_h = 42
    rows = max(1, (len(shown) + cols - 1) // cols)
    canvas_w = cols * cell_img + (cols - 1) * gap
    canvas_h = title_h + rows * (cell_img + label_h) + max(0, rows - 1) * gap
    canvas = Image.new("RGB", (canvas_w, canvas_h), (245, 245, 245))
    draw = ImageDraw.Draw(canvas)
    title_font = _font(18)
    label_font = _font(13)
    draw.text((0, 8), title, fill=(20, 20, 20), font=title_font)

    for i, record in enumerate(shown):
        row, col = divmod(i, cols)
        x = col * (cell_img + gap)
        y = title_h + row * (cell_img + label_h + gap)
        canvas.paste(render_bgra(record["block"], scale=scale), (x, y))
        draw.text((x, y + cell_img + 4), f"{i + 1}. {record['name']} idx={record['index']}", fill=(20, 20, 20), font=label_font)
        draw.text((x, y + cell_img + 26), f"diff={record.get('bgr_diff', '-')}", fill=(20, 20, 20), font=label_font)
        draw.text((x, y + cell_img + 48), record["path"][:20], fill=(20, 20, 20), font=label_font)

    canvas.save(output_path)


def main():
    cache = _get_loot_match_cache()
    bind_required = cache["bind_required"]
    bind_template_region = cache["bind_template_region"]
    files = sorted(CHESTS_IMAGE_DIR.glob("*.png"))
    none_records = []
    bind_records = []
    bind_exact_only = 0
    bind_legacy_only = 0
    bind_both = 0
    total_blocks = 0
    recognized = Counter()

    for image_path in files:
        image = read_image(image_path)
        if image is None or image.shape[0] != 44 or image.shape[1] % 44 != 0:
            continue

        for block_index, block in enumerate(split_image_to_blocks(image=image, mode="chests")):
            total_blocks += 1
            name, _, is_locked = match_what_item_is(
                block=block,
                list_iter=None,
                last_name=None,
                may_locked=True,
                empty_item_names=CHEST_EMPTY_ITEM_NAMES,
            )
            recognized[name] += 1

            exact_bind = False
            if np.any(bind_required):
                bind_source = block[30:44, 0:15, :3]
                exact_bind = np.array_equal(bind_source[bind_required], bind_template_region[bind_required])
            legacy_bind, _ = one_item_match(img_block=block, img_tar=None, mode="match_is_bind")
            if exact_bind and legacy_bind:
                bind_both += 1
            elif exact_bind:
                bind_exact_only += 1
            elif legacy_bind:
                bind_legacy_only += 1

            if exact_bind or legacy_bind or is_locked:
                bind_records.append({
                    "path": image_path.name,
                    "index": block_index,
                    "name": f"{name}{'-绑定' if is_locked else ''}",
                    "block": block,
                    "exact_bind": exact_bind,
                    "legacy_bind": legacy_bind,
                    "old_is_locked": is_locked,
                })

            if name in CHEST_EMPTY_ITEM_NAMES:
                # Use the current resource template for a simple full BGR diff count.
                from function.globals import g_resources
                template_array = g_resources.get_item_loot_images()[name + ".png"]
                bgr_diff = int(np.any(block[:, :, :3] != template_array[:, :, :3], axis=2).sum())

                none_records.append({
                    "path": image_path.name,
                    "index": block_index,
                    "name": name,
                    "block": block,
                    "key": block.tobytes(),
                    "bgr_diff": bgr_diff,
                })

    none_groups = defaultdict(list)
    for record in none_records:
        none_groups[(record["name"], record["key"])].append(record)

    none_representatives = [group[0] for group in none_groups.values()]
    none_representatives = sorted(none_representatives, key=lambda item: (item["name"], item["bgr_diff"], item["path"], item["index"]))
    bind_representatives = bind_records[:30]

    save_contact_sheet(
        records=none_representatives,
        output_path=OUT_DIR / "chests_none_variants.png",
        title=f"宝箱 None 样本：{len(none_records)} 个，精确像素变体 {len(none_groups)} 种",
    )
    if bind_representatives:
        save_contact_sheet(
            records=bind_representatives,
            output_path=OUT_DIR / "chests_bind_samples.png",
            title=f"宝箱绑定角标样本：{len(bind_records)} 个",
        )

    print(f"images={len(files)}")
    print(f"total_blocks={total_blocks}")
    print(f"recognized_top={dict(recognized.most_common(30))}")
    print(f"none_total={len(none_records)}")
    print(f"none_exact_pixel_variants={len(none_groups)}")
    print(f"none_name_distribution={dict(Counter(record['name'] for record in none_records))}")
    print("none_variant_counts=")
    for i, representative in enumerate(none_representatives, 1):
        count = len(none_groups[(representative["name"], representative["key"])])
        print(
            f"{i}: name={representative['name']} count={count} "
            f"bgr_diff={representative['bgr_diff']} first={representative['path']} index={representative['index']}"
        )
    print(f"bind_records={len(bind_records)}")
    print(f"bind_both={bind_both}")
    print(f"bind_exact_only={bind_exact_only}")
    print(f"bind_legacy_only={bind_legacy_only}")
    print(f"none_sheet={OUT_DIR / 'chests_none_variants.png'}")
    if bind_representatives:
        print(f"bind_sheet={OUT_DIR / 'chests_bind_samples.png'}")


if __name__ == "__main__":
    main()
