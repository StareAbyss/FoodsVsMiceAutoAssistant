import ast
import math
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

def load_check_timer():
    """隔离加载真实检测线程，避免导入战斗模块时创建窗口或清空运行日志。"""
    path = Path(__file__).resolve().parents[2] / "function/core_battle/card_manager.py"
    source = ast.parse(path.read_text(encoding="utf-8"))
    timer_class = next(
        node for node in source.body
        if isinstance(node, ast.ClassDef) and node.name == "ThreadCheckTimer"
    )
    namespace = {
        "QThread": object,
        "math": math,
        "capture_image_png": Mock(return_value=object()),
        "EXTRA": SimpleNamespace(EXTRA_LOG_BATTLE=False),
    }
    exec(compile(ast.Module(body=[timer_class], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["ThreadCheckTimer"]


class BattleQueueRefreshTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.timer_class = load_check_timer()

    def make_timer(self, player, interval=None, active=True):
        """构造已进入单人战斗的玩家，保留队列刷新这一真实执行路径。"""
        tweak = {"meta_data": {}}
        if interval is not None:
            tweak["meta_data"]["cd_after_use_random"] = {
                "active": active,
                "range": interval,
            }
        faa = SimpleNamespace(
            player=player,
            battle_plan_tweak=tweak,
            print_info=Mock(),
            is_main=True,
            is_auto_battle=True,
            is_group=False,
            handle=player,
            handle_360=player + 10,
            check_end=Mock(return_value=False),
            use_key=Mock(return_value=False),
            check_wave=Mock(return_value=False),
            update_fire_elemental_1000=Mock(),
            use_gem_skill=Mock(),
            auto_pickup=Mock(),
        )
        card_queue = Mock()
        timer = self.timer_class(
            card_queue=card_queue,
            faa=faa,
            kun_cards=[],
            check_interval=1,
            signal_change_card_plan=Mock(),
            signal_used_key=Mock(),
            signal_stop=Mock(),
            thread_dict={},
        )
        return timer, card_queue

    def test_slow_card_preset_populates_queue_for_both_solo_players(self):
        for player in (1, 2):
            with self.subTest(player=player):
                timer, card_queue = self.make_timer(player, [0.05, 0.25])
                timer.check()
                card_queue.init_card_queue.assert_called_once()
                timer.check()
                self.assertEqual(card_queue.init_card_queue.call_count, 2)

    def test_zero_and_sub_round_intervals_still_populate_queue(self):
        for interval in ([0, 0], [0.01, 0.01], [0.055, 0.275]):
            with self.subTest(interval=interval):
                timer, card_queue = self.make_timer(2, interval)
                timer.check()
                card_queue.init_card_queue.assert_called_once()

    def test_long_random_intervals_do_not_skip_queue_refresh_or_change_check_interval(self):
        for player in (1, 2):
            for interval in ([0.2, 0.2], [0.2, 0.4], [3, 5]):
                with self.subTest(player=player, interval=interval):
                    timer, card_queue = self.make_timer(player, interval)
                    for round_number in range(1, 8):
                        timer.check()
                        self.assertEqual(card_queue.init_card_queue.call_count, round_number)
                        self.assertEqual(card_queue.queue.clear.call_count, round_number)
                        self.assertEqual(card_queue.init_card_queue.call_args.kwargs["check_interval"], 1)
                    self.assertEqual(timer.check_interval, 1)

    def test_default_and_disabled_random_interval_refill_each_round(self):
        for interval in (None, [0.05, 0.25]):
            with self.subTest(interval=interval):
                timer, card_queue = self.make_timer(2, interval, active=False)
                for _ in range(3):
                    timer.check()
                self.assertEqual(card_queue.init_card_queue.call_count, 3)

    def test_disabled_auto_battle_does_not_populate_queue(self):
        timer, card_queue = self.make_timer(2)
        timer.faa.is_auto_battle = False
        timer.check()
        card_queue.init_card_queue.assert_not_called()

    def test_battle_end_stops_checks_without_refilling_queue(self):
        timer, card_queue = self.make_timer(2, [3, 5])
        timer.faa.check_end.return_value = True
        timer.check()
        card_queue.init_card_queue.assert_not_called()
        timer.signal_stop.emit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
