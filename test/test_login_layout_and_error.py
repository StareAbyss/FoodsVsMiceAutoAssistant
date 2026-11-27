import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from function.common import thread_with_exception
from function.core import todo
from function.scattered import resize_360_windows


class LoginLayoutAndErrorTest(unittest.TestCase):
    def test_stopping_finished_worker_does_not_raise_another_error(self):
        worker = thread_with_exception.ThreadWithException(target=lambda: (False, "登录失败"), is_print=False)
        worker.start()
        worker.join()
        worker.stop()
        self.assertEqual(worker.return_value, (False, "登录失败"))

    def test_qq_space_window_adds_width_and_height(self):
        metrics = SimpleNamespace(GetSystemMetrics=lambda axis: (2560, 1600)[axis])
        positions = Mock()
        with (
            patch.object(resize_360_windows, "get_channel_name", return_value=("1P", "2P")),
            patch.object(resize_360_windows, "faa_get_handle", side_effect=(101, 102)),
            patch.object(resize_360_windows.ctypes, "windll", SimpleNamespace(user32=metrics)),
            patch.object(resize_360_windows.win32gui, "SetWindowPos", positions),
            patch.object(resize_360_windows.EXTRA, "ZOOM_RATE", 1),
        ):
            resize_360_windows.batch_resize_window("游戏", "1P", "2P", "QQ空间")

        self.assertEqual(positions.call_count, 2)
        self.assertEqual(positions.call_args_list[0].args[4:6], (975, 743))
        self.assertEqual(positions.call_args_list[1].args[4:6], (975, 743))

    def test_expected_login_failure_does_not_render_traceback(self):
        dialog = Mock()
        traceback_dialog = Mock()

        def fail():
            return False, "区服设置无效"

        with (
            patch.object(thread_with_exception.SIGNAL, "DIALOG", SimpleNamespace(emit=dialog)),
            patch.object(thread_with_exception, "error_by_merged_dialog", traceback_dialog),
            patch.object(thread_with_exception.CUS_LOGGER, "error"),
        ):
            worker = thread_with_exception.ThreadWithException(target=fail, is_print=False)
            worker.run()

        self.assertFalse(hasattr(worker, "failure"))
        self.assertEqual(worker.return_value, (False, "区服设置无效"))
        dialog.assert_not_called()
        traceback_dialog.assert_not_called()

    def test_task_thread_finishes_after_expected_login_failure(self):
        dialog = Mock()
        ended = Mock()
        task = SimpleNamespace(
            todo_id=1,
            start_360=Mock(), remove_outdated_log_images=Mock(),
            task_sequence_uuid="test",
            task_sequence=Mock(return_value=(False, False, "账号未设置")),
            signal_task_failed=SimpleNamespace(emit=Mock()),
            close_360=Mock(), batch_click_final_refresh_btn=Mock(),
        )

        with (
            patch.object(todo.SIGNAL, "DIALOG", SimpleNamespace(emit=dialog)),
            patch.object(todo.SIGNAL, "END", SimpleNamespace(emit=ended)),
            patch.object(todo.SIGNAL, "PRINT_TO_UI", SimpleNamespace(emit=Mock())),
            patch.object(todo.CUS_LOGGER, "error"),
        ):
            todo.ThreadTodo.run(task)

        task.signal_task_failed.emit.assert_called_once_with("账号未设置")
        task.close_360.assert_not_called()
        task.batch_click_final_refresh_btn.assert_not_called()
        dialog.assert_not_called()
        ended.assert_not_called()


if __name__ == "__main__":
    unittest.main()
