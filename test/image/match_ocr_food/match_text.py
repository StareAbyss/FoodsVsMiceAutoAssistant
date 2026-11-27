import cv2
import numpy as np
import os


def split_into_characters(line):
    """从行图像中分割出单个字符图像"""
    characters = []
    line_gray = cv2.cvtColor(line, cv2.COLOR_BGR2GRAY)  # 将行图像转换为灰度图像
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
        latin_match = match_block(latin_block, "texts_matched")

        # 保存半分割
        # cv2.imwrite(
        #     os.path.join("blocks", "unknown_" + str(len(os.listdir("blocks"))) + ".png"),
        #     latin_block)

        # 如果匹配到西文字符，添加到字符列表并更新起始位置
        if latin_match:
            characters.append(latin_block)
            start_pos += latin_width
        else:
            # 否则，尝试按中文字符宽度分割
            chinese_block = line_gray[:, start_pos:start_pos + chinese_width]

            # 如果中文块宽度小于15像素，说明之后换行了 结束这一行
            if chinese_block.shape[1] < chinese_width:
                break

            # 检查这一中文块是否全为白色，如果是 结束这一行
            if np.all(chinese_block == 255):
                break

            characters.append(chinese_block)
            start_pos += chinese_width

    return characters


def split_block(source):
    """分块一张图片"""
    img = cv2.imdecode(np.fromfile(source, dtype=np.uint8), -1)

    # 将所有颜色为 #774626的 像素改成黑色, 其他像素全部改成白色
    # 首先转换颜色空间为HSV，然后根据颜色范围进行阈值化
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_color = np.array([0, 0, 118])  # 对应#774626的颜色在HSV空间的下限
    upper_color = np.array([180, 255, 190])  # 对应#774626的颜色在HSV空间的上限
    mask = cv2.inRange(hsv, lower_color, upper_color)
    img[mask > 0] = [0, 0, 0]
    img[mask == 0] = [255, 255, 255]

    # 将图片分割成两行
    line1 = img[18:32, 54:377]
    line2 = img[34:48, 54:377]
    lines = [line1, line2]

    # 保存行图像到本地
    # cv2.imwrite('line1.png', line1)
    # cv2.imwrite('line2.png', line2)

    character_blocks = []
    for line in lines:
        character_blocks += split_into_characters(line=line)
    return character_blocks


def match_block(block_array, file_path):
    """识别block是否在file_patch文件夹中存在这个字, 直接对比是否完全一致"""
    files = [f for f in os.listdir(file_path) if os.path.isfile(os.path.join(file_path, f))]
    for file_name in files:
        img_path = os.path.join(file_path, file_name)
        template_array = cv2.imdecode(buf=np.fromfile(file=img_path, dtype=np.uint8), flags=-1)

        # 只在图像尺寸相同的情况下进行比较
        if template_array.shape == block_array.shape:
            # 检查两个图像数组是否完全相同
            if np.array_equal(block_array, template_array):
                return file_name[0]  # 去掉文件扩展名

    return None


def match(source):
    """识别一张图片"""
    blocks = split_block(source=source)
    result_str = ""
    for block in blocks:
        result = match_block(block_array=block, file_path="texts_matched")
        if result:
            result_str += result
        else:
            result_str += "?"
            if not match_block(block_array=block, file_path="texts_unmatched"):
                # 保存图片到这个文件夹中
                cv2.imwrite(
                    os.path.join("texts_unmatched", "unknown_" + str(len(os.listdir("texts_unmatched"))) + ".png"),
                    block)
    return result_str


def main():
    # 从source文件夹里面读取所有图片
    sources = [os.path.join("source", f) for f in os.listdir("source") if os.path.isfile(os.path.join("source", f))]

    for source in sources:
        print(match(source=source))


if __name__ == '__main__':
    main()
