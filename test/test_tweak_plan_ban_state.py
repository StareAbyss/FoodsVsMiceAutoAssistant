import unittest

from function.core.faa.tweak_plan import get_auto_card_target_names, get_tweak_plan_ban_state


class TweakPlanBanStateTest(unittest.TestCase):
    def setUp(self):
        self.stage_mat_card_names = ["木盘子", "麦芽糖浆"]
        self.battle_plan_tweak = {"meta_data": {}}

    def test_default_state_keeps_all_auto_card_features(self):
        self.assertEqual(
            get_tweak_plan_ban_state(self.battle_plan_tweak),
            {
                "mat": False,
                "icecream": False,
                "god": False,
                "ikun": False,
                "coffee": False,
            },
        )
        self.assertEqual(
            get_auto_card_target_names(self.stage_mat_card_names, self.battle_plan_tweak),
            (["木盘子", "麦芽糖浆"], ["冰激凌"], ["幻幻鸡", "创造神"]),
        )

    def test_ban_state_removes_corresponding_auto_card_targets(self):
        self.battle_plan_tweak = {
            "meta_data": {
                "ban_state": {
                    "mat": True,
                    "icecream": True,
                    "god": True,
                    "ikun": True,
                }
            }
        }

        self.assertEqual(
            get_auto_card_target_names(self.stage_mat_card_names, self.battle_plan_tweak),
            ([], [], []),
        )

    def test_god_and_ikun_can_be_disabled_independently(self):
        self.battle_plan_tweak = {
            "meta_data": {
                "ban_state": {
                    "god": True,
                }
            }
        }
        self.assertEqual(
            get_auto_card_target_names(self.stage_mat_card_names, self.battle_plan_tweak),
            (["木盘子", "麦芽糖浆"], ["冰激凌"], ["幻幻鸡"]),
        )

        self.battle_plan_tweak["meta_data"]["ban_state"] = {"ikun": True}
        self.assertEqual(
            get_auto_card_target_names(self.stage_mat_card_names, self.battle_plan_tweak),
            (["木盘子", "麦芽糖浆"], ["冰激凌"], ["创造神"]),
        )

    def test_non_boolean_values_do_not_enable_ban(self):
        self.battle_plan_tweak = {
            "meta_data": {
                "ban_state": {
                    "mat": "true",
                    "icecream": 1,
                }
            }
        }

        ban_state = get_tweak_plan_ban_state(self.battle_plan_tweak)
        self.assertFalse(ban_state["mat"])
        self.assertFalse(ban_state["icecream"])


if __name__ == "__main__":
    unittest.main()
