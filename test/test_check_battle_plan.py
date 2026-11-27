import copy
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from function.globals import EXTRA
from function.scattered import check_battle_plan


class CheckBattlePlanTest(unittest.TestCase):
    """验证普通刷新不会承担检查、迁移或写回职责。"""

    def setUp(self) -> None:
        self.old_battle_mapping = copy.deepcopy(EXTRA.BATTLE_PLAN_UUID_TO_PATH)

    def tearDown(self) -> None:
        EXTRA.BATTLE_PLAN_UUID_TO_PATH = self.old_battle_mapping

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )

    def test_refresh_only_rebuilds_uuid_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            plan_uuid = str(uuid.uuid4())
            path = folder / "当前方案.json"
            self._write_json(path, {
                "meta_data": {
                    "uuid": plan_uuid,
                    "version": "3.0",
                },
            })
            original_bytes = path.read_bytes()

            with (
                patch.object(check_battle_plan, "get_list_battle_plan", return_value=["当前方案"]),
                patch.dict(check_battle_plan.PATHS, {"battle_plan": str(folder)}),
                patch.object(check_battle_plan, "_write_json") as write_json,
            ):
                check_battle_plan.refresh_all_battle_plan()

            write_json.assert_not_called()
            self.assertEqual(path.read_bytes(), original_bytes)
            self.assertEqual(
                EXTRA.BATTLE_PLAN_UUID_TO_PATH,
                {plan_uuid: str(path)},
            )

    def test_explicit_check_migrates_v2_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            plan_uuid = str(uuid.uuid4())
            path = folder / "旧方案.json"
            self._write_json(path, {
                "uuid": plan_uuid,
                "tips": "旧方案",
                "player": ["1-1"],
                "card": {
                    "default": [{
                        "id": 1,
                        "name": "测试卡",
                        "ergodic": False,
                        "queue": True,
                        "location": ["1-1"],
                        "kun": 0,
                    }],
                    "wave": {},
                },
            })

            with (
                patch.object(check_battle_plan, "get_list_battle_plan", return_value=["旧方案"]),
                patch.dict(check_battle_plan.PATHS, {"battle_plan": str(folder)}),
            ):
                result = check_battle_plan.check_all_battle_plan()

            migrated = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(result.migrated_count, 1)
            self.assertEqual(migrated["meta_data"]["version"], EXTRA.BATTLE_PLAN_VERSION)
            self.assertEqual(migrated["meta_data"]["uuid"], plan_uuid)

    def test_high_version_battle_plan_is_not_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            path = folder / "高版本方案.json"
            self._write_json(path, {
                "meta_data": {
                    "uuid": str(uuid.uuid4()),
                    "tips": "来自未来版本",
                    "player_position": ["1-1"],
                    "version": "99.0",
                },
                "cards": [],
                "events": [],
            })
            original_bytes = path.read_bytes()

            with (
                patch.object(check_battle_plan, "get_list_battle_plan", return_value=["高版本方案"]),
                patch.dict(check_battle_plan.PATHS, {"battle_plan": str(folder)}),
                patch.object(check_battle_plan, "_write_json") as write_json,
            ):
                result = check_battle_plan.check_all_battle_plan()

            write_json.assert_not_called()
            self.assertEqual(path.read_bytes(), original_bytes)
            self.assertEqual(result.high_version_count, 1)
            self.assertTrue(result.has_issues)


if __name__ == "__main__":
    unittest.main()
