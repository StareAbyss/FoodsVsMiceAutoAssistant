"""验证资源流水线的新入口和共用模块，不联网或改写正式资源。"""

import ast
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tool.image_resource_pipeline.common import download, excel
from tool.image_resource_pipeline.common.paths import PROJECT_ROOT
from tool.image_resource_pipeline.cards import catalog
from tool.image_resource_pipeline.loot import classification
from tool.image_resource_pipeline.sources import snapshots


class ImageResourcePipelineLayoutTests(unittest.TestCase):
    def test_public_module_entrypoints_offer_help_without_network(self):
        for name in ("sources", "loot", "cards", "loot.diagnostics", "loot.compare", "loot.classify"):
            with self.subTest(entry=name):
                result = subprocess.run(
                    [sys.executable, "-X", "utf8", "-m", f"tool.image_resource_pipeline.{name}", "--help"],
                    cwd=PROJECT_ROOT, capture_output=True, encoding="utf-8", timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_both_catalogs_use_shared_excel_reader(self):
        self.assertIs(catalog.read_xlsx_rows, excel.read_xlsx_rows)
        self.assertIs(classification.read_xlsx_rows, excel.read_xlsx_rows)

    def test_private_exporter_has_no_upstream_snapshot_dependency(self):
        path = PROJECT_ROOT / "tool/image_resource_pipeline/sources/xiaye.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertFalse(any("snapshots" in name for name in imports))

    def test_shared_download_preserves_force_and_missing_url_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "中文源.png", root / "target/中文目标.png"
            source.write_bytes(b"first")
            self.assertEqual(download.fetch_sources((str(source),), target, 1, False, "auto")[0], "已下载")
            source.write_bytes(b"second")
            self.assertEqual(download.fetch_sources((str(source),), target, 1, False, "auto")[0], "已存在")
            self.assertEqual(target.read_bytes(), b"first")
            self.assertEqual(download.fetch_sources((str(source),), target, 1, True, "auto")[0], "已下载")
            self.assertEqual(target.read_bytes(), b"second")
            self.assertEqual(download.fetch_sources((), target, 1, True, "auto"), ("无路径", ""))
            self.assertEqual(download.fetch_sources((), target, 1, True, "auto", empty_status="失败"), ("失败", ""))

    def test_shared_auto_downloader_keeps_curl_fallback(self):
        with patch.object(download, "download_url", side_effect=OSError("fixture offline")), \
                patch.object(download, "download_url_with_curl") as curl:
            download.download_remote_source("https://example.invalid/image", Path("fixture.png"), 1, "auto")
        curl.assert_called_once()

    def test_excel_refresh_launches_new_module_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.CompletedProcess([], 1, stdout=b"fixture failure", stderr=b"")
            with patch.object(snapshots.subprocess, "run", return_value=result) as run:
                with self.assertRaises(RuntimeError):
                    snapshots._refresh_excel(root, "2026-11-06_12-00-00", 1)
            argv = run.call_args.args[0]
            self.assertEqual(argv[1:3], ["-m", "tool.image_resource_pipeline.sources.xiaye"])
            self.assertTrue(Path(argv[-1]).is_relative_to(root))


if __name__ == "__main__":
    unittest.main()
