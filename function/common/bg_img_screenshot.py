from ctypes import windll, byref, c_ubyte
from ctypes.wintypes import RECT, HWND

from numpy import uint8, frombuffer

# 如果没有依赖
# pip install opencv-contrib-python

# 排除缩放干扰 但有的时候会出错 可以在这里多测试测试
windll.user32.SetProcessDPIAware()


def capture_picture_png(handle: HWND, raw_range: list):
    """
    窗口客户区截图
    Args:
        handle (HWND): 要截图的窗口句柄
        raw_range: 裁剪, 为 [左上X, 左上Y,右下X, 右下Y], 右下位置超出范围取最大(不会报错)

    Returns:
        numpy.array: 截图数据 3D array (高度,宽度,[B G R A四通道])
    """

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
    windll.gdi32.DeleteObject(cdc)    # 删除内存设备上下文
    windll.user32.ReleaseDC(handle, dc)   # 释放窗口的设备上下文

    # 将缓冲区数据转换为numpy数组，并重塑为图像的形状 (高度,宽度,[B G R A四通道])
    image = frombuffer(buffer, dtype=uint8).reshape(height, width, 4)

    # 裁剪图像到指定区域
    image = png_cropping(image=image, raw_range=raw_range)

    return image


def png_cropping(image, raw_range: list):
    return image[raw_range[1]:raw_range[3], raw_range[0]:raw_range[2], :]


