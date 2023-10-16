# coding:utf-8

from ctypes import windll, byref
from ctypes.wintypes import HWND, POINT
from time import sleep

PostMessageW = windll.user32.PostMessageW
ClientToScreen = windll.user32.ClientToScreen

# WM_MOUSE_MOVE = 0x0200
# WM_L_BUTTON_DOWN = 0x0201
# WM_L_BUTTON_UP = 0x202
# WM_MOUSE_WHEEL = 0x020A
# WHEEL_DELTA = 120


def mouse_move_to(handle: HWND, x: int, y: int):
    """移动鼠标到坐标（x, y)

    Args:
        handle (HWND): 窗口句柄
        x (int): 横坐标
        y (int): 纵坐标
    """
    # https://docs.microsoft.com/en-us/windows/win32/inputdev/wm-mousemove
    # wparam = 0
    # lparam = y << 16 | x
    # PostMessageW(handle, WM_MOUSE_MOVE, wparam, lparam)
    PostMessageW(handle, 0x0200, 0, y << 16 | x)


def mouse_left_down(handle: HWND, x: int, y: int):
    """在坐标(x, y)按下鼠标左键

    Args:
        handle (HWND): 窗口句柄
        x (int): 横坐标
        y (int): 纵坐标
    """
    # https://docs.microsoft.com/en-us/windows/win32/inputdev/wm-lbuttondown
    # wparam = 0
    # lparam = y << 16 | x
    # PostMessageW(handle, WM_L_BUTTON_DOWN, wparam, lparam)
    PostMessageW(handle, 0x0201, 0, y << 16 | x)


def mouse_left_up(handle: HWND, x: int, y: int):
    """在坐标(x, y)放开鼠标左键

    Args:
        handle (HWND): 窗口句柄
        x (int): 横坐标
        y (int): 纵坐标
    """
    # https://docs.microsoft.com/en-us/windows/win32/inputdev/wm-lbuttonup
    # wparam = 0
    # lparam = y << 16 | x
    # PostMessageW(handle, WM_L_BUTTON_UP, wparam, lparam)
    PostMessageW(handle, 0x202, 0, y << 16 | x)


def mouse_left_click(handle: HWND, x: int, y: int, interval_time=0.05, sleep_time=0.05):
    """
    在坐标(x, y)点击(按下 休息 放开)
    Args:
        handle: 窗口句柄
        x: 横坐标
        y: 纵坐标
        interval_time: 按住的时间
        sleep_time: 点击后休息的时间
    """
    PostMessageW(handle, 0x0201, 0, y << 16 | x)
    sleep(interval_time)
    PostMessageW(handle, 0x202, 0, y << 16 | x)
    sleep(sleep_time)


def scroll(handle: HWND, delta: int, x: int, y: int):
    """在坐标(x, y)滚动鼠标滚轮

    Args:
        handle (HWND): 窗口句柄
        delta (int): 为正向上滚动，为负向下滚动
        x (int): 横坐标
        y (int): 纵坐标
    """
    mouse_move_to(handle, x, y)
    # https://docs.microsoft.com/en-us/windows/win32/inputdev/wm-mousewheel
    wparam = delta << 16
    p = POINT(x, y)
    ClientToScreen(handle, byref(p))
    lparam = p.y << 16 | p.x
    PostMessageW(handle, 0x020A, wparam, lparam)


def scroll_up(handle: HWND, x: int, y: int):
    """在坐标(x, y)向上滚动鼠标滚轮

    Args:
        handle (HWND): 窗口句柄
        x (int): 横坐标
        y (int): 纵坐标
    """
    scroll(handle, 120, x, y)


def scroll_down(handle: HWND, x: int, y: int):
    """在坐标(x, y)向下滚动鼠标滚轮

    Args:
        handle (HWND): 窗口句柄
        x (int): 横坐标
        y (int): 纵坐标
    """
    scroll(handle, -120, x, y)
