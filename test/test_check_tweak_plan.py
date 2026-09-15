import json
import tempfile
import unittest
from pathlib import Path

from function.scattered.check_tweak_plan import (
    ISSUE_CURRENT_INVALID,
    ISSUE_HIGH_VERSION,
    ISSUE_LOW_VERSION,
    scan_and_migrate_tweak_plans,
)


CURRENT_VERSION = "0.3"
CURRENT_FAA_VERSION = "v3.1.1"


def write_plan(path: Path, meta_data: dict) -> None:
    """写入测试所需的最小微调方案。"""
    path.write_text(
        json.dumps({"meta_data": meta_data}, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )


class CheckTweakPlanTest(unittest.TestCase):
    def test_current_valid_plan_is_not_rewritten(self):
        with tempfile.TemporaryDirectory(dir="test") as temp_dir:
            path = Path(temp_dir) / "当前方案.json"
            meta_data = {
                "uuid": "11111111-1111-1111-1111-111111111111",
                "version": CURRENT_VERSION,
                "faa_version": "v3.0.0",
                "tips": "保持原样",
                "senior_setting": True,
            }
            write_plan(path, meta_data)
            before = path.read_bytes()

            result = scan_and_migrate_tweak_plans(
                Path(temp_dir), CURRENT_VERSION, CURRENT_FAA_VERSION
            )

            self.assertFalse(result.has_issues)
            self.assertEqual(path.read_bytes(), before)
            self.assertIn("均为最新版本", result.startup_text())

    def test_low_version_converts_known_fields_and_keeps_uuid(self):
        with tempfile.TemporaryDirectory(dir="test") as temp_dir:
            path = Path(temp_dir) / "旧方案.json"
            plan_uuid = "22222222-2222-2222-2222-222222222222"
            write_plan(path, {
                "uuid": plan_uuid,
                "version": "0.2",
                "tips": "旧方案",
                "recording": True,
                "timestamp": True,
                "recording_player": 2,
                "cd_after_use_random_range": [0.1, 0.3],
                "ban_state": {"mat": True, "god": True, "ikun": False},
                "enable_auto_card": {"timer": False},
                "auto_mat_card": {"use_first": False},
                "recording-tip": "旧提示",
            })

            result = scan_and_migrate_tweak_plans(
                Path(temp_dir), CURRENT_VERSION, CURRENT_FAA_VERSION
            )
            meta_data = json.loads(path.read_text(encoding="utf-8"))["meta_data"]

            self.assertEqual(result.migrated_count, 1)
            self.assertEqual(result.issues[0].category, ISSUE_LOW_VERSION)
            self.assertEqual(meta_data["uuid"], plan_uuid)
            self.assertEqual(meta_data["version"], CURRENT_VERSION)
            self.assertEqual(meta_data["faa_version"], CURRENT_FAA_VERSION)
            self.assertEqual(
                meta_data["recording"],
                {"active": True, "timestamp": True, "player": 2},
            )
            self.assertEqual(
                meta_data["cd_after_use_random"],
                {"active": True, "range": [0.1, 0.3]},
            )
            self.assertEqual(
                meta_data["auto_mat_card"],
                {"enabled": False, "use_first": False},
            )
            self.assertEqual(
                meta_data["enable_auto_card"],
                {"god": False, "ikun": True, "timer": False},
            )
            self.assertNotIn("recording-tip", meta_data)
            self.assertNotIn("ban_state", meta_data)

    def test_invalid_current_plan_is_normalized(self):
        with tempfile.TemporaryDirectory(dir="test") as temp_dir:
            path = Path(temp_dir) / "篡改方案.json"
            plan_uuid = "33333333-3333-3333-3333-333333333333"
            write_plan(path, {
                "uuid": plan_uuid,
                "version": CURRENT_VERSION,
                "faa_version": CURRENT_FAA_VERSION,
                "tips": "异常字段会回退",
                "recording": {"active": "yes", "timestamp": True},
                "senior_setting": "yes",
            })

            result = scan_and_migrate_tweak_plans(
                Path(temp_dir), CURRENT_VERSION, CURRENT_FAA_VERSION
            )
            meta_data = json.loads(path.read_text(encoding="utf-8"))["meta_data"]

            self.assertEqual(result.repaired_count, 1)
            self.assertEqual(result.issues[0].category, ISSUE_CURRENT_INVALID)
            self.assertEqual(meta_data["uuid"], plan_uuid)
            self.assertEqual(meta_data["recording"], {"timestamp": True})
            self.assertNotIn("senior_setting", meta_data)

    def test_high_version_only_warns_and_is_not_rewritten(self):
        with tempfile.TemporaryDirectory(dir="test") as temp_dir:
            path = Path(temp_dir) / "高版本方案.json"
            write_plan(path, {
                "uuid": "44444444-4444-4444-4444-444444444444",
                "version": "0.4",
                "faa_version": "v4.0.0",
                "tips": "不能由旧 FAA 改写",
                "future_option": {"active": True},
            })
            before = path.read_bytes()

            result = scan_and_migrate_tweak_plans(
                Path(temp_dir), CURRENT_VERSION, CURRENT_FAA_VERSION
            )

            self.assertEqual(result.high_version_count, 1)
            self.assertEqual(result.issues[0].category, ISSUE_HIGH_VERSION)
            self.assertEqual(path.read_bytes(), before)
            self.assertIn("您的FAA版本过低", result.startup_text())


if __name__ == "__main__":
    unittest.main()
