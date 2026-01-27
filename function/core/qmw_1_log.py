import base64
import datetime

import cv2
import numpy
import numpy as np
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication

from function.core.qmw_0_load_ui_file import QMainWindowLoadUI
from function.globals import SIGNAL, EXTRA
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER


class QMainWindowLog(QMainWindowLoadUI):
    signal_dialog = pyqtSignal(str, str)  # 标题, 正文
    signal_print_to_ui = pyqtSignal(str, str, bool)
    signal_image_to_ui = pyqtSignal(numpy.ndarray)

    def __init__(self):
        # 继承父类构造方法
        super().__init__()

        # 链接防呆弹窗
        self.signal_dialog.connect(self.show_dialog)

        # 并不是直接输出, 其emit方法是 一个可以输入 缺省的颜色 或 时间参数 来生成文本 调用 signal_print_to_ui_1
        SIGNAL.PRINT_TO_UI = self.MidSignalPrint(signal_1=self.signal_print_to_ui)

        # 真正的 发送信息激活 print 的函数, 被链接到直接发送信息到ui的函数
        self.signal_print_to_ui.connect(self.print_to_ui)

        # 用于支持 输入 路径 或 numpy.ndarray
        SIGNAL.IMAGE_TO_UI = self.MidSignalImage(signal_1=self.signal_image_to_ui)

        # 真正的 发送图片到ui的函数, 被链接到直接发送图片到ui的函数
        self.signal_image_to_ui.connect(self.image_to_ui)

        # 储存在全局
        SIGNAL.DIALOG = self.signal_dialog

        # 打印默认输出提示
        self.start_print()

    class MidSignalPrint:
        """
        模仿信号的类, 但其实本身完全不是信号, 是为了可以接受缺省参数而模仿的中间类,
        该类的emit方法是 一个可以输入 缺省的颜色 或 时间参数 来生成文本的方法
        并调用信号发送真正的信息
        """

        def __init__(self, signal_1):
            super().__init__()
            self.signal_1 = signal_1
            match EXTRA.THEME:
                case 'light':
                    self.color_scheme = {
                        1: "C80000",  # 深红色
                        2: "E67800",  # 深橙色暗调
                        3: "006400",  # 深绿色
                        4: "009688",  # 深宝石绿
                        5: "0056A6",  # 深海蓝
                        6: "003153",  # 普鲁士蓝
                        7: "5E2D79",  # 深兰花紫
                        8: "4B0082",  # 靛蓝
                        9: "999999",  # 我也不知道啥色
                    }
                case 'dark':
                    self.color_scheme = {
                        1: "FF4C4C",  # 鲜红色
                        2: "FFA500",  # 橙色
                        3: "00FF00",  # 亮绿色
                        4: "20B2AA",  # 浅海绿色
                        5: "1E90FF",  # 道奇蓝
                        6: "4682B4",  # 钢蓝色
                        7: "9370DB",  # 中兰花紫
                        8: "8A2BE2",  # 蓝紫色
                        9: "CCCCCC",  # 浅灰色
                    }

        def emit(self, text, color_level=9, color=None, time=True, is_line=False, line_type="normal"):
            """
            :param text: 正文文本
            :param color_level: int 1 to 9
            :param color: 支持直接使用颜色代码
            :param time: 是否显示打印时间
            :param is_line: 是否替换本行为横线
            :param line_type: str normal/top/bottom
            :return:
            """
            if color_level in self.color_scheme:
                color = self.color_scheme[color_level]
            elif not color:
                color = self.color_scheme[9]
            if is_line:
                text = "—" * 44
                time = False
                if line_type == "top":
                    text = "‾" * 67
                if line_type == "bottom":
                    text = "_" * 59
            # 处理缺省参数
            self.signal_1.emit(text, color, time)

    class MidSignalImage:
        """
        模仿信号的类, 但其实本身完全不是信号, 是为了可以接受缺省参数而模仿的中间类,
        该类的emit方法是 一个可以输入 numpy.ndarray 或 图片路径 并判断是否读取的方法
        并调用信号发送真正的图片
        """

        def __init__(self, signal_1):
            super().__init__()
            self.signal_1 = signal_1

        def emit(self, image):
            # 根据 路径 或者 numpy.ndarray 选择是否读取
            if type(image) is not np.ndarray:
                # 读取目标图像,中文路径兼容方案
                image_ndarray = cv2.imdecode(buf=np.fromfile(file=image, dtype=np.uint8), flags=-1)
            else:
                image_ndarray = image
            # 处理缺省参数
            self.signal_1.emit(image_ndarray)

    @staticmethod
    def start_print():
        """打印默认输出提示"""

        SIGNAL.PRINT_TO_UI.emit(
            text="嗷呜, 欢迎使用FAA-美食大战老鼠自动放卡作战小助手~",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="♦ 使用安全说明 ♦",
            color_level=1,
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="① 务必有二级密码",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="② 有一定的礼卷防翻牌异常",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="③ 贵重不绑卡/大量多余肥料放储藏室",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="④ 鼠标不在游戏内, 不玩有反外挂的游戏",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="♦ 使用疑难解决 ♦",
            color_level=1,
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            "<a href='https://stareabyss.top/FAA-WebSite'>点 &hearts; 我 &hearts; 看 &hearts; 在 &hearts; 线 &hearts; 文 &hearts; 档 &hearts; 和 &hearts; 视 &hearts; 频 &hearts; 教 &hearts; 学</a>",
            color_level=2,
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="新手入门 / 除错 / 深入使用 / 开发者, 都可以在线文档找到相关内容",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="任务或定时器开始运行后, 将锁定点击按钮时的配置文件, 不应用实时更改",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="FAA会向服务器发送战利品掉落Log以做掉落统计, 不传输<任何>其他内容",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="♦ 支持FAA ♦",
            color_level=1,
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="应用程序的开发和维护不仅耗时, 还需投入资金, 但FAA免费开放供大家使用",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="如果使用满意, 并想要表达感激之情或支持后续版本完善",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text=" 那么您的鼓励就是是FAA 持(不)续(跑)开(路)发 的最大动力!",
            color_level=2,
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="您可以选择以下任意一种方式进行捐赠. 赞助时, 可留下您的称呼以供致谢 ~",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="[微信-赞赏码]  下方直接扫码即可. (推荐)",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="[QQ-红包]  加入讨论QQ群后直接发送即可, 以防高仿.",
            time=False)
        SIGNAL.IMAGE_TO_UI.emit(
            image=PATHS["logo"] + "\\赞赏码.png")

        SIGNAL.PRINT_TO_UI.emit(
            text="",
            time=False)

        SIGNAL.PRINT_TO_UI.emit(
            text="♦ Github ♦",
            time=False,
            color_level=1)
        SIGNAL.PRINT_TO_UI.emit(
            text="<a href=https://github.com/StareAbyss/FoodsVsMiceAutoAssistant>点击跳转, 女装乞讨Star ing</a>",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="开源不易, 为我点个Star吧! 发送Issues是最有效的问题反馈渠道",
            time=False)

        SIGNAL.PRINT_TO_UI.emit(
            text="",
            time=False)

        SIGNAL.PRINT_TO_UI.emit(
            text="♦ Bilibili ♦",
            color_level=1,
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="<a href=https://www.bilibili.com/video/BV1owUFYHEPq>点击跳转, 查看劲爆宣传物料(不)</a>",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="UP主 - 直视深淵, 非全职非专一美食~ 但关注支持一下总是不亏的",
            time=False)

        SIGNAL.PRINT_TO_UI.emit(
            text="",
            time=False)

        SIGNAL.PRINT_TO_UI.emit(
            text="♦ QQ群组 ♦",
            color_level=1,
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="1群: 786921130  2群: 142272678",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="交流游戏和自动化, 获取帮助, 资源分享, 参与开发",
            time=False)

        SIGNAL.PRINT_TO_UI.emit(
            text="",
            time=False)

        SIGNAL.PRINT_TO_UI.emit(
            text="♦ 腾讯频道 ♦",
            color_level=1,
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="https://pd.qq.com/s/a0h4rujt0 ",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="人少维护较差, 但用来获取更新资源很方便, 不易被打扰",
            time=False)

        SIGNAL.PRINT_TO_UI.emit(
            text="",
            time=False)

        SIGNAL.PRINT_TO_UI.emit(
            text="♦ 美食数据站 ♦",
            color_level=1,
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="<a href=https://msdzls.cn>点击跳转, 进入米苏物流</a>",
            time=False)
        SIGNAL.PRINT_TO_UI.emit(
            text="FAA X 米苏物流  数据统计就挂靠在这呢~ By 夏夜浅酌",
            time=False)

    # 用于展示弹窗信息的方法
    @QtCore.pyqtSlot(str, str)
    def show_dialog(self, title, message):
        # 创建/获取对话框实例
        if not hasattr(self, 'log_dialog') or not self.log_dialog:
            self.log_dialog = QtWidgets.QDialog()
            self.log_dialog.setWindowTitle("问题通知")
            self.log_dialog.resize(800, 400)

            # 创建带滚动条的文本框
            self.text_browser = QtWidgets.QTextBrowser(self.log_dialog)
            layout = QtWidgets.QVBoxLayout(self.log_dialog)
            layout.addWidget(self.text_browser)

            # 添加关闭按钮
            btn_close = QtWidgets.QPushButton("关闭", self.log_dialog)
            btn_close.clicked.connect(self.cleanup_dialog)  # 修改连接方法

            layout.addWidget(btn_close)

            # 绑定关闭事件
            self.log_dialog.finished.connect(self.cleanup_dialog)

        # 格式化日志内容
        log_content = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {title}: {message}\n"

        # 追加内容并自动滚动
        self.text_browser.append(log_content)
        self.text_browser.verticalScrollBar().setValue(
            self.text_browser.verticalScrollBar().maximum()
        )

        # 显示对话框
        if not self.log_dialog.isVisible():
            self.log_dialog.show()

    def cleanup_dialog(self):
        """清理对话框资源"""
        if self.log_dialog:
            self.text_browser.clear()  # 清空内容
            self.log_dialog.deleteLater()
            self.log_dialog = None

    def print_to_ui(self, text, color, time):
        """打印文本到输出框 """

        # 时间文本
        text_time = "[{}] ".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) if time else ""

        # 颜色文本
        text_all = f'<span style="color:#{color};">{text_time}{text}</span>'

        # 输出到输出框
        self.TextBrowser.append(text_all)

        # 自动滚动到最新消息
        self.TextBrowser.verticalScrollBar().setValue(
            self.TextBrowser.verticalScrollBar().maximum()
        )

        # 输出到日志和运行框
        CUS_LOGGER.info(text)

    def image_to_ui(self, image_ndarray: numpy.ndarray):
        """
        :param image_ndarray: 必须是 numpy.ndarray 对象
        :return:
        """

        # 編碼字節流
        _, img_encoded = cv2.imencode('.png', image_ndarray)

        # base64
        img_base64 = base64.b64encode(img_encoded).decode('utf-8')

        image_html = f"<img src='data:image/png;base64,{img_base64}'>"

        # self.TextBrowser.insertHtml(image_html)

        # 输出到输出框
        self.TextBrowser.append(image_html)

        # 实时输出
        cursor = self.TextBrowser.textCursor()
        cursor.setPosition(cursor.position(), QTextCursor.MoveMode.MoveAnchor)
        cursor.setPosition(cursor.position() + 1, QTextCursor.MoveMode.KeepAnchor)  # 移动到末尾
        self.TextBrowser.setTextCursor(cursor)
        QApplication.processEvents()
