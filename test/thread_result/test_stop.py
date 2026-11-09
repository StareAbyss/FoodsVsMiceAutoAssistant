"""隔离应用初始化，验证公用线程的停止操作和任务收尾。"""

import ast
import ctypes
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class ThreadStopTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        source = ast.parse((self.root / "function/common/thread_with_exception.py").read_text(encoding="utf-8"))
        thread_class = next(node for node in source.body
                            if isinstance(node, ast.ClassDef) and node.name == "ThreadWithException")
        self.env = {
            "ctypes": ctypes, "threading": threading, "CUS_LOGGER": Mock(),
            "SIGNAL": Mock(), "error_by_merged_dialog": Mock(),
        }
        # 只载入原线程类，避免 Qt 初始化和日志文件重建。
        exec(compile(ast.Module(body=[thread_class], type_ignores=[]), "thread_stop", "exec"), self.env)
        self.worker_type = self.env["ThreadWithException"]

    def test_unstarted_thread_without_id_can_be_stopped_repeatedly(self):
        worker = self.worker_type(target=Mock(), is_print=False)
        self.assertIsNone(worker.get_id())
        # 当前项目 CPython 的该接口将 None 作为空 ID，找不到线程时返回 0。
        self.assertEqual(ctypes.pythonapi.PyThreadState_SetAsyncExc(None, ctypes.py_object(SystemExit)), 0)
        worker.stop()
        worker.stop()
        worker.target.assert_not_called()

    def test_completed_thread_keeps_its_return_value_after_repeated_stop(self):
        worker = self.worker_type(target=lambda: (False, "登录超时"), is_print=False)
        worker.start()
        self.assertEqual(worker.get_return_value(), (False, "登录超时"))
        self.assertIsNone(worker.get_id())
        worker.stop()
        worker.stop()
        self.assertEqual(worker.return_value, (False, "登录超时"))
        self.env["error_by_merged_dialog"].assert_not_called()

    def test_failed_thread_can_be_stopped_without_reporting_again(self):
        error = RuntimeError("测试异常")
        worker = self.worker_type(target=Mock(side_effect=error), is_print=False)
        worker.start()
        worker.join()
        self.assertIsNone(worker.get_id())
        worker.stop()
        self.env["error_by_merged_dialog"].assert_called_once()

    def test_running_thread_stop_still_targets_its_actual_id(self):
        started, release = threading.Event(), threading.Event()

        def wait_for_release():
            """让线程保持运行，供主测试检查 ID；测试结束时由事件正常释放。"""
            started.set()
            release.wait(5)

        worker = self.worker_type(target=wait_for_release, is_print=False)
        worker.start()
        try:
            self.assertTrue(started.wait(2))
            actual_id = worker.get_id()
            self.assertEqual(actual_id, worker.ident)
            self.assertIsNotNone(actual_id)
            injection = Mock(return_value=1)
            # 运行中的线程只核对终止请求参数，不向真实线程注入异常。
            api = SimpleNamespace(pythonapi=SimpleNamespace(PyThreadState_SetAsyncExc=injection),
                                  py_object=ctypes.py_object)
            with patch.dict(self.env, {"ctypes": api}):
                worker.stop()
            injection.assert_called_once()
            self.assertEqual(injection.call_args.args[0], actual_id)
            self.assertIs(injection.call_args.args[1].value, SystemExit)
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())

    def test_task_cleanup_handles_completed_and_unstarted_workers(self):
        completed = self.worker_type(target=lambda: "done", is_print=False)
        completed.start()
        completed.join()
        unstarted = self.worker_type(target=Mock(), is_print=False)
        source = ast.parse((self.root / "function/core/todo.py").read_text(encoding="utf-8"))
        todo_class = next(node for node in source.body
                          if isinstance(node, ast.ClassDef) and node.name == "ThreadTodo")
        stop = next(node for node in todo_class.body if isinstance(node, ast.FunctionDef) and node.name == "stop")
        env = {}
        exec(compile(ast.Module(body=[stop], type_ignores=[]), "todo_stop", "exec"), env)
        task = SimpleNamespace(thread_1p=completed, thread_2p=unstarted, process=None,
                               thread_card_manager=None, faa_dict={}, msleep=Mock(),
                               terminate=Mock(), wait=Mock(), deleteLater=Mock())
        env["stop"](task)
        self.assertIsNone(task.thread_1p)
        self.assertIsNone(task.thread_2p)
        task.terminate.assert_called_once_with()
        task.wait.assert_called_once_with()
        task.deleteLater.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
