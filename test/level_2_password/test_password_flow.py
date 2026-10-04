"""隔离游戏操作，验证密码未确认时不会继续高危任务。"""
import ast
import itertools
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from function.globals.get_paths import PATHS


def load_flow():
    """只载入待测业务方法，不初始化窗口、Qt 或真实动作队列。"""
    source = ast.parse(Path(os.path.join(PATHS["root"], "function", "core", "faa", "faa_core.py"))
                       .read_text(encoding="utf-8"))
    base = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "FAABase")
    base.body = [node for node in base.body if isinstance(node, ast.FunctionDef)
                 and (node.name.startswith("_wait_level_2") or node.name.startswith("_submit_level_2")
                      or node.name.startswith("_input_level_2") or node.name.startswith("_stop_for_level_2")
                      or node.name == "input_level_2_password")]
    signals = SimpleNamespace(PRINT_TO_UI=Mock(), END=Mock(), DIALOG=Mock())
    ticks = itertools.count()
    namespace = {
        "SIGNAL": signals,
        "T_ACTION_QUEUE_TIMER": Mock(),
        "g_resources": SimpleNamespace(RESOURCE_P={"common": {
            "二级密码.png": "password", "退出.png": "exit", "暗晶商店_ui.png": "shop"}}),
        "time": SimpleNamespace(sleep=Mock(), monotonic=lambda: next(ticks)),
        "match_p_in_w": Mock(),
        "loop_match_p_in_w": Mock(return_value=True),
    }
    module = ast.Module(body=[base], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "faa_password_flow", "exec"), namespace)
    faa = namespace["FAABase"]()
    faa.handle, faa.handle_360, faa.player = 1, 2, 1
    faa.action_bottom_menu = Mock(return_value=True)
    faa.action_exit = Mock()
    return faa, namespace, signals


class PasswordFlowTests(unittest.TestCase):
    def test_missing_password_stops_before_any_game_click(self):
        faa, env, signals = load_flow()
        self.assertFalse(faa.input_level_2_password(""))
        env["T_ACTION_QUEUE_TIMER"].add_click_to_queue.assert_not_called()
        signals.END.emit.assert_called_once()
        signals.DIALOG.emit.assert_called_once()

    def test_shop_without_dialog_uses_fallback(self):
        faa, _, signals = load_flow()
        faa._wait_level_2_password_dialog = Mock(return_value=False)
        faa._input_level_2_password_via_card_bag = Mock(return_value=True)
        self.assertTrue(faa.input_level_2_password("example"))
        faa._input_level_2_password_via_card_bag.assert_called_once_with("example")
        signals.END.emit.assert_not_called()

    def test_both_routes_fail_stops_and_notifies(self):
        faa, _, signals = load_flow()
        faa._wait_level_2_password_dialog = Mock(return_value=False)
        faa._input_level_2_password_via_card_bag = Mock(return_value=False)
        self.assertFalse(faa.input_level_2_password("example"))
        signals.END.emit.assert_called_once()
        signals.DIALOG.emit.assert_called_once()

    def test_rejected_shop_password_does_not_sort_card_bag(self):
        faa, _, signals = load_flow()
        faa._wait_level_2_password_dialog = Mock(return_value=True)
        faa._submit_level_2_password = Mock(return_value=False)
        faa._input_level_2_password_via_card_bag = Mock()
        self.assertFalse(faa.input_level_2_password("example"))
        faa._input_level_2_password_via_card_bag.assert_not_called()
        signals.END.emit.assert_called_once()

    def test_fallback_unlock_does_not_repeat_sort(self):
        faa, env, _ = load_flow()
        faa._wait_level_2_password_dialog = Mock(return_value=True)
        faa._submit_level_2_password = Mock(return_value=True)
        self.assertTrue(faa._input_level_2_password_via_card_bag("example"))
        clicks = env["T_ACTION_QUEUE_TIMER"].add_click_to_queue.call_args_list
        self.assertEqual(sum(call.kwargs.get("x") == 905 for call in clicks), 1)
        faa.action_exit.assert_called_once_with(mode="普通红叉", raw_range=[900, 40, 940, 85])

    def test_no_fallback_dialog_does_not_type_password(self):
        faa, env, _ = load_flow()
        faa._wait_level_2_password_dialog = Mock(return_value=False)
        self.assertFalse(faa._input_level_2_password_via_card_bag("example"))
        env["T_ACTION_QUEUE_TIMER"].char_input.assert_not_called()

    def test_submit_requires_dialog_disappearance(self):
        for status, expected in [(1, True), (2, False), (0, False)]:
            with self.subTest(status=status):
                faa, env, _ = load_flow()
                env["match_p_in_w"].return_value = (status, None)
                self.assertIs(faa._submit_level_2_password("example"), expected)


class PasswordBatchTests(unittest.TestCase):
    def make_batch(self, method_name, password_ok):
        source = ast.parse(Path(os.path.join(PATHS["root"], "function", "core", "todo.py"))
                           .read_text(encoding="utf-8"))
        todo_class = next(node for node in source.body
                          if isinstance(node, ast.ClassDef) and node.name == "ThreadTodo")
        method = next(node for node in todo_class.body
                      if isinstance(node, ast.FunctionDef) and node.name == method_name)

        class ImmediateThread:
            def __init__(self, target, kwargs, **unused):
                self.target, self.kwargs = target, kwargs
                self.return_value = None

            def start(self):
                self.return_value = self.target(**self.kwargs)

            def join(self):
                pass

        namespace = {"ThreadWithException": ImmediateThread,
                     "SIGNAL": SimpleNamespace(PRINT_TO_UI=Mock())}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "password_batch", "exec"), namespace)
        players = {1: Mock(channel="first"), 2: Mock(channel="second")}
        for faa in players.values():
            faa.input_level_2_password.return_value = password_ok
        todo = SimpleNamespace(
            faa_dict=players,
            opt={"level_2": {"1p": {"active": True}, "2p": {"active": False}},
                 "login_credentials": {"level_2": {"1p": {"password": "example"},
                                                  "2p": {"password": "example"}}}},
            model_start_print=Mock(), model_end_print=Mock(), batch_reload_game=Mock())
        return lambda: namespace[method_name](todo, player=[1, 2]), todo

    def test_failed_password_skips_operation_and_reload(self):
        for method, operation in [("batch_delete_items", "delete_items"),
                                  ("batch_dark_crystal", "get_dark_crystal"),
                                  ("batch_disenchant_gem", "disenchant_gem")]:
            with self.subTest(method=method):
                run, todo = self.make_batch(method, False)
                run()
                getattr(todo.faa_dict[1], operation).assert_not_called()
                todo.faa_dict[2].input_level_2_password.assert_not_called()
                todo.batch_reload_game.assert_not_called()

    def test_only_enabled_player_runs_operation_and_reload(self):
        for method, operation in [("batch_delete_items", "delete_items"),
                                  ("batch_dark_crystal", "get_dark_crystal"),
                                  ("batch_disenchant_gem", "disenchant_gem")]:
            with self.subTest(method=method):
                run, todo = self.make_batch(method, True)
                run()
                getattr(todo.faa_dict[1], operation).assert_called_once()
                todo.faa_dict[2].input_level_2_password.assert_not_called()
                getattr(todo.faa_dict[2], operation).assert_not_called()
                todo.batch_reload_game.assert_called_once_with(player=[1])


if __name__ == "__main__":
    unittest.main()
