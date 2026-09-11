import unittest
from pathlib import Path
from unittest.mock import patch

from tool.item_resource.item_resource_common import parse_target_items


class ManualLootClassificationTests(unittest.TestCase):
    def test_longyuan_flame_is_the_only_allowed_0x126_example(self):
        rows = [
            {"A": "id", "B": "name"},
            {"A": "0x12618810", "B": "龙渊之焰", "E": "https://example.invalid/longyuan.png"},
            {"A": "0x12618820", "B": "普通活动道具", "E": "https://example.invalid/event.png"},
        ]

        with patch("tool.item_resource.item_resource_common.read_xlsx_rows", return_value=rows):
            items = parse_target_items(Path("unused.xlsx"))

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "龙渊之焰")
        self.assertEqual(items[0].item_type, "其他类型")


if __name__ == "__main__":
    unittest.main()
