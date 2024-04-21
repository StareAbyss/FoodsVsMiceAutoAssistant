import logging
import sys

# 配置日志记录器
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)  # 设置日志级别

# 创建一个日志文件处理器
file_handler = logging.FileHandler('error.log')
file_handler.setLevel(logging.ERROR)  # 只记录ERROR级别以上的日志

# 创建一个控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # 记录所有级别的日志到控制台

# 创建日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 将处理器添加到日志记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 定义一个函数来捕获未处理的异常，并记录到日志
def handle_exception(exc_type, exc_value, exc_traceback):
    """
    捕获未处理的异常，并将其记录到日志。
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

# 设置sys.excepthook来使用我们的异常处理函数
sys.excepthook = handle_exception

# 示例：生成一个未处理的异常
def main():
    raise ValueError("这是一个测试异常")

if __name__ == "__main__":
    main()
