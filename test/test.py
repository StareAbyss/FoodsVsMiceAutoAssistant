import win32con
import win32gui

from function.scattered.gat_handle import faa_get_handle


def restore_window_if_minimized(handle):

    # 检查窗口是否最小化
    if win32gui.IsIconic(handle):
        print("确认处于最小化状态，尝试恢复...")

        # 恢复窗口（但不会将其置于最前面）
        win32gui.ShowWindow(handle, win32con.SW_RESTORE)
    else:
        print("确认窗口激活...")
    # 将窗口置于Z序的底部，但不改变活动状态
    win32gui.SetWindowPos(handle, win32con.HWND_BOTTOM, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)


# 示例：找到记事本窗口并尝试恢复
hwnd = faa_get_handle(channel="锑食-微端", mode="360")
if hwnd:
    restore_window_if_minimized(hwnd)
else:
    print("未找到窗口")
