import sys

from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication, QMainWindow

from function.scattered.gat_handle import faa_get_handle

if __name__ == '__main__':
    class ActionThread(QThread):
        """模拟FAA类"""

        def __init__(self):
            super().__init__()
            global T_ACTION_QUEUE_TIMER

        def run(self):
            handle = faa_get_handle(channel="锑食")

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=100, y=100)
            QThread.msleep(2000)

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=100, y=100)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=100, y=100)
            QThread.msleep(2000)

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=100, y=100)
            QThread.msleep(2000)

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=100, y=100)


    class MainWindow(QMainWindow):
        """模拟窗口主线程"""

        def __init__(self):
            super().__init__()
            self.initUI()
            global T_ACTION_QUEUE_TIMER
            self.t2 = ActionThread()

        def initUI(self):
            self.setWindowTitle('计时器示例')
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

    sys.exit(app.exec_())