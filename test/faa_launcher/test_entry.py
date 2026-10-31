"""使用隔离环境验证 FAA - 快速启动.exe 自动打开环境安装器，不进行真实安装。"""

import os
import ctypes
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from test.faa_launcher import test_startup as startup


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = "FAA - 环境安装器.exe"
STUB = r'''
using System;
using System.IO;
class Fixture {
    static int Main(string[] args) {
        string root = Environment.GetEnvironmentVariable("FAA_ENTRY_FIXTURE_ROOT");
        string executable = System.Diagnostics.Process.GetCurrentProcess().MainModule.FileName;
        if (Path.GetFileName(executable) == "uv.exe") {
            File.AppendAllText(Path.Combine(root, "uv-calls.txt"), string.Join(" ", args) + "\n");
            return File.Exists(Path.Combine(root, "fail-uv")) ? 7 : 0;
        }
        File.AppendAllText(Path.Combine(root, "installer-calls.txt"), "opened\n");
        File.WriteAllText(Path.Combine(root, "installer-pid.txt"), System.Diagnostics.Process.GetCurrentProcess().Id.ToString());
        File.WriteAllLines(Path.Combine(root, "installer-args.txt"), args);
        return 0;
    }
}
'''


@unittest.skipUnless(os.name == "nt" and (ROOT / "FAA - 快速启动.exe").exists(), "需要构建原生 FAA - 快速启动.exe")
class EntryFallbackTests(unittest.TestCase):
    """复用屏幕外窗口夹具，验证准备失败和启动失败的真实进程交接。"""

    @classmethod
    def setUpClass(cls):
        cls.stub_directory = tempfile.TemporaryDirectory(prefix="FAA 启动入口夹具 ")
        folder = Path(cls.stub_directory.name)
        source = folder / "fixture.cs"
        source.write_text(STUB, encoding="utf-8-sig")
        cls.stub = folder / "fixture.exe"
        compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        subprocess.run([str(compiler), "/nologo", "/target:winexe", f"/out:{cls.stub}", str(source)], check=True, timeout=30, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.stub_directory.cleanup()

    def setUp(self):
        startup.StartupLifecycleTests.setUp(self)
        shutil.copy2(ROOT / "FAA - 快速启动.exe", self.root / "FAA - 快速启动.exe")
        shutil.copy2(self.stub, self.root / INSTALLER)
        uv = self.root / "plugins/launcher_scripts/bin/uv.exe"
        uv.parent.mkdir(parents=True)
        shutil.copy2(self.stub, uv)
        for name in ("LICENSE", "uv.lock"):
            (self.root / name).write_text("fixture", encoding="utf-8")
        (self.root / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="0.0.0"\n', encoding="utf-8")

    def tearDown(self):
        startup.StartupLifecycleTests.tearDown(self)

    def run_entry(self, mode="main", expected=0):
        """执行产品启动入口，夹具 uv 和安装器仅记录调用。"""
        environment = dict(os.environ, FAA_ENTRY_FIXTURE_ROOT=str(self.root), FAA_STARTUP_FIXTURE_MODE=mode)
        result = subprocess.run([str(self.root / "FAA - 快速启动.exe")], env=environment, timeout=15)
        self.assertEqual(result.returncode, expected)
        if expected:
            deadline = time.monotonic() + 5
            while not (self.root / "installer-args.txt").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((self.root / "installer-args.txt").exists())
            pid = int((self.root / "installer-pid.txt").read_text())
            kernel = ctypes.WinDLL("kernel32")
            kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
            kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
            process = kernel.OpenProcess(0x100000, False, pid)
            if process:
                try:
                    self.assertEqual(kernel.WaitForSingleObject(process, 5000), 0)
                finally:
                    kernel.CloseHandle(process)
            self.assertEqual((self.root / "installer-calls.txt").read_text(encoding="utf-8-sig").splitlines(), ["opened"])
        self.assertFalse((self.root / "uv-calls.txt").exists(), "快速启动不能执行 uv 或安装环境")

    def test_success_keeps_faa_and_does_not_open_installer(self):
        self.run_entry()
        startup.StartupLifecycleTests.assert_fixture_still_running(self)
        self.assertFalse((self.root / "installer-calls.txt").exists())

    def test_missing_python_opens_installer_without_installing(self):
        (self.root / ".venv/Scripts/pythonw.exe").unlink()
        self.run_entry(expected=1)
        arguments = (self.root / "installer-args.txt").read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual(arguments[0], "--startup-error")
        report = Path(arguments[1]).read_text(encoding="utf-8")
        self.assertTrue(report.startswith("FAA_STARTUP_FAILURE_V1\n5\n"))
        self.assertIn("没有找到 Python 启动程序", report)
        self.assertFalse(list(self.root.glob("fixture-*.json")))

    def test_missing_installer_shows_explicit_message(self):
        """仅关闭本测试进程的错误对话框，核对缺失提示而不操作其他窗口。"""
        (self.root / INSTALLER).unlink()
        (self.root / ".venv/Scripts/pythonw.exe").unlink()
        user = ctypes.WinDLL("user32")
        callback = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t)
        user.EnumWindows.argtypes = (callback, ctypes.c_ssize_t)
        user.EnumChildWindows.argtypes = (ctypes.c_void_p, callback, ctypes.c_ssize_t)
        user.GetWindowThreadProcessId.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))
        user.GetClassNameW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int)
        user.GetWindowTextW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int)
        user.PostMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
        process = subprocess.Popen([str(self.root / "FAA - 快速启动.exe")])
        dialogs, text = [], []

        @callback
        def child(window, _):
            value = ctypes.create_unicode_buffer(4096)
            user.GetWindowTextW(window, value, len(value))
            text.append(value.value)
            return 1

        @callback
        def find(window, _):
            pid = ctypes.c_ulong()
            user.GetWindowThreadProcessId(window, ctypes.byref(pid))
            value = ctypes.create_unicode_buffer(64)
            user.GetClassNameW(window, value, len(value))
            if pid.value == process.pid and value.value == "#32770":
                dialogs.append(window)
                user.EnumChildWindows(window, child, 0)
                return 0
            return 1

        try:
            deadline = time.monotonic() + 5
            # Windows 可能先创建对话框和按钮，再填充正文；窗口出现还不足以开始校验提示内容。
            while time.monotonic() < deadline:
                dialogs.clear()
                text.clear()
                user.EnumWindows(find, 0)
                if dialogs and "未找到环境安装器" in "\n".join(text):
                    break
                time.sleep(0.02)
            self.assertTrue(dialogs)
            self.assertIn("未找到环境安装器", "\n".join(text))
            self.assertIn(INSTALLER, "\n".join(text))
            user.PostMessageW(dialogs[0], 0x10, 0, 0)
            self.assertEqual(process.wait(timeout=10), 1)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    def test_early_exit_opens_installer_with_startup_log(self):
        self.run_entry(mode="splash", expected=1)
        report = next((self.root / "update_cache/launcher/logs").glob("startup-failure-*.txt"))
        self.assertIn("FAA 尚未成功打开", report.read_text(encoding="utf-8"))

    def test_invalid_root_still_opens_installer(self):
        (self.root / "LICENSE").unlink()
        self.run_entry(expected=1)
        self.assertEqual((self.root / "installer-args.txt").read_text(encoding="utf-8-sig"), "")

    def test_exit_after_ready_does_not_trigger_startup_repair(self):
        source = self.root / "function/faa_main.py"
        text = source.read_text(encoding="utf-8")
        text = text.replace('if mode == "splash":', 'if mode == "main":\n    import threading\n    timer = threading.Timer(1.5, lambda: os._exit(9))\n    timer.daemon = True\n    timer.start()\nif mode == "splash":')
        source.write_text(text, encoding="utf-8")
        self.run_entry()
        time.sleep(2)
        self.assertFalse((self.root / "installer-calls.txt").exists())

    def test_legacy_handoff_uses_cached_native_ui_and_does_not_loop(self):
        """真实入口自动交接到缓存进程；完成后等待用户安装，完成记录和源码目录不再次过渡。"""
        bridge = self.root / "plugins/updater/legacy_bridge.py"
        bridge.parent.mkdir(parents=True)
        bridge.write_text('''
import argparse
import ctypes
import json
import os
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
root = parser.parse_args().root
calls = root / "native-bridge-calls.json"
entries = json.loads(calls.read_text(encoding="utf-8")) if calls.exists() else []
entries.append({"root": str(root), "pid": os.getpid(), "console": bool(ctypes.windll.kernel32.GetConsoleWindow())})
calls.write_text(json.dumps(entries), encoding="utf-8")
print("FAA_LEGACY_PHASE:0:checking fixture", flush=True)
(root / "update_cache/update_state.json").write_text(json.dumps({"update_protocol": 1}), encoding="utf-8")
print("FAA_LEGACY_PHASE:5:fixture completed", flush=True)
''', encoding="utf-8")
        calls = self.root / "native-bridge-calls.json"
        cache = self.root / "update_cache/legacy_bridge"
        cache.mkdir(parents=True)
        user, kernel = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")
        callback = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t)
        user.EnumWindows.argtypes = (callback, ctypes.c_ssize_t)
        user.GetWindowThreadProcessId.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))
        user.PostMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
        user.SetWindowPos.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint)
        kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.QueryFullProcessImageNameW.argtypes = (ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong))
        kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
        kernel.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        kernel.CloseHandle.argtypes = (ctypes.c_void_p,)

        for index, name in enumerate(("FAA.exe", "FAA - 快速启动.exe"), start=1):
            with self.subTest(entry=name):
                shutil.copy2(ROOT / "FAA - 快速启动.exe", self.root / name)
                (self.root / "update_cache/update_state.json").write_text('{"commit": "legacy"}', encoding="utf-8")
                (self.root / "update_cache/updater_state.json").write_text('{"phase": "update_completed"}', encoding="utf-8")
                for previous_log in cache.glob("launcher-*.log"):
                    previous_log.unlink()
                entry = subprocess.Popen([str(self.root / name)])
                expected_image = cache / f"entry-{entry.pid}.exe"
                found = []

                @callback
                def find(window, _):
                    pid = ctypes.c_ulong()
                    user.GetWindowThreadProcessId(window, ctypes.byref(pid))
                    handle = kernel.OpenProcess(0x1000, False, pid.value)
                    if handle:
                        try:
                            image_path, size = ctypes.create_unicode_buffer(32768), ctypes.c_ulong(32768)
                            if kernel.QueryFullProcessImageNameW(handle, 0, image_path, ctypes.byref(size)):
                                if Path(image_path.value).resolve() == expected_image.resolve():
                                    found[:] = [(window, pid.value)]
                                    return 0
                        finally:
                            kernel.CloseHandle(handle)
                    return 1

                handle = None
                try:
                    self.assertEqual(entry.wait(timeout=10), 0)
                    deadline = time.monotonic() + 10
                    logs = ""
                    while time.monotonic() < deadline:
                        user.EnumWindows(find, 0)
                        if found:
                            # 夹具窗口移到屏幕外，不占用用户当前工作区域。
                            user.SetWindowPos(found[0][0], None, -30000, -30000, 0, 0, 0x15)
                        logs = "\n".join(path.read_text(encoding="utf-8") for path in cache.glob("launcher-*.log"))
                        if found and "[更新] 请自行运行 FAA - 环境安装器.exe" in logs:
                            break
                        time.sleep(0.02)
                    self.assertTrue(found, "应由根目录入口派生缓存内的原生进度窗口")
                    self.assertIn("[更新] 请自行运行 FAA - 环境安装器.exe", logs)
                    handle = kernel.OpenProcess(0x100001, False, found[0][1])
                    self.assertTrue(handle)
                    self.assertEqual(kernel.WaitForSingleObject(handle, 0), 258, "完成页应保留供用户阅读")
                    entries = json.loads(calls.read_text(encoding="utf-8"))
                    self.assertEqual(len(entries), index)
                    self.assertEqual(Path(entries[-1]["root"]), self.root)
                    self.assertFalse(entries[-1]["console"], "过渡脚本不能打开额外控制台")
                    self.assertFalse(list(self.root.glob("fixture-*.json")), "更新完成不自动启动 FAA")
                    self.assertFalse((self.root / "installer-calls.txt").exists())
                    self.assertFalse((self.root / "uv-calls.txt").exists())
                finally:
                    user.EnumWindows(find, 0)
                    if found:
                        if handle is None:
                            handle = kernel.OpenProcess(0x100001, False, found[0][1])
                        user.PostMessageW(found[0][0], 0x10, 0, 0)
                        if handle and kernel.WaitForSingleObject(handle, 3000) != 0:
                            kernel.TerminateProcess(handle, 1)
                            kernel.WaitForSingleObject(handle, 3000)
                    if handle:
                        kernel.CloseHandle(handle)
                    if entry.poll() is None:
                        entry.kill()
                        entry.wait(timeout=5)

        # 即使仍有上一轮 completed 记录，完成协议标识也应让快速入口正常启动 FAA。
        self.run_entry()
        self.assertEqual(len(json.loads(calls.read_text(encoding="utf-8"))), 2)

        self.assertTrue(list(self.root.glob("fixture-*.json")))
        # 源码目录不应根据本地调试遗留的更新记录运行用户过渡流程。
        (self.root / ".git").mkdir()
        (self.root / "update_cache/update_state.json").write_text('{"commit": "legacy"}', encoding="utf-8")
        self.run_entry()
        self.assertEqual(len(json.loads(calls.read_text(encoding="utf-8"))), 2)

        # 由真实隐藏子进程上报下载失败，核对原生事件最终落在网络错误页的对应步骤。
        (self.root / ".git").rmdir()
        bridge.write_text('''
print("FAA_LEGACY_PHASE:1:正在连接 GitHub", flush=True)
print("FAA_LEGACY_NETWORK_ERROR:GitHub HTTPS 证书校验失败，原始备份和过渡记录已保留。", flush=True)
raise SystemExit(1)
''', encoding="utf-8")
        report = startup.StartupLifecycleTests.run_launcher(self, operation="legacy")
        self.assertEqual(report["failed"], "1")
        self.assertEqual(report["window_open"], "1")
        self.assertEqual(report["stage"], "1")
        self.assertEqual(report["network"], "1")
        self.assertEqual(report["network_visible"], "0", "GitHub 失败不能引导用户修改 Python 镜像")
        self.assertIn("GitHub", report["title"])
        self.assertIn("证书", report["detail"])


if __name__ == "__main__":
    unittest.main()
