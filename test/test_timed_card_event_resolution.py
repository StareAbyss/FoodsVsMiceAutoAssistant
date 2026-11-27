import copy
import unittest

from function.core.faa.battle_card_roles import (
    ROLE_PLAN,
    make_card_requirement,
    resolve_insert_use_card_events,
)


def make_resolved_plan_card(plan_id: int, slot_id: int) -> dict:
    """创建已经完成方案 ID 到真实槽位映射的测试卡片。"""
    card = make_card_requirement(
        name=f"方案卡{plan_id}",
        roles=[ROLE_PLAN],
        plan_id=plan_id,
        can_failed=False,
        source="battle_plan",
    )
    card["slot_id"] = slot_id
    return card


def make_timed_event(
        plan_id: int,
        *,
        location: str,
        before_shovel: bool = False,
        after_shovel: bool = False,
) -> dict:
    """创建包含完整前铲和后铲字段的定时放卡事件。"""
    return {
        "trigger": {
            "type": "wave_timer",
            "wave_id": 0,
            "time": 5.0,
        },
        "action": {
            "type": "insert_use_card",
            "card_id": plan_id,
            "location": location,
            "before_shovel": before_shovel,
            "after_shovel": after_shovel,
            "after_shovel_time": 1.0,
        },
    }


class TimedCardEventResolutionTest(unittest.TestCase):
    def test_removed_card_event_is_deleted_and_retained_card_uses_real_slot(self):
        """
        方案卡 2 未携带时，其整个定时事件必须消失；方案卡 3 前移后必须使用槽位 2。

        被删除事件包含前铲和后铲，用于确认这些附属动作不会脱离主体事件继续执行。
        """
        events = [
            make_timed_event(
                2,
                location="2-2",
                before_shovel=True,
                after_shovel=True,
            ),
            make_timed_event(
                3,
                location="3-3",
                before_shovel=True,
                after_shovel=True,
            ),
        ]
        original_events = copy.deepcopy(events)
        cards = [
            make_resolved_plan_card(1, 1),
            make_resolved_plan_card(3, 2),
        ]

        result = resolve_insert_use_card_events(
            events=events,
            cards=cards,
            resolved_plan_ready=True,
        )

        self.assertEqual(events, original_events)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["action"]["card_id"], 3)
        self.assertEqual(result[0]["action"]["plan_id"], 3)
        self.assertEqual(result[0]["action"]["slot_id"], 2)
        self.assertEqual(result[0]["action"]["location"], "3-3")

    def test_unresolved_legacy_call_keeps_original_slot_behavior(self):
        """没有经过战备实体卡解析的旧调用仍将原始方案 ID 作为槽位。"""
        result = resolve_insert_use_card_events(
            events=[make_timed_event(3, location="3-3")],
            cards=[],
            resolved_plan_ready=False,
        )

        self.assertEqual(result[0]["action"]["plan_id"], 3)
        self.assertEqual(result[0]["action"]["slot_id"], 3)

if __name__ == "__main__":
    unittest.main()
