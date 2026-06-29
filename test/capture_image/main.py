import os
import time

import cv2
from win32gui import FindWindow, FindWindowEx

from function.common.bg_img_screenshot import capture_image_png

channel = "锑食"
handle_360 = FindWindow("DUIWindow", channel)  # 360窗口 该层级有刷新框
handle = FindWindowEx(handle_360, None, "TabContentWnd", "")
handle = FindWindowEx(handle, None, "CefBrowserWindow", "")
handle = FindWindowEx(handle, None, "Chrome_WidgetWin_0", "")  # 该层级 有 服务器序号输入框
handle = FindWindowEx(handle, None, "WrapperNativeWindowClass", "")
handle = FindWindowEx(handle, None, "NativeWindowClass", "")  # game窗口

# 计算耗时 0.004s

start_time = time.time()
img = capture_image_png(
    handle=handle,
    raw_range=[0,0,2000,2000],
    root_handle=handle_360
)
print(f"耗时: {time.time() - start_time}")

# 检查图像是否有效
if img is not None and img.size > 0:
    if not os.path.exists("img"):
        os.makedirs("img")
    cv2.imencode(ext=".png", img=img)[1].tofile(os.path.join("img", "test.png"))
    print("图像保存成功")
else:
    print("捕获的图像是空的或无效的")
