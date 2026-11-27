from dataclasses import dataclass

import cv2
import numpy as np

from function.scattered.match_ocr_text.match_text import match as match_legacy


# 任务卡定位后，正文从第 54 列起排版。两条基线间距为 16 像素。
TEXT_LEFT = 54
TEXT_RIGHT = 377
LINE_HEIGHT = 14
GLYPH_WIDTHS = (7, 14)


@dataclass
class FoodTextLine:
    """紧贴文字的黑白行图及其在 14 像素字格中的偏移。"""

    pixels: np.ndarray
    x: int
    y: int


@dataclass
class FoodGlyphIndex:
    """普通字形与尾列含有笔画的完整模板。"""

    glyphs: dict[bytes, str]
    occupied_gaps: dict[bytes, str]


def crop_food_text_lines(source: np.ndarray) -> list[FoodTextLine]:
    """从任务卡的正文区域提取一到两行，去掉外围空白。"""
    # FAA 截图是 RGBA。PNG 模板通过 OpenCV 加载时则是 BGR。
    image = cv2.cvtColor(source, cv2.COLOR_RGBA2BGR) if source.shape[2] == 4 else source
    ink = cv2.inRange(image[10:, TEXT_LEFT:TEXT_RIGHT], (118, 69, 37), (120, 71, 39))
    rows = np.flatnonzero(ink[:38].any(axis=1))
    if not rows.size:
        return []

    first_row = rows[0]
    lines = []
    for start in (first_row, first_row + 16):
        line = ink[start:start + LINE_HEIGHT]
        ys, xs = np.nonzero(line)
        if xs.size:
            left, right = int(xs.min()), int(xs.max()) + 1
            top, bottom = int(ys.min()), int(ys.max()) + 1
            lines.append(FoodTextLine(255 - line[top:bottom, left:right], left, top))
    return lines


def build_food_glyph_index(templates: dict[str, np.ndarray]) -> FoodGlyphIndex:
    """索引 7 或 14 像素宽的字形。兼容带尾列的旧资源。"""
    index = FoodGlyphIndex({}, {})
    for filename, image in templates.items():
        if image.shape not in ((LINE_HEIGHT, 7), (LINE_HEIGHT, 8),
                               (LINE_HEIGHT, 14), (LINE_HEIGHT, 15)):
            continue
        if image.shape[1] in (8, 15):
            if np.any(image[:, -1] != 255):
                # 历史截图中的 A+ 等字形会占到间隔列，必须逐像素验证这一列。
                index.occupied_gaps.setdefault(image.tobytes(), filename[:-4])
                continue
            image = image[:, :-1]
        index.glyphs.setdefault(image.tobytes(), filename[:-4])
    return index


def recognize_food_line(
    line: FoodTextLine, index: FoodGlyphIndex,
) -> tuple[tuple[str, int, int], ...] | None:
    """沿白色间隔寻找可完整识别的切分，返回字符及其字格起点和宽度。"""
    ink_end = line.x + line.pixels.shape[1]
    row = np.full((LINE_HEIGHT, TEXT_RIGHT - TEXT_LEFT), 255, dtype=np.uint8)
    height = line.pixels.shape[0]
    row[line.y:line.y + height, line.x:ink_end] = line.pixels
    white = np.all(row == 255, axis=0)
    next_glyph = {}

    # 从右往左判断哪些起点能走到行末。标点内部的白列只能提供备选切点。
    for start in range(ink_end - 1, -1, -1):
        for width in GLYPH_WIDTHS:
            gap = start + width
            if gap >= row.shape[1]:
                continue
            following = gap + 1
            if following < ink_end and following not in next_glyph:
                continue
            if white[gap]:
                char = index.glyphs.get(row[:, start:gap].tobytes())
            else:
                char = index.occupied_gaps.get(row[:, start:following].tobytes())
            if char is not None:
                next_glyph[start] = (char, width)
                break

    if 0 not in next_glyph:
        return None
    result = []
    start = 0
    while start < ink_end:
        char, width = next_glyph[start]
        result.append((char, start, width))
        start += width + 1
    return tuple(result)


def recognize_food_task(source: np.ndarray, index: FoodGlyphIndex):
    """返回任务全文、行图和切分坐标。任一行无法对齐时，全文为 None。"""
    lines = crop_food_text_lines(source)
    cuts = [recognize_food_line(line, index) for line in lines]
    if not cuts or any(cut is None for cut in cuts):
        return None, lines, cuts
    return "".join(char for cut in cuts for char, _, _ in cut), lines, cuts


def match_food_task(source: np.ndarray, index: FoodGlyphIndex) -> str | None:
    """识别一张任务卡，遇到缺字时保存字块并跳过该任务。"""
    text, lines, _ = recognize_food_task(source, index)
    if text is None and lines:
        # 旧函数负责去重并保存两种候选字宽。残缺文本不能作为有效任务。
        match_legacy(source.copy(), mode="美食大赛")
    return text
