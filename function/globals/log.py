import logging
import sys

import colorlog
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal

from function.globals.get_paths import PATHS


class LogEmitter(QObject):
    """用于跨线程发送日志信号的Qt对象"""
    show_error_signal = pyqtSignal(str, str)  # (标题, 内容)


log_emitter = LogEmitter()


class QMessageBoxHandler(logging.Handler):
    """自定义Handler用于触发PyQt弹窗"""

    def __init__(self):
        super().__init__()
        self.setLevel(logging.ERROR)  # 只处理ERROR及以上级别

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            msg = self.format(record)
            # 通过信号发送到主线程显示弹窗
            log_emitter.show_error_signal.emit("什么！居然报错了？", msg)


class KeywordFilter(logging.Filter):
    """多关键词过滤器"""

    def __init__(self, keywords):
        super().__init__()
        self.keywords = keywords

    def filter(self, record):
        return not any(keyword in record.getMessage() for keyword in self.keywords)


class CusLogger(logging.Logger):
    """自定义logger类"""

    def __init__(self, name):
        super().__init__(name)
        self.setLevel(logging.DEBUG)

        # 初始化Qt弹窗处理器
        qt_handler = QMessageBoxHandler()
        qt_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        self.addHandler(qt_handler)

        # 其他原有处理器配置...
        keywords = ["property", "widget", "push", "layout"]
        keyword_filter = KeywordFilter(keywords)

        # 常规日志文件处理器
        file_handler = logging.FileHandler(
            filename=PATHS["logs"] + '\\running_log.log',
            mode='w',
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        file_handler.addFilter(keyword_filter)
        self.addHandler(file_handler)

        # 错误日志文件处理器
        error_file_handler = logging.FileHandler(
            filename=PATHS["logs"] + '\\error_log.log',
            mode='w',
            encoding='utf-8'
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.addHandler(error_file_handler)

        # 控制台处理器
        stream_handler = colorlog.StreamHandler()
        stream_formatter = colorlog.ColoredFormatter('%(log_color)s%(asctime)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(stream_formatter)
        stream_handler.addFilter(keyword_filter)
        self.addHandler(stream_handler)

        # 异常处理
        sys.excepthook = self.handle_exception

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        self.critical("未捕获的严重异常发生! ", exc_info=(exc_type, exc_value, exc_traceback))


# 初始化Qt应用对象（确保在创建Logger前调用）
app = QApplication.instance() or QApplication(sys.argv)


# 配置弹窗信号回调
def show_error_dialog(title, message):
    QMessageBox.critical(None, title, message)


log_emitter.show_error_signal.connect(show_error_dialog)

# 设置自定义Logger
logging.setLoggerClass(CusLogger)
CUS_LOGGER = logging.getLogger('my customize logger')

if __name__ == '__main__':
    # 测试用例
    CUS_LOGGER.error("这是一个测试错误，应该触发弹窗！")
    sys.exit(app.exec())