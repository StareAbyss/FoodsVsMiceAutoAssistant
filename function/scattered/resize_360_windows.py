import ctypes

import win32con
import win32gui

from function.globals import EXTRA
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_channel_name import get_channel_name


def batch_resize_window(game_name, name_1p: str, name_2p: str, platform: str):
    """
    按所选区服调整360窗口尺寸与位置。

    QQ空间选服页比其他平台更大，窗口按逻辑像素额外增加宽20、高75，
    再统一应用屏幕缩放；双窗口并排时宽度仍受半屏空间限制。

    Args:
        game_name: 游戏名称，用于取得两个窗口的频道名。
        name_1p: 1P窗口名。
        name_2p: 2P窗口名。
        platform: 首页选择的区服。
    """

    # 获取窗口名称
    channel_1p, channel_2p = get_channel_name(game_name=game_name, name_1p=name_1p, name_2p=name_2p)

    handles = {
        1: faa_get_handle(channel=channel_1p, mode="360"),
        2: faa_get_handle(channel=channel_2p, mode="360")}
    extra_width, extra_height = (20, 75) if platform == "QQ空间" else (0, 0)
    width = int((955 + extra_width) * EXTRA.ZOOM_RATE)
    height = int((668 + extra_height) * EXTRA.ZOOM_RATE)

    # 获取屏幕工作区域大小
    user32 = ctypes.windll.user32
    screen_width = user32.GetSystemMetrics(0)
    screen_height = user32.GetSystemMetrics(1)

    if height * 2 <= screen_height:

        # 第一个窗口放置在屏幕右上角,最小大小
        win32gui.SetWindowPos(
            handles[1],
            win32con.HWND_TOP,
            screen_width - width,  # X坐标：屏幕宽度减去窗口宽度
            0,  # Y坐标：顶部对齐
            width,
            height,
            win32con.SWP_SHOWWINDOW
        )

        if handles[2]:
            # 第二个窗口放置在第一个窗口下方（紧贴）,最小大小
            win32gui.SetWindowPos(
                handles[2],
                win32con.HWND_TOP,
                screen_width - width,  # X坐标
                height,  # Y坐标
                width,
                height,
                win32con.SWP_SHOWWINDOW
            )
    else:
        if handles[2]:
            # 顶部居中，宽度占满屏幕，高度最小
            win32gui.SetWindowPos(
                handles[1],
                win32con.HWND_TOP,
                0,  # X坐标：屏幕宽度减去窗口宽度
                0,  # Y坐标：顶部对齐
                int(screen_width / 2),
                height,
                win32con.SWP_SHOWWINDOW
            )
            win32gui.SetWindowPos(
                handles[2],
                win32con.HWND_TOP,
                int(screen_width / 2),  # X坐标：屏幕宽度减去窗口宽度
                0,  # Y坐标：顶部对齐
                int(screen_width / 2),
                height,
                win32con.SWP_SHOWWINDOW
            )
        else:
            # 第一个窗口放置在屏幕右上角,最小大小
            win32gui.SetWindowPos(
                handles[1],
                win32con.HWND_TOP,
                screen_width - width,  # X坐标：屏幕宽度减去窗口宽度
                0,  # Y坐标：顶部对齐
                width,
                height,
                win32con.SWP_SHOWWINDOW
            )
