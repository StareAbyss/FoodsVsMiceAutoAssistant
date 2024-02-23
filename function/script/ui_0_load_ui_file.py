import os
import sys

from PyQt5 import uic, QtWidgets
from PyQt5.QtGui import QIcon, QFont, QFontDatabase
from PyQt5.QtWidgets import QMainWindow, QApplication

from function.get_paths import paths


class MyMainWindow0(QMainWindow):
    """读取.ui文件创建类 并加上一些常用方法"""

    # 注意：
    # 若ui界面文件是个对话框，那么MyApp就必须继承 QDialog
    # 若ui界面文件是个MainWindow，那么MyApp就必须继承 QMainWindow
    def __init__(self):
        # 继承父方法
        super().__init__()

        # 加载 ui文件
        uic.loadUi(paths["root"] + '\\resource\\ui\\fvm_2.0.ui', self)

        # 设置窗口名称
        self.setWindowTitle("FAA - 本软件免费且开源 - 反馈交流: 786921130")

        # 设置窗口图标
        self.setWindowIcon(QIcon(paths["logo"] + "\\FetTuo-192x.png"))

        # 设定字体
        QFontDatabase.addApplicationFont(paths["font"] + "\\金山云技术体.ttf")
        font = QFont()
        font.setFamily("金山云技术体")
        font.setPointSize(10)
        self.setFont(font)

        # 打印默认输出提示
        self.start_print()

    def printf(self, mes):
        """打印文本到输出框 """
        self.TextBrowser.append(mes)  # 在TextBrowser显示提示信息
        self.TextBrowser.moveCursor(self.TextBrowser.textCursor().End)
        QtWidgets.QApplication.processEvents()  # 实时输出

    def start_print(self):
        """打印默认输出提示"""
        self.printf("使用安全说明")
        self.printf("[1] 务必有二级密码")
        self.printf("[2] 有一定的礼卷防翻牌异常")
        self.printf("[3] 高星或珍贵不绑卡挂拍卖/提前转移")
        self.printf("")
        self.printf("任何用户使用前, 请认真阅读[使用前请看我.pdf], 以解决[运行直接闪退][开始后没反应]多数问题")
        self.printf("开发者和深入使用, 请参考[README.md]")
        self.printf("[Github] https://github.com/StareAbyss/FoodsVsMouses_AutoAssistant")
        self.printf("[B站] https://www.bilibili.com/video/BV1fS421N7")
        self.printf("[反馈&交流QQ] 786921130 欢迎加入获取帮助")
        self.printf("[开源][免费][绿色] 请为我在 Github点个Star/B站三连评论弹幕支持吧")

    def closeEvent(self, event):
        """
        对MainWindow的函数closeEvent进行重构, 退出软件时弹窗提醒 并且结束所有进程(和内部的线程)
        """

        # 退出提示
        # self.reply = QMessageBox.question(
        #     self,
        #     '提示',
        #     "确认退出吗？",
        #     QMessageBox.Yes | QMessageBox.No,
        #     QMessageBox.No
        # )
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
