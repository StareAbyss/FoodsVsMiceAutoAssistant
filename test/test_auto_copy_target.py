import unittest

from function.core.faa.tweak_plan import (
    get_auto_card_target_names,
    get_kun_cards_for_wave,
)


def make_battle_plan(action_cards):
    return {
        "cards": [{"card_id": 1, "name": "测试目标"}],
        "events": [
            {
                "trigger": {"type": "wave_timer", "wave_id": 0},
                "action": {"type": "loop_use_cards", "cards": action_cards},
            }
        ],
    }


class AutoCopyTargetTest(unittest.TestCase):
    def test_copy_cards_are_not_carried_without_positive_kun_target(self):
        targets = get_auto_card_target_names(
            stage_mat_card_names=[],
            battle_plan_tweak={},
            battle_plan=make_battle_plan([
                {"card_id": 1, "location": ["3-3"], "kun": 0},
            ]),
            card_types=[],
        )

        self.assertEqual(targets[2], [])

    def test_positive_kun_target_enables_available_copy_cards(self):
        targets = get_auto_card_target_names(
            stage_mat_card_names=[],
            battle_plan_tweak={},
            battle_plan=make_battle_plan([
                {"card_id": 1, "location": ["3-3"], "kun": 1},
            ]),
            card_types=[],
        )

        self.assertEqual(targets[2], ["幻幻鸡"])

    def test_copy_cards_can_be_reenabled_on_a_later_wave(self):
        detected = [
            {"name": "幻幻鸡", "card_id": 7},
            {"name": "创造神", "card_id": 8},
        ]

        first_wave = get_kun_cards_for_wave(
            detected,
            [{"card_id": 1, "location": ["1-1"], "kun": 0}],
        )
        later_wave = get_kun_cards_for_wave(
            detected,
            [{"card_id": 1, "location": ["1-1"], "kun": 2}],
        )

        self.assertEqual(first_wave, [])
        self.assertEqual(later_wave, detected)
        self.assertIsNot(later_wave, detected)


if __name__ == "__main__":
    unittest.main()
