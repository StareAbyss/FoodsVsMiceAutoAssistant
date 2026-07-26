import unittest
from unittest.mock import patch

from function.common.file_name_sort import sort_file_names_like_windows
from function.scattered.get_list_battle_plan import (
    get_list_battle_plan,
    get_list_tweak_plan,
)
from function.scattered.get_task_sequence_list import get_task_sequence_list


class FileNameSortTest(unittest.TestCase):
    def test_sort_matches_windows_numeric_order(self):
        names = [
            "NO-6-10-1P 多拿滋.json",
            "NO-6-3to4 苏打水.json",
            "NO-6-7-1P 巴旦木.json",
            "NO-6-5 汉堡王.json",
        ]

        self.assertEqual(
            sort_file_names_like_windows(names),
            [
                "NO-6-3to4 苏打水.json",
                "NO-6-5 汉堡王.json",
                "NO-6-7-1P 巴旦木.json",
                "NO-6-10-1P 多拿滋.json",
            ],
        )

    @patch(
        "function.scattered.get_list_battle_plan.os.listdir",
        return_value=["方案10.json", "说明.txt", "方案2.json", "方案1.json"],
    )
    def test_battle_plan_list_is_sorted_without_extension(self, _listdir):
        self.assertEqual(
            get_list_battle_plan(with_extension=False),
            ["方案1", "方案2", "方案10"],
        )

    @patch(
        "function.scattered.get_list_battle_plan.os.listdir",
        return_value=["微调10.json", "微调2.json", "微调1.json"],
    )
    def test_tweak_plan_list_is_sorted_with_extension(self, _listdir):
        self.assertEqual(
            get_list_tweak_plan(with_extension=True),
            ["微调1.json", "微调2.json", "微调10.json"],
        )

    @patch(
        "function.scattered.get_task_sequence_list.os.listdir",
        return_value=["任务10.json", "说明.txt", "任务2.json", "任务1.json"],
    )
    def test_task_sequence_list_is_sorted_without_extension(self, _listdir):
        self.assertEqual(
            get_task_sequence_list(with_extension=False),
            ["任务1", "任务2", "任务10"],
        )


if __name__ == "__main__":
    unittest.main()
