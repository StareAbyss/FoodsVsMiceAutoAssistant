import cv2


def match_histogram(block, target_image):
    """
    计算直方图匹配两张几乎相同的图片, 需要两张图片的分辨率相同
    由于是1080个像素, 因此允许误差为54个像素
    :param block: 图片
    :param target_image: 查找的模板
    :return: 匹配成功返回True，否则返回False
    """
    # 计算直方图
    block_hist = cv2.calcHist(
        [block],
        [0, 1, 2],
        None,
        [8, 8, 8],
        [0, 256, 0, 256, 0, 256]
    )

    target_hist = cv2.calcHist(
        [target_image],
        [0, 1, 2],
        None,
        [8, 8, 8],
        [0, 256, 0, 256, 0, 256]
    )

    score = cv2.compareHist(
        H1=block_hist,
        H2=target_hist,
        method=cv2.HISTCMP_CORREL
    )

    if score > 0.90:
        return True

    else:
        return False