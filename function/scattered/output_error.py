import traceback

from PyQt6.QtWidgets import QMessageBox

from function.globals import SIGNAL
from function.globals.log import CUS_LOGGER

"""
多种样式输出错误
"""


def error_by_merged_dialog(e, extra_message="", title="错误"):
    """
    显示错误信息于: 1.批量信息框体 2.日志
    :param e: 错误对象
    :param extra_message: 输出额外信息
    :param title: 弹窗标题
    """

    log_message = f"{title}\n{extra_message}" if extra_message else f"{title}"
    CUS_LOGGER.error(log_message, exc_info=(type(e), e, e.__traceback__))

    traceback_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
    if extra_message:
        dialog_message = (
            f"{extra_message}\n"
            f"\n"
            f"完整错误调用栈:\n"
            f"{traceback_details}"
        )
    else:
        dialog_message = (
            f"完整错误调用栈:\n"
            f"{traceback_details}"
        )
    SIGNAL.DIALOG.emit(title=title, text=dialog_message)


def error_by_single_dialog(e, parent, extra_message="", title="错误"):
    """
    显示错误信息于: 1.独立信息框体 2.日志 会影响交互, 需要设置父级
    :param e: 错误对象
    :param extra_message: 输出额外信息
    :param parent: 弹窗父窗口
    :param title: 弹窗标题
    """

    log_message = f"{title}\n{extra_message}" if extra_message else f"{title}"
    CUS_LOGGER.error(log_message, exc_info=(type(e), e, e.__traceback__))

    traceback_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
    if extra_message:
        dialog_message = (
            f"{extra_message}\n"
            f"\n"
            f"完整错误调用栈:\n"
            f"{traceback_details}"
        )
    else:
        dialog_message = (
            f"完整错误调用栈:\n"
            f"{traceback_details}"
        )
    QMessageBox.critical(parent, title, dialog_message)
