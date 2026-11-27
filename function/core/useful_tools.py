import win32gui
from PyQt6.QtCore import QThread

from function.common.bg_img_match import loop_match_p_in_w
from function.globals.g_resources import RESOURCE_P


def once_gacha_gold_trevi_fountain(handle):
    """
    自动抽金币许愿池
    """
    # 循环识图并点击许愿十次按钮
    if loop_match_p_in_w(
            source_handle=handle,
            source_range=[600, 470, 710, 500],
            template=RESOURCE_P["common"]["许愿十次.png"],
            match_failed_check=1,
            match_tolerance=0.9
    ):
        # 等待200毫秒
        QThread.msleep(200)
    else:
        # 如果没有找到许愿十次按钮，则返回False
        return False, "没有找到许愿十次按钮，请确认是否在许愿池界面"
    # 点击完成后点击确定按钮
    if loop_match_p_in_w(
            source_handle=handle,
            source_range=[387, 336, 563, 367],
            template=RESOURCE_P["common"]["通用_确定.png"],
            match_failed_check=0,
            match_tolerance=0.9,
            match_interval=0,
            after_sleep=0
    ):
        # 等待200毫秒
        QThread.msleep(200)
    return True, None


def get_pixel_position(handle, x, y):
    """
    获取鼠标点击位置相对于目标句柄窗口的位置
    :param handle: 目标窗口句柄
    :param x: 鼠标点击位置的x坐标
    :param y: 鼠标点击位置的y坐标
    """
    # 获取窗口的坐标
    window_left, window_top, _, _ = win32gui.GetWindowRect(handle)

    # 计算鼠标相对于窗口的坐标
    relative_x = x - window_left
    relative_y = y - window_top

    return relative_x, relative_y
