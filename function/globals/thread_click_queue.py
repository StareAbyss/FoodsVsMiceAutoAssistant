# 鼠标点击队列，包含处理队列和添加队列
import queue
import sys

from PyQt5.QtCore import QTimer, QThread
from PyQt5.QtWidgets import QApplication, QMainWindow

from function.common.bg_mouse import PostMessageW
from function.scattered.gat_handle import faa_get_handle


class ThreadClickQueueTimer(QThread):
    """
    线程类
    包含一个队列和定时器，队列用于储存需要进行的操作，定时器用于绑定点击函数执行队列中的操作
    """

    def __init__(self):
        super().__init__()
        self.click_queue_timer = None
        self.zoom_rate = None
        self.click_queue = queue.Queue()

    def run(self):
        self.click_queue_timer = QTimer()  # 不能放在init方法里，否则无效果
        self.click_queue_timer.timeout.connect(self.execute_click_queue)
        self.click_queue_timer.start(15)
        self.exec()  # 开始事件循环

    def stop(self):
        self.click_queue.queue.clear()
        self.click_queue_timer.stop()
        self.quit()

    def execute_click_queue(self):
        if not self.click_queue.empty():
            # 获取任务
            d_type, handle, x, y = self.click_queue.get()
            # 执行任务
            self.do_something(d_type=d_type, handle=handle, x=x, y=y)
            # 标记任务已完成
            self.click_queue.task_done()

    def add_click_to_queue(self, handle, x, y):
        self.click_queue.put(("click", handle, x, y))

        # print("鼠标左键点击添加到队列")

    def add_move_to_queue(self, handle, x, y):
        self.click_queue.put(("move_to", handle, x, y))

        # print("鼠标移动添加到队列")

    def do_something(self, d_type, handle, x, y):
        if d_type == "click":
            self.do_left_mouse_click(handle=handle, x=x, y=y)
        elif d_type == "move_to":
            self.do_left_mouse_move_to(handle=handle, x=x, y=y)

    def do_left_mouse_click(self, handle, x, y):
        x = int(x * self.zoom_rate)
        y = int(y * self.zoom_rate)
        PostMessageW(handle, 0x0201, 0, y << 16 | x)
        PostMessageW(handle, 0x0202, 0, y << 16 | x)

    def do_left_mouse_move_to(self, handle, x, y):
        x = int(x * self.zoom_rate)
        y = int(y * self.zoom_rate)
        PostMessageW(handle, 0x0200, 0, y << 16 | x)

    def set_zoom_rate(self, zoom_rate):
        if __name__ == '__main__':
            self.zoom_rate = 1.0
        else:
            self.zoom_rate = zoom_rate


# 实例化为全局线程
T_CLICK_QUEUE_TIMER = ThreadClickQueueTimer()

if __name__ == '__main__':
    class ActionThread(QThread):
        """模拟FAA类"""

        def __init__(self):
            super().__init__()
            global T_CLICK_QUEUE_TIMER

        def run(self):
            handle = faa_get_handle(channel="锑食")

            T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=handle, x=100, y=100)
            QThread.msleep(2000)

            T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=handle, x=100, y=100)
            T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=handle, x=100, y=100)
            QThread.msleep(2000)

            T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=handle, x=100, y=100)
            QThread.msleep(2000)

            T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=handle, x=100, y=100)


    class MainWindow(QMainWindow):
        """模拟窗口主线程"""

        def __init__(self):
            super().__init__()
            self.initUI()
            global T_CLICK_QUEUE_TIMER
            self.t2 = ActionThread()

        def initUI(self):
            self.setWindowTitle('计时器示例')
            self.setGeometry(300, 300, 250, 150)

        def do_something(self):
            self.t2.start()
            T_CLICK_QUEUE_TIMER.set_zoom_rate(1.0)
            T_CLICK_QUEUE_TIMER.start()


    """模拟启动"""
    app = QApplication(sys.argv)

    main_win = MainWindow()
    main_win.show()
    main_win.do_something()

    sys.exit(app.exec_())

"""
外部调用示例
T_CLICK_QUEUE_TIMER.add_to_click_queue(handle=self.handle, x=920, y=422)
QThread.msleep(200)
"""
