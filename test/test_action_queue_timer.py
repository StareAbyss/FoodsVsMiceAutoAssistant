import cProfile
import sys

from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow

from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.gat_handle import faa_get_handle

if __name__ == '__main__':
    class ActionThread(QThread):
        """模拟FAA类"""

        def __init__(self):
            super().__init__()

            self.check_interval = 1
            self.spend_time = 0
            self.test_num_click = 1000

            # 设置定时器每1000毫秒（1秒）触发一次 以打印
            self.timer = QTimer()
            self.timer.timeout.connect(self.remaining)
            self.timer.start(self.check_interval * 1000)

        def run(self):
            handle = faa_get_handle(channel="锑食-微端")

            # 创建一个cProfile.Profile对象
            pr = cProfile.Profile()
            for i in range(self.test_num_click):
                # 使用cProfile来分析add_click_to_queue的性能
                pr.runctx('T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=1, y=1)',
                          globals(), locals())

            self.exec()  # 启动事件循环

            # 分析结果输出到文件
            pr.dump_stats('profile_results.prof')

        def remaining(self):
            self.spend_time += self.check_interval
            # 假设T_ACTION_QUEUE_TIMER是您的全局线程类实例
            if T_ACTION_QUEUE_TIMER.print_queue_statue() == 0:
                # print(f"队列已归零. 使用了{self.spend_time}s")
                # print(f"每秒处理了{self.test_num_click / self.spend_time}次点击")
                self.timer.stop()
                self.quit()


    class MainWindow(QMainWindow):
        """模拟窗口主线程"""

        def __init__(self):
            super().__init__()
            self.initUI()
            self.t2 = ActionThread()

        def initUI(self):
            self.setWindowTitle('剩余点击次数')
            self.setGeometry(300, 300, 250, 150)

        def do_something(self):
            self.t2.start()
            T_ACTION_QUEUE_TIMER.set_zoom_rate(1.0)
            T_ACTION_QUEUE_TIMER.start()


    """模拟启动"""
    app = QApplication(sys.argv)

    main_win = MainWindow()
    main_win.show()
    main_win.do_something()

    sys.exit(app.exec())
