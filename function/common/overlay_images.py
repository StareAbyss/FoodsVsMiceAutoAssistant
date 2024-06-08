import cv2
import numpy as np


def overlay_images(img_background, img_overlay, test_show=False):
    """叠放两张图, A在上, B在下, 支持阿尔法通道缺省, 需要大小相同, 支持数组或文件路径格式"""

    # 根据 路径 或者 numpy.array 选择是否读取
    if type(img_background) is not np.ndarray:
        # 读取目标图像,中文路径兼容方案
        img_background = cv2.imdecode(buf=np.fromfile(file=img_background, dtype=np.uint8), flags=-1)

    # 根据 路径 或者 numpy.array 选择是否读取
    if type(img_overlay) is not np.ndarray:
        # 读取目标图像,中文路径兼容方案
        img_overlay = cv2.imdecode(buf=np.fromfile(file=img_overlay, dtype=np.uint8), flags=-1)

    # 获取图像A和B的形状
    height_a, width_a, channels_a = img_background.shape
    height_b, width_b, channels_b = img_overlay.shape
    # 检查图像A和B的大小是否相同
    if height_a != height_b or width_a != width_b:
        raise ValueError("Image A and Image B must have the same size.")
    # 将图像A和B转换为相同的通道数 即 非四通道 全部设置Alpha通道为255
    if channels_b == 3:
        img_overlay = cv2.cvtColor(img_overlay, cv2.COLOR_BGR2BGRA)
    elif channels_a == 3:
        img_background = cv2.cvtColor(img_background, cv2.COLOR_BGR2BGRA)

    # 叠加图像
    result = img_background.copy()
    overlay_mask = img_overlay[:, :, 3] / 255.0  # 获取覆盖图像的 Alpha 通道掩码
    result[:, :, :3] = (img_overlay[:, :, :3] * overlay_mask[:, :, np.newaxis]).astype(np.uint8) + \
                       (result[:, :, :3] * (1 - overlay_mask[:, :, np.newaxis])).astype(np.uint8)
    result[:, :, 3] = np.maximum(img_overlay[:, :, 3], result[:, :, 3])  # 保留最大 Alpha 值

    if test_show:
        cv2.imshow('Result', result)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return result
