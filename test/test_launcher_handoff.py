"""在隔离目录验证更新替换与历史备份恢复后的真实启动交接。"""

import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from function.common.distribution_layout import LAUNCHER_EXE
from test.faa_launcher.test_maintenance import UPDATER, updater


STUB = r'''
using System;
using System.IO;
class Fixture {
    static void Main() {
        string report = Environment.GetEnvironmentVariable("FAA_HANDOFF_REPORT");
        string executable = System.Diagnostics.Process.GetCurrentProcess().MainModule.FileName;
        File.WriteAllLines(report, new string[] { Path.GetFileName(executable), Environment.CurrentDirectory });
    }
}
'''


@unittest.skipUnless(os.name == "nt", "启动交接测试需要 Windows")
class LauncherHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_directory = tempfile.TemporaryDirectory(prefix="FAA 交接夹具 ")
        directory = Path(cls.build_directory.name)
        source = directory / "fixture.cs"
        source.write_text(STUB, encoding="utf-8-sig")
        cls.stub = directory / "fixture.exe"
        compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        subprocess.run(
            [str(compiler), "/nologo", "/target:winexe", f"/out:{cls.stub}", str(source)],
            capture_output=True, check=True, timeout=30,
        )

    @classmethod
    def tearDownClass(cls):
        cls.build_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="FAA 更新交接 & 中文目录 ")
        self.addCleanup(self.directory.cleanup)
        self.root = (Path(self.directory.name) / "FAA 安装根目录").resolve()
        self.root.mkdir()
        self.report = Path(self.directory.name) / "启动结果.txt"
        environment = patch.dict(os.environ, FAA_HANDOFF_REPORT=str(self.report))
        environment.start()
        self.addCleanup(environment.stop)

    def install_stub(self, directory, name=LAUNCHER_EXE):
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.stub, directory / name)

    def assert_recorded_launch(self, operation, expected_name=LAUNCHER_EXE):
        """保留真实进程句柄，等待退出后再读记录，避免清理时 EXE 仍被占用。"""
        popen = subprocess.Popen
        processes = []

        def start(*args, **kwargs):
            process = popen(*args, **kwargs)
            processes.append(process)
            return process

        with patch.object(updater.subprocess, "Popen", side_effect=start), \
                contextlib.redirect_stdout(io.StringIO()):
            operation()
        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0].wait(timeout=10), 0)
        lines = self.report.read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual(lines, [expected_name, str(self.root)])

    def test_restore_historical_backup_launches_legacy_entry(self):
        self.install_stub(self.root)
        backup = self.root / "backups" / "FAA.backup.old"
        self.install_stub(backup, updater.LEGACY_LAUNCHER_EXE)
        self.assert_recorded_launch(
            lambda: updater.restore(self.root, backup, LAUNCHER_EXE), updater.LEGACY_LAUNCHER_EXE,
        )
        self.assertFalse((self.root / LAUNCHER_EXE).exists())
        previous = next((self.root / "backups").glob("FAA.before-restore.*"))
        self.assertTrue((previous / LAUNCHER_EXE).is_file())

    def test_updater_cli_default_launch_after_replacement(self):
        """实际执行参数解析与文件替换，不打开 FAA 或访问用户备份。"""
        self.install_stub(self.root, updater.LEGACY_LAUNCHER_EXE)
        staging = self.root / "update_cache" / "staging" / "FAA.update.new"
        self.install_stub(staging)
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(UPDATER), "update", "--root", str(self.root),
             "--staging", str(staging)],
            capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(result.returncode, 0, result.stdout.decode("utf-8") + result.stderr.decode("utf-8"))
        self.assertEqual(self.report.read_text(encoding="utf-8-sig").splitlines(), [LAUNCHER_EXE, str(self.root)])
        self.assertFalse((self.root / updater.LEGACY_LAUNCHER_EXE).exists())
        self.assertTrue(next((self.root / "backups").glob("FAA.backup.*")).joinpath(updater.LEGACY_LAUNCHER_EXE).is_file())

if __name__ == "__main__":
    unittest.main()
