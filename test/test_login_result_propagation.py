"""验证登录返回值跨线程、嵌套任务和战斗重试的中断行为。"""

import ast
from pathlib import Path
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock, mock_open, patch

from function.core import todo


class LoginResultPropagationTest(unittest.TestCase):
    def setUp(self):
        self.signal = SimpleNamespace(PRINT_TO_UI=SimpleNamespace(emit=Mock()), DIALOG=SimpleNamespace(emit=Mock()))
        self.signals = patch.object(todo, "SIGNAL", self.signal)
        self.signals.start()
        self.addCleanup(self.signals.stop)

    def test_batch_collects_both_players_without_reporting_in_workers(self):
        task = SimpleNamespace(
            opt={"login_settings": {"fresh_resize_360_windows": False}},
            check_player=Mock(return_value=[1, 2]),
            faa_dict={
                1: SimpleNamespace(reload_game=Mock(return_value=(False, "账号未设置"))),
                2: SimpleNamespace(reload_game=Mock(return_value=(False, "连续十次刷新失败"))),
            },
        )
        with patch.object(todo.time, "sleep"):
            reason = todo.ThreadTodo.batch_reload_game(task, player=[1, 2])
        self.assertIn("1P：账号未设置", reason)
        self.assertIn("2P：连续十次刷新失败", reason)
        self.signal.DIALOG.emit.assert_not_called()
        self.assertFalse(any("刷新游戏, 完成" in str(call) for call in self.signal.PRINT_TO_UI.emit.call_args_list))

    def sequence_task(self, tasks):
        """隔离任务文件读取，保留任务分派和嵌套序列的真实代码。"""
        task = SimpleNamespace(
            task_sequence_uuid="test",
            model_end_print=Mock(), batch_reload_game=Mock(return_value="选服设置错误"),
            batch_get_warm_gift=Mock(), batch_top_up_money=Mock(return_value=None),
            batch_sign_in=Mock(return_value=None),
        )
        task.task_sequence = MethodType(todo.ThreadTodo.task_sequence, task)
        loader = patch.object(todo.json, "load", side_effect=tasks)
        opened = patch("builtins.open", mock_open(read_data="[]"))
        files = patch.object(todo, "get_task_sequence_list", return_value=["test.json"])
        for context in (loader, opened, files):
            context.start()
            self.addCleanup(context.stop)
        return task

    def test_nested_sequence_stops_before_next_task(self):
        task = self.sequence_task([
            [
                {"task_id": 1, "task_type": "任务序列", "task_args": {
                    "sequence_integer": 1, "task_sequence_uuid": "nested",
                }},
                {"task_id": 2, "task_type": "签到", "task_args": {"player": [1]}},
            ],
            [{"task_id": 1, "task_type": "刷新游戏", "task_args": {"player": [1]}}],
        ])
        self.assertEqual(task.task_sequence("主序列", 1, "test"), (False, False, "选服设置错误"))
        task.batch_sign_in.assert_not_called()
        task.model_end_print.assert_not_called()

    def test_top_up_recovery_failure_stops_sign_in(self):
        task = self.sequence_task([
            [{"task_id": 1, "task_type": "签到", "task_args": {"player": [1]}}],
        ])
        task.batch_top_up_money.return_value = "登录重试耗尽"
        result = task.task_sequence("主序列", 1, "test")
        self.assertEqual(result[2], "登录重试耗尽")
        task.batch_sign_in.assert_not_called()

    def test_multi_stage_failure_does_not_start_next_stage_or_wait_for_partner(self):
        quest = {
            "stage_id": "NO-1-1", "player": [1], "need_key": False, "max_times": 1,
            "dict_exit": {}, "global_plan_active": False, "deck": 1,
            "battle_plan_1p": "a", "battle_plan_2p": "b",
        }
        task = SimpleNamespace(
            todo_id=1, battle_1_1_n=Mock(return_value="登录超时"),
            signal_todo_lock=SimpleNamespace(emit=Mock()),
        )
        with patch.object(todo, "sleep") as wait:
            reason = todo.ThreadTodo.battle_1_n_n(task, [quest, dict(quest)], need_lock=True)
        self.assertEqual(reason, "登录超时")
        self.assertEqual(task.battle_1_1_n.call_count, 1)
        task.signal_todo_lock.emit.assert_not_called()
        wait.assert_not_called()

    def test_invitation_recovery_failure_stops_retry(self):
        players = {pid: SimpleNamespace(action_goto_stage=Mock(), action_exit=Mock()) for pid in (1, 2)}
        task = SimpleNamespace(faa_dict=players, invite=Mock(return_value=False),
                               batch_reload_game=Mock(return_value="刷新失败"))
        result = todo.ThreadTodo.goto_stage_and_invite(task, "NO-1-1", False, 1, 2)
        self.assertEqual(result, (False, "刷新失败"))
        self.assertEqual(task.invite.call_count, 3)
        task.batch_reload_game.assert_called_once_with()

    def test_second_task_thread_returns_failure_to_main_window(self):
        task = SimpleNamespace(todo_id=2, run_thread_2=Mock(return_value="2P登录失败"),
                               signal_task_failed=SimpleNamespace(emit=Mock()))
        todo.ThreadTodo.run(task)
        task.signal_task_failed.emit.assert_called_once_with("2P登录失败")
        self.signal.DIALOG.emit.assert_not_called()

    def test_main_window_reports_once_when_both_tasks_fail(self):
        # 仅提取接收槽，避免创建真实主窗口、读取用户配置和启动后台线程。
        root = Path(__file__).resolve().parents[1]
        source = ast.parse((root / "function/core/qmw_3_service.py").read_text(encoding="utf-8-sig"))
        handler = next(node for node in ast.walk(source)
                       if isinstance(node, ast.FunctionDef) and node.name == "stop_failed_task")
        window = SimpleNamespace(thread_todo_running=True)
        window.todo_end = Mock(side_effect=lambda: setattr(window, "thread_todo_running", False))
        logger = Mock()
        env = {"self": window, "CUS_LOGGER": logger, "SIGNAL": self.signal}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), "task_failure_receiver", "exec"), env)
        env["stop_failed_task"]("1P登录失败")
        env["stop_failed_task"]("2P登录失败")
        window.todo_end.assert_called_once_with()
        logger.error.assert_called_once()
        self.signal.DIALOG.emit.assert_called_once_with(title="登录错误", text="1P登录失败")

    def test_battle_refresh_failure_stops_remaining_rounds(self):
        players = {
            pid: SimpleNamespace(
                stage_info={"b_id": "NO-1-1"}, set_config_for_battle=Mock(), set_battle_plan=Mock(),
                check_stage_id_is_true=Mock(return_value=True), check_stage_is_active=Mock(return_value=True),
                check_level=Mock(return_value=True), action_exit=Mock(),
            ) for pid in (1, 2)
        }
        task = SimpleNamespace(
            faa_dict=players, goto_stage_and_invite=Mock(return_value=(True, None)),
            battle=Mock(return_value=(1, {}, 0)), batch_reload_game=Mock(return_value="登录超时"),
        )
        tweak = "00000000-0000-0000-0000-000000000000"
        with (
            patch.object(todo.g_resources, "RESOURCE_B", {"a": {}, "b": {}}),
            patch.object(todo.g_resources, "RESOURCE_T", {tweak: {}}),
            patch.object(todo.EXTRA, "BATTLE_PLAN_UUID_TO_PATH", {"a": "a.json", "b": "b.json"}),
            patch.object(todo.EXTRA, "TWEAK_BATTLE_PLAN_UUID_TO_PATH", {tweak: "tweak.json"}),
        ):
            result = todo.ThreadTodo.battle_1_1_n(
                task, stage_id="NO-1-1", player=[1, 2], need_key=False, max_times=3,
                dict_exit={}, global_plan_active=False, deck=1, battle_plan_1p="a", battle_plan_2p="b",
                quest_card=None, ban_card_list=None, max_card_num=None, extra_title=None,
            )
        self.assertEqual(result, "登录超时")
        self.assertEqual(task.battle.call_count, 1)
        task.batch_reload_game.assert_called_once_with(player=[2, 1])
        for player in players.values():
            player.action_exit.assert_not_called()

    def test_cross_server_second_player_failure_does_not_wait_for_first_player_loop(self):
        workers = []

        class Worker:
            def __init__(self, target, **kwargs):
                self.return_value = target()
                self.join = Mock()
                workers.append(self)

            def start(self):
                pass

            def is_alive(self):
                return self.return_value is None

        task = SimpleNamespace(
            faa_dict={1: SimpleNamespace(loop_cross_server=Mock(return_value=None)),
                      2: SimpleNamespace(loop_cross_server=Mock(return_value="2P登录失败"))},
            model_start_print=Mock(), model_end_print=Mock(), check_player=Mock(return_value=[1, 2]),
        )
        with patch.object(todo, "ThreadWithException", Worker), patch.object(todo, "sleep"):
            reason = todo.ThreadTodo.batch_loop_cross_server(task, player=[1, 2])
        self.assertIn("2P登录失败", reason)
        workers[0].join.assert_not_called()
        workers[1].join.assert_called_once()
        task.model_end_print.assert_not_called()


if __name__ == "__main__":
    unittest.main()
