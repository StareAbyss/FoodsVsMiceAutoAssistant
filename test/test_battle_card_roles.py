import unittest

from function.core.faa.battle_card_roles import (
    ROLE_PLAN,
    ROLE_PRIMARY_MAT,
    ROLE_QUEST,
    ROLE_SMOOTHIE,
    add_role,
    apply_removed_slots,
    assign_successful_slot,
    attach_quest_role,
    get_plan_slot_map,
    make_card_requirement,
    merge_detected_card,
    retain_cards_by_role,
)


def make_card(name, roles, plan_id=None, source="extra"):
    card = make_card_requirement(
        name=name,
        roles=roles,
        plan_id=plan_id,
        can_failed=ROLE_PLAN not in roles and ROLE_PRIMARY_MAT not in roles,
        source=source,
    )
    card["names"] = [f"{name}-2", f"{name}-1"]
    return card


class BattleCardRolesTest(unittest.TestCase):
    def test_quest_role_merges_with_primary_mat_instead_of_adding_card(self):
        cards = [
            make_card("用户卡", [ROLE_PLAN], 1, "battle_plan"),
            make_card("木盘子", [ROLE_PRIMARY_MAT], source="mat"),
        ]

        owner = attach_quest_role(cards, ["木盘子-2", "木盘子-1"])

        self.assertIs(owner, cards[1])
        self.assertEqual(owner["roles"], [ROLE_PRIMARY_MAT, ROLE_QUEST])
        self.assertFalse(owner["can_failed"])
        self.assertEqual(len(cards), 2)

    def test_high_plan_id_with_quest_role_survives_card_limit(self):
        cards = [
            make_card(f"方案卡{plan_id}", [ROLE_PLAN], plan_id, "battle_plan")
            for plan_id in range(1, 6)
        ]
        primary_mat = make_card("木盘子", [ROLE_PRIMARY_MAT], source="mat")
        cards.append(primary_mat)
        add_role(cards[4], ROLE_QUEST)

        retained = retain_cards_by_role(cards, 3)

        self.assertEqual(
            [card.get("plan_id") for card in retained],
            [1, 5, None],
        )

        for slot_id, card in enumerate(retained, 1):
            assign_successful_slot(card, slot_id, card["names"][0])
        self.assertEqual(get_plan_slot_map(retained), {1: 1, 5: 2})

    def test_limit_priority_does_not_change_physical_order(self):
        cards = [
            make_card("方案卡1", [ROLE_PLAN], 1, "battle_plan"),
            make_card("独立任务卡", [ROLE_QUEST], source="quest"),
            make_card("第一承载", [ROLE_PRIMARY_MAT], source="mat"),
            make_card("冰沙", [ROLE_SMOOTHIE]),
        ]

        retained = retain_cards_by_role(cards, 3)

        self.assertEqual(
            [card["name"] for card in retained],
            ["方案卡1", "独立任务卡", "第一承载"],
        )

    def test_battle_scan_merges_auxiliary_role_by_slot(self):
        quest_card = make_card("冰激凌", [ROLE_QUEST], source="quest")
        quest_card["slot_id"] = 3
        cards = [quest_card]

        detected = merge_detected_card(
            cards,
            slot_id=3,
            name="极寒冰沙",
            role=ROLE_SMOOTHIE,
        )

        self.assertIs(detected, quest_card)
        self.assertEqual(len(cards), 1)
        self.assertEqual(detected["roles"], [ROLE_QUEST, ROLE_SMOOTHIE])

    def test_removed_physical_slots_do_not_modify_plan_identity(self):
        cards = [
            make_card(f"方案卡{plan_id}", [ROLE_PLAN], plan_id, "battle_plan")
            for plan_id in range(1, 4)
        ]
        for slot_id, card in enumerate(cards, 1):
            card["slot_id"] = slot_id

        apply_removed_slots(cards, [2])

        self.assertEqual(
            [(card["plan_id"], card["slot_id"]) for card in cards],
            [(1, 1), (3, 2)],
        )


if __name__ == "__main__":
    unittest.main()
