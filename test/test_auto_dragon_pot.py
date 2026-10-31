"""自动转龙壶的配置、识别和每波动作回归测试。"""

import copy
import unittest
from unittest.mock import patch

from function.core.faa.battle_card_roles import ROLE_DRAGON_POT, ROLE_PLAN, ROLE_QUEST
from function.core.faa.tweak_plan import (
    build_auto_cooldown_card,
    get_auto_dragon_pot_target_names,
    get_auto_timer_target_names,
    get_tweak_plan_auto_card_enabled,
)
from function.core.tweak_plan_editor_model import TweakPlanDraft
from test.test_auto_timer import make_battle_plan
from test import test_battle_card_role_integration as integration


class AutoDragonPotTest(unittest.TestCase):
    def setUp(self):
        self.plan = make_battle_plan(
            action_cards=[{"card_id": 1, "kun": 2, "location": ["9-4"]}],
        )

    def test_defaults_on_and_can_be_disabled_independently(self):
        self.assertTrue(get_tweak_plan_auto_card_enabled({})["dragon_pot"])
        self.assertEqual(get_auto_dragon_pot_target_names({}, self.plan), ["转龙壶"])
        for timer_enabled, dragon_enabled in ((False, True), (True, False)):
            tweak = {"meta_data": {"enable_auto_card": {
                "timer": timer_enabled, "dragon_pot": dragon_enabled,
            }}}
            self.assertEqual(
                get_auto_dragon_pot_target_names(tweak, self.plan),
                ["转龙壶"] if dragon_enabled else [],
            )
            self.assertEqual(
                get_auto_timer_target_names(tweak, self.plan),
                ["美味计时器"] if timer_enabled else [],
            )

    def test_requires_positive_kun_target_and_deduplicates_plan_cards(self):
        for kun in (0, -1, True):
            with self.subTest(kun=kun):
                plan = make_battle_plan(action_cards=[{"kun": kun, "location": ["5-4"]}])
                self.assertEqual(get_auto_dragon_pot_target_names({}, plan), [])
        for name in ("转龙壶", "转龙壶-2", "冷却辅助", "冷却拐", "自定义冷却卡"):
            with self.subTest(name=name):
                plan = copy.deepcopy(self.plan)
                plan["cards"] = [{"card_id": 1, "name": name}]
                card_types = [{"key": ["自定义冷却卡"], "value": ["转龙壶"]}]
                self.assertEqual(get_auto_dragon_pot_target_names({}, plan, card_types), [])
                self.assertEqual(
                    get_auto_dragon_pot_target_names({}, plan, card_types, exclude_plan_cards=False),
                    ["转龙壶"],
                )

    def test_uses_timer_target_order_and_second_job_offset(self):
        cards = [
            {"kun": 1, "location": ["1-1"]},
            {"kun": 4, "location": ["9-4", "7-4"]},
            {"kun": 4, "location": ["3-3"]},
        ]
        for second_job, location in ((False, "9-4"), (True, "8-4")):
            info = {"name": "转龙壶", "card_id": 8, "second_job": second_job}
            action = build_auto_cooldown_card(info, cards)
            self.assertEqual(action["name"], "转龙壶")
            self.assertEqual(action["card_id"], 8)
            self.assertEqual(action["location"], [location])
            self.assertFalse(action["queue"])
            self.assertFalse(action["ergodic"])
            self.assertEqual(action["kun"], 0)
        self.assertIsNone(build_auto_cooldown_card(info, [{"kun": 0, "location": ["1-1"]}]))
        self.assertIsNone(build_auto_cooldown_card(None, cards))

    def test_editor_preserves_inheritance_and_explicit_switch(self):
        inherited = TweakPlanDraft.from_mapping({"meta_data": {}})
        self.assertIsNone(inherited.enable_auto_card["dragon_pot"])
        self.assertNotIn("enable_auto_card", inherited.to_mapping()["meta_data"])
        for enabled in (True, False):
            draft = TweakPlanDraft.from_mapping({"meta_data": {
                "enable_auto_card": {"dragon_pot": enabled},
            }})
            self.assertEqual(
                draft.to_mapping()["meta_data"]["enable_auto_card"],
                {"dragon_pot": enabled},
            )


class AutoDragonPotRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def make_faa(self, plan, quest_card=None):
        """复用既有卡槽集成测试的最小 FAA 对象。"""
        return integration.BattleCardRoleIntegrationTest.make_faa(self, plan, quest_card)

    def test_auto_carry_quest_merge_and_limit(self):
        from function.core.faa.faa_battle_preparation import BattlePreparation

        preparation = BattlePreparation.__new__(BattlePreparation)
        preparation.battle_plan = make_battle_plan(
            card_names=["产火卡", "输出卡"],
            action_cards=[{"card_id": 2, "kun": 1, "location": ["5-4"]}],
        )
        preparation.battle_plan_tweak = {}
        preparation.stage_info = {"mat_card": []}
        preparation.card_types = []
        preparation.max_card_num = None
        preparation.quest_card = "转龙壶"
        preparation.ban_card_list = []
        preparation.print_debug = lambda text: None
        preparation._card_name_to_tar_list = lambda card_name: [f"{card_name}-2"]

        required = preparation._auto_carry_card_get_card_name_list_from_battle_plan()
        for card in required:
            card["names"] = preparation._card_name_to_tar_list(card["name"])
        preparation._auto_carry_card_add_quest_card(required)
        preparation.max_card_num = 3
        required = preparation._auto_carry_card_apply_limit(required)

        self.assertEqual([card["name"] for card in required], ["产火卡", "输出卡", "转龙壶"])
        self.assertEqual(required[-1]["roles"], [ROLE_DRAGON_POT, ROLE_QUEST])
        self.assertFalse(required[-1]["can_failed"])

    def test_manual_scan_uses_real_slot_and_merges_quest_role(self):
        from function.core.faa import faa_core

        plan = make_battle_plan(
            card_names=["转龙壶"],
            action_cards=[{"card_id": 1, "kun": 1, "location": ["9-4"]}],
        )
        faa = self.make_faa(plan, quest_card="转龙壶")
        faa.auto_carry_card = False
        faa.card_types = []
        faa.handle = 1
        faa.handle_360 = 2
        faa.bp_card = {1: [195, 10], 2: [250, 10]}
        faa.print_info = lambda text: None
        faa.battle_card_plan = [
            integration.make_resolved_card("方案卡1", [ROLE_PLAN], 1, 1),
            integration.make_resolved_card("转龙壶", [ROLE_QUEST], 2),
        ]
        resources = {"card": {"战斗": {"转龙壶-2-1.png": "dragon_template"}}}

        with (
            patch.object(faa_core, "RESOURCE_P", resources),
            patch.object(faa_core, "capture_image_png", return_value=None),
            patch.object(faa_core, "match_p_in_w", return_value=(2, [70, 5])),
            patch.object(faa_core.time, "sleep"),
        ):
            faa.init_mat_smoothie_kun_card_info()

        self.assertEqual(faa.dragon_pot_info["slot_id"], 2)
        self.assertTrue(faa.dragon_pot_info["second_job"])
        self.assertEqual(faa.dragon_pot_info["roles"], [ROLE_QUEST, ROLE_DRAGON_POT])
        self.assertEqual(len(faa.battle_card_plan), 2)

        faa.init_battle_plan_card(0)
        actions = [card for card in faa.battle_plan_card if card["slot_id"] == 2]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["location"], ["8-4"])
        self.assertEqual(actions[0]["coordinate_from"], [250, 10])

    def test_missing_templates_clear_previous_detection_and_skip_auto_use(self):
        from function.core.faa import faa_core

        faa = self.make_faa(integration.make_battle_plan(1, kun_id=1))
        faa.card_types = []
        faa.handle = 1
        faa.handle_360 = 2
        faa.print_info = lambda text: None
        faa.battle_card_plan = [integration.make_resolved_card("方案卡1", [ROLE_PLAN], 1, 1)]
        faa.dragon_pot_info = {
            "name": "转龙壶", "card_id": None, "slot_id": 2, "second_job": True,
        }

        with (
            patch.object(faa_core, "RESOURCE_P", {"card": {"战斗": {}}}),
            patch.object(faa_core, "capture_image_png", return_value=None),
            patch.object(faa_core, "match_p_in_w") as matcher,
            patch.object(faa_core.time, "sleep"),
        ):
            faa.init_mat_smoothie_kun_card_info()

        matcher.assert_not_called()
        self.assertIsNone(faa.dragon_pot_info)
        faa.init_battle_plan_card(0)
        self.assertEqual([card["name"] for card in faa.battle_plan_card], ["方案卡1"])

    def test_cooldown_cards_coexist_and_follow_each_wave(self):
        plan = integration.make_battle_plan(1, kun_id=1)
        plan["events"].extend([
            {"trigger": {"type": "wave_timer", "wave_id": 1},
             "action": {"type": "loop_use_cards", "cards": [
                 {"card_id": 1, "kun": 0, "location": ["2-2"]},
             ]}},
            {"trigger": {"type": "wave_timer", "wave_id": 2},
             "action": {"type": "loop_use_cards", "cards": [
                 {"card_id": 1, "kun": 3, "location": ["1-3"]},
             ]}},
        ])
        faa = self.make_faa(plan)
        faa.battle_card_plan = [integration.make_resolved_card("方案卡1", [ROLE_PLAN], 1, 1)]
        faa.timer_info = {
            "name": "美味计时器", "card_id": None, "slot_id": 2, "second_job": False,
        }
        faa.dragon_pot_info = {
            "name": "转龙壶", "card_id": None, "slot_id": 3, "second_job": True,
        }
        faa.smoothie_info = {"name": "极寒冰沙", "slot_id": 4}
        original = copy.deepcopy(plan)

        for wave, expected_locations in ((0, [["9-7"], ["8-7"]]), (1, []), (2, [["1-3"], ["2-3"]])):
            with self.subTest(wave=wave):
                faa.init_battle_plan_card(wave)
                support_cards = [card for card in faa.battle_plan_card if card["name"] in ("美味计时器", "转龙壶")]
                self.assertEqual([card["location"] for card in support_cards], expected_locations)
                self.assertEqual(faa.battle_plan_card[-1]["name"], "极寒冰沙")
        self.assertEqual(faa.battle_plan, original)


if __name__ == "__main__":
    unittest.main()
