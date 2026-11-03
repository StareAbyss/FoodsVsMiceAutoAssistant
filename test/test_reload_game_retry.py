import unittest
from itertools import count
from types import SimpleNamespace
from unittest.mock import Mock, patch

from function.core.faa import faa_core


class ReloadGameRetryTest(unittest.TestCase):
    def make_faa(self, platform="4399"):
        faa = SimpleNamespace(
            channel="测试窗口",
            player=1,
            opt={
                "login_settings": {
                    "platform": platform,
                    "qq_space_server": 0,
                    "server_wait_enabled": False,
                    "server_wait_seconds": 5,
                },
                "4399_login_info": {"use_password": False},
            },
            click_refresh_btn=Mock(return_value=True),
            print_info=Mock(),
            print_debug=Mock(),
            print_warning=Mock(),
            print_error=Mock(),
        )
        return faa

    def test_loading_timeout_retries_ten_times_before_reporting_failure(self):
        faa = self.make_faa()
        dialog = Mock()
        clock = iter(range(0, 100000, 60))
        fake_time = SimpleNamespace(sleep=Mock(), monotonic=lambda: next(clock))

        with (
            patch.object(faa_core, "SIGNAL", SimpleNamespace(DIALOG=SimpleNamespace(emit=dialog))),
            patch.object(faa_core, "time", fake_time),
            patch.object(faa_core, "faa_get_handle", side_effect=lambda channel, mode: 0 if mode == "flash" else 1),
            patch.object(faa_core, "match_p_in_w", return_value=(1, None)),
            patch.object(faa_core, "loop_match_p_in_w", return_value=False),
            patch.object(faa_core, "loop_match_ps_in_w", return_value=False),
            patch.object(faa_core.CUS_LOGGER, "warning"),
        ):
            success, reason = faa_core.FAABase.reload_game(faa)

        self.assertFalse(success)
        self.assertIn("连续10次刷新", reason)
        self.assertEqual(faa.click_refresh_btn.call_count, 10)
        dialog.assert_not_called()

    def test_invalid_platform_fails_without_refreshing(self):
        faa = self.make_faa(platform="不存在的区服")
        dialog = Mock()

        with patch.object(faa_core, "SIGNAL", SimpleNamespace(DIALOG=SimpleNamespace(emit=dialog))):
            success, reason = faa_core.FAABase.reload_game(faa)

        self.assertFalse(success)
        self.assertIn("区服设置", reason)
        faa.click_refresh_btn.assert_not_called()
        dialog.assert_not_called()

    def test_success_after_transient_refresh_failures_stops_retrying(self):
        faa = self.make_faa()
        faa.click_refresh_btn.side_effect = (False, False, True)
        dialog = Mock()
        clock = count(step=0.1)
        fake_time = SimpleNamespace(sleep=Mock(), monotonic=lambda: next(clock))

        def find_image(**kwargs):
            if kwargs.get("template") is faa_core.RESOURCE_P["common"]["登录"]["通用"]["3_健康游戏公告_确定.png"]:
                return 2, (100, 100)
            return 1, None

        with (
            patch.object(faa_core, "SIGNAL", SimpleNamespace(DIALOG=SimpleNamespace(emit=dialog))),
            patch.object(faa_core, "time", fake_time),
            patch.object(faa_core, "faa_get_handle", return_value=1),
            patch.object(faa_core, "match_p_in_w", side_effect=find_image),
            patch.object(faa_core, "match_ps_in_w", return_value=[(1, 1)] * 3),
            patch.object(faa_core, "loop_match_p_in_w", return_value=False),
            patch.object(faa_core, "loop_match_ps_in_w", return_value=False),
            patch.object(faa_core, "capture_image_png", return_value=object()),
            patch.object(faa_core, "T_ACTION_QUEUE_TIMER", SimpleNamespace(add_click_to_queue=Mock())),
        ):
            self.assertEqual(faa_core.FAABase.reload_game(faa), (True, ""))

        self.assertEqual(faa.click_refresh_btn.call_count, 3)
        dialog.assert_not_called()

    def test_missing_credentials_stop_both_platforms_without_loading_wait_or_retry(self):
        for platform in ("4399", "QQ空间"):
            with self.subTest(platform=platform):
                faa = self.make_faa(platform)
                faa.opt["4399_login_info"]["use_password"] = True
                faa.opt["qq_login_info"] = {"use_password": True}
                faa.opt["login_credentials"] = {}
                login_images = faa_core.RESOURCE_P["common"]["登录"]["4399"]
                labels = {id(login_images[name]) for name in (
                    "4399_账号密码登录_已选中.png", "4399_用户名.png", "4399_密码.png", "4399_登录按钮.png",
                )}

                def find_image(**kwargs):
                    if id(kwargs.get("template")) in labels:
                        return 2, (100, 100)
                    return 1, None

                with (
                    patch.object(faa_core.time, "sleep"),
                    patch.object(faa_core.time, "monotonic", side_effect=count(step=1)),
                    patch.object(faa_core, "faa_get_handle", return_value=1),
                    patch.object(faa_core, "match_p_in_w", side_effect=find_image),
                    patch.object(faa_core, "loop_match_p_in_w", return_value=True),
                    patch.object(faa_core, "loop_match_ps_in_w", return_value=False),
                ):
                    success, reason = faa_core.FAABase.reload_game(faa)
                self.assertFalse(success)
                self.assertIn("账号或密码未正确设置", reason)
                self.assertEqual(faa.click_refresh_btn.call_count, 1)


if __name__ == "__main__":
    unittest.main()
