"""按区服缩放窗口的尺寸、屏幕缩放和调用入口检查。"""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from function.globals.get_paths import PATHS

os.makedirs(PATHS["logs"], exist_ok=True)

from function.scattered import resize_360_windows


class ResizeGameWindowsTest(unittest.TestCase):
    def resize(self, platform, zoom=1, screen=(2560, 1600), second_handle=102):
        positions = Mock()
        metrics = SimpleNamespace(GetSystemMetrics=lambda axis: screen[axis])
        with (
            patch.object(resize_360_windows, "get_channel_name", return_value=("1P", "2P")),
            patch.object(resize_360_windows, "faa_get_handle", side_effect=(101, second_handle)),
            patch.object(resize_360_windows.ctypes, "windll", SimpleNamespace(user32=metrics)),
            patch.object(resize_360_windows.win32gui, "SetWindowPos", positions),
            patch.object(resize_360_windows.EXTRA, "ZOOM_RATE", zoom),
        ):
            resize_360_windows.batch_resize_window("游戏", "1P", "2P", platform)
        return [call.args for call in positions.call_args_list]

    def test_qq_space_shows_a_larger_window_for_each_player(self):
        calls = self.resize("QQ空间")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][2:6], (1585, 0, 975, 743))
        self.assertEqual(calls[1][2:6], (1585, 743, 975, 743))

    def test_other_platforms_keep_existing_dimensions(self):
        for platform in ("4399", "QQ大厅"):
            with self.subTest(platform=platform):
                calls = self.resize(platform)
                self.assertEqual(calls[0][4:6], (955, 668))
                self.assertEqual(calls[1][4:6], (955, 668))

    def test_larger_dimensions_follow_display_scaling(self):
        calls = self.resize("QQ空间", zoom=1.5, screen=(3840, 2400))
        self.assertEqual(calls[0][4:6], (1462, 1114))
        self.assertEqual(calls[1][3], 1114)

    def test_short_screen_keeps_two_windows_side_by_side(self):
        calls = self.resize("QQ空间", screen=(1920, 1080))
        self.assertEqual(calls[0][2:6], (0, 0, 960, 743))
        self.assertEqual(calls[1][2:6], (960, 0, 960, 743))

    def test_single_window_uses_full_requested_width_on_short_screen(self):
        calls = self.resize("QQ空间", screen=(1920, 1080), second_handle=0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2:6], (945, 0, 975, 743))

    def test_manual_resize_passes_selected_platform(self):
        from function.core import qmw_3_service

        settings = {
            "base_settings": {"game_name": "游戏", "name_1p": "1P", "name_2p": "2P"},
            "login_settings": {"platform": "QQ空间"},
        }
        with patch.object(qmw_3_service, "batch_resize_window") as resize:
            qmw_3_service.QMainWindowService.click_btn_batch_resize_window(
                SimpleNamespace(opt=settings)
            )
        resize.assert_called_once_with(
            game_name="游戏", name_1p="1P", name_2p="2P", platform="QQ空间"
        )

    def test_refresh_resize_passes_selected_platform_and_finishes_reload(self):
        from function.core import todo

        settings = {
            "base_settings": {"game_name": "游戏", "name_1p": "1P", "name_2p": "2P"},
            "login_settings": {"platform": "QQ空间", "fresh_resize_360_windows": True},
        }
        reload_game = Mock(return_value=True)
        task = SimpleNamespace(
            opt=settings,
            check_player=Mock(return_value=[1]),
            faa_dict={1: SimpleNamespace(reload_game=reload_game)},
        )
        with (
            patch.object(todo, "batch_resize_window") as resize,
            patch.object(todo.SIGNAL, "PRINT_TO_UI", SimpleNamespace(emit=Mock())),
        ):
            todo.ThreadTodo.batch_reload_game(task, player=[1])
        resize.assert_called_once_with(
            game_name="游戏", name_1p="1P", name_2p="2P", platform="QQ空间"
        )
        reload_game.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
