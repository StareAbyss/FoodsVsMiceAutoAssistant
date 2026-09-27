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
            with self.assertRaisesRegex(RuntimeError, "登录失败"):
                faa_core.FAABase.reload_game(faa)

        self.assertEqual(faa.click_refresh_btn.call_count, 10)
        dialog.assert_called_once()
        self.assertIn("连续10次", dialog.call_args.kwargs["text"])

    def test_invalid_platform_fails_without_refreshing(self):
        faa = self.make_faa(platform="不存在的区服")
        dialog = Mock()

        with patch.object(faa_core, "SIGNAL", SimpleNamespace(DIALOG=SimpleNamespace(emit=dialog))):
            with self.assertRaisesRegex(RuntimeError, "登录失败"):
                faa_core.FAABase.reload_game(faa)

        faa.click_refresh_btn.assert_not_called()
        dialog.assert_called_once()

    def test_success_after_transient_refresh_failures_stops_retrying(self):
        faa = self.make_faa()
        faa.click_refresh_btn.side_effect = (False, False, True)
        dialog = Mock()
        clock = count(step=0.1)
        fake_time = SimpleNamespace(sleep=Mock(), monotonic=lambda: next(clock))

        def find_image(**kwargs):
            if str(kwargs.get("template", "")).endswith("3_健康游戏公告_确定.png"):
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
            self.assertTrue(faa_core.FAABase.reload_game(faa))

        self.assertEqual(faa.click_refresh_btn.call_count, 3)
        dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
