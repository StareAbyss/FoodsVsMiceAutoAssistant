import os
import sys
import winreg
from function.globals.get_paths import PATHS
from function.globals.loadings import loading
loading.update_progress(10,"正在加载FAA启动协议...")
# 程序名称
APP_NAME = "FAA-Your Automatic Assistant"
# 启动参数
startup_args = "start_with_task"  # 该参数代表启动后自动开始任务


def get_exe_path(extra_args=None):
    """获取打包后的 exe 文件的绝对路径，如果运行的是 .py 文件，则返回解释器路径."""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 exe
        exe_path = sys.executable
    else:
        # 如果是 .py 脚本，返回 python 解释器路径加上脚本路径
        py_path = PATHS["root"] + "\\function\\faa_main.py"
        exe_path = f'"{sys.executable}" "{py_path}"'

    if extra_args:
        exe_path += f' --{extra_args}'

    return exe_path


def add_to_startup(app_path, app_name):
    """将应用程序添加到 Windows 开机启动项."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
                             0, winreg.KEY_ALL_ACCESS)
        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
        winreg.CloseKey(key)
        print(f"Successfully added '{app_name}' to startup: {app_path}")
        return True
    except Exception as e:
        print(f"Error adding to startup: {e}")
        return False


def remove_from_startup(app_name):
    """从 Windows 开机启动项中删除应用程序."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
                             0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteValue(key, app_name)
        winreg.CloseKey(key)
        print(f"Successfully removed '{app_name}' from startup.")
        return True
    except FileNotFoundError:
        print(f"'{app_name}' not found in startup.")
        return True
    except Exception as e:
        print(f"Error removing from startup: {e}")
        return False


def toggle_startup(state):
    """切换开机启动状态."""
    app_path = get_exe_path(startup_args)  # 默认带自动启动参数
    if state == 2:
        add_to_startup(app_path, APP_NAME)
    else:
        remove_from_startup(APP_NAME)
