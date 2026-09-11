import json
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

QT_APP = QApplication.instance() or QApplication([])

from function.core import analyzer_of_loot_logs


class TestRankingDataIo(unittest.TestCase):
    def test_save_failure_returns_false_and_removes_temp_file(self):
        with tempfile.TemporaryDirectory(dir="test") as temp_dir:
            json_path = os.path.join(temp_dir, "ranking.json")
            with (
                    patch.object(analyzer_of_loot_logs.os, "replace", side_effect=PermissionError(5, "拒绝访问")),
                    patch.object(analyzer_of_loot_logs.CUS_LOGGER, "error") as error_log,
            ):
                result = analyzer_of_loot_logs.ranking_save_data(
                    json_path=json_path,
                    data={"ranking": [], "graph": {}},
                )

            self.assertFalse(result)
            self.assertEqual(os.listdir(temp_dir), [])
            error_log.assert_called_once()

    def test_save_success_returns_true(self):
        with tempfile.TemporaryDirectory(dir="test") as temp_dir:
            json_path = os.path.join(temp_dir, "ranking.json")
            data = {"ranking": ["A"], "graph": {"A": []}}

            result = analyzer_of_loot_logs.ranking_save_data(json_path=json_path, data=data)

            self.assertTrue(result)
            with open(json_path, mode="r", encoding="utf-8") as file:
                self.assertEqual(json.load(file), data)

    def test_update_graph_skips_record_when_save_fails(self):
        data = {"ranking": [], "graph": {}}
        with (
                patch.object(analyzer_of_loot_logs, "ranking_read_data", return_value=data),
                patch.object(analyzer_of_loot_logs, "ranking_save_data", return_value=False),
        ):
            result = analyzer_of_loot_logs.update_dag_graph(["A", "B"])

        self.assertFalse(result)

    def test_longest_path_returns_none_when_save_fails(self):
        data = {"ranking": [], "graph": {"A": ["B"], "B": []}}
        with (
                patch.object(analyzer_of_loot_logs, "ranking_read_data", return_value=data),
                patch.object(analyzer_of_loot_logs, "ranking_save_data", return_value=False),
        ):
            result = analyzer_of_loot_logs.find_longest_path_from_dag()

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
