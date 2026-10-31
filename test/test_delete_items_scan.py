"""隔离真实点击，验证删除道具扫描的重叠、底部覆盖及原有删除流程。"""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class DeleteItemsScanTest(unittest.TestCase):
    def setUp(self):
        # 只加载生产方法，避免导入主程序时启动真实动作队列。
        path = Path(__file__).resolve().parents[1] / "function/core/faa/faa_core.py"
        source = ast.parse(path.read_text(encoding="utf-8"))
        base = next(node for node in source.body
                    if isinstance(node, ast.ClassDef) and node.name == "FAABase")
        method = next(node for node in base.body
                      if isinstance(node, ast.FunctionDef) and node.name == "delete_items")
        self.queue = Mock()
        self.match = Mock(return_value=(1, None))
        self.confirm = Mock(return_value=True)
        self.environment = {
            "SIGNAL": SimpleNamespace(PRINT_TO_UI=Mock()),
            "T_ACTION_QUEUE_TIMER": self.queue,
            "time": SimpleNamespace(sleep=Mock()),
            "g_resources": SimpleNamespace(RESOURCE_CP={"背包_道具_需删除的": {"测试道具": "item"}}),
            "RESOURCE_P": {"item": {"物品-掩模-不绑定.png": "mask"},
                           "common": {"通用_确定.png": "confirm"}},
            "match_p_in_w": self.match,
            "loop_match_p_in_w": self.confirm,
        }
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), self.environment)
        self.faa = SimpleNamespace(handle=1, handle_360=2, player=1,
                                   print_debug=Mock(), print_info=Mock(),
                                   action_bottom_menu=Mock(), action_exit=Mock())

    def run_scan(self):
        self.environment["delete_items"](self.faa)

    def scroll_count(self):
        return sum(call.kwargs.get("x") == 920 and call.kwargs.get("y") == 420
                   for call in self.queue.add_click_to_queue.call_args_list)

    def test_scans_first_screen_and_each_two_scrolls_until_bottom(self):
        offsets = []

        def miss(**unused):
            offsets.append(self.scroll_count())
            return 1, None

        self.match.side_effect = miss
        self.run_scan()
        self.assertEqual(offsets, list(range(0, 21, 2)))
        self.assertEqual(self.scroll_count(), 20)
        self.confirm.assert_not_called()
        self.faa.action_bottom_menu.assert_called_once_with(mode="背包")
        self.faa.action_exit.assert_called_once_with(mode="普通红叉")

    def test_item_on_overlapping_screen_uses_existing_delete_confirmation(self):
        self.match.side_effect = [(1, None), (2, (10, 20))] + [(1, None)] * 9
        self.run_scan()
        self.queue.add_click_to_queue.assert_any_call(handle=1, x=476, y=108)
        self.confirm.assert_called_once()
        self.assertEqual(self.confirm.call_args.kwargs["source_range"], [420, 339, 450, 365])
        self.assertTrue(self.confirm.call_args.kwargs["click"])
        self.assertEqual(self.match.call_count, 11)

    def test_item_on_bottom_screen_is_still_reached(self):
        self.match.side_effect = [(1, None)] * 10 + [(2, (30, 40))]
        self.run_scan()
        self.queue.add_click_to_queue.assert_any_call(handle=1, x=496, y=128)
        self.confirm.assert_called_once()
        self.assertEqual(self.scroll_count(), 20)

    def test_all_configured_templates_are_scanned_without_changing_match_range(self):
        self.environment["g_resources"].RESOURCE_CP["背包_道具_需删除的"]["第二道具"] = "second"
        self.run_scan()
        self.assertEqual(self.match.call_count, 22)
        self.assertEqual([call.kwargs["template"] for call in self.match.call_args_list],
                         ["item", "second"] * 11)
        for call in self.match.call_args_list:
            self.assertEqual(call.kwargs["source_range"], [466, 88, 910, 435])
            self.assertEqual(call.kwargs["match_tolerance"], 0.999)
        self.confirm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
