import datetime

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import pyqtSignal

from function.core.QMW_1_load_settings import QMainWindowLoadSettings
from function.globals.log import CUS_LOGGER


class QMainWindowLog(QMainWindowLoadSettings):
    signal_dialog = pyqtSignal(str, str)  # 标题, 正文
    signal_print_to_ui_1 = pyqtSignal(str, str, bool)

    def __init__(self):
        # 继承父类构造方法
        super().__init__()

        # 链接防呆弹窗
        self.signal_dialog.connect(self.show_dialog)

        # 链接日志输入信号
        self.signal_print_to_ui = self.SignalPrintf(signal_1=self.signal_print_to_ui_1)
        self.signal_print_to_ui_1.connect(self.print_to_ui)

        # 储存所有信号
        self.signal_dict = {
            "print_to_ui": self.signal_print_to_ui,
            "dialog": self.signal_dialog,
            "end": self.signal_end
        }

        # 打印默认输出提示
        self.start_print()

    class SignalPrintf:

        def __init__(self, signal_1):
            super().__init__()
            self.signal_1 = signal_1

        def emit(self, text, color="black", time=True):
            # 处理缺省参数
            self.signal_1.emit(text, color, time)

    def start_print(self):
        """打印默认输出提示"""
        self.signal_print_to_ui.emit("嗷呜, 欢迎使用FAA-美食大战老鼠自动放卡作战小助手~", time=False)
        self.signal_print_to_ui.emit("当前版本: 1.3.0", time=False)
        self.signal_print_to_ui.emit("", time=False)
        self.signal_print_to_ui.emit("使用安全说明", color="red", time=False)
        self.signal_print_to_ui.emit("[1] 务必有二级密码", time=False)
        self.signal_print_to_ui.emit("[2] 有一定的礼卷防翻牌异常", time=False)
        self.signal_print_to_ui.emit("[3] 高星或珍贵不绑卡挂拍卖/提前转移", time=False)
        self.signal_print_to_ui.emit("", time=False)
        self.signal_print_to_ui.emit("用户请认真阅读[FAA从入门到神殿.pdf], 以解决[闪退][没反应][UI缩放异常]等多数问题", time=False)
        self.signal_print_to_ui.emit("开发者和深入使用, 请参考[README.md]", time=False)
        self.signal_print_to_ui.emit("鼠标悬停在文字或按钮上会显示部分提示信息~", time=False)
        self.signal_print_to_ui.emit("任务或定时器开始运行后, 将以点击运行时的配置进行工作", time=False)
        self.signal_print_to_ui.emit("", time=False)
        self.signal_print_to_ui.emit("[Github] https://github.com/StareAbyss/FoodsVsMiceAutoAssistant", time=False)
        self.signal_print_to_ui.emit("[B站][UP直视深淵][老版宣传视频]https://www.bilibili.com/video/BV1fS421N7zf",
                                     time=False)
        self.signal_print_to_ui.emit("[反馈&交流QQ] 786921130 欢迎加入获取帮助", time=False)
        self.signal_print_to_ui.emit("[开源][免费][绿色] 请为我在 Github点个Star/B站三连评论弹幕支持吧", time=False)

    # 用于展示弹窗信息的方法
    @QtCore.pyqtSlot(str, str)
    def show_dialog(self, title, message):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg.exec_()

    def print_to_ui(self, text, color, time):
        """打印文本到输出框 """
        if time:
            # 在TextBrowser显示提示信息
            self.TextBrowser.append('<span style="color: {};">[{}] {}</span>'.format(
                color,
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text)
            )
        else:
            # 在TextBrowser显示提示信息
            self.TextBrowser.append('<span style="color: {};">{}</span>'.format(
                color,
                text)
            )
        self.TextBrowser.moveCursor(self.TextBrowser.textCursor().End)
        QtWidgets.QApplication.processEvents()  # 实时输出

        # 输出到日志
        CUS_LOGGER.info(text)
