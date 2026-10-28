"""在隔离目录中验证图形恢复入口的文件保留和回滚。"""

import contextlib
import importlib.util
import io
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
    def test_update_preserves_environment_and_installer(self):
        """FAA 内执行更新时保留独立备份工具及运行环境。"""
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
            self.assertEqual(version_area_size(root), len(b"current") + len(b"unlisted executable"))
            with contextlib.redirect_stdout(io.StringIO()):
                updater.update(root, staging, None)
            self.assertEqual((root / "app.txt").read_text(encoding="utf-8"), "new")
            self.assertEqual((root / "FAA - 环境安装器.exe").read_bytes(), b"backup tool")
            self.assertTrue((root / ".venv").is_dir())
            backup = next((root / "backups").glob("FAA.backup.*"))
            self.assertEqual((backup / "app.txt").read_text(encoding="utf-8"), "current")
            self.assertEqual((backup / "extra-entry.exe").read_bytes(), b"unlisted executable")
            self.assertFalse((root / "extra-entry.exe").exists())
            self.assertFalse((backup / "FAA - 环境安装器.exe").exists())

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

    def test_backup_failure_returns_already_moved_files(self):
        with tempfile.TemporaryDirectory(prefix="FAA 备份中断 ") as directory:
            root = Path(directory)
            (root / "first.txt").write_text("first", encoding="utf-8")
            (root / "second.txt").write_text("second", encoding="utf-8")
            original = updater.shutil.move
            calls = 0

            def fail_second_move(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise PermissionError("fixture locked file")
                return original(source, target)

            with patch.object(updater.shutil, "move", side_effect=fail_second_move):
                with self.assertRaises(PermissionError):
                    updater.create_backup(root, root / "backups", "FAA.before-restore")
            self.assertEqual((root / "first.txt").read_text(encoding="utf-8"), "first")
            self.assertEqual((root / "second.txt").read_text(encoding="utf-8"), "second")

    def test_preservation_cannot_escape_root(self):
        with tempfile.TemporaryDirectory(prefix="FAA 保留路径 ") as directory:
            root, backup = self.fixture(directory)
            with self.assertRaises(ValueError):
                updater.restore(root, backup, None, preserve_entries={"../outside"})
            self.assertEqual((root / "app.txt").read_text(encoding="utf-8"), "current")


if __name__ == "__main__":
    unittest.main()
