"""使用未修改的历史更新模块验证自动过渡，而不是给旧安装手动覆盖补丁。"""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_MODULES = (
    "function/common/update_manifest.py", "function/common/update_state.py",
    "function/common/update_staging.py", "function/common/update_space.py",
    "function/core/update_prepare.py", "function/core/settings_migration.py",
    "function/core/update_apply.py", "plugins/updater/updater.py",
)
TARGET_COMMIT = "e" * 40


def run_historical_update(root: Path, archive: Path, number: int) -> None:
    """独立进程加载用户原有版本的更新器，实际准备、迁移、备份和替换一次。"""
    sys.path.insert(0, str(root))
    from function.core.update_apply import build_update_command
    from function.core.update_prepare import prepare_update_from_archive

    with patch("function.common.update_manifest.GitHubClient.compare_commits", return_value={"status": "ahead"}):
        result = prepare_update_from_archive(root, archive, {"commit": TARGET_COMMIT, "title": "过渡验证"})
    staging = Path(result["staging"]["path"])
    command = build_update_command(root, staging, root / "plugins/updater/updater.py")
    expected = "FAA.exe" if number == 1055 else "FAA - 快速启动.exe"
    assert command[command.index("--launch") + 1] == expected
    assert not (staging / "target-only.txt").exists(), "历史复制器不应知道目标新增文件"
    assert not (staging / "config/new_user_format.json").exists(), "历史迁移器不应执行新增规则"
    spec = importlib.util.spec_from_file_location("historical_updater", root / "plugins/updater/updater.py")
    updater = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(updater)
    # 只停止最后启动进程这一动作；旧 updater 的文件操作和状态记录全部保留。
    updater.update(root, staging, None)
    assert not (root / "config/target_user.json").exists(), "测试要求原始用户数据只在旧备份中保留"
    assert "update_protocol" not in json.loads((root / "update_cache/update_state.json").read_text(encoding="utf-8"))


