"""在临时目录实际执行目标版本的布局、迁移和更新脚本，核对跨版本责任边界。"""

import json
import ctypes
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile
import venv

from function.common.distribution_layout import ENVIRONMENT_INSTALLER_EXE, LAUNCHER_EXE
from function.common.update_staging import StagingError
from function.core import update_prepare


ROOT = Path(__file__).resolve().parents[1]
TARGET_MODULES = (
    "function/common/distribution_layout.py",
    "function/common/update_staging.py",
    "function/common/update_state.py",
    "function/common/update_manifest.py",
    "function/common/windows_https.py",
    "function/common/update_space.py",
    "function/core/update_prepare.py",
    "function/core/settings_migration.py",
    "plugins/updater/prepare.py",
    "plugins/updater/updater.py",
)


class TargetUpdateRulesTests(unittest.TestCase):
    """有意令目标规则不同于本地规则，避免新旧规则恰好一致造成误判。"""

    def setUp(self):
        from test.test_distribution_layout import DistributionLayoutTests

        self.directory = tempfile.TemporaryDirectory(prefix="FAA 目标规则更新 ")
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.root = self.base / "FAA 用户目录"
        self.source = self.base / "target-source"
        self.root.mkdir()
        (self.root / "config").mkdir()
        (self.root / "config/settings.json").write_text('{"iteration": 1}', encoding="utf-8")
        (self.root / "config/target_user.json").write_text('{"value": 1}', encoding="utf-8")
        (self.root / ".venv").mkdir()
        (self.root / ".venv/keep.txt").write_bytes(b"existing environment")
        (self.root / ENVIRONMENT_INSTALLER_EXE).write_bytes(b"old installer")
        (self.root / "old-version.txt").write_bytes(b"old version")
        old_updater = self.root / "plugins/updater/updater.py"
        old_updater.parent.mkdir(parents=True)
        old_updater.write_text('raise RuntimeError("old updater must not run")\n', encoding="utf-8")

        DistributionLayoutTests().fixture(self.source)
        for relative in TARGET_MODULES:
            target = self.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        for relative in ("function/__init__.py", "function/common/__init__.py", "function/core/__init__.py"):
            (self.source / relative).write_bytes(b"")
        (self.source / "target-only.txt").write_bytes(b"new version only")
        (self.source / "target_tree").mkdir()
        (self.source / "target_tree/keep.bin").write_bytes(b"mapped payload")
        (self.source / "target_tree/excluded.bin").write_bytes(b"must not be distributed")
        (self.source / "config/excluded_by_target.json").write_bytes(b"must not be distributed")
        layout = self.source / "function/common/distribution_layout.py"
        with layout.open("a", encoding="utf-8") as file:
            file.write('''
PACKAGE_FILES += ("target-only.txt",)
PACKAGE_FOLDERS += (("target_tree", Path("mapped_payload"), {"excluded.bin"}, set(), set()),)
CONFIG_EXCLUDE_FILES.add("excluded_by_target.json")
REQUIRED_DISTRIBUTION_FILES += ("mapped_payload/keep.bin",)
''')
        migration = self.source / "function/core/settings_migration.py"
        # 此处模拟新版新增的真实迁移业务：旧版完全不知道这一份用户文件及其目标位置。
        with migration.open("a", encoding="utf-8") as file:
            file.write('''
_migrate_builtin_data = migrate_user_data
def migrate_user_data(source_root, target_root, selected_names=None, allow_missing_target=True):
    results = _migrate_builtin_data(source_root, target_root, selected_names, allow_missing_target)
    data = json.loads((Path(source_root) / "config/target_user.json").read_text(encoding="utf-8"))
    if data.get("fail"):
        raise ValueError("target migration refused user data")
    destination = Path(target_root) / "config/new_user_format.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({"new_format_value": data["value"]}), encoding="utf-8")
    results.append({"name": "target user data", "status": "migrated"})
    return results
''')
        self.archive = self.base / "source.zip"

    def make_archive(self):
        """生成 GitHub 单根目录样式的 ZIP，更新过程不访问外网。"""
        with zipfile.ZipFile(self.archive, "w") as archive:
            for path in self.source.rglob("*"):
                if path.is_file():
                    archive.write(path, "FAA-target/" + path.relative_to(self.source).as_posix())

    def prepare(self):
        """运行本地旧进程入口，远端比较被隔离，目标准备子进程实际运行。"""
        self.make_archive()
        with patch.object(update_prepare, "validate_update_target", return_value={"allowed": True, "status": "ahead"}):
            result = update_prepare.prepare_update_from_archive(
                self.root, self.archive, {"commit": "b" * 40, "title": "目标规则验证"},
            )
        return Path(result["staging"]["path"]), result

    def execute_updater(self, staging):
        """模拟真正交接到临时目录的目标脚本，默认参数必须不启动 FAA。"""
        script = self.base / "external-updater.py"
        shutil.copy2(staging / "plugins/updater/updater.py", script)
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(script), "update", "--root", str(self.root), "--staging", str(staging),
             "--stdio-isolated"],
            cwd=self.base, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", timeout=35,
        )

    def run_update_parent(self, command, *, locked_stdout=False, expected_phase="update_completed"):
        """真实父进程启动更新并退出，保留虚拟环境跳板与标准流的 Windows 行为。"""
        environment = dict(os.environ)
        temporary = self.base / "process-temp"
        temporary.mkdir(exist_ok=True)
        environment.update(TEMP=str(temporary), TMP=str(temporary))
        log_file = None
        output = subprocess.PIPE
        if locked_stdout:
            import msvcrt

            path = self.root / "logs/launcher_demo/parent-stdout.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateFileW.argtypes = (
                ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
                ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
            )
            kernel.CreateFileW.restype = ctypes.c_void_p
            handle = kernel.CreateFileW(str(path), 0x40000000, 0x1 | 0x2, None, 2, 0x80, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
            log_file = os.fdopen(msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY), "wb", buffering=0)
            output = log_file
        process = subprocess.Popen(
            command, cwd=self.base, env=environment, stdin=subprocess.DEVNULL,
            stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # Popen 已为父 FAA 复制句柄，测试协调进程立即释放自己的原件。
        if log_file:
            log_file.close()
        captured, _ = process.communicate(timeout=50)
        self.assertEqual(process.returncode, 0, (captured or b"").decode("utf-8", errors="replace"))
        handoff = json.loads((self.base / "handoff.json").read_text(encoding="utf-8"))
        if locked_stdout:
            candidates = [path] if path.exists() else list((self.root / "backups").rglob("parent-stdout.log"))
            self.assertTrue(candidates, "父进程的日志原件应仍在版本区或备份内")
            kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
            probe = kernel.CreateFileW(str(candidates[0]), 0x10000, 0x1 | 0x2 | 0x4, None, 3, 0x80, None)
            handoff["stdout_delete_error_after_faa_exit"] = (
                ctypes.get_last_error() if probe == ctypes.c_void_p(-1).value else 0
            )
            if probe != ctypes.c_void_p(-1).value:
                kernel.CloseHandle(probe)
        kernel, user = ctypes.WinDLL("kernel32"), ctypes.WinDLL("user32")
        kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
        kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        callback = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t)
        user.EnumWindows.argtypes = (callback, ctypes.c_ssize_t)
        user.GetWindowThreadProcessId.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))
        user.GetClassNameW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int)
        user.PostMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
        owned = {handoff["pid"]}

        @callback
        def close_own_completion_dialog(window, _):
            pid, name = ctypes.c_ulong(), ctypes.create_unicode_buffer(64)
            user.GetWindowThreadProcessId(window, ctypes.byref(pid))
            user.GetClassNameW(window, name, len(name))
            if pid.value in owned and name.value == "#32770":
                user.PostMessageW(window, 0x10, 0, 0)
            return 1

        deadline, state = time.monotonic() + 45, {}
        while time.monotonic() < deadline:
            for path in (self.root / "update_cache/updater_logs").glob("updater.*.log"):
                pid = path.stem.rsplit(".", 1)[-1]
                if pid.isdecimal():
                    owned.add(int(pid))
            user.EnumWindows(close_own_completion_dialog, 0)
            state_file = self.root / "update_cache/updater_state.json"
            try:
                state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
            except json.JSONDecodeError:
                continue
            if state.get("phase") in {"update_completed", "failed"}:
                break
            time.sleep(0.02)
        # 新入口可能先退出交接进程，再由干净子进程执行；不能只等待最初 Popen 的 PID。
        for pid in owned:
            handle = kernel.OpenProcess(0x100000, False, pid)
            if handle:
                try:
                    for _ in range(750):
                        user.EnumWindows(close_own_completion_dialog, 0)
                        if kernel.WaitForSingleObject(handle, 20) == 0:
                            break
                    else:
                        self.fail(f"本轮更新进程未退出：{pid}")
                finally:
                    kernel.CloseHandle(handle)
        logs = "\n".join(path.read_text(encoding="utf-8") for path in (self.root / "update_cache/updater_logs").glob("*.log"))
        self.assertEqual(state.get("phase"), expected_phase, logs)
        return handoff, logs

    def test_target_layout_and_migration_override_loaded_local_rules(self):
        staging, result = self.prepare()
        self.assertEqual((staging / "target-only.txt").read_bytes(), b"new version only")
        self.assertEqual((staging / "mapped_payload/keep.bin").read_bytes(), b"mapped payload")
        self.assertFalse((staging / "mapped_payload/excluded.bin").exists())
        self.assertFalse((staging / "config/excluded_by_target.json").exists())
        self.assertEqual(
            json.loads((staging / "config/new_user_format.json").read_text(encoding="utf-8")),
            {"new_format_value": 1},
        )
        report = json.loads(Path(result["migration_report"]).read_text(encoding="utf-8"))
        self.assertIn({"name": "target user data", "status": "migrated"}, report["results"])
        self.assertEqual((self.root / "old-version.txt").read_bytes(), b"old version")
        self.assertFalse((self.root / "backups").exists())

    def test_target_validation_failure_does_not_modify_old_installation(self):
        layout = self.source / "function/common/distribution_layout.py"
        with layout.open("a", encoding="utf-8") as file:
            file.write('\nREQUIRED_DISTRIBUTION_FILES += ("target-requires-missing.json",)\n')
        with self.assertRaisesRegex(StagingError, "target-requires-missing"):
            self.prepare()
        self.assertEqual((self.root / "old-version.txt").read_bytes(), b"old version")
        self.assertEqual(json.loads((self.root / "config/settings.json").read_text(encoding="utf-8")), {"iteration": 1})
        self.assertFalse((self.root / "backups").exists())

    def test_apply_uses_final_user_data_and_replaces_installer_without_launching(self):
        staging, _ = self.prepare()
        (self.root / "config/settings.json").write_text('{"iteration": 2}', encoding="utf-8")
        (self.root / "config/target_user.json").write_text('{"value": 2}', encoding="utf-8")
        # 若没有退出后的重新构建，这个预览期间产生的文件会误进入最终安装。
        (staging / "preview-only.txt").write_bytes(b"discard preview")
        result = self.execute_updater(staging)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads((self.root / "config/settings.json").read_text(encoding="utf-8")), {"iteration": 2})
        self.assertEqual(
            json.loads((self.root / "config/new_user_format.json").read_text(encoding="utf-8")),
            {"new_format_value": 2},
        )
        self.assertFalse((self.root / "preview-only.txt").exists())
        self.assertEqual((self.root / ENVIRONMENT_INSTALLER_EXE).read_bytes(), ENVIRONMENT_INSTALLER_EXE.encode("utf-8"))
        self.assertEqual((self.root / LAUNCHER_EXE).read_bytes(), LAUNCHER_EXE.encode("utf-8"))
        self.assertEqual((self.root / ".venv/keep.txt").read_bytes(), b"existing environment")
        backup = next((self.root / "backups").glob("FAA.backup.*"))
        self.assertEqual((backup / ENVIRONMENT_INSTALLER_EXE).read_bytes(), b"old installer")
        self.assertEqual(json.loads((backup / "config/settings.json").read_text(encoding="utf-8")), {"iteration": 2})

    def test_final_migration_failure_keeps_old_version_and_user_changes(self):
        staging, _ = self.prepare()
        (self.root / "config/target_user.json").write_text('{"fail": true}', encoding="utf-8")
        result = self.execute_updater(staging)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("target migration refused user data", result.stdout)
        self.assertEqual((self.root / "old-version.txt").read_bytes(), b"old version")
        self.assertEqual((self.root / ENVIRONMENT_INSTALLER_EXE).read_bytes(), b"old installer")
        self.assertEqual(json.loads((self.root / "config/target_user.json").read_text(encoding="utf-8")), {"fail": True})
        self.assertFalse((self.root / "backups").exists())
        (self.root / "config/target_user.json").write_text('{"value": 3}', encoding="utf-8")
        retry = self.execute_updater(staging)
        self.assertEqual(retry.returncode, 0, retry.stdout)
        self.assertEqual(
            json.loads((self.root / "config/new_user_format.json").read_text(encoding="utf-8")),
            {"new_format_value": 3},
        )

    @unittest.skipUnless(os.name == "nt", "需要真实 Windows 进程与日志句柄")
    def test_handoff_copies_target_updater_and_disables_automatic_launch(self):
        """父 FAA 的拒删标准流不能被更新器自持；真正备份成功后仍有缓存日志。"""
        venv.EnvBuilder(with_pip=False).create(self.root / ".venv")
        with (self.source / "plugins/updater/updater.py").open("a", encoding="utf-8") as file:
            file.write('''
if __name__ == "__main__" and "--stdio-isolated" in sys.argv:
    import ctypes
    kernel = ctypes.WinDLL("kernel32")
    kernel.GetStdHandle.argtypes = (ctypes.c_ulong,)
    kernel.GetStdHandle.restype = ctypes.c_void_p
    kernel.GetFileType.argtypes = (ctypes.c_void_p,)
    root = Path(sys.argv[sys.argv.index("--root") + 1])
    (root / "update_cache/stdio-fixture.json").write_text(json.dumps({
        "console": bool(kernel.GetConsoleWindow()),
        "types": [kernel.GetFileType(kernel.GetStdHandle(value & 0xffffffff)) for value in (-10, -11, -12)],
    }), encoding="utf-8")
''')
        staging, _ = self.prepare()
        expected = (staging / "plugins/updater/updater.py").read_bytes()
        parent = '''
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from function.core.update_apply import launch_update_from_staging
print("FAA parent stdout marker", flush=True)
result = launch_update_from_staging(Path(sys.argv[2]), Path(sys.argv[3]))
result["faa_pid"] = os.getpid()
Path(sys.argv[4]).write_text(json.dumps(result), encoding="utf-8")
'''
        result, logs = self.run_update_parent([
            str(self.root / ".venv/Scripts/pythonw.exe"), "-c", parent,
            str(ROOT), str(self.root), str(staging), str(self.base / "handoff.json"),
        ], locked_stdout=True)
        self.assertEqual(Path(result["updater_script"]).read_bytes(), expected)
        command = result["command"]
        self.assertEqual(command[command.index("--launch") + 1], "")
        self.assertEqual(command[command.index("--wait-pid") + 1], str(result["faa_pid"]))
        backup = next((self.root / "backups").glob("FAA.backup.*"))
        self.assertIn(b"FAA parent stdout marker", (backup / "logs/launcher_demo/parent-stdout.log").read_bytes())
        self.assertIn("update completed", logs)
        self.assertEqual(result["stdout_delete_error_after_faa_exit"], 0)
        self.assertEqual((self.root / "target-only.txt").read_bytes(), b"new version only")
        streams = json.loads((self.root / "update_cache/stdio-fixture.json").read_text(encoding="utf-8"))
        self.assertFalse(streams["console"])
        self.assertEqual(streams["types"], [2, 2, 2], "三个标准流都应指向 NUL 字符设备")

    def test_insufficient_initial_space_prevents_download(self):
        """空间不足应在下载之前中止，不创建暂存包或改写用户数据。"""
        with patch("function.common.update_space.free_space", return_value=0), \
                patch.object(update_prepare, "prepare_staging_from_github") as download, \
                patch.object(update_prepare, "validate_update_target", return_value={"allowed": True, "status": "ahead"}):
            with self.assertRaises(OSError):
                update_prepare.prepare_update_from_github(self.root, {"commit": "c" * 40})
        download.assert_not_called()
        self.assertFalse((self.root / "update_cache/staging").exists())
        self.assertEqual((self.root / "old-version.txt").read_bytes(), b"old version")

    @unittest.skipUnless(os.name == "nt", "需要 Windows 命名互斥锁")
    def test_update_cli_refuses_root_held_by_another_operation(self):
        """真实父进程持锁时，外部 CLI 必须在迁移、备份或替换前中止。"""
        staging, _ = self.prepare()
        spec = importlib.util.spec_from_file_location("mutex_fixture_updater", ROOT / "plugins/updater/updater.py")
        updater = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(updater)
        # 另一轮更新的完成记录仍可能供旧版过渡读取，抢锁失败不能覆盖它。
        state_file = self.root / "update_cache/updater_state.json"
        state_file.write_text(
            json.dumps({"phase": "update_completed", "details": {"backup": "original-backup-sentinel"}}),
            encoding="utf-8",
        )
        original_state = state_file.read_bytes()
        with updater.update_mutex(self.root):
            result = self.execute_updater(staging)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(state_file.read_bytes(), original_state)
        self.assertEqual((self.root / "old-version.txt").read_bytes(), b"old version")
        self.assertEqual((self.root / ENVIRONMENT_INSTALLER_EXE).read_bytes(), b"old installer")
        self.assertFalse((self.root / "backups").exists())


if __name__ == "__main__":
    unittest.main()
