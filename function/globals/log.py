import logging
import sys

import colorlog

from function.globals.get_paths import PATHS


# DEBUG -> INFO -> WARNING -> ERROR -> CRITICAL
# 创建自定义logger类

class CusLogger(logging.Logger):
    def __init__(self, name):
        super().__init__(name)  # 调用父类的构造函数，并传递name参数

        # 阻止日志消息向上传递到更高级别的日志记录器，避免PyQt的日志消息出现在我的logger
        self.propagate = False

        # 设置日志记录的最低级别
        self.setLevel(logging.DEBUG)

        # 保存路径 log文件会自动创建
        log_path = PATHS["logs"] + '\\running_log.log'

        # 输出到文件
        file_handler = logging.FileHandler(filename=log_path, mode='w', encoding='utf-8')  # 创建一个FileHandler来写日志到文件
        file_handler.setLevel(logging.DEBUG)  # 设置FileHandler的最低日志级别
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')  # 创建一个formatter来定义日志的格式
        file_handler.setFormatter(formatter)  # 应用formatter
        self.addHandler(file_handler)  # 添加到logger

        # 输出到运行框 标准输出流
        stream_handler = colorlog.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(levelname)s - %(message)s')  # 创建一个formatter来定义日志的格式
        stream_handler.setFormatter(formatter)  # 应用formatter
        self.addHandler(stream_handler)

        # 设置sys.excepthook 使用自定义的异常处理函数 取代默认输出
        # sys.excepthook = self.handle_exception

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """
        捕获未处理的异常，并将其记录到日志。
        """
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        # 只将异常信息记录到日志
        self.error("未捕获的异常: ", exc_info=(exc_type, exc_value, exc_traceback))
        # 保留默认的异常打印行为，以便在PyCharm中可以点击跳转
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


logging.setLoggerClass(CusLogger)
CUS_LOGGER = logging.getLogger('my cus logger')  # 使用自定义的Logger类

if __name__ == '__main__':
    # 配置自定义logger
    logging.setLoggerClass(CusLogger)
    logger = logging.getLogger('custom')  # 使用自定义的Logger类
    # 记录一些日志消息
    logger.debug('这是一个debug级别的消息，会被写入文件')
    logger.info('这是一个info级别的消息，会被写入文件')
    logger.warning('这是一个warning级别的消息，会被写入文件')
