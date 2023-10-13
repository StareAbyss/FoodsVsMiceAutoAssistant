# coding:utf-8

from ctypes import windll, byref, c_ubyte, c_void_p
from ctypes.wintypes import RECT, HWND

import numpy as np
from cv2 import imwrite, waitKey, imshow
from win32gui import FindWindow,FindWindowEx

# 如果没有依赖
# pip install opencv-contrib-python

# 排除缩放干扰 但有的时候会出错 可以在这里多测试测试
windll.user32.SetProcessDPIAware()


def capture_picture_png(f_handle: HWND):
    """窗口客户区截图

    Args:
        f_handle (HWND): 要截图的窗口句柄

    Returns:
        numpy.ndarray: 截图数据
    """

    # 获取窗口客户区的大小
    r = RECT()
    windll.user32.GetClientRect(f_handle, byref(r))
    width, height = r.right, r.bottom

    # 开始截图
    dc = windll.user32.GetDC(f_handle)
    cdc = windll.gdi32.CreateCompatibleDC(dc)
    bitmap = windll.gdi32.CreateCompatibleBitmap(dc, width, height)
    windll.gdi32.SelectObject(cdc, bitmap)
    windll.gdi32.BitBlt(cdc, 0, 0, width, height, dc, 0, 0, 0x00CC0020)

    # 截图是 B G R A 排列，因此总元素个数需要乘以4
    total_bytes = width * height * 4
    buffer = bytearray(total_bytes)
    byte_array = c_ubyte * total_bytes
    windll.gdi32.GetBitmapBits(bitmap, total_bytes, byte_array.from_buffer(buffer))
    windll.gdi32.DeleteObject(bitmap)
    windll.gdi32.DeleteObject(cdc)
    windll.user32.ReleaseDC(f_handle, dc)

    # 返回截图数据为numpy.ndarray
    return np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)


if __name__ == "__main__":
    handle = FindWindow("DUIWindow", None)
    handle = FindWindowEx(handle, None, "TabContentWnd", "")
    handle = FindWindowEx(handle, None, "CefBrowserWindow", "")
    handle = FindWindowEx(handle, None, "Chrome_WidgetWin_0", "")
    handle = FindWindowEx(handle, None, "WrapperNativeWindowClass", "")
    handle = FindWindowEx(handle, None, "NativeWindowClass", "")
    handle = c_void_p(handle)
    image = capture_picture_png(handle)

    imwrite("test_screenshot.png", image)

    imshow("Capture Test", image)
    waitKey()
