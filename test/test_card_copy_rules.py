import unittest

from function.core.faa.tweak_plan import battle_plan_has_creator_god_target
from function.core_battle.card_copy_rules import get_creator_god_safe_locations


class CreatorGodCopyRuleTest(unittest.TestCase):
    def test_only_full_three_by_three_centers_are_returned(self):
        locations = [
            "2-2", "2-3", "2-4",
            "3-2", "3-3", "3-4",
            "4-2", "4-3", "4-4",
            "7-4", "7-5", "7-6",
            "8-4", "8-5", "8-6",
            "9-4", "9-5", "9-6",
        ]
        self.assertEqual(
            get_creator_god_safe_locations(locations),
            ["3-3", "8-5"],
        )

    def test_incomplete_neighborhood_and_board_edges_are_rejected(self):
        self.assertEqual(
            get_creator_god_safe_locations(
                ["1-1", "1-2", "2-1", "2-2", "3-1", "3-2"]
            ),
            [],
        )
        self.assertEqual(
            get_creator_god_safe_locations(
                [
                    "4-3", "4-4", "4-5",
                    "5-3", "5-4", "5-5",
                    "6-3", "6-4",
                ]
            ),
            [],
        )

    def test_creator_god_requires_positive_kun_and_safe_center(self):
        def plan(kun, locations):
            return {
                "events": [
                    {
                        "action": {
                            "type": "loop_use_cards",
                            "cards": [{"kun": kun, "location": locations}],
                        }
                    }
                ]
            }

        full_area = [f"{column}-{row}" for column in range(2, 5) for row in range(2, 5)]
        self.assertTrue(battle_plan_has_creator_god_target(plan(1, full_area)))
        self.assertFalse(battle_plan_has_creator_god_target(plan(0, full_area)))
        self.assertFalse(battle_plan_has_creator_god_target(plan(1, ["3-3"])))


if __name__ == "__main__":
    unittest.main()
