"""隔离识图和窗口操作，验证刷新次数、重开边界及失败传播。"""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call


class LoginRestartRecoveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 执行真实刷新调度，仅替换嵌套的识图辅助函数，避免测试操作游戏窗口。
        path = Path(__file__).resolve().parents[1] / "function/core/faa/faa_core.py"
        source = ast.parse(path.read_text(encoding="utf-8-sig"))
        reload_game = next(node for node in ast.walk(source)
                           if isinstance(node, ast.FunctionDef) and node.name == "reload_game")
        main = next(node for node in reload_game.body
                    if isinstance(node, ast.FunctionDef) and node.name == "main")
        cls.main_code = compile(ast.Module(body=[main], type_ignores=[]), str(path), "exec")

    def setUp(self):
        self.settings = {
            "platform": "4399", "qq_space_server": 0, "login_open_settings": True,
            "first_num": 1, "second_num": 2, "login_path": "360Game.exe",
        }
        self.faa = SimpleNamespace(
            opt={"login_settings": self.settings, "4399_login_info": {"use_password": False}},
            player=1, channel="测试账号1", click_refresh_btn=Mock(return_value=True),
            print_info=Mock(), print_debug=Mock(), print_warning=Mock(), start_360=Mock(),
        )
        self.env = {
            "self": self.faa, "time": SimpleNamespace(sleep=Mock()),
            "faa_get_handle": Mock(return_value=123), "close_software_by_title": Mock(),
            "try_close_sub_account_list": Mock(return_value=False),
            "try_relink": Mock(return_value=False),
            "wait_for_server_button": Mock(return_value=False),
            "try_enter_server_4399": Mock(), "try_enter_server_4399_wd": Mock(),
            "wait_game_home_page": Mock(return_value=False), "wait_health_notice": Mock(),
            "confirm_home_and_close_popups": Mock(return_value=False),
            "action_after_success": Mock(), "login_4399": Mock(),
        }
        self.events = Mock()
        self.events.attach_mock(self.faa.click_refresh_btn, "refresh")
        self.events.attach_mock(self.env["close_software_by_title"], "close")
        self.events.attach_mock(self.faa.start_360, "start")
        exec(self.main_code, self.env)

    def run_main(self):
        return self.env["main"]()

    def test_disabled_stops_after_ten_without_restart(self):
        self.settings["login_open_settings"] = False
        success, reason = self.run_main()
        self.assertFalse(success)
        self.assertIn("连续10次", reason)
        self.assertEqual(self.events.mock_calls, [call.refresh()] * 10)

    def test_enabled_restarts_once_after_ten_then_stops_after_twenty(self):
        success, reason = self.run_main()
        self.assertFalse(success)
        self.assertIn("重启游戏窗口后再次连续10次", reason)
        self.assertIn("共20次", reason)
        self.assertEqual(self.events.mock_calls, [call.refresh()] * 10 + [
            call.close(window_title=self.faa.channel), call.start(),
        ] + [call.refresh()] * 10)
        self.assertEqual(self.env["faa_get_handle"].call_count, 40)

    def test_success_before_restart_returns_immediately(self):
        self.env["confirm_home_and_close_popups"].side_effect = [False, True]
        self.assertEqual(self.run_main(), (True, ""))
        self.assertEqual(self.events.mock_calls, [call.refresh()] * 2)
        self.env["action_after_success"].assert_called_once_with()

    def test_success_after_restart_returns_immediately(self):
        self.env["confirm_home_and_close_popups"].side_effect = [False] * 10 + [True]
        self.assertEqual(self.run_main(), (True, ""))
        self.assertEqual(self.faa.click_refresh_btn.call_count, 11)
        self.faa.start_360.assert_called_once_with()
        self.env["action_after_success"].assert_called_once_with()

    def test_missing_refresh_button_also_restarts_once(self):
        self.faa.click_refresh_btn.return_value = False
        success, reason = self.run_main()
        self.assertFalse(success)
        self.assertIn("未找到360游戏大厅的刷新按钮", reason)
        self.assertEqual(self.faa.click_refresh_btn.call_count, 20)
        self.faa.start_360.assert_called_once_with()

    def test_second_player_requires_own_startup_account(self):
        self.faa.player = 2
        self.settings["second_num"] = 0
        success, reason = self.run_main()
        self.assertFalse(success)
        self.assertIn("2P自动启动的小号编号或大厅路径未配置", reason)
        self.assertEqual(self.events.mock_calls, [call.refresh()] * 10)

    def test_missing_startup_path_keeps_existing_window(self):
        self.settings["login_path"] = ""
        self.assertFalse(self.run_main()[0])
        self.assertEqual(self.events.mock_calls, [call.refresh()] * 10)

    def test_invalid_platform_fails_without_refresh_or_restart(self):
        self.settings["platform"] = "无效区服"
        success, reason = self.run_main()
        self.assertFalse(success)
        self.assertIn("区服设置", reason)
        self.assertEqual(self.events.mock_calls, [])

    def test_invalid_credentials_do_not_trigger_restart(self):
        self.faa.opt["4399_login_info"]["use_password"] = True
        self.env["login_4399"].return_value = False, "账号未设置"
        self.assertEqual(self.run_main(), (False, "账号未设置"))
        self.assertEqual(self.events.mock_calls, [call.refresh()])


if __name__ == "__main__":
    unittest.main()
