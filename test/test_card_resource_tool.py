import unittest
from pathlib import Path
from unittest.mock import patch

from tool.card_resource.get_card_resource_tool import (
    build_card_prepare_room_url,
    parse_excel_cards,
)


class CardResourceToolTest(unittest.TestCase):
    def test_build_card_prepare_room_url_uses_fixed_cdn_path(self):
        self.assertEqual(
            build_card_prepare_room_url("0x1112059e"),
            "https://q.ms.huanlecdn.com/4399/cdn.123u.com/images/1/1/0x1112059e.png",
        )

    def test_parse_excel_cards_builds_url_from_id(self):
        rows = [
            {"A": "ID", "B": "名称"},
            {
                "A": "0x11122860",
                "B": "浮生茶",
                "D": "-1",
                "H": "https://example.invalid/images/1/5/0x11122860.png",
            },
            {
                "A": "0x1112059e",
                "B": "测试卡片",
                "D": "https://example.invalid/not-the-card-icon.png",
                "H": "-1",
            },
            {"A": "0x1170003a", "B": "未提供图片的卡片", "D": "-1", "H": "-1"},
            {"A": "0x124205c0", "B": "卡片配方"},
            {"A": "0x11100000", "B": ""},
        ]

        with patch(
            "tool.card_resource.get_card_resource_tool.read_xlsx_rows",
            return_value=rows,
        ):
            cards = parse_excel_cards(Path("unused.xlsx"))

        self.assertEqual(set(cards), {"0x11122860", "0x1112059e"})
        self.assertEqual(cards["0x11122860"].name, "浮生茶")
        self.assertEqual(
            cards["0x11122860"].urls,
            (
                "https://q.ms.huanlecdn.com/4399/cdn.123u.com/"
                "images/1/1/0x11122860.png",
            ),
        )
        self.assertEqual(cards["0x11122860"].source_row, 2)
        self.assertEqual(cards["0x1112059e"].source_row, 3)


if __name__ == "__main__":
    unittest.main()
