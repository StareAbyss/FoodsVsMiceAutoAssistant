import traceback

from PyQt6.QtWidgets import QMessageBox

from function.globals.log import CUS_LOGGER


def error_dialog_and_log(e, message, parent, title="错误"):
    """
    显示错误信息并写入日志
    :param e: 错误对象
    :param message: 输出额外信息
    :param parent: 弹窗父窗口
    :param title: 弹窗标题
    """
    log_message = (
        f"{title}\n"
        f"{message}"
    )
    CUS_LOGGER.error(log_message, exc_info=(type(e), e, e.__traceback__))

    traceback_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
    dialog_message = (
        f"{message}\n"
        f"\n"
        f"完整错误调用栈:\n"
        f"{traceback_details}"
    )
    QMessageBox.critical(parent, title, dialog_message)
