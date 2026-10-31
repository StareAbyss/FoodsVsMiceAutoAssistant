"""在临时目录实际执行目标版本的布局、迁移和更新脚本，核对跨版本责任边界。"""

import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from function.common.distribution_layout import ENVIRONMENT_INSTALLER_EXE, LAUNCHER_EXE
from function.common.update_staging import StagingError
from function.core import update_apply, update_prepare


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
            [sys.executable, "-X", "utf8", str(script), "update", "--root", str(self.root), "--staging", str(staging)],
            cwd=self.base, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", timeout=35,
        )

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

    def test_handoff_copies_target_updater_and_disables_automatic_launch(self):
        staging, _ = self.prepare()
        expected = (staging / "plugins/updater/updater.py").read_bytes()
        with patch.object(update_apply.tempfile, "gettempdir", return_value=str(self.base)), \
                patch.object(update_apply.subprocess, "Popen", return_value=SimpleNamespace(pid=1234)):
            result = update_apply.launch_update_from_staging(self.root, staging, wait_pid=123)
        self.assertEqual(Path(result["updater_script"]).read_bytes(), expected)
        command = result["command"]
        self.assertEqual(command[command.index("--launch") + 1], "")
        self.assertEqual(command[command.index("--wait-pid") + 1], "123")

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
