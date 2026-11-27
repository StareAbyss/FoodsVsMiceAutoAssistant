"""resource/db 快照的保留、排序与失败回退。"""

import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from tool.image_resource_pipeline.sources import snapshots


class ResourceDbSnapshotsTest(unittest.TestCase):
    def test_ensure_updates_each_resource_once_even_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempts = []

            def fake_refresh(*, kinds, **_kwargs):
                attempts.append(kinds)
                return snapshots.RefreshResult(
                    {kind: root / f"{kind}.snapshot" for kind in kinds},
                    {"compose": "offline"} if "compose" in kinds else {},
                )

            with patch.object(snapshots, "refresh_snapshots", side_effect=fake_refresh):
                first = snapshots.ensure_snapshots(db_dir=root, kinds=("excel", "compose"))
                second = snapshots.ensure_snapshots(db_dir=root, kinds=("excel", "compose", "CardFusion"))
                third = snapshots.ensure_snapshots(db_dir=root, kinds=("compose",))

            self.assertEqual(attempts, [("excel", "compose"), ("CardFusion",)])
            self.assertEqual(first.errors["compose"], "offline")
            self.assertEqual(second.errors["compose"], "offline")
            self.assertEqual(third.files["compose"], first.files["compose"])

    def test_concurrent_ensure_calls_share_one_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def fake_refresh(*, kinds, **_kwargs):
                time.sleep(0.05)
                return snapshots.RefreshResult({kind: root / f"{kind}.snapshot" for kind in kinds}, {})

            with patch.object(snapshots, "refresh_snapshots", side_effect=fake_refresh) as refresh:
                with ThreadPoolExecutor(max_workers=4) as workers:
                    results = list(workers.map(
                        lambda _: snapshots.ensure_snapshots(db_dir=root), range(4)
                    ))

            self.assertEqual(refresh.call_count, 1)
            self.assertTrue(all(result.files == results[0].files for result in results))

    def test_new_snapshot_prunes_only_its_own_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "compose 2026-09-27_10-00-00.xml"
            old.write_bytes(b"old")
            fusion = root / "CardFusion 2026-09-27_10-00-00.xml"
            fusion.write_bytes(b"fusion")
            tasks_db = root / "tasks.db"
            tasks_db.write_bytes(b"database")
            temporary = root / "compose-download.tmp"
            temporary.write_bytes(b"new")

            result = snapshots._install_snapshot(temporary, "compose", root, "2026-09-28_12-30-00")

            self.assertEqual(result.read_bytes(), b"new")
            self.assertFalse(old.exists())
            self.assertTrue(fusion.exists())
            self.assertEqual(tasks_db.read_bytes(), b"database")

    def test_failed_refresh_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "compose 2026-09-27_10-00-00.xml"
            old.write_bytes(b"old")
            with patch.object(snapshots, "_refresh_xml", side_effect=OSError("offline")):
                result = snapshots.refresh_snapshots(db_dir=root, kinds=("compose",))
            self.assertEqual(result.files["compose"], old)
            self.assertEqual(old.read_bytes(), b"old")
            self.assertIn("offline", result.errors["compose"])

    def test_excel_export_with_non_gbk_output_falls_back_without_reader_thread_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "点我获取更多图像资源 2026-09-27_10-00-00.xlsx"
            old.write_bytes(b"old snapshot")
            exporter = root / "invalid_output_exporter.py"
            exporter.write_text(
                "import sys\nsys.stderr.buffer.write(bytes([0x93, 0xFF]))\nsys.exit(1)\n",
                encoding="utf-8",
            )
            from subprocess import CompletedProcess
            completed = CompletedProcess([], 1, stdout=b"", stderr=bytes([0x93, 0xFF]))
            with patch.object(snapshots.subprocess, "run", return_value=completed):
                result = snapshots.refresh_snapshots(db_dir=root, kinds=("excel",))

            self.assertEqual(result.files["excel"], old)
            self.assertEqual(old.read_bytes(), b"old snapshot")
            self.assertIn("excel", result.errors)

    def test_timestamp_orders_same_day_and_legacy_date(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "点我获取更多图像资源 2026-09-28.xlsx"
            early = root / "点我获取更多图像资源 2026-09-28_08-00-00.xlsx"
            late = root / "点我获取更多图像资源 2026-09-28_09-00-00.xlsx"
            for path in (legacy, early, late):
                path.touch()
            self.assertEqual(snapshots.latest_snapshot("excel", root), late)

    def test_failed_excel_refresh_never_bootstraps_from_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "点我获取更多图像资源 2026-09-28.xlsx"
            legacy.write_bytes(b"root workbook must not be read")
            db_dir = root / "resource" / "db"
            with patch.object(snapshots, "PROJECT_ROOT", root), \
                    patch.object(snapshots, "_refresh_excel", side_effect=OSError("offline")):
                result = snapshots.refresh_snapshots(db_dir=db_dir, kinds=("excel",))
            self.assertIsNone(result.files["excel"])
            self.assertIn("excel", result.errors)
            self.assertEqual(list(db_dir.iterdir()), [])
            self.assertTrue(legacy.is_file())


if __name__ == "__main__":
    unittest.main()
