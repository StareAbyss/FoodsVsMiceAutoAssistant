"""隔离识图和游戏操作，验证 core 内部的日氪恢复与调度边界。"""

import ast
from pathlib import Path
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock


class TopUpRecoveryTests(unittest.TestCase):
    def make_faa(self, pid, find_results):
        """加载原日氪方法，用识图结果序列替代真实窗口。

        Args:
            pid: 当前玩家编号。
            find_results: 每次循环识图的返回值，按业务调用顺序提供。

        Returns:
            玩家对象与隔离后的模块环境。
        """
        # 完整导入会初始化 Qt、动作队列并重建日志；提取原方法可保留现场日志。
        root = Path(__file__).resolve().parents[2]
        source = ast.parse((root / "function/core/faa/faa_core.py").read_text(encoding="utf-8"))
        base = next(node for node in source.body
                    if isinstance(node, ast.ClassDef) and node.name == "FAABase")
        method = next(node for node in base.body
                      if isinstance(node, ast.FunctionDef) and node.name == "sign_top_up_money")
        names = (
            "每日必充_判定点.png", "每日必充_领取.png", "每日必充_充值.png", "充值界面_游币兑换.png",
            "充值界面_游币兑换_已选中.png", "充值界面_请输入.png", "充值界面_请输入_已输入.png",
            "充值界面_立即充值.png", "充值界面_退出.png",
        )
        env = {
            "RESOURCE_P": {"top_up_money": {name: name for name in names}},
            "SIGNAL": SimpleNamespace(END=Mock(), PRINT_TO_UI=Mock()),
            "CUS_LOGGER": Mock(),
            "T_ACTION_QUEUE_TIMER": Mock(),
            "time": SimpleNamespace(sleep=Mock()),
            "get_window_position": Mock(return_value=(0, 0, 950, 596)),
            "get_system_dpi": Mock(return_value=96),
            "loop_match_p_in_w": Mock(side_effect=find_results),
        }
        exec(compile(ast.Module(body=[method], type_ignores=[]), "top_up_core", "exec"), env)
        faa = SimpleNamespace(
            player=pid, channel=f"测试窗口{pid}", handle=pid, handle_browser=pid + 10, handle_360=pid + 20,
            action_top_menu=Mock(), print_warning=Mock(), reload_game=Mock(return_value=(True, "")),
        )
        faa.sign_top_up_money = Mock(wraps=MethodType(env["sign_top_up_money"], faa))
        return faa, env

    def test_each_fatal_step_refreshes_current_player_before_returning(self):
        steps = (
            "点击游币兑换", "点击-氪金值输入框", "复核-氪金值输入1元",
            "点击-立刻充值按钮", "点击-退出充值界面按钮",
        )
        for pid in (1, 2):
            for index, step in enumerate(steps):
                with self.subTest(player=pid, step=step):
                    faa, env = self.make_faa(pid, [True, False, True] + [True] * index + [False])
                    result = faa.sign_top_up_money()
                    self.assertEqual(result, (f"步骤: 充值界面-{step}. 出现致命失误! 请联系开发者!", ""))
                    faa.reload_game.assert_called_once_with()
                    self.assertEqual(env["loop_match_p_in_w"].call_count, index + 4)
                    env["SIGNAL"].END.emit.assert_not_called()

    def test_exit_failure_does_not_repeat_payment_after_refresh(self):
        faa, env = self.make_faa(1, [True, False, True] + [True] * 4 + [False])
        faa.sign_top_up_money()
        faa.reload_game.assert_called_once_with()
        faa.action_top_menu.assert_called_once_with(mode="每日充值")
        env["T_ACTION_QUEUE_TIMER"].add_keyboard_up_down_to_queue.assert_called_once_with(
            handle=faa.handle_browser, key="1",
        )
        payments = [call for call in env["loop_match_p_in_w"].call_args_list
                    if call.kwargs["template"] == "充值界面_立即充值.png"]
        self.assertEqual(len(payments), 1)

    def test_normal_outcomes_do_not_refresh(self):
        completed = [True, False, True] + [True] * 5 + [False]
        cases = (
            ([False], "本期日氪没有假期票Skip... 或进入每日必冲失败, 请联系开发者!"),
            ([True, True, False], "你今天氪过, 但未领取, 已帮忙领取, 下次别忘了哦~"),
            ([True, False, False, False], "今天氪过了~"),
            (completed + [True, False], "成功氪金并领取~"),
            (completed + [False, False], "你游币用完了! 氪不了一点 orz"),
        )
        for results, expected in cases:
            with self.subTest(result=expected):
                faa, env = self.make_faa(1, results)
                self.assertEqual(faa.sign_top_up_money(), (expected, ""))
                faa.reload_game.assert_not_called()
                env["SIGNAL"].END.emit.assert_not_called()

    def test_refresh_failure_returns_reason_without_continuing_or_reporting(self):
        faa, env = self.make_faa(1, [True, False, True, False])
        faa.reload_game.return_value = (False, "连续10次刷新失败")
        message, reason = faa.sign_top_up_money()
        self.assertIn("充值界面", message)
        self.assertEqual(reason, "连续10次刷新失败")
        env["SIGNAL"].END.emit.assert_not_called()
        self.assertEqual(env["loop_match_p_in_w"].call_count, 4)

    def test_unexpected_refresh_exception_remains_reportable(self):
        faa, _env = self.make_faa(1, [True, False, True, False])
        faa.reload_game.side_effect = RuntimeError("刷新线程异常")
        with self.assertRaisesRegex(RuntimeError, "刷新线程异常"):
            faa.sign_top_up_money()

    def test_todo_continues_after_core_recovery_without_refreshing_again(self):
        root = Path(__file__).resolve().parents[2]
        source = ast.parse((root / "function/core/todo.py").read_text(encoding="utf-8"))
        todo_class = next(node for node in source.body
                          if isinstance(node, ast.ClassDef) and node.name == "ThreadTodo")
        todo_class.bases = []
        todo_class.body = [node for node in todo_class.body if isinstance(node, ast.FunctionDef)
                           and node.name in {"check_player", "batch_top_up_money"}]

        class ImmediateThread:
            """同步执行调度目标，不启动后台线程。"""

            def __init__(self, target, kwargs=None, **unused):
                self.target, self.kwargs = target, kwargs or {}

            def start(self):
                self.return_value = self.target(**self.kwargs)

            def join(self):
                pass

            def get_return_value(self):
                return self.return_value

        env = {
            "ThreadWithException": ImmediateThread, "CUS_LOGGER": Mock(),
            "SIGNAL": SimpleNamespace(PRINT_TO_UI=Mock()), "EXTRA": SimpleNamespace(ETHICAL_MODE=False),
        }
        exec(compile(ast.Module(body=[todo_class], type_ignores=[]), "top_up_batch", "exec"), env)
        task = env["ThreadTodo"]()
        task.faa_dict = {1: self.make_faa(1, [True, False, True, False])[0], 2: self.make_faa(2, [False])[0]}
        task.opt = {"advanced_settings": {"top_up_money_1p": True, "top_up_money_2p": True}}
        task.model_start_print, task.model_end_print, task.batch_reload_game = Mock(), Mock(), Mock()
        events = []

        for pid, faa in task.faa_dict.items():
            original = faa.sign_top_up_money

            def top_up(pid=pid, original=original):
                events.append(("top_up", pid))
                return original()

            faa.sign_top_up_money = Mock(side_effect=top_up)
            faa.reload_game.side_effect = lambda pid=pid: events.append(("reload", pid)) or (True, "")

        task.batch_top_up_money(player=[1, 2])
        self.assertEqual(events, [("top_up", 1), ("reload", 1), ("top_up", 2)])
        task.faa_dict[1].reload_game.assert_called_once_with()
        task.faa_dict[2].reload_game.assert_not_called()
        task.batch_reload_game.assert_not_called()
        task.model_end_print.assert_called_once_with(text="日氪")


if __name__ == "__main__":
    unittest.main()
