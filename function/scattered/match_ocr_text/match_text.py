import os

import cv2
import numpy as np

from function.common.same_size_match import match_block_equal_in_images
from function.globals import init_resources
from function.globals.get_paths import PATHS


def find_topmost_text_pixel_in_range(gray_img, col_start, col_end, row_start, row_end):
    """在指定列和行范围内找到图像中第一排文字最上面的像素点所在的行"""
    for y in range(row_start, row_end):
        if np.any(gray_img[y, col_start:col_end] != 255):
            return y
    return None


def split_into_characters(line):
    """从行图像中分割出单个字符图像"""
    characters = []
    line_gray = cv2.cvtColor(line, cv2.COLOR_BGR2GRAY)  # 将行图像转换为灰度图像 注意 只有两个维度!
    width, _ = line_gray.shape[::-1]

    # 西文字符宽度
    latin_width = 8
    # 中文字符宽度
    chinese_width = 15

    # 当前行的起始位置
    start_pos = 0
    while start_pos < width:

        # 尝试按西文字符宽度分割
        latin_block = line_gray[:, start_pos:start_pos + latin_width]
        latin_match = match_block_equal_in_images(
            block_array=latin_block,
            images=init_resources.RESOURCE_P["ocr"]["texts_matched"])

        # 如果匹配到西文字符，添加到字符列表并更新起始位置
        if latin_match:
            characters.append(latin_block)
            start_pos += latin_width
            continue

        # 否则，尝试按中文字符宽度分割
        chinese_block = line_gray[:, start_pos:start_pos + chinese_width]
        # 如果中文块宽度小于15像素，说明之后换行了 结束这一行
        if chinese_block.shape[1] < chinese_width:
            break
        # 检查这一中文块是否全为白色，如果是 结束这一行
        if np.all(chinese_block == 255):
            break

        chinese_match = match_block_equal_in_images(
            block_array=chinese_block,
            images=init_resources.RESOURCE_P["ocr"]["texts_matched"])

        if not chinese_match:

            # 保存半分割
            cus_path = PATHS["logs"] + "\\match_failed\\texts\\blocks_half"
            name_id = len(os.listdir(cus_path))
            save_path = f"{cus_path}\\unknown_{name_id}.png"
            cv2.imencode('.png', latin_block)[1].tofile(save_path)

            # 保存全分割
            cus_path = PATHS["logs"] + "\\match_failed\\texts\\blocks"
            name_id = len(os.listdir(cus_path))
            save_path = f"{cus_path}\\unknown_{name_id}.png"
            cv2.imencode('.png', chinese_block)[1].tofile(save_path)

        characters.append(chinese_block)
        start_pos += chinese_width

    return characters


def split_block(img_source):
    """分块一张图片"""
    img = img_source

    # 将所有颜色为 #774626的 像素改成黑色, 其他像素全部改成白色
    # 首先转换颜色空间为HSV，然后根据颜色范围进行阈值化
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_color = np.array([0, 0, 118])  # 对应#774626的颜色在HSV空间的下限
    upper_color = np.array([180, 255, 190])  # 对应#774626的颜色在HSV空间的上限
    mask = cv2.inRange(hsv, lower_color, upper_color)

    img[mask > 0] = [0, 0, 0]
    img[mask == 0] = [255, 255, 255]

    # 转换为灰度图像
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 找到在指定行范围内的第一排文字最上面的像素点所在的行
    topmost_text_row = find_topmost_text_pixel_in_range(gray, 54, 377, 10, 48)

    # 根据找到的基线动态裁剪line1和line2
    line_height = 14
    if topmost_text_row is not None:
        line1 = img[topmost_text_row:topmost_text_row + line_height, 54:377]
        line2 = img[topmost_text_row + line_height + 2:topmost_text_row + 2 * line_height + 2, 54:377]
    else:
        line1 = None
        line2 = None

    lines = [line1, line2]

    # 保存行图像到本地
    # cv2.imwrite('line1.png', line1)
    # cv2.imwrite('line2.png', line2)

    character_blocks = []
    for line in lines:
        character_blocks += split_into_characters(line=line)
    return character_blocks


def match(source):
    """识别一张图片"""
    blocks = split_block(img_source=source)
    result_str = ""
    for block in blocks:

        result = match_block_equal_in_images(
            block_array=block,
            images=init_resources.RESOURCE_P["ocr"]["texts_matched"])

        if result:
            result_str += result

        else:
            result_str += "?"

    return result_str


if __name__ == '__main__':
    def main():
        # 从source文件夹里面读取所有图片
        sources = [os.path.join("source", f) for f in os.listdir("source") if os.path.isfile(os.path.join("source", f))]

        for source in sources:
            print(match(source=source))


    main()
