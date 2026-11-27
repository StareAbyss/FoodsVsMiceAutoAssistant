"""
测试对最小化窗口进行截图的多种方法
"""
import os
import sys

# 添加项目根目录到路径，以便导入 function 模块
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import time
import ctypes
from ctypes import windll, byref, c_ubyte, POINTER
from ctypes.wintypes import RECT, BOOL, HWND, HDC, HBITMAP

# 先导入 numpy，再导入 cv2（避免 python_loader 的 typing 冲突）
import numpy as np
import cv2

from win32gui import FindWindow, FindWindowEx, IsIconic, ShowWindow, SetWindowPos
import win32con

from function.common.bg_img_screenshot import capture_image_png
from test.output_paths import get_test_output_dir


def capture_with_printwindow(handle: int, raw_range: list = None) -> np.ndarray:
    """
    使用 PrintWindow API 对窗口进行截图（支持最小化窗口）

    Args:
        handle: 窗口句柄
        raw_range: 裁剪区域 [左上X, 左上Y, 右下X, 右下Y]

    Returns:
        numpy.ndarray: 截图数据 (高度, 宽度, BGR三通道)
    """
    # 获取窗口客户区大小
    r = RECT()
    windll.user32.GetClientRect(handle, byref(r))
    width, height = r.right, r.bottom

    if width <= 0 or height <= 0:
        print(f"警告: 窗口尺寸无效 ({width}x{height})")
        return np.zeros((100, 100, 3), dtype=np.uint8)

    print(f"窗口尺寸: {width}x{height}")

    # 创建设备上下文
    dc = windll.user32.GetDC(handle)
    cdc = windll.gdi32.CreateCompatibleDC(dc)
    bitmap = windll.gdi32.CreateCompatibleBitmap(dc, width, height)
    windll.gdi32.SelectObject(cdc, bitmap)

    # 使用 PrintWindow 替代 BitBlt
    # PW_RENDERFULLCONTENT = 0x00000002 (Windows 8.1+)
    # 0 = 只渲染客户区
    result = windll.user32.PrintWindow(handle, cdc, 0)

    if not result:
        print("警告: PrintWindow 返回失败")

    # 获取像素数据
    total_bytes = width * height * 4
    buffer = bytearray(total_bytes)
    byte_array = c_ubyte * total_bytes
    windll.gdi32.GetBitmapBits(bitmap, total_bytes, byte_array.from_buffer(buffer))

    # 清理资源
    windll.gdi32.DeleteObject(bitmap)
    windll.gdi32.DeleteObject(cdc)
    windll.user32.ReleaseDC(handle, dc)

    # 转换为 numpy 数组 (BGRA格式)
    image = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)

    # 转换为 BGR 格式（去掉 Alpha 通道）
    image_bgr = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    # 如果指定了裁剪区域，进行裁剪
    if raw_range:
        x1, y1, x2, y2 = raw_range
        image_bgr = image_bgr[y1:y2, x1:x2]

    return image_bgr


def test_minimized_window_capture():
    output_dir = get_test_output_dir("capture_image", "minimized")

    """测试对最小化窗口截图 - 对比老函数和新函数"""

    # === 配置部分 ===
    channel = "锑食"

    # 查找窗口句柄
    handle_360 = FindWindow("DUIWindow", channel)
    if not handle_360:
        print(f"错误: 未找到窗口 '{channel}'")
        return

    handle = FindWindowEx(handle_360, None, "TabContentWnd", "")
    handle = FindWindowEx(handle, None, "CefBrowserWindow", "")
    handle = FindWindowEx(handle, None, "Chrome_WidgetWin_0", "")
    handle = FindWindowEx(handle, None, "WrapperNativeWindowClass", "")
    handle = FindWindowEx(handle, None, "NativeWindowClass", "")

    if not handle:
        print("错误: 未找到游戏窗口句柄")
        return

    print(f"窗口句柄: {handle}")
    print(f"是否最小化: {IsIconic(handle_360)}")

    # 创建保存目录
    if not os.path.exists("test_output"):
        os.makedirs("test_output")

    screenshot_range = [0, 0, 950, 600]

    # === 使用老函数截图3张 ===
    print("\n" + "="*60)
    print("使用老函数 (BitBlt) 截图 3 张")
    print("="*60)
    for i in range(1, 4):
        print(f"\n第 {i} 张...")
        start_time = time.time()
        try:
            img = capture_image_png(
                handle=handle,
                raw_range=screenshot_range,
                root_handle=handle_360
            )
            elapsed = time.time() - start_time

            # 检查是否为黑屏
            is_black = np.all(img == 0)
            status = "❌ 黑屏" if is_black else "✅ 成功"
            print(f"  耗时: {elapsed:.3f}s | 尺寸: {img.shape} | 结果: {status}")

            filename = output_dir / f"old_method_{i}.png"
            cv2.imencode('.png', img)[1].tofile(str(filename))
            print(f"  已保存: {filename}")

            # 每张间隔0.5秒
            if i < 3:
                time.sleep(0.5)

        except Exception as e:
            print(f"  ❌ 错误: {e}")
            import traceback
            traceback.print_exc()

    # === 使用新函数截图3张 ===
    print("\n" + "="*60)
    print("使用新函数 (PrintWindow) 截图 3 张")
    print("="*60)
    for i in range(1, 4):
        print(f"\n第 {i} 张...")
        start_time = time.time()
        try:
            img = capture_with_printwindow(
                handle=handle,
                raw_range=screenshot_range
            )
            elapsed = time.time() - start_time

            # 检查是否为黑屏
            is_black = np.all(img == 0)
            status = "❌ 黑屏" if is_black else "✅ 成功"
            print(f"  耗时: {elapsed:.3f}s | 尺寸: {img.shape} | 结果: {status}")

            filename = output_dir / f"new_method_{i}.png"
            cv2.imencode('.png', img)[1].tofile(str(filename))
            print(f"  已保存: {filename}")

            # 每张间隔0.5秒
            if i < 3:
                time.sleep(0.5)

        except Exception as e:
            print(f"  ❌ 错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("最小化窗口截图测试")
    print("=" * 60)
    test_minimized_window_capture()
    print("\n测试完成！")
