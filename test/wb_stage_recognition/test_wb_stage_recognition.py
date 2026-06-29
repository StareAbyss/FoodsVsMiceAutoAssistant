import csv
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import win32gui
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from function.common.bg_img_match import match_template_with_optional_mask
from function.common.bg_img_screenshot import capture_image_png, capture_image_png_all
from function.globals.get_paths import PATHS
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_channel_name import get_channel_name


ROOT = Path(PATHS["root"])
OUTPUT_DIR = ROOT / "test" / "wb_stage_recognition" / "output"
WORLD_BOSS_DIR = ROOT / "resource" / "image" / "world_boss"

BOSS_RANGE = [680, 20, 850, 65]
BUFF_RANGE = [830, 270, 910, 350]
MATCH_TOLERANCE = 0.975


def im_read(path: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)


def im_write(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(path.suffix, image)[1].tofile(str(path))


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_path in [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def to_bgr(image: np.ndarray, background=(255, 255, 255)) -> np.ndarray:
    if image.shape[2] == 3:
        return image[:, :, :3]

    alpha = image[:, :, 3:4].astype(np.float32) / 255
    foreground = image[:, :, :3].astype(np.float32)
    bg = np.full_like(foreground, background, dtype=np.float32)
    return (foreground * alpha + bg * (1 - alpha)).astype(np.uint8)


def add_label(image: np.ndarray, text: str) -> np.ndarray:
    font = load_font(18)
    bgr = to_bgr(image)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(pil_image)
    label_height = 30
    canvas = Image.new("RGB", (pil_image.width, pil_image.height + label_height), (255, 255, 255))
    canvas.paste(pil_image, (0, label_height))
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 4), text, fill=(0, 0, 0), font=font)
    return cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR)


def resize_to_height(image: np.ndarray, height: int) -> np.ndarray:
    if image.shape[0] == height:
        return image
    width = max(1, int(image.shape[1] * height / image.shape[0]))
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_NEAREST)


