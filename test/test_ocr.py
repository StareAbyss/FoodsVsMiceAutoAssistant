import cv2
import numpy as np
from paddleocr import PaddleOCR

# 创建一个OCR实例，指定使用中文模型
ocr = PaddleOCR(use_angle_cls=True, lang='ch')  # lang='ch'表示使用中文模型


def imread(filename, flags=cv2.IMREAD_COLOR):
    # 使用 numpy 库的 fromfile 函数读取二进制内容
    file_stream = np.fromfile(filename, dtype=np.uint8)
    # 使用 cv2.imdecode 函数将二进制内容解码为图像格式
    image = cv2.imdecode(file_stream, flags)
    return image


def imresize(image, num):  # 使用 cv2.resize 函数进行缩放

    # 定义要填充的像素数
    top_padding = 50  # 图像顶部填充50像素
    bottom_padding = 50  # 图像底部填充50像素
    left_padding = 50  # 图像左侧填充50像素
    right_padding = 50  # 图像右侧填充50像素

    # 定义填充的颜色，白色为(255, 255, 255)
    border_color = (255, 255, 255)

    # 使用cv2.copyMakeBorder()函数填充图像
    image = cv2.copyMakeBorder(
        image,
        top_padding,
        bottom_padding,
        left_padding,
        right_padding,
        cv2.BORDER_CONSTANT,
        value=border_color)

    width = int(image.shape[1] * num)
    height = int(image.shape[0] * num)
    new_dimensions = (width, height)
    # 使用双三次插值算法放大图像
    resized_image = cv2.resize(image, new_dimensions, interpolation=cv2.INTER_CUBIC)
    return resized_image


# 图片路径（这里假设您的图片路径包含中文）
image_path = 'my_test.png'
image = imread(image_path)
image = imresize(image, 2)
# 对本地图片进行OCR
for i in range(1000):
    result = ocr.ocr(image, cls=True)
# 打印结果
for line in result:
    print(line)


# 可视化结果
# image_with_boxes = draw_ocr(image_path, result)
