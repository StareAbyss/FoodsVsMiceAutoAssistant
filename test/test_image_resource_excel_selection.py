import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from function.common.update_staging import copy_latest_image_resource_excel
from tool.card_resource.get_card_resource_tool import find_latest_existing_excel
from tool.item_resource.item_resource_common import find_default_excel


ROOT = Path(__file__).resolve().parents[1]
QT_APP = QApplication.instance() or QApplication([])


def load_packaging_module():
    """加载中文文件名的打包脚本，以验证其资源表选择函数。"""
    module_path = ROOT / "一键生成分发资源.py"
    spec = importlib.util.spec_from_file_location("faa_packaging", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ImageResourceExcelSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_dir.name)
        self.old_excel = self.root / "点我获取更多图像资源 2026-07-10.xlsx"
        self.new_excel = self.root / "点我获取更多图像资源 2026-07-28.xlsx"
        self.old_excel.touch()
        self.new_excel.touch()

        # 故意让旧日期文件拥有更新的修改时间，确保选择依据不是 mtime。
        os.utime(self.new_excel, (1000, 1000))
        os.utime(self.old_excel, (2000, 2000))

    def tearDown(self):
        self.temporary_dir.cleanup()

    def test_all_resource_workflows_select_latest_filename_date(self):
        self.assertEqual(find_default_excel(self.root), self.new_excel)
        self.assertEqual(find_latest_existing_excel(self.root), self.new_excel)

        packaging = load_packaging_module()
        self.assertEqual(packaging.get_latest_existing_excel_file(self.root), Path(self.new_excel.name))

        destination = self.root / "staging"
        destination.mkdir()
        copied = copy_latest_image_resource_excel(self.root, destination)
        self.assertEqual(copied, destination / self.new_excel.name)

    def test_invalid_date_falls_back_behind_valid_resource_date(self):
        invalid_excel = self.root / "点我获取更多图像资源 2026-99-99.xlsx"
        invalid_excel.touch()
        os.utime(invalid_excel, (3000, 3000))

        self.assertEqual(find_default_excel(self.root), self.new_excel)
        self.assertEqual(find_latest_existing_excel(self.root), self.new_excel)

if __name__ == "__main__":
    unittest.main()
