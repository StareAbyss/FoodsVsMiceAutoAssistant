import cv2
import numpy as np


def match_histogram(img_a, img_b):
    """
    计算直方图匹配两张几乎相同的图片, 需要两张图片的分辨率相同
    由于是1080个像素, 因此允许误差为54个像素
    :param img_a: 图片A
    :param img_b: 图片B
    :return: 匹配成功返回True，否则返回False
    """
    # 计算直方图
    block_hist = cv2.calcHist(
        [img_a],
        [0, 1, 2],
        None,
        [16, 16, 16],
        [0, 256, 0, 256, 0, 256]
    )

    target_hist = cv2.calcHist(
        [img_b],
        [0, 1, 2],
        None,
        [16, 16, 16],
        [0, 256, 0, 256, 0, 256]
    )

    score = cv2.compareHist(
        H1=block_hist,
        H2=target_hist,
        method=cv2.HISTCMP_CORREL
    )

    if score > 0.97:
        return True

    else:
        return False


def match(block, tar_img, mode="equal"):
    """
    :param block: array 被查找图片
    :param tar_img: array
    :param mode: str equal:相等  histogram:直方图匹配  match_template:模板匹配
    :return: bool 是否满足匹配条件
    """
    if mode == "equal":
        return np.array_equal(block, tar_img)

    if mode == "histogram":
        return match_histogram(img_a=block, img_b=tar_img)

    if mode == "match_template":
        # 被检查者 目标 目标缩小一圈来检查
        target_tolerance = 0.98
        result = cv2.matchTemplate(image=tar_img, templ=block[2:-2, 2:-2, :], method=cv2.TM_SQDIFF_NORMED)
        (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(src=result)
        # 如果匹配度<阈值，就认为没有找到
        if minVal > 1 - target_tolerance:
            return False
        return True
