"""用独立的原生窗口夹具验证启动识别、自动退出和子进程保留。"""

import ctypes
import json
import os
import subprocess
import tempfile
import time
import unittest
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE = ROOT / "FAA - 环境安装器.exe"
FIXTURE = r'''
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path

user = ctypes.WinDLL("user32", use_last_error=True)
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
callback = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user.DefWindowProcW.restype = ctypes.c_ssize_t
user.CreateWindowExW.argtypes = (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p)
user.CreateWindowExW.restype = wintypes.HWND
user.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
kernel.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel.GetModuleHandleW.restype = wintypes.HMODULE

@callback
def procedure(window, message, wparam, lparam):
    if message == 2:
        user.PostQuitMessage(0)
        return 0
    return user.DefWindowProcW(window, message, wparam, lparam)

class WindowClass(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("procedure", callback), ("class_extra", ctypes.c_int),
        ("window_extra", ctypes.c_int), ("instance", wintypes.HINSTANCE), ("icon", wintypes.HICON),
        ("cursor", wintypes.HANDLE), ("background", wintypes.HBRUSH), ("menu", wintypes.LPCWSTR), ("name", wintypes.LPCWSTR)]

instance = kernel.GetModuleHandleW(None)
window_class = WindowClass()
window_class.procedure = procedure
window_class.instance = instance
window_class.name = f"FAA.Startup.Fixture.{os.getpid()}"
user.RegisterClassW(ctypes.byref(window_class))
mode = os.environ.get("FAA_STARTUP_FIXTURE_MODE", "main")
titles = ["FAA - 启动验证夹具"] if mode == "main" else ["FAA 正在加载"] if mode == "splash" else ["FAA - 启动验证夹具", "FAA 启动失败"]
# 先记录进程再显示窗口，避免启动器已判定就绪但测试尚无记录可核对或清理。
windows = [user.CreateWindowExW(0, window_class.name, title, 0x00CF0000, -30000, -30000, 240, 120, None, None, instance, None) for title in titles]
Path(f"fixture-{os.getpid()}.json").write_text(json.dumps({"pid": os.getpid(), "windows": windows}), encoding="utf-8")
# 错误夹具先显示错误窗口，避免主窗口先出现的瞬间被当成成功；窗口仍在屏幕外。
for window in reversed(windows):
    user.ShowWindow(window, 5)
if mode == "splash":
    import time
    time.sleep(0.5)
else:
    message = wintypes.MSG()
    while user.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
        user.TranslateMessage(ctypes.byref(message))
        user.DispatchMessageW(ctypes.byref(message))
'''


@unittest.skipUnless(EXECUTABLE.is_file(), "请先构建 FAA - 环境安装器.exe")
class StartupLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="FAA 启动退出 中文 ")
        self.root = Path(self.directory.name).resolve()
        venv.EnvBuilder(with_pip=False).create(self.root / ".venv")
        (self.root / ".faa-launcher-startup-test").touch()
        (self.root / "function").mkdir()
        (self.root / "function" / "faa_main.py").write_text(FIXTURE, encoding="utf-8")
        self.external = None

    def tearDown(self):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
        kernel.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        user = ctypes.WinDLL("user32")
        user.PostMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
        for path in self.root.glob("fixture-*.json"):
            entry = json.loads(path.read_text(encoding="utf-8"))
            process = kernel.OpenProcess(0x100001, False, entry["pid"])
            if not process:
                continue
            try:
                for window in entry["windows"]:
                    user.PostMessageW(window, 0x10, 0, 0)
                if kernel.WaitForSingleObject(process, 2000) != 0:
                    kernel.TerminateProcess(process, 1)
                    kernel.WaitForSingleObject(process, 2000)
            finally:
                kernel.CloseHandle(process)
        if self.external:
            self.external.wait(timeout=5)
        # 虚拟环境的启动跳板可能稍晚才释放 pythonw.exe，等文件句柄释放后再删除临时目录。
        deadline = time.monotonic() + 2
        while True:
            try:
                self.directory.cleanup()
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)

    def run_launcher(self, mode="normal", fixture="main", operation="install"):
        environment = dict(os.environ, FAA_STARTUP_FIXTURE_MODE=fixture)
        report = self.root / "启动检查.txt"
        result = subprocess.run(
            [str(EXECUTABLE), "--startup-self-test", str(self.root), str(report), mode, operation],
            env=environment, timeout=15, check=False,
        )
        self.assertEqual(result.returncode, 0)
        return dict(line.split("=", 1) for line in report.read_text(encoding="utf-8").splitlines())

    def assert_fixture_still_running(self):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
        kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        entries = list(self.root.glob("fixture-*.json"))
        self.assertTrue(entries)
        entry = json.loads(entries[-1].read_text(encoding="utf-8"))
        process = kernel.OpenProcess(0x100000, False, entry["pid"])
        self.assertTrue(process)
        try:
            self.assertEqual(kernel.WaitForSingleObject(process, 0), 258, "启动器退出不应结束已就绪的 FAA")
        finally:
            kernel.CloseHandle(process)

    def test_normal_start_closes_launcher_and_preserves_faa(self):
        self.assertEqual(self.run_launcher(), {"launch_success": "1", "window_open": "0", "monitoring": "0", "failed": "0"})
        self.assert_fixture_still_running()

    def test_debug_start_keeps_log_window_and_preserves_faa(self):
        report = self.run_launcher(mode="debug")
        self.assertEqual((report["launch_success"], report["window_open"], report["monitoring"]), ("1", "1", "1"))
        self.assert_fixture_still_running()

    def test_error_window_prevents_autoclose_even_if_main_is_visible(self):
        report = self.run_launcher(fixture="error")
        self.assertEqual((report["launch_success"], report["window_open"], report["failed"]), ("0", "1", "1"))

    def test_another_faa_window_does_not_count_as_this_launch(self):
        self.external = subprocess.Popen(
            [str(self.root / ".venv" / "Scripts" / "python.exe"), "-m", "function.faa_main"], cwd=self.root,
            env=dict(os.environ, FAA_STARTUP_FIXTURE_MODE="main"), creationflags=subprocess.CREATE_NO_WINDOW,
        )
        deadline = time.monotonic() + 5
        while not list(self.root.glob("fixture-*.json")) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(list(self.root.glob("fixture-*.json")))
        report = self.run_launcher(fixture="splash")
        self.assertEqual((report["launch_success"], report["window_open"]), ("0", "1"))


if __name__ == "__main__":
    unittest.main()
