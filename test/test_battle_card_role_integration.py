import unittest

from function.core.faa.battle_card_roles import (
    ROLE_PLAN,
    ROLE_PRIMARY_MAT,
    ROLE_QUEST,
    ROLE_TIMER,
    make_card_requirement,
)


def make_resolved_card(name, roles, slot_id, plan_id=None):
    card = make_card_requirement(
        name=name,
        roles=roles,
        plan_id=plan_id,
        can_failed=False,
        source="battle_plan" if plan_id is not None else "extra",
    )
    card["slot_id"] = slot_id
    return card


def make_battle_plan(card_count, *, kun_id=None):
    return {
        "cards": [
            {"card_id": card_id, "name": f"方案卡{card_id}"}
            for card_id in range(1, card_count + 1)
        ],
        "events": [
            {
                "trigger": {"type": "wave_timer", "wave_id": 0},
                "action": {
                    "type": "loop_use_cards",
                    "cards": [
                        {
                            "card_id": card_id,
                            "location": ["9-7"] if card_id == kun_id else ["1-2"],
                            "ergodic": True,
                            "queue": True,
                            "kun": 2 if card_id == kun_id else 0,
                        }
                        for card_id in range(1, card_count + 1)
                    ],
                },
            }
        ],
    }


class BattleCardRoleIntegrationTest(unittest.TestCase):
    def make_faa(self, battle_plan, quest_card=None):
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa.faa_core import FAABase

        faa = FAABase.__new__(FAABase)
        faa.is_group = False
        faa.is_main = True
        faa.player = 1
        faa.max_card_num = 3
        faa.quest_card = quest_card
        faa.banned_card_index = None
        faa.bp_cell = {
            f"{column}-{row}": [column * 10, row * 10]
            for column in range(1, 10)
            for row in range(1, 8)
        }
        faa.bp_card = {
            card_id: [card_id * 50, 10]
            for card_id in range(1, 10)
        }
        faa.stage_info = {
            "mat_card": [],
            "mat_card_type": "",
            "mat_cell": ["1-1", "2-1", "3-1", "4-1"],
            "obstacle": [],
        }
        faa.battle_plan = battle_plan
        faa.battle_plan_tweak = {
            "meta_data": {"auto_mat_card": {"use_first": True}}
        }
        faa.mat_cards_info = []
        faa.smoothie_info = None
        faa.timer_info = None
        faa.kun_cards_info = []
        faa.detected_kun_cards_info = []
        faa.battle_card_plan = []
        faa.battle_card_plan_ready = True
        faa.print_debug = lambda text: None
        self.assertIsNotNone(app)
        return faa

    def test_quest_mat_role_emits_one_action_for_same_slot(self):
        faa = self.make_faa(make_battle_plan(1), quest_card="木盘子")
        faa.stage_info.update({
            "mat_card": ["木盘子"],
            "mat_card_type": "水面",
        })
        faa.battle_card_plan = [
            make_resolved_card("方案卡1", [ROLE_PLAN], 1, 1),
            make_resolved_card(
                "木盘子",
                [ROLE_PRIMARY_MAT, ROLE_QUEST],
                2,
            ),
        ]
        faa.mat_cards_info = [
            {
                "name": "木盘子",
                "card_id": None,
                "plan_id": None,
                "slot_id": 2,
                "roles": [ROLE_PRIMARY_MAT, ROLE_QUEST],
            }
        ]

        faa.init_battle_plan_card(0)

        slot_two_actions = [
            card for card in faa.battle_plan_card
            if card["slot_id"] == 2
        ]
        self.assertEqual(len(slot_two_actions), 1)
        self.assertEqual(slot_two_actions[0]["name"], "木盘子")
        self.assertIsNone(slot_two_actions[0]["card_id"])

    def test_quest_timer_role_uses_only_timer_action(self):
        faa = self.make_faa(
            make_battle_plan(1, kun_id=1),
            quest_card="美味计时器",
        )
        faa.battle_card_plan = [
            make_resolved_card("方案卡1", [ROLE_PLAN], 1, 1),
            make_resolved_card(
                "美味计时器",
                [ROLE_TIMER, ROLE_QUEST],
                2,
            ),
        ]
        faa.timer_info = {
            "name": "美味计时器",
            "card_id": None,
            "plan_id": None,
            "slot_id": 2,
            "roles": [ROLE_TIMER, ROLE_QUEST],
            "second_job": True,
        }

        faa.init_battle_plan_card(0)

        slot_two_actions = [
            card for card in faa.battle_plan_card
            if card["slot_id"] == 2
        ]
        self.assertEqual(len(slot_two_actions), 1)
        self.assertEqual(slot_two_actions[0]["location"], ["8-7"])
        self.assertFalse(slot_two_actions[0]["ergodic"])
        self.assertFalse(slot_two_actions[0]["queue"])

    def test_high_plan_id_quest_uses_explicit_slot_mapping(self):
        faa = self.make_faa(make_battle_plan(5), quest_card="油灯")
        faa.battle_card_plan = [
            make_resolved_card("方案卡1", [ROLE_PLAN], 1, 1),
            make_resolved_card("方案卡2", [ROLE_PLAN], 2, 2),
            make_resolved_card("油灯", [ROLE_PLAN, ROLE_QUEST], 3, 5),
        ]

        faa.init_battle_plan_card(0)

        self.assertEqual(
            [(card["card_id"], card["slot_id"]) for card in faa.battle_plan_card],
            [(1, 1), (2, 2), (5, 3)],
        )


if __name__ == "__main__":
    unittest.main()
