"""在独立源码副本验证构建清理，不修改工作区里的正式 EXE。"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tool/faa_launcher"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
CXX = os.environ.get("FAA_CXX") or shutil.which("g++.exe")
ICON = "圆角-FetDeathWing-256x-AllSize.ico"


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "构建清理验证需要 Windows PowerShell")
class BuildCleanupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="FAA 构建清理 中文 ")
        self.addCleanup(self.directory.cleanup)
        self.root = (Path(self.directory.name) / "source").resolve()
        self.source = self.root / "tool/faa_launcher"
        shutil.copytree(SOURCE, self.source, ignore=shutil.ignore_patterns("__pycache__"))
        updater = self.root / "plugins/updater/updater.py"
        updater.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "plugins/updater/updater.py", updater)
        icon = self.root / "resource/logo" / ICON
        icon.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "resource/logo" / ICON, icon)
        (self.root / "plugins/root_entries").mkdir()

    @unittest.skipUnless(CXX, "请通过 FAA_CXX 指定 MinGW-w64 编译器")
    def test_success_cleans_current_workspace_and_preserves_outputs(self):
        work_root = self.root / "dist/faa_launcher"
        output = work_root / "export"
        output.mkdir(parents=True)
        marker = output / "keep.txt"
        marker.write_text("custom output", encoding="utf-8")
        previous_failure = work_root / ("build-" + "a" * 32)
        previous_failure.mkdir()
        (previous_failure / "failure.log").write_text("diagnostic", encoding="utf-8")
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.source / "build.ps1"),
             "-Cxx", str(CXX), "-OutputDirectory", str(output), "-Variant", "Both"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout.decode("utf-8", errors="replace"))
        for name in ("FAA - 快速启动.exe", "FAA - 环境安装器.exe"):
            self.assertGreater((output / name).stat().st_size, 0)
            self.assertEqual((output / name).read_bytes(), (self.root / "plugins/root_entries" / name).read_bytes())
            self.assertIn((self.root / "plugins/updater/updater.py").read_bytes(), (output / name).read_bytes())
            self.assertIn((self.source / "runtime_probe.py").read_bytes(), (output / name).read_bytes())
        self.assertEqual(set(work_root.iterdir()), {output, previous_failure})
        self.assertEqual(marker.read_text(encoding="utf-8"), "custom output")
        self.assertFalse((self.source / "launcher.generated.ico").exists())
        self.assertEqual({path.name for path in output.glob("*.exe")}, {"FAA - 快速启动.exe", "FAA - 环境安装器.exe"})

if __name__ == "__main__":
    unittest.main()
