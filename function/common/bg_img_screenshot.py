import numpy as np
import time
from ctypes import windll, byref, c_ubyte
from ctypes.wintypes import RECT, HWND
from numpy import uint8, frombuffer


# 如果没有依赖
# pip install opencv-contrib-python

# 排除缩放干扰 但有的时候会出错 可以在这里多测试测试
# windll.user32.SetProcessDPIAware()

def restore_window_if_minimized(handle) -> bool:
    """
    :param handle: 句柄
    :return: 如果是最小化, 并恢复至激活窗口的底层, 则返回True, 否则返回False.
    """

    # 检查窗口是否最小化
    if win32gui.IsIconic(handle):
        # 恢复窗口（但不会将其置于最前面）
        win32gui.ShowWindow(handle, win32con.SW_RESTORE)

        # 将窗口置于Z序的底部，但不改变活动状态
        win32gui.SetWindowPos(
            handle,
            win32con.HWND_BOTTOM,
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)

        return True
    return False

def capture_image_png(handle: HWND, raw_range: list, root_handle: HWND = None):
    """
    窗口客户区截图
    Args:
        handle (HWND): 要截图的窗口句柄
        raw_range: 裁剪, 为 [左上X, 左上Y,右下X, 右下Y], 右下位置超出范围取最大(不会报错)
        root_handle: 根窗口句柄, 用于检查窗口是否最小化, 如果最小化则尝试恢复至激活窗口的底层 可空置

    Returns:
        numpy.array: 截图数据 3D array (高度,宽度,[B G R A四通道])
    """

    # 尝试截图一次
    image = capture_image_png_once(handle=handle)

    # image == [], 句柄错误, 返回一个对应大小的 全0 图像
    if image is None:
        return np.zeros((raw_range[3] - raw_range[1], raw_range[2] - raw_range[0], 3), dtype=np.uint8)

    # 检查是否为全黑 如果全0 大概率是最小化了
    if is_mostly_black(image=image, sample_points=9):
        # 检查窗口是否最小化
        if root_handle:
            # 尝试恢复至激活窗口的底层
            if restore_window_if_minimized(handle=root_handle):
                # 如果恢复成功, 再次尝试截图一次
                time.sleep(0.1)
                image = capture_image_png_once(handle=handle)

    # 裁剪图像到指定区域
    image = png_cropping(image=image, raw_range=raw_range)

    return image


def capture_image_png_all(handle: HWND, root_handle: HWND = None):
    """
    跟上边那个函数一毛一样，只是用来截取全屏
    """
    # 尝试截图一次
    image = capture_image_png_once(handle=handle)

    # image == [], 句柄错误, 返回一个对应大小的 全0 图像
    if image is None:
        return np.zeros((1, 1, 3), dtype=np.uint8)

    # 检查是否为全黑 如果全0 大概率是最小化了
    if is_mostly_black(image=image, sample_points=9):
        # 检查窗口是否最小化
        if root_handle:
            # 尝试恢复至激活窗口的底层
            if restore_window_if_minimized(handle=root_handle):
                # 如果恢复成功, 再次尝试截图一次
                image = capture_image_png_once(handle=handle)

    return image


def is_mostly_black(image, sample_points=9):
    """
    检查图像是否主要是黑色, 通过抽样像素来判断, 能减少占用.
    :param image: NumPy数组表示的图像.
    :param sample_points: 要检查的像素点数, 默认为9.
    :return: 如果抽样的像素都是黑色,则返回True; 否则返回False.
    """
    if image.size == 0:
        return True
    height, width = image.shape[:2]

    # 定义要检查的像素位置
    positions = [
        (0, 0),
        (0, width - 1),
        (height - 1, 0),
        (height - 1, width - 1),
        (height // 2, width // 2),
        (0, width // 2),
        (height // 2, 0),
        (height - 1, width // 2),
        (height // 2, width - 1)
    ]

    # 仅使用前sample_points个位置
    positions = positions[:sample_points]

    # 检查每个位置的像素是否都是黑色
    for y, x in positions:
        if np.any(image[y, x] != 0):  # 如果任何一个像素不是全黑
            return False
    return True


def capture_image_png_once(handle: HWND):
    # 获取窗口客户区的大小
    r = RECT()
    windll.user32.GetClientRect(handle, byref(r))  # 获取指定窗口句柄的客户区大小
    width, height = r.right, r.bottom  # 客户区宽度和高度

    # 创建设备上下文
    dc = windll.user32.GetDC(handle)  # 获取窗口的设备上下文
    cdc = windll.gdi32.CreateCompatibleDC(dc)  # 创建一个与给定设备兼容的内存设备上下文
    bitmap = windll.gdi32.CreateCompatibleBitmap(dc, width, height)  # 创建兼容位图
    windll.gdi32.SelectObject(cdc, bitmap)  # 将位图选入到内存设备上下文中，准备绘图

    # 执行位块传输，将窗口客户区的内容复制到内存设备上下文中的位图
    windll.gdi32.BitBlt(cdc, 0, 0, width, height, dc, 0, 0, 0x00CC0020)

    # 准备缓冲区，用于接收位图的像素数据
    total_bytes = width * height * 4  # 计算总字节数，每个像素4字节（RGBA）
    buffer = bytearray(total_bytes)  # 创建字节数组作为缓冲区
    byte_array = c_ubyte * total_bytes  # 定义C类型数组类型

    # 从位图中获取像素数据到缓冲区
    windll.gdi32.GetBitmapBits(bitmap, total_bytes, byte_array.from_buffer(buffer))

    # 清理资源
    windll.gdi32.DeleteObject(bitmap)  # 删除位图对象
    windll.gdi32.DeleteObject(cdc)  # 删除内存设备上下文
    windll.user32.ReleaseDC(handle, dc)  # 释放窗口的设备上下文

    # 将缓冲区数据转换为numpy数组，并重塑为图像的形状 (高度,宽度,[B G R A四通道])
    image = frombuffer(buffer, dtype=uint8).reshape(height, width, 4)

    return image


def png_cropping(image, raw_range: list = None):
    """
    裁剪图像
    :param image:
    :param raw_range: [左上X, 左上Y,右下X, 右下Y]
    :return:
    """
    if raw_range is None:
        return image
    return image[raw_range[1]:raw_range[3], raw_range[0]:raw_range[2], :]
