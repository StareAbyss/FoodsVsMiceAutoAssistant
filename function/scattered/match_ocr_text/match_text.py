import os

import cv2
import numpy as np

from function.common.same_size_match import match_block_equal_in_images
from function.globals import g_resources, EXTRA
from function.globals.get_paths import PATHS


def find_topmost_text_pixel_in_range(gray_img, col_start, col_end, row_start, row_end):
    """在指定列和行范围内找到图像中第一排文字最上面的像素点所在的行"""
    for y in range(row_start, row_end):
        if np.any(gray_img[y, col_start:col_end] != 255):
            return y
    return None


def split_into_characters(line, mode="美食大赛"):
    """从行图像中分割出单个字符图像"""
    characters = []
    line_gray = line
    width, _ = line_gray.shape[::-1]

    # 美食大赛 西文字符宽度 8 中文字符宽度 15
    latin_width = 8
    chinese_width = 15
    match mode:
        case "美食大赛":
            latin_width = 8
            chinese_width = 15
        case "关卡名称":
            latin_width = 7
            chinese_width = 13

    # 当前行的起始位置
    start_pos = 0
    while start_pos < width:

        # 尝试按西文字符宽度分割
        latin_block = line_gray[:, start_pos:start_pos + latin_width]
        latin_match = match_block_equal_in_images(
            block_array=latin_block,
            images=g_resources.RESOURCE_P["ocr"][mode])

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
            images=g_resources.RESOURCE_P["ocr"][mode])

        if not chinese_match:

            with EXTRA.FILE_LOCK:

                # 刷新资源
                g_resources.fresh_resource_log_img()

                # 保存半分割
                result = match_block_equal_in_images(
                    block_array=latin_block,
                    images=g_resources.RESOURCE_LOG_IMG[f"texts_{mode}"]["blocks_half"])
                if not result:
                    cus_path = PATHS["logs"] + f"\\match_failed\\texts_{mode}\\blocks_half"

                    # 获得最小的未使用的id
                    used_ids = set()
                    for name, _ in g_resources.RESOURCE_LOG_IMG[f"texts_{mode}"]["blocks_half"].items():
                        name_id = int(name.split('.')[0].split("_")[1])
                        used_ids.add(name_id)
                    name_id = 0
                    while name_id in used_ids:
                        name_id += 1

                    save_path = f"{cus_path}\\unknown_{name_id}.png"
                    cv2.imencode('.png', latin_block)[1].tofile(save_path)

                # 保存全分割
                result = match_block_equal_in_images(
                    block_array=chinese_block,
                    images=g_resources.RESOURCE_LOG_IMG[f"texts_{mode}"]["blocks"])
                if not result:
                    cus_path = PATHS["logs"] + f"\\match_failed\\texts_{mode}\\blocks"

                    # 获得最小的未使用的id
                    used_ids = set()
                    for name, _ in g_resources.RESOURCE_LOG_IMG[f"texts_{mode}"]["blocks"].items():
                        name_id = int(name.split('.')[0].split("_")[1])
                        used_ids.add(name_id)
                    name_id = 0
                    while name_id in used_ids:
                        name_id += 1

                    save_path = f"{cus_path}\\unknown_{name_id}.png"
                    cv2.imencode('.png', chinese_block)[1].tofile(save_path)

        characters.append(chinese_block)
        start_pos += chinese_width

    return characters


def split_block(img_source, mode="美食大赛"):
    """分块一张图片, 用于美食大赛"""
    img = img_source

    # 检查是否有Alpha通道 将RGBA转换为BGR
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)

    # 将所有 文本颜色 改成黑色, 其他颜色变成白色
    # 定义纯黑色的下限和上限
    lower_white = np.array([118, 69, 37])
    upper_white = np.array([120, 71, 39])
    match mode:
        case "美食大赛":
            lower_white = np.array([118, 69, 37])
            upper_white = np.array([120, 71, 39])
        case "关卡名称":
            lower_white = np.array([254, 254, 254])
            upper_white = np.array([255, 255, 255])

    # 创建一个掩码，用于标记非纯白色的像素
    mask = cv2.inRange(img, lower_white, upper_white)

    # 将特定颜色的像素设置为白色
    img[mask > 0] = [0, 0, 0]

    # 将非纯白色的像素设置为黑色
    img[mask == 0] = [255, 255, 255]

    # 转换为灰度图像
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 显示
    # cv2.imshow("img", img)
    # cv2.waitKey(0)

    # 找到在指定行范围内的第一排文字最上面的像素点所在的行
    lines = [gray]
    match mode:
        case "美食大赛":
            topmost_text_row = find_topmost_text_pixel_in_range(gray, 54, 377, 10, 48)

            # 根据找到的基线动态裁剪line1和line2
            line_height = 14
            if topmost_text_row is not None:
                line1 = img[topmost_text_row:topmost_text_row + line_height, 54:377]
                line2 = img[topmost_text_row + line_height + 2:topmost_text_row + 2 * line_height + 2, 54:377]
                # 将行图像转换为灰度图像 注意 只有两个维度!
                line1 = cv2.cvtColor(line1, cv2.COLOR_BGR2GRAY)
                line2 = cv2.cvtColor(line2, cv2.COLOR_BGR2GRAY)
            else:
                line1 = None
                line2 = None

            lines = [line1, line2]
        case "关卡名称":
            lines = [gray]

    character_blocks = []
    for line in lines:
        character_blocks += split_into_characters(line=line, mode=mode)
    return character_blocks


def match(source, mode="美食大赛"):
    """识别一张图片, 美食大赛"""
    blocks = split_block(img_source=source, mode=mode)
    result_str = ""
    for block in blocks:

        result = match_block_equal_in_images(
            block_array=block,
            images=g_resources.RESOURCE_P["ocr"][mode])

        if result:
            result_str += result

        else:
            result_str += "?"

    return result_str


if __name__ == '__main__':
    def main():
        # 从source文件夹里面读取所有图片
        source_path = PATHS["image"]["current"] + "/ocr/source"

        # 请补充 兼容中文路径
        sources = []

        # 遍历文件夹内的所有文件
        for filename in os.listdir(source_path):
            # 构建完整的文件路径
            file_path = os.path.join(source_path, filename)

            # 检查是否为文件
            if os.path.isfile(file_path):
                # 读取图片
                img = cv2.imdecode(buf=np.fromfile(file=file_path, dtype=np.uint8), flags=-1)

                # 如果图片读取成功，则添加到列表中
                if img is not None:
                    sources.append(img)

        for source in sources:
            print(match(source=source))


    main()
