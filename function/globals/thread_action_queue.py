# 鼠标点击队列，包含处理队列和添加队列
import queue
from ctypes import windll
from string import printable
from threading import Timer

import win32con
import win32gui
from PyQt6.QtCore import QThread

from function.globals import EXTRA
from function.globals.log import CUS_LOGGER


class ThreadActionQueueTimer(QThread):
    """
    线程类
    包含一个队列和定时器，队列用于储存需要进行的操作，定时器用于绑定点击函数执行队列中的操作
    """

    def __init__(self):
        super().__init__()
        self.action_timer = None
        self.zoom_rate = None
        self.action_queue = queue.Queue()
        self.interval_time = 1 / EXTRA.CLICK_PER_SECOND  # 处理点击间隔, 单位: 秒
        # 计数每次统计间隔期间, 分别增减了多少次点击, 以查看消费者是否跟得上生产者
        self.count_addition = 0
        self.count_subtraction = 0
        # 按键名称和虚拟键码对应表
        self.VkCode = {
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

    def run(self):
        self.action_timer = Timer(self.interval_time, self.execute_click_queue)
        self.action_timer.start()
        self.exec()  # 开始事件循环
        self.action_timer.cancel()
        self.action_timer = None

    def stop(self):
        self.action_queue.queue.clear()
        self.quit()

    def print_queue(self):
        """线程不安全的方式查看队列内容"""
        items = []
        while not self.action_queue.empty():
            item = self.action_queue.get()
            items.append(item)
        # 将元素放回队列
        for item in items:
            self.action_queue.put(item)

        CUS_LOGGER.debug(f"点击列表:{items}")

    def print_queue_size(self) -> int:
        """线程安全的方式查看队列长度, 打印并返回"""
        q_size = self.action_queue.qsize()
        CUS_LOGGER.debug(f"点击列表长度:{q_size}")
        return q_size

    def print_queue_statue(self) -> int:
        q_size = self.action_queue.qsize()
        CUS_LOGGER.debug(f"点击列表长度:{q_size}, +{self.count_addition}, -{self.count_subtraction}")
        self.count_addition = 0
        self.count_subtraction = 0
        return q_size

    def execute_click_queue(self) -> None:
        """用于执行队列中的任务. 即消费者"""
        if not self.action_queue.empty():
            self.count_subtraction += 1
            # 获取任务
            d_type, handle, args = self.action_queue.get()
            # 执行任务
            self.do_something(d_type=d_type, handle=handle, args=args)
            # 标记任务已完成
            self.action_queue.task_done()

        # 回调
        self.action_timer = Timer(self.interval_time, self.execute_click_queue)
        self.action_timer.start()

    def add_click_to_queue(self, handle, x, y):
        """添加动作任务函数, 即生产者"""
        self.count_addition += 1
        self.action_queue.put(("click", handle, [x, y]))
        # print("鼠标左键点击添加到队列")

    def add_move_to_queue(self, handle, x, y):
        """添加动作任务函数, 即生产者"""
        self.count_addition += 1
        self.action_queue.put(("move_to", handle, [x, y]))
        # print("鼠标移动添加到队列")

    def add_keyboard_up_down_to_queue(self, handle, key):
        """添加动作任务函数, 即生产者"""
        self.count_addition += 1
        self.action_queue.put(("keyboard_up_down", handle, [key]))

    def do_something(self, d_type, handle, args) -> None:
        """聚合多种消费策略的执行"""
        if d_type == "click":
            self.do_left_mouse_click(handle=handle, x=args[0], y=args[1])
        elif d_type == "move_to":
            self.do_left_mouse_move_to(handle=handle, x=args[0], y=args[1])
        elif d_type == "keyboard_up_down":
            self.do_keyboard_up_down(handle=handle, key=args[0])

    def do_left_mouse_click(self, handle, x, y):
        """执行动作函数 子函数"""
        x = int(x * self.zoom_rate)
        y = int(y * self.zoom_rate)
        windll.user32.PostMessageW(handle, 0x0201, 0, y << 16 | x)
        windll.user32.PostMessageW(handle, 0x0202, 0, y << 16 | x)

    def do_left_mouse_move_to(self, handle, x, y):
        """执行动作函数 子函数"""
        x = int(x * self.zoom_rate)
        y = int(y * self.zoom_rate)
        windll.user32.PostMessageW(handle, 0x0200, 0, y << 16 | x)

    def do_keyboard_up_down(self, handle, key):
        """执行动作函数 子函数"""

        # 根据按键名获取虚拟按键码
        if len(key) == 1 and key in printable:
            vk_code = windll.user32.VkKeyScanA(ord(key)) & 0xff
        else:
            vk_code = self.VkCode[key]

        scan_code = windll.user32.MapVirtualKeyW(vk_code, 0)

        # 按下
        windll.user32.PostMessageW(handle, 0x100, vk_code, (scan_code << 16) | 1)
        # 松开
        windll.user32.PostMessageW(handle, 0x101, vk_code, (scan_code << 16) | 0XC0000001)

    def char_input(self, handle, char):
        """
        输入文字
        """
        win32gui.PostMessage(handle, win32con.WM_CHAR, ord(char), 0)

    def set_zoom_rate(self, zoom_rate):
        if __name__ == '__main__':
            self.zoom_rate = 1.0
        else:
            self.zoom_rate = zoom_rate


# 实例化为全局线程
T_ACTION_QUEUE_TIMER = ThreadActionQueueTimer()

"""
外部调用示例
T_CLICK_QUEUE_TIMER.add_to_click_queue(handle=self.handle, x=920, y=422)
QThread.msleep(200)
"""