def hstack_with_padding(images: list[np.ndarray], gap: int = 12) -> np.ndarray:
    max_height = max(image.shape[0] for image in images)
    normalized = []
    for image in images:
        top = 0
        bottom = max_height - image.shape[0]
        normalized.append(cv2.copyMakeBorder(
            image, top, bottom, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
    gap_image = np.full((max_height, gap, 3), 255, dtype=np.uint8)
    result = normalized[0]
    for image in normalized[1:]:
        result = np.hstack([result, gap_image, image])
    return result


def vstack_with_padding(images: list[np.ndarray], gap: int = 18) -> np.ndarray:
    max_width = max(image.shape[1] for image in images)
    normalized = []
    for image in images:
        right = max_width - image.shape[1]
        normalized.append(cv2.copyMakeBorder(
            image, 0, 0, 0, right, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
    gap_image = np.full((gap, max_width, 3), 255, dtype=np.uint8)
    result = normalized[0]
    for image in normalized[1:]:
        result = np.vstack([result, gap_image, image])
    return result


def diff_image(actual_patch: np.ndarray, template: np.ndarray) -> np.ndarray:
    actual = actual_patch[:, :, :3]
    target = template[:, :, :3]
    diff = cv2.absdiff(actual, target)
    if template.shape[2] == 4:
        mask = template[:, :, 3] == 255
        diff[~mask] = 255
    return diff


def read_settings() -> dict:
    with open(ROOT / "config" / "settings.json", encoding="utf-8") as file:
        return json.load(file)


def match_candidates(source_img: np.ndarray, candidates: list[Path]) -> list[dict]:
    rows = []
    for path in candidates:
        template = im_read(path)
        status, result = match_template_with_optional_mask(source=source_img, template=template)
        if status == 0:
            rows.append({
                "name": path.stem,
                "path": str(path),
                "score": 0,
                "top_left_x": None,
                "top_left_y": None,
                "template": template,
            })
            continue
        min_val, _, min_loc, _ = cv2.minMaxLoc(result)
        rows.append({
            "name": path.stem,
            "path": str(path),
            "score": 1 - min_val,
            "top_left_x": min_loc[0],
            "top_left_y": min_loc[1],
            "template": template,
        })
    rows.sort(key=lambda item: item["score"], reverse=True)
    return rows


def build_comparison_row(title: str, source_img: np.ndarray, best: dict, tolerance: float) -> np.ndarray:
    template = best["template"]
    x = best["top_left_x"]
    y = best["top_left_y"]
    target = to_bgr(template)
    actual_patch = source_img[y:y + template.shape[0], x:x + template.shape[1], :3]

    marked_source = source_img[:, :, :3].copy()
    cv2.rectangle(
        marked_source,
        (x, y),
        (x + template.shape[1], y + template.shape[0]),
        (0, 0, 255),
        1,
    )

    panels = [
        add_label(marked_source, f"{title}区域截图 / 红框为最佳位置"),
        add_label(target, f"目标图像：{best['name']}"),
        add_label(actual_patch, "实际图像：最佳匹配块"),
        add_label(diff_image(actual_patch, template), "差异图：越黑越接近"),
    ]
    max_panel_height = 130
    panels = [resize_to_height(panel, min(max_panel_height, panel.shape[0])) for panel in panels]
    header = np.full((34, sum(panel.shape[1] for panel in panels) + 12 * (len(panels) - 1), 3), 255, dtype=np.uint8)
    header = add_label(
        header,
        f"{title}：识别={best['name']}  匹配度={best['score']:.5f}  阈值={tolerance:.2f}",
    )
    return vstack_with_padding([header, hstack_with_padding(panels)], gap=6)


def write_scores_csv(
        path: Path,
        boss_rows: list[dict],
        buff_rows: list[dict],
        flow_buff_rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["识别区域", "候选名称", "匹配度", "是否通过阈值", "左上X", "左上Y", "模板路径"])
        for area, rows in [
            ("Boss名称", boss_rows),
            ("词条图标-最佳Boss候选", buff_rows),
            ("词条图标-当前主流程Boss候选", flow_buff_rows),
        ]:
            for row in rows:
                writer.writerow([
                    area,
                    row["name"],
                    f"{row['score']:.8f}",
                    row["score"] > MATCH_TOLERANCE,
                    row["top_left_x"],
                    row["top_left_y"],
                    row["path"],
                ])


def first_passed(rows: list[dict]) -> dict | None:
    for row in rows:
        if row["score"] > MATCH_TOLERANCE:
            return row
    return None


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    settings = read_settings()
    channel_1p, _ = get_channel_name(
        game_name=settings["base_settings"]["game_name"],
        name_1p=settings["base_settings"]["name_1p"],
        name_2p=settings["base_settings"]["name_2p"],
    )

    handle = faa_get_handle(channel=channel_1p, mode="flash")
    handle_360 = faa_get_handle(channel=channel_1p, mode="360")
    print(f"1P窗口名: {channel_1p}")
    print(f"flash句柄: {handle}")
    print(f"360句柄: {handle_360}")
    print(f"窗口标题: {win32gui.GetWindowText(handle_360) if handle_360 else ''}")

    full_image = capture_image_png_all(handle=handle, root_handle=handle_360)
    boss_source = capture_image_png(handle=handle, raw_range=BOSS_RANGE, root_handle=handle_360)
    buff_source = capture_image_png(handle=handle, raw_range=BUFF_RANGE, root_handle=handle_360)

    im_write(OUTPUT_DIR / "完整窗口截图.png", full_image)
    im_write(OUTPUT_DIR / "Boss名称实际截图.png", boss_source)
    im_write(OUTPUT_DIR / "词条图标实际截图.png", buff_source)

    boss_candidates = sorted(path for path in WORLD_BOSS_DIR.glob("WB-*.png") if path.stem.count("-") == 1)
    boss_rows = match_candidates(boss_source[:, :, :3], boss_candidates)
    best_boss = boss_rows[0]

    buff_candidates = sorted(path for path in WORLD_BOSS_DIR.glob(f"{best_boss['name']}-*.png"))
    buff_rows = match_candidates(buff_source[:, :, :3], buff_candidates)
    best_buff = buff_rows[0]

    flow_boss = first_passed(boss_rows)
    flow_boss_name = flow_boss["name"] if flow_boss else "WB-1"
    flow_buff_candidates = sorted(path for path in WORLD_BOSS_DIR.glob(f"{flow_boss_name}-*.png"))
    flow_buff_rows = match_candidates(buff_source[:, :, :3], flow_buff_candidates)
    flow_buff = first_passed(flow_buff_rows)
    flow_stage_id = flow_buff["name"] if flow_buff else "WB-1-0"

    comparison = vstack_with_padding([
        build_comparison_row("Boss名称", boss_source, best_boss, MATCH_TOLERANCE),
        build_comparison_row("词条图标", buff_source, best_buff, MATCH_TOLERANCE),
    ])
    im_write(OUTPUT_DIR / "WB识别关键图像比对.png", comparison)
    write_scores_csv(OUTPUT_DIR / "WB识别候选匹配度.csv", boss_rows, buff_rows, flow_buff_rows)

    final_stage_id = best_buff["name"]
    print(f"Boss识别结果: {best_boss['name']}  匹配度: {best_boss['score']:.5f}")
    print(f"词条识别结果: {best_buff['name']}  匹配度: {best_buff['score']:.5f}")
    print(f"最佳候选下 WB-0-0 将切换为: {final_stage_id}")
    print(f"Boss是否通过阈值: {best_boss['score'] > MATCH_TOLERANCE}")
    print(f"词条是否通过阈值: {best_buff['score'] > MATCH_TOLERANCE}")
    print(f"按当前主流程阈值模拟 Boss: {flow_boss_name}")
    print(f"按当前主流程阈值模拟最终切换: {flow_stage_id}")
    print(f"输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
