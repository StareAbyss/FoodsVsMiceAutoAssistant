import time
from ctypes import windll, byref, c_ubyte
from ctypes.wintypes import RECT, HWND

from cv2 import imwrite, imshow, waitKey
from numpy import uint8, frombuffer

from function.scattered.gat_handle import faa_get_handle

# 如果没有依赖
# pip install opencv-contrib-python

# 排除缩放干扰 但有的时候会出错 可以在这里多测试测试
windll.user32.SetProcessDPIAware()


def capture_picture_png(handle: HWND, raw_range: list):
    """窗口客户区截图

    Args:
        handle (HWND): 要截图的窗口句柄
        raw_range: 裁剪, 为 [左上X, 左上Y,右下X, 右下Y], 右下位置超出范围取最大(不会报错)

    Returns:
        numpy.array: 截图数据 3D array (高度,宽度,[B G R A四通道])
    """

    # 获取窗口客户区的大小
    r = RECT()
    windll.user32.GetClientRect(handle, byref(r))
    width, height = r.right, r.bottom

    # 开始截图
    dc = windll.user32.GetDC(handle)
    cdc = windll.gdi32.CreateCompatibleDC(dc)
    bitmap = windll.gdi32.CreateCompatibleBitmap(dc, width, height)
    windll.gdi32.SelectObject(cdc, bitmap)
    windll.gdi32.BitBlt(cdc, 0, 0, width, height, dc, 0, 0, 0x00CC0020)

    # 截图的一个像素是 [B,G,R,A] 排列，因此总元素个数需要乘以4
    total_bytes = width * height * 4
    buffer = bytearray(total_bytes)
    byte_array = c_ubyte * total_bytes
    windll.gdi32.GetBitmapBits(bitmap, total_bytes, byte_array.from_buffer(buffer))
    windll.gdi32.DeleteObject(bitmap)
    windll.gdi32.DeleteObject(cdc)
    windll.user32.ReleaseDC(handle, dc)

    # 返回截图数据为 numpy.array (高度,宽度,[B G R A四通道])
    image = frombuffer(buffer, dtype=uint8).reshape(height, width, 4)
    # 裁剪
    image = png_cropping(image=image,raw_range=raw_range)
    return image


def png_cropping(image, raw_range: list):
    return image[raw_range[1]:raw_range[3], raw_range[0]:raw_range[2], :]


def main():
    handle = faa_get_handle(channel="锑食", mode="flash")
    # handle = faa_get_handle(channel="深渊之下 | 锑食", mode="flash")
    # handle = faa_get_handle(channel="深渊之下 | 锑食", mode="360")

    # 调用截图
    image = capture_picture_png(handle=handle, raw_range=[0, 0, 2000, 2000])
    # image = capture_picture_png(handle=handle, raw_range=[0, 0, 950, 600])

    # 保存图片
    imwrite(time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()) + ".png", image)

    # 暂时显示
    imshow(winname="Capture Test.png", mat=image)
    waitKey()


if __name__ == "__main__":
    main()
