"""验证资源导出路径与私有凭据边界，不连接真实数据库。"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tool.image_resource_pipeline.sources import xiaye as exporter
from tool.image_resource_pipeline.sources import __main__ as source_cli
from tool.image_resource_pipeline.sources.snapshots import RefreshResult


class ImageResourceDbExportTest(unittest.TestCase):
    def test_credentials_come_only_from_fixed_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local_file = root / "image_resource_db.local.json"
            config = {"host": "fixture.invalid", "user": "fixture", "password": "fake-secret", "database": "fixture"}
            local_file.write_text(json.dumps(config), encoding="utf-8")
            with patch.object(exporter, "LOCAL_CONFIG_PATH", local_file), \
                    patch.dict(os.environ, {"FAA_IMAGE_RESOURCE_DB_PASSWORD": "must-not-be-used"}):
                result = exporter.require_db_config()
            self.assertEqual(result, dict(config, port=3306))
            local_file.unlink()
            with patch.object(exporter, "LOCAL_CONFIG_PATH", local_file), \
                    patch.dict(os.environ, {"FAA_IMAGE_RESOURCE_DB_PASSWORD": "must-not-be-used"}):
                with self.assertRaises(ValueError):
                    exporter.require_db_config()

    def test_default_cli_uses_snapshot_publisher(self):
        snapshot = exporter.DB_DIR / "点我获取更多图像资源 2026-11-06_10-00-00.xlsx"
        with patch("sys.argv", ["source", "--excel-only"]), \
                patch.object(source_cli, "ensure_snapshots", return_value=RefreshResult({"excel": snapshot}, {})) as refresh, \
                patch.object(exporter, "export_image_resource_excel") as export, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(source_cli.main(), 0)
        refresh.assert_called_once_with(kinds=("excel",))
        export.assert_not_called()

    def test_export_only_writes_inside_db(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_dir = root / "resource" / "db"
            dataframe = Mock()
            with patch.object(exporter, "DB_DIR", db_dir), \
                    patch.object(exporter.mysql.connector, "connect") as connect, \
                    patch.object(exporter.pd, "read_sql", return_value=dataframe), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError):
                    exporter.export_image_resource_excel({}, "card_image_url", root)
                connect.assert_not_called()
                target = exporter.export_image_resource_excel({}, "card_image_url", db_dir / "temporary")
            self.assertTrue(target.is_relative_to(db_dir))
            dataframe.to_excel.assert_called_once_with(target, index=False)
            self.assertEqual(list(root.glob("*.xlsx")), [])

    def test_private_database_error_is_not_printed(self):
        stream = io.StringIO()
        with patch("sys.argv", ["exporter", "--output-dir", str(exporter.DB_DIR / "temporary")]), \
                patch.object(exporter, "require_db_config", side_effect=RuntimeError("fake-secret@private-host")), \
                contextlib.redirect_stdout(stream):
            self.assertEqual(exporter.main(), 1)
        self.assertNotIn("fake-secret", stream.getvalue())
        self.assertNotIn("private-host", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
