import ctypes
import os
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from function.globals.get_paths import PATHS


def set_windows_app_user_model_id():
    """在创建 Qt 窗口前设置 Windows 任务栏身份，避免被归到 pythonw.exe。"""
    if sys.platform != "win32":
        return

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "StareAbyss.FAA.FoodsVsMousesAutoAssistant"
        )
    except Exception:
        pass


def set_application_icon(q_app):
    """设置 Qt 默认图标；主窗口显示后还会再写入 Windows 原生窗口图标。"""
    icon_path = os.path.join(PATHS["logo"], "\u5706\u89d2-FetDeathWing-256x-AllSize.ico")
    if os.path.exists(icon_path):
        q_app.setWindowIcon(QIcon(icon_path))


set_windows_app_user_model_id()
app = QApplication(sys.argv)
set_application_icon(app)
from function.core.loading_window import LoadingWindow
loading = LoadingWindow()