class LegacyUpdateTests(unittest.TestCase):
    def historical_fixture(self, number, commit):
        """生成真实历史模块和包含正式兼容文件的目标源码，仅联网部分使用本地 ZIP。"""
        from plugins.updater.legacy_bridge import COMPATIBILITY_FILES
        from test.test_update_target_rules import TargetUpdateRulesTests

        fixture = TargetUpdateRulesTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root, source = fixture.root, fixture.source
        for relative in HISTORICAL_MODULES:
            result = subprocess.run(
                ["git", "show", f"{commit}:{relative}"], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            )
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(result.stdout)
        if number >= 1056:
            target = root / "function/common/distribution_layout.py"
            target.write_bytes(subprocess.run(
                ["git", "show", f"{commit}:function/common/distribution_layout.py"], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            ).stdout)
        for relative in ("function/__init__.py", "function/common/__init__.py", "function/core/__init__.py"):
            (root / relative).write_bytes(b"")
        (root / "update_cache").mkdir()
        (root / "update_cache/update_state.json").write_text(json.dumps({"commit": commit}), encoding="utf-8")
        (root / "battle_plan").mkdir()
        (root / "battle_plan/user.json").write_text(
            json.dumps({"meta_data": {"uuid": "user-plan"}, "user_value": 123}), encoding="utf-8",
        )
        (root / "FAA.exe").write_bytes(b"original old entry")
        for relative in (*COMPATIBILITY_FILES, "plugins/updater/legacy_bridge.py", "plugins/root_entries/FAA.exe"):
            # 卸除、调试 BAT 在源码入口目录，由旧复制器展开到用户根目录。
            source_relative = Path("plugins/root_entries") / relative if relative in {
                "FAA-卸除运行环境.bat", "FAA-调试模式启动.bat",
            } else Path(relative)
            target = source / source_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / source_relative).read_bytes())
        # 别名必须与正式原生入口相同，才能验证生产代码的受限自动清理。
        (source / "plugins/root_entries/FAA - 快速启动.exe").write_bytes(
            (ROOT / "plugins/root_entries/FAA - 快速启动.exe").read_bytes(),
        )
        with (source / "function/core/settings_migration.py").open("a", encoding="utf-8") as file:
            file.write('''
_migrate_before_failure_check = migrate_user_data
def migrate_user_data(source_root, target_root, selected_names=None, allow_missing_target=True):
    if (Path(target_root).parents[1] / "fixture-legacy-failure").exists():
        raise ValueError("legacy target migration blocked by fixture")
    return _migrate_before_failure_check(source_root, target_root, selected_names, allow_missing_target)
''')
        fixture.make_archive()
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--historical", str(root), str(fixture.archive), str(number)],
            cwd=fixture.base, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        operation = json.loads((root / "update_cache/updater_state.json").read_text(encoding="utf-8"))
        original_backup = Path(operation["details"]["backup"])
        self.assertEqual((original_backup / "old-version.txt").read_bytes(), b"old version")
        self.assertEqual(json.loads((original_backup / "config/target_user.json").read_text(encoding="utf-8")), {"value": 1})
        return fixture, original_backup

    def run_bridge(self, fixture):
        """原生入口调用的同一生产桥接脚本，仅使用已有离线源码包替代 GitHub 下载。"""
        return subprocess.run(
            [sys.executable, "-I", "-X", "utf8", str(fixture.root / "plugins/updater/legacy_bridge.py"),
             "--root", str(fixture.root), "--archive", str(fixture.archive)],
            cwd=fixture.base, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", timeout=45,
        )

    def assert_completed(self, fixture, original_backup):
        """确认目标规则生效、原始备份完整以及根目录没有过渡文件。"""
        from plugins.updater.legacy_bridge import COMPATIBILITY_FILES

        root = fixture.root
        self.assertEqual((root / "target-only.txt").read_bytes(), b"new version only")
        self.assertEqual((root / "mapped_payload/keep.bin").read_bytes(), b"mapped payload")
        self.assertFalse((root / "mapped_payload/excluded.bin").exists())
        self.assertFalse((root / "config/excluded_by_target.json").exists())
        self.assertEqual(
            json.loads((root / "config/new_user_format.json").read_text(encoding="utf-8")),
            {"new_format_value": 1},
        )
        self.assertEqual(json.loads((root / "config/settings.json").read_text(encoding="utf-8")), {"iteration": 1})
        self.assertEqual(json.loads((root / "battle_plan/user.json").read_text(encoding="utf-8"))["user_value"], 123)
        self.assertEqual(json.loads((original_backup / "config/target_user.json").read_text(encoding="utf-8")), {"value": 1})
        self.assertEqual((original_backup / "FAA.exe").read_bytes(), b"original old entry")
        self.assertEqual((root / ".venv/keep.txt").read_bytes(), b"existing environment")
        for relative in (*COMPATIBILITY_FILES, "FAA.exe"):
            self.assertFalse((root / relative).exists(), relative)
        self.assertFalse((root / "update_cache/legacy_bridge/state.json").exists())
        state = json.loads((root / "update_cache/update_state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["commit"], TARGET_COMMIT)
        self.assertEqual(state["update_protocol"], 1)

    def test_unmodified_historical_versions_complete_target_rules_and_cleanup(self):
        for number, commit in (
            (1055, "82659f2b84b6bf893de0f1d33199130194a214f1"),
            (1056, "a885ea31"),
            (1057, "39ae8583"),
        ):
            with self.subTest(version=number):
                fixture, backup = self.historical_fixture(number, commit)
                result = self.run_bridge(fixture)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assert_completed(fixture, backup)

    def test_failed_bridge_retries_from_same_original_backup(self):
        fixture, backup = self.historical_fixture(1055, "82659f2b84b6bf893de0f1d33199130194a214f1")
        marker = fixture.root / "update_cache/fixture-legacy-failure"
        marker.write_bytes(b"temporary migration failure")
        first = self.run_bridge(fixture)
        self.assertNotEqual(first.returncode, 0, first.stdout)
        self.assertIn("legacy target migration blocked by fixture", first.stdout)
        pending = json.loads((fixture.root / "update_cache/legacy_bridge/state.json").read_text(encoding="utf-8"))
        self.assertEqual(Path(pending["backup"]), backup)
        self.assertEqual(json.loads((backup / "config/target_user.json").read_text(encoding="utf-8")), {"value": 1})
        marker.unlink()
        retry = self.run_bridge(fixture)
        self.assertEqual(retry.returncode, 0, retry.stdout)
        self.assert_completed(fixture, backup)

    def test_https_failure_reports_network_reason_and_keeps_original_backup(self):
        """第二次下载真实握手失败时，CLI 保留原始备份与交接记录并说明证书原因。"""
        from test.test_update_https import LocalHttpsFixture

        fixture, backup = self.historical_fixture(1055, "82659f2b84b6bf893de0f1d33199130194a214f1")
        before = {path.relative_to(backup): path.read_bytes() for path in backup.rglob("*") if path.is_file()}
        version_state = (fixture.root / "update_cache/update_state.json").read_bytes()
        tls = LocalHttpsFixture()
        self.addCleanup(tls.close)
        endpoint = tls.start("unknown")
        wrapper = '''
import ssl, sys, urllib.request
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from plugins.updater import legacy_bridge
real_context, real_request = ssl.create_default_context, urllib.request.Request
system_ca, additional_ca, endpoint = sys.argv[2:5]
def request(url, *args, **kwargs):
    return real_request(endpoint if str(url).startswith("https://github.com/") else url, *args, **kwargs)
sys.argv = ["legacy_bridge.py", "--root", sys.argv[1]]
with patch.object(ssl, "create_default_context", side_effect=lambda: real_context(cafile=system_ca)), \\
        patch("certifi.where", return_value=additional_ca), patch.object(urllib.request, "Request", side_effect=request):
    raise SystemExit(legacy_bridge.main())
'''
        result = subprocess.run([
            sys.executable, "-I", "-X", "utf8", "-c", wrapper, str(fixture.root),
            str(tls.ca("system")), str(tls.ca("additional")), endpoint,
        ], cwd=fixture.base, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("SSLCertVerificationError", result.stdout)
        self.assertIn("FAA_LEGACY_NETWORK_ERROR:", result.stdout)
        self.assertIn("证书", result.stdout)
        self.assertIn("原始备份和过渡记录已保留", result.stdout)
        self.assertIn("代理", result.stdout)
        self.assertIn("Python 和依赖包镜像设置不影响 GitHub", result.stdout)
        pending = json.loads((fixture.root / "update_cache/legacy_bridge/state.json").read_text(encoding="utf-8"))
        self.assertEqual(Path(pending["backup"]), backup)
        self.assertEqual((fixture.root / "update_cache/update_state.json").read_bytes(), version_state)
        self.assertEqual({path.relative_to(backup): path.read_bytes() for path in backup.rglob("*") if path.is_file()}, before)
        self.assertFalse((fixture.root / "update_cache/legacy_bridge/source.zip").exists())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--historical":
        run_historical_update(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]))
    else:
        unittest.main()
