import os
import sys

from PyQt5 import uic, QtWidgets
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QApplication

from function.get_paths import get_root_path


class MyMainWindow0(QMainWindow):
    """读取.ui文件创建类 并加上一些常用方法"""

    # 注意：
    # 若ui界面文件是个对话框，那么MyApp就必须继承 QDialog
    # 若ui界面文件是个MainWindow，那么MyApp就必须继承 QMainWindow
    def __init__(self):
        # 继承父方法
        super().__init__()

        # 根目录获取
        self.path_root = get_root_path()

        # 加载 ui文件
        uic.loadUi(self.path_root + '\\resource\\ui\\fvm_2.0.ui', self)

        # 加载图标
        self.setWindowIcon(QIcon(self.path_root + '\\resource\\logo\\png-512x512.png'))

        # 设置窗口名称
        self.setWindowTitle("FAA - 本软件免费且开源 - 反馈交流: 786921130")

    def printf(self, mes):
        """打印文本到输出框"""
        self.TextBrowser.append(mes)  # 在TextBrowser显示提示信息
        cursor = self.TextBrowser.textCursor()
        self.TextBrowser.moveCursor(cursor.End)
        QtWidgets.QApplication.processEvents()  # 实时输出

    def closeEvent(self, event):
        """对MainWindow的函数closeEvent进行重构, 退出软件时弹窗提醒 并且结束所有进程(和内部的线程)"""
        # self.reply = QMessageBox.question(self,
        #                                   '提示',
        #                                   "确认退出吗？",
        #                                   QMessageBox.Yes | QMessageBox.No,
        #                                   QMessageBox.No)
        # if self.reply == QMessageBox.Yes:
        #     event.accept()
        #     # 用过sys.exit(0)和sys.exit(app.exec_())，但没起效果
        #     os._exit(0)
        # else:
        #     event.ignore()

        event.accept()
        # 用过sys.exit(0)和sys.exit(app.exec_())，但没起效果
        os._exit(0)


if __name__ == "__main__":
    def main():
        # 实例化 PyQt后台管理
        app = QApplication(sys.argv)

        # 实例化 主窗口
        my_main_window = MyMainWindow0()

        my_main_window.show()

        # 运行主循环，必须调用此函数才可以开始事件处理
        sys.exit(app.exec_())


    main()
