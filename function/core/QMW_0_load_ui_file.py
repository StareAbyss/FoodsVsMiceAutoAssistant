import os
import sys

from PyQt5 import uic
from PyQt5.QtGui import QIcon, QFont, QFontDatabase
from PyQt5.QtWidgets import QMainWindow, QApplication

from function.common.get_system_dpi import get_system_dpi
from function.globals.get_paths import PATHS
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

ZOOM_RATE = None


class QMainWindowLoadUI(QMainWindow):
    """读取.ui文件创建类 并加上一些常用方法"""

    # 注意：
    # 若ui界面文件是个对话框，那么MyApp就必须继承 QDialog
    # 若ui界面文件是个MainWindow，那么MyApp就必须继承 QMainWindow
    def __init__(self):
        # 继承父方法
        super().__init__()

        # 加载 ui文件
        uic.loadUi(PATHS["root"] + '\\resource\\ui\\FAA_3.0.ui', self)

        # 设置窗口名称
        self.setWindowTitle("FAA - 本软件免费且开源 - 反馈交流: 786921130")

        # 设置窗口图标
        self.setWindowIcon(QIcon(PATHS["logo"] + "\\圆角-FetTuo-192x.png"))

        # 获取 dpi & zoom 仅能在类中调用
        self.zoom_rate = get_system_dpi() / 96
        T_ACTION_QUEUE_TIMER.set_zoom_rate(self.zoom_rate)

        # 设定字体
        font_id = QFontDatabase.addApplicationFont(PATHS["font"] + "\\SmileySans-Oblique.ttf")
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            self.font = QFont(font_family, 11)
            self.setFont( self.font)

    def closeEvent(self, event):
        """
        对MainWindow的函数closeEvent进行重构, 退出软件时弹窗提醒 并且结束所有进程(和内部的线程)
        """

        event.accept()
        # 用过sys.exit(0)和sys.exit(app.exec_())，但没起效果
        os._exit(0)


if __name__ == "__main__":
    def main():
        # 实例化 PyQt后台管理
        app = QApplication(sys.argv)

        # 实例化 主窗口
        my_main_window = QMainWindowLoadUI()

        my_main_window.show()

        # 运行主循环，必须调用此函数才可以开始事件处理
        sys.exit(app.exec_())


    main()
