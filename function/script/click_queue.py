# 鼠标点击队列，包含处理队列和添加队列
import queue
from PyQt6.QtCore import Qtimer
from function.common.bg_mouse import mouse_left_click

class ClickQueue:
    def __init__(self):
        self.click_queue = queue.Queue()
        self.click_timer = Qtimer()
        self.click_timer.timeout.connect(self.execute_click_queue)
        self.click_timer.start(25)

    def execute_click_queue(self):
        if not self.click_queue.empty():
            # 获取任务
            handle, x, y = self.click_queue.get()
            # 执行任务
            mouse_left_click(handle, x, y)
            # 标记任务已完成
            self.click_queue.task_done()


    def add_to_click_queue(self, handle, x, y):
        self.click_queue.put((handle, x, y))
