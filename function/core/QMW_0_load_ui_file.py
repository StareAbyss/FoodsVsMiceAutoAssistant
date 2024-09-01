import os
import sys

from PyQt6 import uic, QtGui
from PyQt6.QtGui import QIcon, QFontDatabase
from PyQt6.QtWidgets import QMainWindow, QApplication

from function.common.get_system_dpi import get_system_dpi
from function.globals.get_paths import PATHS
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.qrc import test_rc,theme_rc,qdarkgraystyle_rc,modern_rc,GTRONICK_rc

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
        self.setWindowTitle("FAA - 本软件免费且开源")

        # 设置版本号
        self.version = "v1.5.0-beta.3"
        self.version += "   "
        self.Label_Version.setText(self.version)

        # 从服务器获取最新版本号，如果和本地一致，就把版本号改成金色；不一致改成绿色

        # 设置窗口图标
        # self.setWindowIcon(QIcon(PATHS["logo"] + "\\圆角-FetTuo-192x.png"))

        # 获取 dpi & zoom 仅能在类中调用
        self.zoom_rate = get_system_dpi() / 96
        T_ACTION_QUEUE_TIMER.set_zoom_rate(self.zoom_rate)

        # 设定字体
        font2=QFontDatabase.addApplicationFont(PATHS["font"] + "\\NotoSansMonoCJKhk-Bold.ttf")
        font_family2 = QFontDatabase.applicationFontFamilies(font2)[0]
        print(font_family2)




        # 获取系统样式
        if self.palette().color(QtGui.QPalette.ColorRole.Window).lightness() < 128:
            self.theme = "dark"
        else:
            self.theme = "light"



    def closeEvent(self, event):
        """
        对MainWindow的函数closeEvent进行重构, 退出软件时弹窗提醒 并且结束所有进程(和内部的线程)
        """

        event.accept()
        # 用过sys.exit(0)和sys.exit(app.exec())，但没起效果
        os._exit(0)




if __name__ == "__main__":
    def main():
        # 实例化 PyQt后台管理
        app = QApplication(sys.argv)

        # 实例化 主窗口
        my_main_window = QMainWindowLoadUI()

        my_main_window.show()

        # 运行主循环，必须调用此函数才可以开始事件处理
        sys.exit(app.exec())


    main()
