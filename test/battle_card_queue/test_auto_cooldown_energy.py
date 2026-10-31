"""自动冷却辅助卡的火苗门槛与状态试放测试。"""

import ast
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

from function.core.faa.battle_card_roles import ROLE_DRAGON_POT, ROLE_PLAN, ROLE_QUEST, ROLE_TIMER
from function.core.faa.tweak_plan import get_tweak_plan_random_interval


def load_card_class():
    """隔离加载真实 Card 类，避免测试导入完整 FAA 时创建窗口或改写运行日志。"""
    path = Path(__file__).resolve().parents[2] / "function/core_battle/card.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    card_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Card")
    namespace = {
        "FAA": object,
        "ROLE_DRAGON_POT": ROLE_DRAGON_POT,
        "ROLE_TIMER": ROLE_TIMER,
        "get_tweak_plan_random_interval": get_tweak_plan_random_interval,
        "np": np,
        "EXTRA": SimpleNamespace(LOWEST_FPS=10, EXTRA_LOG_BATTLE=False, SMOOTHIE_LOCK_TIME=0),
        "time": SimpleNamespace(sleep=Mock()),
        "CUS_LOGGER": Mock(),
        "T_ACTION_QUEUE_TIMER": Mock(),
        "RESOURCE_P": {"card": {"状态判定": {}}},
    }
    exec(compile(ast.Module(body=[card_class], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["Card"], namespace


class AutoCooldownEnergyTest(unittest.TestCase):
    def setUp(self):
        self.card_class, self.namespace = load_card_class()

    def make_card(self, name, roles, fire_ready, player=1, is_group=False):
        """构造带真实自动角色的 Card，并用模拟点击记录验证是否放卡。"""
        faa = SimpleNamespace(
            handle=player,
            handle_360=player + 10,
            need_key=False,
            is_auto_battle=True,
            player=player,
            battle_plan_tweak={},
            battle_plan_card=[{"name": name, "roles": roles}],
            click_sleep=0,
            stage_info={"mat_card_type": "", "mat_card": []},
            fire_elemental_1000=fire_ready,
            is_group=is_group,
            battle_lock=threading.Lock(),
        )
        card = self.card_class(set_priority=0, faa=faa)
        statuses = iter((True, False))
        card.fresh_status = Mock(side_effect=lambda: setattr(card, "status_usable", next(statuses)))
        card.choice_card = Mock()
        card.put_card = Mock()
        return card

    def test_low_fire_blocks_both_auto_cards_for_each_player(self):
        for name, role in (("美味计时器", ROLE_TIMER), ("转龙壶", ROLE_DRAGON_POT)):
            for player in (1, 2):
                with self.subTest(name=name, player=player):
                    card = self.make_card(name, [role, ROLE_QUEST], False, player=player)
                    self.assertFalse(card.use_card())
                    card.fresh_status.assert_not_called()
                    card.choice_card.assert_not_called()
                    card.put_card.assert_not_called()

    def test_high_fire_allows_both_cards_without_taking_smoothie_lock(self):
        self.namespace["EXTRA"].SMOOTHIE_LOCK_TIME = 7
        for name, role in (("美味计时器", ROLE_TIMER), ("转龙壶", ROLE_DRAGON_POT)):
            with self.subTest(name=name):
                card = self.make_card(name, [role], True, is_group=True)
                self.assertTrue(card.use_card())
                card.choice_card.assert_called_once()
                card.put_card.assert_called_once()
        self.assertEqual(self.namespace["EXTRA"].SMOOTHIE_LOCK_TIME, 7)

    def test_energy_changes_take_effect_on_every_attempt(self):
        for name, role in (("美味计时器", ROLE_TIMER), ("转龙壶", ROLE_DRAGON_POT)):
            with self.subTest(name=name):
                card = self.make_card(name, [role], False)
                self.assertFalse(card.use_card())
                card.faa.fire_elemental_1000 = True
                self.assertTrue(card.use_card())
                card.faa.fire_elemental_1000 = False
                self.assertFalse(card.use_card())
                card.put_card.assert_called_once()

    def test_low_fire_blocks_unknown_state_trial_and_high_fire_resumes_it(self):
        for name, role in (("美味计时器", ROLE_TIMER), ("转龙壶", ROLE_DRAGON_POT)):
            with self.subTest(name=name):
                card = self.make_card(name, [role], False)
                current = np.zeros((1, 36, 3), dtype=np.uint8)
                card.get_card_current_img = Mock(return_value=current)
                self.assertEqual(card.try_get_img_for_check_card_states(), 0)
                card.choice_card.assert_not_called()
                card.put_card.assert_not_called()

                card.faa.fire_elemental_1000 = True
                card.get_card_current_img = Mock(side_effect=(current, current + 1, current + 2))
                self.assertEqual(card.try_get_img_for_check_card_states(), 2)
                card.choice_card.assert_called_once()
                card.put_card.assert_called_once()

    def test_high_fire_still_requires_card_usable_status(self):
        for name, role in (("美味计时器", ROLE_TIMER), ("转龙壶", ROLE_DRAGON_POT)):
            with self.subTest(name=name):
                card = self.make_card(name, [role], True)
                card.fresh_status = Mock()
                card.status_usable = False
                self.assertFalse(card.use_card())
                card.put_card.assert_not_called()

    def test_plan_actions_and_existing_smoothie_gate_keep_their_rules(self):
        for name in ("产火卡", "美味计时器", "转龙壶"):
            with self.subTest(name=name):
                card = self.make_card(name, [ROLE_PLAN], False)
                self.assertTrue(card.use_card())
                card.put_card.assert_called_once()
        smoothie = self.make_card("极寒冰沙", [], False)
        self.assertFalse(smoothie.use_card())
        smoothie.put_card.assert_not_called()


if __name__ == "__main__":
    unittest.main()
