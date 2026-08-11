import unittest

from function.core.faa.tweak_plan import (
    build_auto_timer_card,
    get_auto_timer_target_names,
    get_highest_kun_target,
    get_tweak_plan_auto_timer_enabled,
    offset_timer_location,
)


def make_battle_plan(card_names=None, action_cards=None):
    return {
        "cards": [
            {"card_id": index, "name": name}
            for index, name in enumerate(card_names or [], start=1)
        ],
        "events": [
            {
                "trigger": {"type": "wave_timer", "wave_id": 0},
                "action": {
                    "type": "loop_use_cards",
                    "cards": action_cards or [],
                },
            }
        ],
    }


class AutoTimerTest(unittest.TestCase):
    def test_timer_is_opt_in_and_requires_positive_kun_target(self):
        battle_plan = make_battle_plan(
            action_cards=[{"kun": 2, "location": ["5-4"]}],
        )
        self.assertFalse(get_tweak_plan_auto_timer_enabled({"meta_data": {}}))
        self.assertEqual(get_auto_timer_target_names({"meta_data": {}}, battle_plan), [])

        tweak = {"meta_data": {"enable_auto_card": {"timer": True}}}
        self.assertEqual(get_auto_timer_target_names(tweak, battle_plan), ["美味计时器"])

        no_target_plan = make_battle_plan(
            action_cards=[{"kun": 0, "location": ["5-4"]}],
        )
        self.assertEqual(get_auto_timer_target_names(tweak, no_target_plan), [])

    def test_existing_timer_is_not_carried_twice(self):
        tweak = {"meta_data": {"enable_auto_card": {"timer": True}}}
        battle_plan = make_battle_plan(
            card_names=["美味计时器"],
            action_cards=[{"kun": 1, "location": ["5-4"]}],
        )
        self.assertEqual(get_auto_timer_target_names(tweak, battle_plan), [])

        alias_plan = make_battle_plan(
            card_names=["冷却辅助"],
            action_cards=[{"kun": 1, "location": ["5-4"]}],
        )
        self.assertEqual(get_auto_timer_target_names(tweak, alias_plan), [])

    def test_highest_kun_target_keeps_original_order_on_tie(self):
        first = {"kun": 3, "location": ["2-2"]}
        second = {"kun": 3, "location": ["8-6"]}
        battle_plan = make_battle_plan(action_cards=[first, second])
        self.assertEqual(get_highest_kun_target(battle_plan), first)

    def test_timer_uses_first_location_of_highest_kun_target(self):
        cards = [
            {"kun": 1, "location": ["1-1"]},
            {"kun": 4, "location": ["7-3", "8-3"]},
        ]
        timer = {"name": "美味计时器", "card_id": 8, "second_job": False}
        self.assertEqual(
            build_auto_timer_card(timer, cards),
            {
                "name": "美味计时器",
                "card_id": 8,
                "location": ["7-3"],
                "ergodic": False,
                "queue": False,
                "kun": 0,
            },
        )

    def test_second_job_timer_moves_edge_target_inside_board(self):
        timer = {"name": "美味计时器", "card_id": 8, "second_job": True}
        self.assertEqual(
            build_auto_timer_card(timer, [{"kun": 1, "location": ["1-4"]}])["location"],
            ["2-4"],
        )
        self.assertEqual(offset_timer_location("9-4"), "8-4")
        self.assertEqual(offset_timer_location("5-4"), "5-4")


if __name__ == "__main__":
    unittest.main()
