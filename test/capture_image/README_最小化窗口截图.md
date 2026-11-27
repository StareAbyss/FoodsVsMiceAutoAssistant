# 最小化窗口截图技术研究

## 问题背景

传统的 Windows 截图方法（如 `BitBlt`）无法对最小化或隐藏的窗口进行截图，会得到黑屏。

## 解决方案对比

### 方案1: PrintWindow API ✅ 推荐

**优点:**
- ✅ 支持最小化窗口截图
- ✅ 支持隐藏/被遮挡窗口截图
- ✅ 不需要改变窗口状态
- ✅ 性能较好

**缺点:**
- ⚠️ 对于某些使用 DirectX/OpenGL 渲染的应用可能无效
- ⚠️ 需要目标窗口支持 WM_PRINT 消息

**实现代码:**
```python
import ctypes
from ctypes import windll, byref, c_ubyte
from ctypes.wintypes import RECT
import numpy as np

def capture_with_printwindow(handle: int, raw_range: list = None):
    """使用 PrintWindow API 截图（支持最小化窗口）"""

    # 获取窗口客户区大小
    r = RECT()
    windll.user32.GetClientRect(handle, byref(r))
    width, height = r.right, r.bottom

    # 创建设备上下文
    dc = windll.user32.GetDC(handle)
    cdc = windll.gdi32.CreateCompatibleDC(dc)
    bitmap = windll.gdi32.CreateCompatibleBitmap(dc, width, height)
    windll.gdi32.SelectObject(cdc, bitmap)

    # 关键：使用 PrintWindow 替代 BitBlt
    result = windll.user32.PrintWindow(handle, cdc, 0)

    # 获取像素数据
    total_bytes = width * height * 4
    buffer = bytearray(total_bytes)
    byte_array = c_ubyte * total_bytes
    windll.gdi32.GetBitmapBits(bitmap, total_bytes, byte_array.from_buffer(buffer))

    # 清理资源
    windll.gdi32.DeleteObject(bitmap)
    windll.gdi32.DeleteObject(cdc)
    windll.user32.ReleaseDC(handle, dc)

    # 转换为 numpy 数组
    image = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)

    return image
```

### 方案2: 临时恢复窗口

**优点:**
- ✅ 兼容性好，适用于所有窗口
- ✅ 可以使用现有的截图代码

**缺点:**
- ❌ 会短暂显示窗口（用户体验差）
- ❌ 速度较慢
- ❌ 可能导致窗口闪烁

**实现要点:**
```python
import win32con
from win32gui import IsIconic, ShowWindow, SetWindowPos

# 检查是否最小化
if IsIconic(handle):
    # 禁用动画效果
    SPI_SETANIMATION = 0x0049
    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETANIMATION, 0, byref(ctypes.c_bool(False)), 0
    )

    # 恢复窗口但不激活（置于底部）
    ShowWindow(handle, win32con.SW_RESTORE)
    ShowWindow(handle, win32con.SW_SHOWNA)
    SetWindowPos(handle, win32con.HWND_BOTTOM, 0, 0, 0, 0,
                 win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)

    time.sleep(0.3)  # 等待窗口恢复

    # ... 执行截图 ...

    # 重新最小化
    ShowWindow(handle, win32con.SW_MINIMIZE)
```

### 方案3: BitBlt（传统方法）❌ 不推荐

**仅适用于:**
- 窗口未最小化且可见时

**不支持:**
- ❌ 最小化窗口
- ❌ 隐藏窗口
- ❌ 被完全遮挡的窗口

## 技术原理

### PrintWindow 工作原理

PrintWindow 向目标窗口发送 `WM_PRINT` 或 `WM_PRINTCLIENT` 消息，迫使窗口自行调用其绘制逻辑（如 OnPaint），将图形输出到指定的设备上下文（DC）。这绕过了前台显示状态的限制。

```
PrintWindow(hwnd, hdc, flags)
    ↓
发送 WM_PRINT 消息给窗口
    ↓
窗口调用自己的绘制代码
    ↓
绘制到指定的 HDC
    ↓
返回位图数据
```

### BitBlt 为何失败

BitBlt 直接从屏幕缓冲区复制像素数据。当窗口最小化时：
- 窗口的内容不再被渲染到屏幕
- 屏幕缓冲区中该区域是黑色的
- 因此复制得到的是黑屏

## 实际应用建议

### 对于 FAA 项目

**推荐方案：PrintWindow**

修改 `function/common/bg_img_screenshot.py` 中的 `capture_image_png_once` 函数：

```python
def capture_image_png_once(handle: int) -> numpy.ndarray:
    """单次窗口客户区截图（使用 PrintWindow 支持最小化窗口）"""

    # 获取窗口客户区的大小
    r = RECT()
    windll.user32.GetClientRect(handle, byref(r))
    width, height = r.right, r.bottom

    if width <= 0 or height <= 0:
        return np.zeros((1, 1, 3), dtype=np.uint8)

    # 创建设备上下文
    dc = windll.user32.GetDC(handle)
    cdc = windll.gdi32.CreateCompatibleDC(dc)
    bitmap = windll.gdi32.CreateCompatibleBitmap(dc, width, height)
    windll.gdi32.SelectObject(cdc, bitmap)

    # 使用 PrintWindow 替代 BitBlt
    windll.user32.PrintWindow(handle, cdc, 0)

    # 准备缓冲区
    total_bytes = width * height * 4
    buffer = bytearray(total_bytes)
    byte_array = c_ubyte * total_bytes

    # 从位图中获取像素数据
    windll.gdi32.GetBitmapBits(bitmap, total_bytes, byte_array.from_buffer(buffer))

    # 清理资源
    windll.gdi32.DeleteObject(bitmap)
    windll.gdi32.DeleteObject(cdc)
    windll.user32.ReleaseDC(handle, dc)

    # 转换为numpy数组
    image = frombuffer(buffer, dtype=uint8).reshape(height, width, 4)

    return image
```

## 测试文件

已创建测试文件：`test/capture_image/test_minimized_capture.py`

运行测试：
```bash
cd test/capture_image
python test_minimized_capture.py
```

测试内容包括：
1. 传统 BitBlt 方法（预期失败）
2. PrintWindow 方法（预期成功）
3. 临时恢复窗口方法（备选方案）

## 参考资料

1. [PrintWindow 官方文档](https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-printwindow)
2. [Capturing Minimized Window - CodeProject](https://www.codeproject.com/Articles/20651/Capturing-Minimized-Window-A-Kid-s-Trick)
3. [最小化窗口截图技术详解](https://blog.csdn.net/weixin_42372837/article/details/154203841)

## 注意事项

⚠️ **重要提示:**
1. PrintWindow 对某些游戏引擎（DirectX/OpenGL）可能无效
2. 如果 PrintWindow 返回黑屏，可能需要回退到"临时恢复窗口"方案
3. 在生产环境中使用时，建议添加错误处理和降级策略
4. 确保目标窗口句柄有效且窗口未被销毁
