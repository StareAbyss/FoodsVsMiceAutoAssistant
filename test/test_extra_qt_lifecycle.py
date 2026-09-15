import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestExtraQtLifecycle(unittest.TestCase):
    def run_python(self, code: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def test_import_without_qapplication_exits_cleanly(self):
        result = self.run_python(
            "import ctypes; "
            "ctypes.windll.kernel32.SetErrorMode(2); "
            "import function.globals.EXTRA"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_font_is_initialized_after_qapplication(self):
        result = self.run_python(
            "import ctypes; "
            "ctypes.windll.kernel32.SetErrorMode(2); "
            "from PyQt6.QtWidgets import QApplication; "
            "import function.globals.EXTRA as extra; "
            "app = QApplication([]); "
            "font = extra.Q_FONT; "
            "assert font.family(); "
            "app.quit()"
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
