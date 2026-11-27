import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from function.common.update_staging import copy_latest_image_resource_excel
from tool.image_resource_pipeline.common.excel import find_latest_existing_excel
from tool.image_resource_pipeline.common.excel import find_default_excel as find_card_excel
from tool.image_resource_pipeline.common.excel import find_default_excel
from tool.image_resource_pipeline.common.snapshot_files import resolve_excel_path


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
        self.db_dir = self.root / "resource" / "db"
        self.db_dir.mkdir(parents=True)
        self.old_excel = self.db_dir / "点我获取更多图像资源 2026-07-10.xlsx"
        self.new_excel = self.db_dir / "点我获取更多图像资源 2026-07-28.xlsx"
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
        self.assertEqual(packaging.get_latest_existing_excel_file(self.root), self.new_excel.relative_to(self.root))

        destination = self.root / "staging"
        destination.mkdir()
        copied = copy_latest_image_resource_excel(self.root, destination)
        self.assertEqual(copied, destination / self.new_excel.relative_to(self.root))

    def test_invalid_date_falls_back_behind_valid_resource_date(self):
        invalid_excel = self.db_dir / "点我获取更多图像资源 2026-99-99.xlsx"
        invalid_excel.touch()
        os.utime(invalid_excel, (3000, 3000))

        self.assertEqual(find_default_excel(self.root), self.new_excel)
        self.assertEqual(find_latest_existing_excel(self.root), self.new_excel)

    def test_root_excel_is_ignored_even_when_newer_or_db_is_empty(self):
        root_excel = self.root / "点我获取更多图像资源 2099-01-01.xlsx"
        root_excel.touch()
        self.assertEqual(find_default_excel(self.root), self.new_excel)
        self.assertEqual(find_card_excel(self.root), self.new_excel)
        self.old_excel.unlink()
        self.new_excel.unlink()
        with self.assertRaises(FileNotFoundError):
            find_default_excel(self.root)
        with self.assertRaises(FileNotFoundError):
            find_card_excel(self.root)
        self.assertIsNone(find_latest_existing_excel(self.root))
        packaging = load_packaging_module()
        self.assertIsNone(packaging.get_latest_existing_excel_file(self.root))
        destination = self.root / "staging"
        destination.mkdir()
        self.assertIsNone(copy_latest_image_resource_excel(self.root, destination))
        self.assertEqual(list(destination.iterdir()), [])

    def test_explicit_excel_rejects_root_and_accepts_db(self):
        root_excel = self.root / self.new_excel.name
        root_excel.touch()
        with self.assertRaises(ValueError):
            resolve_excel_path(root_excel, self.db_dir)
        self.assertEqual(resolve_excel_path(self.new_excel, self.db_dir), self.new_excel)

    def test_explicit_excel_is_not_deleted_by_startup_refresh(self):
        # 在刷新入口截停，验证下载、分类和卡片流程都不会刷新已选 Excel。
        from tool.image_resource_pipeline.loot import __main__ as download_item_resources
        from tool.image_resource_pipeline.loot import classify as classify_loot_resources_once
        from tool.image_resource_pipeline.cards import __main__ as get_card_resource_tool
        from tool.image_resource_pipeline.cards import workflow as card_workflow

        for module in (download_item_resources, classify_loot_resources_once, get_card_resource_tool):
            with self.subTest(module=module.__name__), \
                    patch("sys.argv", ["tool", "--excel", str(self.new_excel)]), \
                    patch.object(card_workflow if module is get_card_resource_tool else module, "resolve_excel_path"), \
                    patch("tool.image_resource_pipeline.sources.snapshots.ensure_snapshots", side_effect=RuntimeError("stop-before-refresh")) as refresh:
                if module is get_card_resource_tool:
                    with patch.object(card_workflow, "ensure_snapshots", side_effect=RuntimeError("stop-before-refresh")) as card_refresh:
                        with self.assertRaisesRegex(RuntimeError, "stop-before-refresh"):
                            module.main()
                        self.assertNotIn("excel", card_refresh.call_args.kwargs["kinds"])
                else:
                    with self.assertRaisesRegex(RuntimeError, "stop-before-refresh"):
                        module.main()
                    self.assertNotIn("excel", refresh.call_args.kwargs["kinds"])

if __name__ == "__main__":
    unittest.main()
