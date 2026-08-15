import json
import tempfile
import unittest
from pathlib import Path

from test.complex_battle_runner.runner import (
    load_plan_library,
    resolve_plan_reference,
    validate_battle_config,
)


class ComplexBattleRunnerConfigTest(unittest.TestCase):
    def test_plan_reference_accepts_file_name_and_uuid(self):
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / "测试方案.json"
            plan_path.write_text(
                json.dumps({"meta_data": {"uuid": "test-uuid"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            names, paths, _ = load_plan_library(Path(directory), "战斗方案")

        self.assertEqual(resolve_plan_reference("测试方案", names, paths, "战斗方案"), "test-uuid")
        self.assertEqual(resolve_plan_reference("测试方案.json", names, paths, "战斗方案"), "test-uuid")
        self.assertEqual(resolve_plan_reference("test-uuid", names, paths, "战斗方案"), "test-uuid")

    def test_duplicate_uuid_is_rejected_without_rewriting_files(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            for name in ("方案一", "方案二"):
                (directory_path / f"{name}.json").write_text(
                    json.dumps({"meta_data": {"uuid": "same-uuid"}}, ensure_ascii=False),
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(ValueError, "UUID 冲突"):
                load_plan_library(directory_path, "战斗方案")

    def test_current_battle_config_shape_is_valid(self):
        validate_battle_config({
            "stage_id": "NO-1-1",
            "player": [2, 1],
            "max_times": 1,
            "need_key": True,
            "deck": 0,
            "battle_plan_1p": "!通用-海星-1P",
            "battle_plan_2p": "!通用-海星-2P",
            "battle_plan_tweak": "!默认",
            "quest_card": None,
            "ban_card_list": [],
            "max_card_num": None,
            "global_plan_active": False,
            "is_cu": False,
            "dict_exit": {
                "other_time_player_a": [],
                "other_time_player_b": [],
                "last_time_player_a": ["竞技岛"],
                "last_time_player_b": ["竞技岛"],
            },
        })


if __name__ == "__main__":
    unittest.main()
