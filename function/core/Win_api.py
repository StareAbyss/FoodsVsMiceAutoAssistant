import subprocess
import psutil
import pygetwindow as gw
import win32gui
import win32process

loginHandle={}
logintitle=[]

def close_all_software(software_name):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] == software_name:
                proc.terminate()
                print(f"已关闭 {software_name} (PID: {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def close_software_by_title(window_title):
    try:
        window = gw.getWindowsWithTitle(window_title)[0]
        window.close()
        print(f"已关闭标题为 {window_title} 的窗口")
        if window_title=="360游戏大厅":
            close_all_software("360Game.exe")#说明没有进程了，可以把后台全杀掉了
    except IndexError:
        print(f"未找到标题为 {window_title} 的窗口")



def start_software_with_args(executable_path, *args):
    try:
        process = subprocess.Popen([executable_path] + list(args))
        print(f"已启动 {executable_path} 并传递参数 {args}")
        return process
    except Exception as e:
        print(f"启动 {executable_path} 时出错: {e}")
        return None
def create_start_args(account_id,game_id=1):
    return ["-action:opengame", f"-gid:{game_id}", f"-gaid:{account_id}"]

def get_executable_path_by_name(process_name):
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            if proc.info['name'] == process_name:
                return proc.info['exe']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None
def get_pid_by_name(process_name):
    process_pids=[]
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == process_name:
            process_pids.append(proc.info['pid'])
    return process_pids



def get_all_hwnd(hwnd,mouse):
  if win32gui.IsWindow(hwnd) and win32gui.IsWindowEnabled(hwnd) and win32gui.IsWindowVisible(hwnd):
    nID=win32process.GetWindowThreadProcessId(hwnd)
    #print(nID,win32gui.GetWindowText(hwnd))
    del nID[0]
    for abc in nID:
      try:
        pro=psutil.Process(abc).name()
      except psutil.NoSuchProcess:
        pass
      else:
        #print(abc,win32gui.GetWindowText(hwnd))
        if pro == "360Game.exe":
          print("进程ID：",abc,"窗口句柄: ",hwnd,"标题: ",win32gui.GetWindowText(hwnd))
          loginHandle[abc]=hwnd
          if win32gui.GetWindowText(hwnd):
            logintitle.append(win32gui.GetWindowText(hwnd))


def get_path_and_title():
    path=get_executable_path_by_name("360Game.exe")
    logintitle.clear()
    win32gui.EnumWindows(get_all_hwnd, 0)
    logintitle.sort()
    # print(path, logintitle)
    return path,logintitle

#
# if __name__ == "__main__":
    # # 启动 360Game.exe 并传递参数
    # executable_path = r"E:\360Game5\bin\360Game.exe"
    # args = create_start_args(1)
    # process=start_software_with_args(executable_path, *args)
    #
    # get_path_and_title()

    # process_pids=get_pid_by_name(process_name)
    # win32gui.EnumWindows(get_all_hwnd, 0)
    # logintitle.sort()
    # print(logintitle)

#
# if __name__ == "__main__":
#     window_title = "丑食"  # 替换为你要关闭的软件的窗口标题
#     window_title2 = "360游戏大厅"  # 替换为你要关闭的软件的窗口标题
#     close_software_by_title(window_title)
#     sleep(1)
#     close_software_by_title(window_title2)
#
