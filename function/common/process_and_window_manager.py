import subprocess
import time

import psutil
import win32con
import win32gui
import win32process

from function.globals.log import CUS_LOGGER


def close_all_software_by_name(software_name: str):
    """
    根据软件名称关闭所有相关进程
    该函数会遍历所有正在运行的进程，如果进程名称与指定的软件名称匹配，则终止该进程并记录关闭操作的日志信息
    如果在关闭过程中遇到进程不存在、访问被拒绝或僵尸进程的情况则记录错误日志
    :param software_name: 要关闭的软件名称
    :return: None
    """

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] == software_name:
                proc.terminate()
                CUS_LOGGER.info(f"[程序开关] 已关闭 {software_name} (PID: {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            CUS_LOGGER.error(f"[程序开关] 关闭 {software_name} 时出错: {e}")
            pass


def close_software_by_title(window_title: str):
    """
    根据窗口标题关闭指定窗口。

    该函数会根据提供的窗口标题查找对应的窗口句柄，并发送关闭消息以关闭窗口。

    :param window_title: 要关闭的窗口标题
    :return: None
    """

    # 根据标题名获取窗口句柄
    hd = win32gui.FindWindow(None, window_title)

    # 根据句柄值关闭窗口
    close_hd = win32gui.SendMessage(hd, win32con.WM_CLOSE)


def start_software_with_args(executable_path, *args):
    try:
        process = subprocess.Popen([executable_path] + list(args))
        CUS_LOGGER.debug(f"已启动 {executable_path} 并传递参数 {args}")
        return process
    except Exception as e:
        CUS_LOGGER.error(f"启动 {executable_path} 时出错: {e}")
        return None


def get_executable_path_by_name(process_name):
    """
    根据进程名获取可执行文件的文件系统路径
    :param process_name: 进程名
    :return: str or None: 如果找到匹配的进程，返回其可执行文件的路径；否则返回 None
    """

    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            if proc.info['name'] == process_name:
                return proc.info['exe']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None


def get_pid_by_name(process_name):
    process_pids = []
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == process_name:
            process_pids.append(proc.info['pid'])
    return process_pids


def get_all_hwnd(hwnd, mouse, login_handle, window_title_list, exe_name):
    if not (win32gui.IsWindow(hwnd) and win32gui.IsWindowEnabled(hwnd) and win32gui.IsWindowVisible(hwnd)):
        return

    nID = win32process.GetWindowThreadProcessId(hwnd)
    # print(nID,win32gui.GetWindowText(hwnd))
    del nID[0]

    for abc in nID:

        try:
            pro = psutil.Process(abc).name()

        except psutil.NoSuchProcess:
            pass

        else:
            # print(abc,win32gui.GetWindowText(hwnd))
            if not pro == exe_name:
                continue
            # CUS_LOGGER.debug(f"进程ID:{abc}, 窗口句柄:{hwnd}, 标题:{win32gui.GetWindowText(hwnd)}")
            login_handle[abc] = hwnd
            if win32gui.GetWindowText(hwnd):
                window_title_list.append(win32gui.GetWindowText(hwnd))


def get_path_and_sub_titles(exe_name: str = "360Game.exe"):
    """
    获取指定可执行文件的路径及其关联窗口的标题
    :param exe_name: 可执行文件的名称
    :return: tuple, 包含可执行文件路径和窗口标题列表的元组 按名称排序
    """

    login_handle = {}  # 进程id: 窗口句柄
    window_title_list = []

    # 获取名为 exe_name 的可执行文件路径
    path = get_executable_path_by_name(exe_name)

    # 枚举所有顶级窗口，并使用 get_all_hwnd 函数处理每个窗口
    win32gui.EnumWindows(lambda hwnd, mouse: get_all_hwnd(hwnd, mouse, login_handle, window_title_list, exe_name), 0)

    # 对 log_int_title 列表进行排序，以便按字母顺序返回窗口标题
    window_title_list.sort()

    CUS_LOGGER.debug(f"[窗口操作] 根据软件名称{exe_name}, 获取其文件系统路径为:{path}, 窗口标题list为:{window_title_list}")
    return path, window_title_list


if __name__ == "__main__":
    def test_get_path_and_sub_titles():
        # # 启动 360Game.exe 并传递参数
        # executable_path = r"E:\360Game5\bin\360Game.exe"
        # args = create_start_args(1)
        # process = start_software_with_args(executable_path, *args)

        path, sub_window_titles = get_path_and_sub_titles(exe_name="360Game.exe")

        print(path, sub_window_titles)


    def test_close():

        # 关闭所有目标窗口
        for window_title in ["锑食-微端", "小号2 | 锑食-微端"]:
            close_software_by_title(window_title=window_title)
            time.sleep(1)

        _, sub_window_titles = get_path_and_sub_titles()

        if len(sub_window_titles) == 1 and sub_window_titles[0] == "360游戏大厅":
            # 只有一个360大厅主窗口, 鲨了它
            close_software_by_title("360游戏大厅")
            # 等待悄悄打开的360后台 准备一网打尽
            time.sleep(2)

        if len(sub_window_titles) == 0:
            # 不再有窗口了, 可以直接根据软件名称把后台杀干净
            close_all_software_by_name("360Game.exe")


    test_close()
