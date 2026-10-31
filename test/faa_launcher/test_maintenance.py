"""在隔离目录中验证图形恢复入口的文件保留和回滚。"""

import contextlib
import ctypes
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from function.common.update_space import version_area_size


ROOT = Path(__file__).resolve().parents[2]
UPDATER = ROOT / "plugins" / "updater" / "updater.py"
SPEC = importlib.util.spec_from_file_location("native_launcher_updater", UPDATER)
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)


class GuiRestoreTests(unittest.TestCase):
    def test_update_preserves_environment_and_replaces_installer(self):
        """普通更新部署目标安装器，运行环境保留，旧安装器可从备份恢复。"""
        with tempfile.TemporaryDirectory(prefix="FAA 更新保留备份工具 ") as directory:
            root = Path(directory) / "FAA"
            staging = root / "update_cache/staging/FAA.update.new"
            staging.mkdir(parents=True)
            (root / "app.txt").write_text("current", encoding="utf-8")
            (root / "extra-entry.exe").write_bytes(b"unlisted executable")
            (staging / "app.txt").write_text("new", encoding="utf-8")
            (root / "FAA - 环境安装器.exe").write_bytes(b"backup tool")
            (staging / "FAA - 环境安装器.exe").write_bytes(b"staging copy")
            (root / ".venv").mkdir()
            self.assertEqual(version_area_size(root), len(b"current") + len(b"unlisted executable") + len(b"backup tool"))
            with contextlib.redirect_stdout(io.StringIO()):
                updater.update(root, staging, None)
            self.assertEqual((root / "app.txt").read_text(encoding="utf-8"), "new")
            self.assertEqual((root / "FAA - 环境安装器.exe").read_bytes(), b"staging copy")
            self.assertTrue((root / ".venv").is_dir())
            backup = next((root / "backups").glob("FAA.backup.*"))
            self.assertEqual((backup / "app.txt").read_text(encoding="utf-8"), "current")
            self.assertEqual((backup / "extra-entry.exe").read_bytes(), b"unlisted executable")
            self.assertFalse((root / "extra-entry.exe").exists())
            self.assertEqual((backup / "FAA - 环境安装器.exe").read_bytes(), b"backup tool")

    def test_update_adds_missing_environment_installer(self):
        """目标目录缺少环境安装器时，必须从暂存包补入。"""
        with tempfile.TemporaryDirectory(prefix="FAA 更新补入备份工具 ") as directory:
            root = Path(directory) / "FAA"
            staging = root / "update_cache/staging/FAA.update.new"
            staging.mkdir(parents=True)
            (root / "app.txt").write_text("current", encoding="utf-8")
            (staging / "app.txt").write_text("new", encoding="utf-8")
            (staging / "FAA - 环境安装器.exe").write_bytes(b"new backup tool")
            with contextlib.redirect_stdout(io.StringIO()):
                updater.update(root, staging, None)
            self.assertEqual((root / "FAA - 环境安装器.exe").read_bytes(), b"new backup tool")
            self.assertFalse(list((root / "update_cache").glob("tmp*.exe")))

    def fixture(self, base):
        root = Path(base) / "FAA 中文目录"
        backup = root / "backups" / "FAA.backup.20261020-123000"
        backup.mkdir(parents=True)
        (root / "app.txt").write_text("current", encoding="utf-8")
        (backup / "app.txt").write_text("backup", encoding="utf-8")
        (root / "FAA - 环境安装器.exe").write_bytes(b"running launcher")
        (backup / "FAA - 环境安装器.exe").write_bytes(b"older launcher")
        (root / "logs").mkdir()
        (root / "logs" / "active.log").write_text("current log", encoding="utf-8")
        (backup / "logs").mkdir()
        (backup / "logs" / "old.log").write_text("old log", encoding="utf-8")
        (root / ".venv").mkdir()
        (root / ".venv" / "keep.txt").write_text("environment", encoding="utf-8")
        return root, backup

    def test_gui_restore_keeps_launcher_environment_and_logs(self):
        with tempfile.TemporaryDirectory(prefix="FAA 图形恢复 ") as directory:
            root, backup = self.fixture(directory)
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(UPDATER), "restore", "--root", str(root),
                 "--backup", str(backup), "--launch", "", "--gui",
                 "--preserve-entry", "FAA - 环境安装器.exe", "--preserve-entry", "logs"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output = result.stdout.decode("utf-8")
            self.assertEqual(result.returncode, 0, output)
            self.assertEqual((root / "app.txt").read_text(encoding="utf-8"), "backup")
            self.assertEqual((root / "FAA - 环境安装器.exe").read_bytes(), b"running launcher")
            self.assertEqual((root / "logs" / "active.log").read_text(encoding="utf-8"), "current log")
            self.assertEqual((root / ".venv" / "keep.txt").read_text(encoding="utf-8"), "environment")
            self.assertEqual((backup / "app.txt").read_text(encoding="utf-8"), "backup")
            previous = next((root / "backups").glob("FAA.before-restore.*"))
            self.assertEqual((previous / "app.txt").read_text(encoding="utf-8"), "current")
            self.assertFalse((previous / "FAA - 环境安装器.exe").exists())
            for phase in ("backup_current_version", "restoring_backup", "restore_completed"):
                self.assertIn(f"FAA_LAUNCHER_PHASE:{phase}", output)
            self.assertNotIn("窗口将在", output)
            self.assertNotIn("FAA 已启动", output)

    def test_failed_restore_rolls_back_and_preserves_launcher(self):
        with tempfile.TemporaryDirectory(prefix="FAA 恢复回滚 ") as directory:
            root, backup = self.fixture(directory)
            original = updater.copy_items
            phases = []
            calls = 0

            def fail_first_copy(items, destination):
                nonlocal calls
                calls += 1
                if calls == 1:
                    (destination / "partial.txt").write_text("partial", encoding="utf-8")
                    raise OSError("fixture copy failure")
                return original(items, destination)

            with patch.object(updater, "copy_items", side_effect=fail_first_copy), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(OSError, "fixture copy failure"):
                    updater.restore(root, backup, None, preserve_entries={"FAA - 环境安装器.exe", "logs"}, on_phase=phases.append)
            self.assertEqual((root / "app.txt").read_text(encoding="utf-8"), "current")
            self.assertEqual((root / "FAA - 环境安装器.exe").read_bytes(), b"running launcher")
            self.assertTrue((root / "logs" / "active.log").is_file())
            self.assertFalse((root / "partial.txt").exists())
            self.assertIn("restore_rollback_started", phases)

    @unittest.skipUnless(os.name == "nt", "需要真实 Windows 文件共享锁")
    def test_locked_log_returns_moved_items_without_copying_and_allows_retry(self):
        """日志拒绝删除共享时，备份中止并完整归还版本区；关闭句柄后可重试。"""
        with tempfile.TemporaryDirectory(prefix="FAA 备份真实日志占用 ") as directory:
            root = Path(directory) / "FAA"
            files = {
                "config/settings.json": b'{"user": "preserved"}',
                "function/core/main.py": b"original application",
                "FAA.exe": b"original launcher",
                "logs/launcher_demo/python-20261030-550.log": b"active launcher log",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            log_path = root / "logs/launcher_demo/python-20261030-550.log"
            original_identity = log_path.stat().st_ino
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateFileW.argtypes = (
                ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
                ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
            )
            kernel.CreateFileW.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
            # 保持读写共享，但不授予 FILE_SHARE_DELETE，模拟仍打开日志的启动器。
            handle = kernel.CreateFileW(str(log_path), 0x80000000, 0x1 | 0x2, None, 3, 0x80, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value, ctypes.WinError(ctypes.get_last_error()))
            original_items = updater.version_items
            try:
                # 只固定枚举顺序，确保真实锁错误发生前已有目录和 EXE 被实际移走。
                with patch.object(updater, "version_items", side_effect=lambda *args, **kwargs: sorted(
                    original_items(*args, **kwargs), key=lambda path: path.name == "logs",
                )), patch.object(updater.shutil, "copytree", wraps=updater.shutil.copytree) as copied, \
                        patch.object(updater.shutil, "rmtree", wraps=updater.shutil.rmtree) as removed:
                    with self.assertRaises(OSError):
                        updater.create_backup(root, root / "backups", "FAA.backup")
                copied.assert_not_called()
                removed.assert_not_called()
                self.assertEqual(log_path.stat().st_ino, original_identity)
                restored = {
                    path.relative_to(root).as_posix(): path.read_bytes()
                    for path in root.rglob("*")
                    if path.is_file() and "backups" not in path.relative_to(root).parts
                }
                self.assertEqual(restored, files, "失败后不能丢文件或产生 logs/logs 等嵌套目录")
                self.assertFalse((root / "logs/logs").exists())
                self.assertFalse(any(path.is_file() for path in (root / "backups").rglob("*")))
            finally:
                kernel.CloseHandle(handle)

            backup = updater.create_backup(root, root / "backups", "FAA.backup")
            self.assertEqual({
                path.relative_to(backup).as_posix(): path.read_bytes()
                for path in backup.rglob("*") if path.is_file()
            }, files)
            for relative in files:
                self.assertFalse((root / relative).exists(), relative)

    def test_preservation_cannot_escape_root(self):
        with tempfile.TemporaryDirectory(prefix="FAA 保留路径 ") as directory:
            root, backup = self.fixture(directory)
            with self.assertRaises(ValueError):
                updater.restore(root, backup, None, preserve_entries={"../outside"})
            self.assertEqual((root / "app.txt").read_text(encoding="utf-8"), "current")


if __name__ == "__main__":
    unittest.main()
