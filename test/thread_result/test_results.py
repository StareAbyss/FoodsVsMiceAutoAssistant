"""使用真实公用线程和模拟业务对象验证返回值，不操作游戏窗口。"""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from function.common import thread_with_exception
from function.core import todo


class ThreadResultTests(unittest.TestCase):
    def setUp(self):
        self.signals = SimpleNamespace(PRINT_TO_UI=SimpleNamespace(emit=Mock()))
        self.traceback_dialog = Mock()
        contexts = (
            patch.object(todo, "SIGNAL", self.signals),
            patch.object(thread_with_exception, "SIGNAL", self.signals),
            patch.object(thread_with_exception, "CUS_LOGGER", Mock()),
            patch.object(thread_with_exception, "error_by_merged_dialog", self.traceback_dialog),
            patch.object(todo.time, "sleep"),
        )
        for context in contexts:
            context.start()
            self.addCleanup(context.stop)

    def make_task(self):
        """构造业务返回值可独立配置的双号任务对象。"""
        return SimpleNamespace(
            check_player=Mock(side_effect=lambda title, player: player),
            model_start_print=Mock(), model_end_print=Mock(),
            opt={
                "login_settings": {"fresh_resize_360_windows": False},
                "advanced_settings": {"top_up_money_1p": True, "top_up_money_2p": True},
            },
            faa_dict={pid: SimpleNamespace(
                reload_game=Mock(return_value=(True, "")),
                sign_top_up_money=Mock(return_value=("今天氪过了~", "")),
                fed_and_watered=Mock(return_value=None),
            ) for pid in (1, 2)},
        )

    def test_worker_preserves_business_return_values_without_failure_field(self):
        for result in ((True, ""), (False, "账号未设置"), "", None):
            with self.subTest(result=result):
                worker = thread_with_exception.ThreadWithException(target=lambda: result, is_print=False)
                worker.start()
                self.assertIs(worker.get_return_value(), result)
                self.assertFalse(hasattr(worker, "failure"))
        self.traceback_dialog.assert_not_called()

    def test_worker_exception_keeps_result_none_and_reports_original_traceback_once(self):
        error = RuntimeError("模拟程序异常")
        worker = thread_with_exception.ThreadWithException(target=Mock(side_effect=error), is_print=False)
        worker.start()
        self.assertIsNone(worker.get_return_value())
        self.assertFalse(hasattr(worker, "failure"))
        self.traceback_dialog.assert_called_once()
        self.assertIs(self.traceback_dialog.call_args.kwargs["e"], error)

    def test_reload_success_and_expected_failure_are_passed_through(self):
        task = self.make_task()
        self.assertIsNone(todo.ThreadTodo.batch_reload_game(task, player=[1, 2]))
        task.faa_dict[1].reload_game.return_value = (False, "账号未设置")
        task.faa_dict[2].reload_game.return_value = (False, "登录超时")
        reason = todo.ThreadTodo.batch_reload_game(task, player=[1, 2])
        self.assertIn("1P：账号未设置", reason)
        self.assertIn("2P：登录超时", reason)
        self.traceback_dialog.assert_not_called()

    def test_reload_missing_result_stops_without_unpacking_none(self):
        for raises in (False, True):
            with self.subTest(raises=raises):
                task = self.make_task()
                task.faa_dict[2].reload_game.return_value = None
                if raises:
                    task.faa_dict[2].reload_game.side_effect = RuntimeError("刷新程序异常")
                reason = todo.ThreadTodo.batch_reload_game(task, player=[1, 2])
                self.assertIn("2P", reason)
                self.assertIn("未获得有效结果", reason)
        self.traceback_dialog.assert_called_once()

    def test_top_up_exception_stops_before_next_player(self):
        task = self.make_task()
        task.faa_dict[1].sign_top_up_money.side_effect = RuntimeError("充值程序异常")
        reason = todo.ThreadTodo.batch_top_up_money(task, player=[1, 2])
        self.assertIn("1P", reason)
        self.assertIn("未获得有效结果", reason)
        task.faa_dict[2].sign_top_up_money.assert_not_called()
        task.model_end_print.assert_not_called()
        self.traceback_dialog.assert_called_once()

    def test_top_up_login_failure_stops_before_next_player_without_traceback(self):
        task = self.make_task()
        task.faa_dict[1].sign_top_up_money.return_value = ("充值复核失败", "恢复登录失败")
        self.assertEqual(todo.ThreadTodo.batch_top_up_money(task, player=[1, 2]), "1P：恢复登录失败")
        task.faa_dict[2].sign_top_up_money.assert_not_called()
        self.traceback_dialog.assert_not_called()

    def test_water_normal_none_result_does_not_stop_next_player(self):
        task = self.make_task()
        self.assertIsNone(todo.ThreadTodo.batch_fed_and_watered(task, player=[1, 2]))
        for faa in task.faa_dict.values():
            faa.fed_and_watered.assert_called_once_with()
        self.assertEqual(task.thread_1p.return_value, "")
        task.model_end_print.assert_called_once_with(text="浇水 施肥 摘果")
        self.traceback_dialog.assert_not_called()

    def test_water_expected_failure_stops_before_next_player(self):
        task = self.make_task()
        task.faa_dict[1].fed_and_watered.return_value = "公会恢复登录失败"
        self.assertEqual(todo.ThreadTodo.batch_fed_and_watered(task, player=[1, 2]), "1P：公会恢复登录失败")
        task.faa_dict[2].fed_and_watered.assert_not_called()
        self.traceback_dialog.assert_not_called()

    def test_water_exception_is_not_mistaken_for_normal_none_return(self):
        task = self.make_task()
        task.faa_dict[1].fed_and_watered.side_effect = RuntimeError("浇水程序异常")
        reason = todo.ThreadTodo.batch_fed_and_watered(task, player=[1, 2])
        self.assertIn("1P", reason)
        self.assertIn("未获得有效结果", reason)
        task.faa_dict[2].fed_and_watered.assert_not_called()
        task.model_end_print.assert_not_called()
        self.traceback_dialog.assert_called_once()


if __name__ == "__main__":
    unittest.main()
