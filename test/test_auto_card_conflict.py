import unittest
from unittest.mock import patch

from function.core.faa.tweak_plan import (
    get_auto_card_target_names,
    get_auto_timer_target_names,
)


def make_battle_plan(card_names=None, action_cards=None):
    card_names = card_names or []
    action_cards = action_cards or []
    return {
        "cards": [
            {"card_id": index, "name": name}
            for index, name in enumerate(card_names, start=1)
        ],
        "events": [
            {
                "trigger": {"type": "wave_timer", "wave_id": 0},
                "action": {"type": "loop_use_cards", "cards": action_cards},
            }
        ],
    }


class AutoCardConflictTest(unittest.TestCase):
    def setUp(self):
        self.stage_mat_card_names = ["木盘子", "麦芽糖浆"]
        self.card_types = [
            {
                "key": ["冷却辅助", "冷却拐"],
                "value": ["时间神", "转龙壶", "美味计时器"],
            },
            {
                "key": ["复制辅助"],
                "value": ["幻幻鸡", "创造神"],
            },
        ]
        self.safe_kun_action = {
            "card_id": 1,
            "location": [
                f"{column}-{row}"
                for column in range(2, 5)
                for row in range(2, 5)
            ],
            "kun": 2,
        }

    def targets(self, card_names):
        plan = make_battle_plan(card_names, [self.safe_kun_action])
        auto_targets = get_auto_card_target_names(
            stage_mat_card_names=self.stage_mat_card_names,
            battle_plan_tweak={"meta_data": {"enable_auto_card": {"timer": True}}},
            battle_plan=plan,
            card_types=self.card_types,
        )
        timer_targets = get_auto_timer_target_names(
            battle_plan_tweak={"meta_data": {"enable_auto_card": {"timer": True}}},
            battle_plan=plan,
            card_types=self.card_types,
        )
        return (*auto_targets, timer_targets)

    def test_direct_cards_cancel_only_their_automatic_features(self):
        self.assertEqual(
            self.targets(["木盘子-3", "极寒冰沙-2", "幻幻鸡", "美味计时器"]),
            (["麦芽糖浆"], [], ["创造神"], []),
        )

    def test_card_type_candidates_cancel_copy_and_timer_features(self):
        self.assertEqual(
            self.targets(["冷却辅助", "复制辅助"]),
            (["木盘子", "麦芽糖浆"], ["冰激凌"], [], []),
        )

    def test_runtime_discovers_all_available_card_stages(self):
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.card_types = []
        resources = {
            "card": {
                "准备房间": {
                    "用户自制卡-0.png": None,
                    "用户自制卡-2.png": None,
                    "用户自制卡-4.png": None,
                }
            }
        }

        with patch.object(faa_battle_preparation, "RESOURCE_P", resources):
            targets = preparation._card_name_to_tar_list("用户自制卡")

        self.assertEqual(targets, ["用户自制卡-4", "用户自制卡-2", "用户自制卡-0"])
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
