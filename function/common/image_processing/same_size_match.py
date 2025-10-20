import cv2
import numpy as np

from function.common.bg_img_match import match_template_with_optional_mask
from function.common.image_processing.overlay_images import overlay_images
from function.globals.g_resources import RESOURCE_P


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


def one_item_match(img_block, img_tar, mode="equal"):
    """
    :param img_block: array 目标对象 包含alpha通道
    :param img_tar: array 游戏素材 包含alpha通道, 识别是否绑定则任意
    :param mode: str
        equal: 相等
        histogram: 直方图匹配
        match_template: 模板匹配 支持匹配度输出
        match_is_bind: 物品是否为绑定的 支持匹配度输出
        match_template_with_mask_tradable: 掩模板单通道匹配可交易物品 支持匹配度输出
        match_template_with_mask_locked: 掩模板单通道匹配可交易物品绑定物品
    :return: bool 是否满足匹配条件 None or float 匹配度
    """

    if mode == "equal":
        return np.array_equal(img_block[:, :, :-1], img_tar[:, :, :-1]), None

    if mode == "histogram":
        return match_histogram(img_a=img_block[:, :, :-1], img_b=img_tar[:, :, :-1]), None

    if mode == "match_template":
        # 被检查者 目标 目标缩小一圈来检查
        match_tolerance = 0.98
        result = cv2.matchTemplate(
            image=img_tar[:, :, :-1],
            templ=img_block[2:-2, 2:-2, :-1],
            method=cv2.TM_SQDIFF_NORMED)
        (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(src=result)
        # 如果匹配度<阈值，就认为没有找到
        matching_degree = 1 - minVal
        if matching_degree <= match_tolerance:
            return False, matching_degree
        return True, matching_degree

    if mode == "match_is_bind":
        match_tolerance = 0.98
        source = img_block[30:44, 0:15, :]
        template = RESOURCE_P["item"]["物品-绑定角标-战利品.png"][30:44, 0:15, :]  # 特别注意 背包和战利品使用的角标不一样!!!
        match_status_code, match_result = match_template_with_optional_mask(
            source=source,
            template=template,
            test_show=False)
        if match_status_code == 0:
            return False, 0
        (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(src=match_result)
        # 如果匹配度<阈值，就认为没有找到
        matching_degree = 1 - minVal
        if matching_degree <= match_tolerance:
            return False, matching_degree
        return True, matching_degree

    if mode == "match_template_with_mask_tradable":
        match_tolerance = 0.98
        mask = RESOURCE_P["item"]["物品-掩模-不绑定.png"]
        source = img_block[2:-10:2, 2:-10:2, :]
        template = img_tar[2:-10:2, 2:-10:2, :]
        match_status_code, match_result = match_template_with_optional_mask(
            source=source,
            template=template,
            mask=mask[2:-10:2, 2:-10:2, :],
            test_show=False)
        if match_status_code == 0:
            return False, 0
        (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(src=match_result)
        # 如果匹配度<阈值，就认为没有找到
        matching_degree = 1 - minVal
        if matching_degree <= match_tolerance:
            return False, matching_degree
        return True, matching_degree

    if mode == "match_template_with_mask_locked":
        match_tolerance = 0.98
        mask = RESOURCE_P["item"]["物品-掩模-绑定.png"]
        img_tar = overlay_images(
            img_background=img_tar,
            img_overlay=RESOURCE_P["item"]["物品-绑定角标-战利品.png"],  # 特别注意 背包和战利品使用的角标不一样!!!
            test_show=False)
        match_status_code, match_result = match_template_with_optional_mask(
            source=img_block[2:-10:2, 2:-10:2, :],
            template=img_tar[2:-10:2, 2:-10:2, :],
            mask=mask[2:-10:2, 2:-10:2, :],
            test_show=False)
        if match_status_code == 0:
            return False, 0
        (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(src=match_result)
        # 如果匹配度<阈值，就认为没有找到
        matching_degree = 1 - minVal
        if matching_degree <= match_tolerance:
            return False, matching_degree
        return True, matching_degree


def match_block_equal_in_images(block_array, images):
    """
    识别block是否在file_patch文件夹中, 直接对比是否完全一致
    """

    for img_name, img_array in images.items():

        # 只在图像尺寸相同的情况下进行比较
        if not img_array.shape == block_array.shape:
            continue

        # 检查两个图像数组是否完全相同
        if not np.array_equal(block_array, img_array):
            continue

        return img_name[:-4]  # 去掉文件扩展名输出

    return None
