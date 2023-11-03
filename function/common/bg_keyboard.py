from ctypes import windll
from ctypes.wintypes import HWND
from string import printable
from time import sleep

PostMessageW = windll.user32.PostMessageW
MapVirtualKeyW = windll.user32.MapVirtualKeyW
VkKeyScanA = windll.user32.VkKeyScanA

WM_KEYDOWN = 0x100  # 按下操作
WM_KEYUP = 0x101  # 松开操作

# 详情可查阅
# https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
# https://learn.microsoft.com/zh-cn/windows/win32/inputdev/virtual-key-codes
VkCode = {
    "l_button": 0x01,  # 鼠标左键
    "r_button": 0x02,  # 鼠标右键
    "backspace": 0x08,
    "tab": 0x09,
    "return": 0x0D,
    "shift": 0x10,
    "control": 0x11,  # ctrl
    "menu": 0x12,
    "pause": 0x13,
    "capital": 0x14,
    "enter": 0x0D,  # 回车键
    "escape": 0x1B,  # ESC
    "space": 0x20,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "print": 0x2A,
    "snapshot": 0x2C,
    "insert": 0x2D,
    "delete": 0x2E,
    "0": 0x30,  # 主键盘0
    "1": 0x31,  # 主键盘1
    "2": 0x32,  # 主键盘2
    "3": 0x33,  # 主键盘3
    "4": 0x34,  # 主键盘4
    "5": 0x35,  # 主键盘5
    "6": 0x36,  # 主键盘6
    "7": 0x37,  # 主键盘7
    "8": 0x38,  # 主键盘8
    "9": 0x39,  # 主键盘9
    "left_win": 0x5B,
    "right_win": 0x5C,
    "num0": 0x60,  # 数字键盘0
    "num1": 0x61,  # 数字键盘1
    "num2": 0x62,  # 数字键盘2
    "num3": 0x63,  # 数字键盘3
    "num4": 0x64,  # 数字键盘4
    "num5": 0x65,  # 数字键盘5
    "num6": 0x66,  # 数字键盘6
    "num7": 0x67,  # 数字键盘7
    "num8": 0x68,  # 数字键盘8
    "num9": 0x69,  # 数字键盘9
    "multiply": 0x6A,  # 数字键盘乘键
    "add": 0x6B,
    "separator": 0x6C,
    "subtract": 0x6D,
    "decimal": 0x6E,
    "divide": 0x6F,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "numlock": 0x90,
    "scroll": 0x91,
    "left_shift": 0xA0,
    "right_shift": 0xA1,
    "left_control": 0xA2,
    "right_control": 0xA3,
    "left_menu": 0xA4,
    "right_menu": 0XA5
}


def get_virtual_keycode(key: str):
    """根据按键名获取虚拟按键码

    Args:
        key (str): 按键名

    Returns:
        int: 虚拟按键码
    """
    if len(key) == 1 and key in printable:
        # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-vkkeyscana
        return VkKeyScanA(ord(key)) & 0xff
    else:
        return VkCode[key]


def key_down(handle: HWND, key: str):
    """按下指定按键

    Args:
        handle (HWND): 窗口句柄
        key (str): 按键名
    """
    vk_code = get_virtual_keycode(key)
    scan_code = MapVirtualKeyW(vk_code, 0)
    # https://docs.microsoft.com/en-us/windows/win32/inputdev/wm-keydown
    wparam = vk_code
    lparam = (scan_code << 16) | 1
    PostMessageW(handle, WM_KEYDOWN, wparam, lparam)  # 发送信息给窗口是按键操作本质，PostMessageW(句柄,操作码(按下和放开), wparam, lparam)


def key_up(handle: HWND, key: str):
    """放开指定按键

    Args:
        handle (HWND): 窗口句柄
        key (str): 按键名
    """
    vk_code = get_virtual_keycode(key)
    scan_code = MapVirtualKeyW(vk_code, 0)
    # https://docs.microsoft.com/en-us/windows/win32/inputdev/wm-keyup
    wparam = vk_code
    lparam = (scan_code << 16) | 0XC0000001
    PostMessageW(handle, WM_KEYUP, wparam, lparam)  # 发送信息给窗口是按键操作本质，PostMessageW(句柄,操作码(按下和放开), wparam, lparam)


def key_down_up(handle: HWND, key: str, interval_time: float = 0.05, sleep_time: float = 0.05):
    key_down(handle, key)
    sleep(interval_time)
    key_up(handle, key)
    sleep(sleep_time)


# 测试代码
if __name__ == "__main__":
    # 需要和目标窗口同一权限，游戏窗口通常是管理员权限 不是管理员就提权
    import sys

    if not windll.shell32.IsUserAnAdmin():
        windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, __file__, None, 1)
    handle = windll.user32.FindWindowW(None, "魔兽世界")

    # 控制角色向前移动两秒
    key_down(handle, 'w')
    sleep(2)
    key_up(handle, 'w')
