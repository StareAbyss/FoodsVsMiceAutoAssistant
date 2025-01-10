import time

from PyQt6.QtCore import QThread

from function.common.process_and_window_manager import start_software_with_args


class ThreadStart360(QThread):

    def __init__(self, game_id, account_id, executable_path, wait_sleep_time):
        super().__init__()
        self.game_id = game_id
        self.account_id = account_id
        self.executable_path = executable_path
        self.wait_sleep_time = wait_sleep_time

    def stop(self):
        self.terminate()
        self.wait()  # 等待线程确实中断 QThread
        self.deleteLater()

    def run(self):
        if self.account_id == 0:
            return
        args = ["-action:opengame", f"-gid:{self.game_id}", f"-gaid:{self.account_id}"]
        start_software_with_args(self.executable_path,  *args)
        time.sleep(self.wait_sleep_time)