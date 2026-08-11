import unittest

from function.core.faa.tweak_plan import (
    get_tweak_plan_mat_card_first,
    insert_mat_cards_by_priority,
)


class AutoMatPriorityTest(unittest.TestCase):
    def test_default_keeps_existing_mat_first_behavior(self):
        self.assertTrue(get_tweak_plan_mat_card_first({"meta_data": {}}))
        self.assertTrue(get_tweak_plan_mat_card_first(None))

    def test_nested_setting_accepts_explicit_false(self):
        tweak = {"meta_data": {"auto_mat_card": {"use_first": False}}}
        self.assertFalse(get_tweak_plan_mat_card_first(tweak))

    def test_legacy_flat_setting_remains_compatible(self):
        tweak = {"meta_data": {"mat_card_first": False}}
        self.assertFalse(get_tweak_plan_mat_card_first(tweak))

    def test_mat_cards_can_run_before_all_plan_cards(self):
        cards = [{"name": "产火卡"}, {"name": "输出卡"}]
        mats = [{"name": "承载一"}, {"name": "承载二"}]
        self.assertEqual(
            insert_mat_cards_by_priority(cards, mats, True),
            [
                {"name": "承载一"},
                {"name": "承载二"},
                {"name": "产火卡"},
                {"name": "输出卡"},
            ],
        )

    def test_plan_first_keeps_only_first_plan_card_ahead_of_mats(self):
        cards = [{"name": "产火卡"}, {"name": "输出卡"}]
        mats = [{"name": "承载一"}, {"name": "承载二"}]
        self.assertEqual(
            insert_mat_cards_by_priority(cards, mats, False),
            [
                {"name": "产火卡"},
                {"name": "承载一"},
                {"name": "承载二"},
                {"name": "输出卡"},
            ],
        )

    def test_empty_plan_still_places_mats_first(self):
        self.assertEqual(
            insert_mat_cards_by_priority([], [{"name": "承载"}], False),
            [{"name": "承载"}],
        )


if __name__ == "__main__":
    unittest.main()
