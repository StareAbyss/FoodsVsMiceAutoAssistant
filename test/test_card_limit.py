import unittest

from function.core.faa.card_limit import (
    get_manual_card_slots_to_remove,
    get_required_manual_mat_slot,
    get_retained_plan_card_count,
    normalize_max_card_num,
    stage_requires_mat,
)


class CardLimitTest(unittest.TestCase):
    def test_limit_is_normalized_when_task_is_assigned(self):
        self.assertIsNone(normalize_max_card_num(None))
        self.assertEqual(normalize_max_card_num(1), 3)
        self.assertEqual(normalize_max_card_num(2), 3)
        self.assertEqual(normalize_max_card_num(5), 5)

    def test_runtime_retention_does_not_repeat_upstream_normalization(self):
        """运行时只消费任务层给出的限制值，最小三张规则不应藏在战斗内部。"""
        self.assertEqual(
            get_retained_plan_card_count(
                plan_card_count=5,
                max_card_num=2,
                stage_info={"mat_card": ["木盘子"], "mat_card_type": "水面"},
                has_quest_card=True,
            ),
            0,
        )

    def test_mat_requirement_uses_resolved_candidate_priority(self):
        self.assertFalse(stage_requires_mat({"mat_card": [], "mat_card_type": ""}))
        self.assertTrue(stage_requires_mat({"mat_card": [], "mat_card_type": "岩浆"}))
        self.assertEqual(
            get_required_manual_mat_slot({
                "mat_card": ["葡萄味软糖", "木盘子-2", "麦芽糖-1"],
                "mat_card_type": "海底",
            }),
            "wood",
        )
        self.assertEqual(
            get_required_manual_mat_slot({
                "mat_card": ["葡萄味软糖", "麦芽糖-1", "木盘子-2"],
                "mat_card_type": "水面",
            }),
            "malt",
        )

    def test_retention_priority_is_mat_then_quest_then_plan_id(self):
        stage_info = {"mat_card": ["麦芽糖-1"], "mat_card_type": "海底"}
        self.assertEqual(
            get_retained_plan_card_count(8, 5, stage_info, True),
            3,
        )
        self.assertEqual(
            get_retained_plan_card_count(8, 5, stage_info, False),
            4,
        )

    def test_manual_slots_follow_fixed_layout_and_are_removed_descending(self):
        stage_info = {"mat_card": ["麦芽糖-1"], "mat_card_type": "海底"}
        removed = get_manual_card_slots_to_remove(
            plan_card_count=5,
            max_card_num=4,
            stage_info=stage_info,
            has_quest_card=True,
        )

        # 原布局：1..5 方案、6 任务空位、7 木盘子、8 麦芽糖。
        # 限四张后保留方案 1/2、任务卡 6 和麦芽糖 8；倒序删除其余位置。
        self.assertEqual(removed, sorted(removed, reverse=True))
        self.assertTrue({1, 2, 6, 8}.isdisjoint(removed))
        self.assertTrue({3, 4, 5, 7, 9, 21}.issubset(removed))

    def test_no_mat_keeps_as_many_low_plan_ids_as_limit_allows(self):
        removed = get_manual_card_slots_to_remove(
            plan_card_count=5,
            max_card_num=3,
            stage_info={"mat_card": [], "mat_card_type": ""},
            has_quest_card=False,
        )
        self.assertTrue({1, 2, 3}.isdisjoint(removed))
        self.assertTrue({4, 5, 6, 7, 21}.issubset(removed))

    def test_manual_removal_uses_fixed_two_page_slot_mapping(self):
        """左页固定为 1..11，右页固定为 11..21，重叠的 11 只在右页删除。"""
        from unittest.mock import patch

        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.handle = 123
        preparation.max_card_num = 3
        preparation.quest_card = None
        preparation.battle_plan = {"cards": []}
        preparation.stage_info = {"mat_card": [], "mat_card_type": ""}

        clicks = []

        def record_click(**kwargs):
            clicks.append((kwargs["x"], kwargs["y"]))

        with (
            patch.object(
                faa_battle_preparation,
                "get_manual_card_slots_to_remove",
                return_value=[21, 12, 11, 10, 1],
            ),
            patch.object(
                faa_battle_preparation.T_ACTION_QUEUE_TIMER,
                "add_click_to_queue",
                side_effect=record_click,
            ),
            patch.object(faa_battle_preparation.time, "sleep"),
        ):
            preparation._manual_carry_remove_cards_for_card_num_limit()

        # 先点到最右页；右页可见槽 1/2/11 分别对应全局槽 11/12/21。
        self.assertEqual(clicks[:6], [(930, 85)] * 6)
        self.assertEqual(clicks[6:9], [(890, 73), (458, 73), (410, 73)])
        # 再回到最左页；11 号重叠槽不应在这里被点击第二次。
        self.assertEqual(clicks[9:15], [(930, 55)] * 6)
        self.assertEqual(clicks[15:], [(842, 73), (410, 73)])
        self.assertEqual(clicks.count((410, 73)), 2)
        self.assertIsNotNone(app)

    def test_battle_actions_map_plan_quest_and_mat_to_real_card_ids(self):
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa.faa_core import FAABase

        faa = FAABase.__new__(FAABase)
        faa.is_group = False
        faa.is_main = True
        faa.player = 1
        faa.max_card_num = 3
        faa.quest_card = "任务卡"
        faa.banned_card_index = None
        faa.bp_cell = {
            f"{column}-{row}": [column * 10, row * 10]
            for column in range(1, 10)
            for row in range(1, 8)
        }
        faa.bp_card = {card_id: [card_id * 50, 10] for card_id in range(1, 6)}
        faa.stage_info = {
            "mat_card": ["麦芽糖-1"],
            "mat_card_type": "海底",
            "mat_cell": ["2-2"],
            "obstacle": [],
        }
        faa.battle_plan = {
            "cards": [
                {"card_id": card_id, "name": f"方案卡{card_id}"}
                for card_id in range(1, 6)
            ],
            "events": [
                {
                    "trigger": {"type": "wave_timer", "wave_id": 0},
                    "action": {
                        "type": "loop_use_cards",
                        "cards": [
                            {
                                "card_id": card_id,
                                "location": ["1-1"],
                                "ergodic": False,
                                "queue": True,
                                "kun": 0,
                            }
                            for card_id in range(1, 6)
                        ],
                    },
                }
            ],
        }
        faa.battle_plan_tweak = {"meta_data": {"auto_mat_card": {"use_first": True}}}
        faa.mat_cards_info = [{"name": "麦芽糖", "card_id": 3}]
        faa.smoothie_info = None
        faa.timer_info = None
        faa.kun_cards_info = []
        faa.detected_kun_cards_info = []
        faa.print_debug = lambda text: None

        faa.init_battle_plan_card(wave=0)

        cards = {card["name"]: card for card in faa.battle_plan_card}
        self.assertEqual(cards["方案卡1"]["card_id"], 1)
        self.assertEqual(cards["方案卡1"]["slot_id"], 1)
        self.assertIsNone(cards["任务卡"]["card_id"])
        self.assertEqual(cards["任务卡"]["slot_id"], 2)
        self.assertIsNone(cards["麦芽糖"]["card_id"])
        self.assertEqual(cards["麦芽糖"]["slot_id"], 3)
        self.assertNotIn("方案卡2", cards)
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
