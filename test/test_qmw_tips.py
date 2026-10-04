"""验证提示窗口子包的导入路径、主窗口引用与窗口创建。"""

import ast
import importlib
import inspect
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow

from function.core import qmw_tips


class QMWTipsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """复用 Qt 应用，避免创建测试窗口时缺少 QApplication。"""
        cls.app = QApplication.instance() or QApplication([])
        cls.directory = Path(qmw_tips.__file__).parent

    def test_tip_files_are_grouped_under_package(self):
        self.assertEqual(len(list(self.directory.glob("qmw_tip_*.py"))), 12)
        self.assertEqual(list(self.directory.parent.glob("qmw_tip_*.py")), [])

    def test_main_window_imports_tips_from_package(self):
        service = ast.parse((self.directory.parent / "qmw_3_service.py").read_text(encoding="utf-8-sig"))
        imports = [node.module for node in ast.walk(service)
                   if isinstance(node, ast.ImportFrom) and node.module
                   and any(alias.name.startswith("QMWTip") for alias in node.names)]
        expected = {f"function.core.qmw_tips.{file.stem}"
                    for file in self.directory.glob("qmw_tip_*.py")}
        self.assertEqual(set(imports), expected)

    def test_every_tip_window_can_be_created(self):
        for file in sorted(self.directory.glob("qmw_tip_*.py")):
            with self.subTest(module=file.stem):
                module = importlib.import_module(f"function.core.qmw_tips.{file.stem}")
                classes = [value for value in vars(module).values()
                           if inspect.isclass(value) and value.__module__ == module.__name__
                           and issubclass(value, QMainWindow)]
                self.assertEqual(len(classes), 1)
                window = classes[0]()
                try:
                    self.assertIsNotNone(window.centralWidget())
                    self.assertTrue(window.windowTitle())
                finally:
                    window.close()
                    window.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
