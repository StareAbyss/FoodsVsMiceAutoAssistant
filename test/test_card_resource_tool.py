import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tool.card_resource.get_card_resource_tool import (
    build_card_evolution_metadata,
    build_card_prepare_room_url,
    parse_excel_cards,
    write_card_evolution_metadata,
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

    def test_card_evolution_metadata_is_standard_json_and_uses_existing_images(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            image_dir = root / "准备房间"
            image_dir.mkdir()
            for filename in (
                    "普通卡-0.png",
                    "普通卡-1.png",
                    "融合卡-0.png",
                    "融合卡-1.png",
                    "融合卡-2.png",
                    "雷神-0.png",
                    "雷神-1.png",
                    "雷神-2.png",
                    "雷神-3.png",
            ):
                (image_dir / filename).touch()

            rows = [
                {"基础卡片名称": "普通卡", "序号": 0, "进化树名称": "普通卡", "链路类型": "普通进化", "目标文件名": "普通卡-0.png"},
                {"基础卡片名称": "普通卡", "序号": 1, "进化树名称": "强化普通卡", "链路类型": "普通进化", "目标文件名": "普通卡-1.png"},
                {"基础卡片名称": "普通卡", "序号": 2, "进化树名称": "缺图阶段", "链路类型": "普通进化", "目标文件名": "普通卡-2.png"},
                {"基础卡片名称": "融合卡", "序号": 0, "进化树名称": "初融卡", "链路类型": "融合卡", "目标文件名": "融合卡-0.png"},
                {"基础卡片名称": "融合卡", "序号": 1, "进化树名称": "深融卡", "链路类型": "融合卡", "目标文件名": "融合卡-1.png"},
                {"基础卡片名称": "融合卡", "序号": 2, "进化树名称": "灵融卡", "链路类型": "融合卡", "目标文件名": "融合卡-2.png"},
                {"基础卡片名称": "雷神", "序号": 0, "进化树名称": "索尔神使", "链路类型": "普通进化", "目标文件名": "雷神-0.png"},
                {"基础卡片名称": "雷神", "序号": 1, "进化树名称": "索尔圣神", "链路类型": "普通进化", "目标文件名": "雷神-1.png"},
                {"基础卡片名称": "雷神", "序号": 2, "进化树名称": "雷神·索尔", "链路类型": "普通进化", "目标文件名": "雷神-2.png"},
                {"基础卡片名称": "雷神", "序号": 3, "进化树名称": "至尊雷神", "链路类型": "普通进化", "目标文件名": "雷神-3.png"},
            ]

            metadata = build_card_evolution_metadata(rows, image_dir)
            self.assertEqual(metadata["普通卡"]["stages"], {"0": "普通卡", "1": "强化普通卡"})
            self.assertEqual(metadata["融合卡"]["kind"], "fusion")
            self.assertEqual(metadata["雷神"]["kind"], "gold")

            output_path = root / "card_evolution.json"
            write_card_evolution_metadata(output_path, rows, image_dir)
            loaded_metadata = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded_metadata, metadata)
            self.assertTrue(output_path.read_text(encoding="utf-8").startswith("{\n"))


if __name__ == "__main__":
    unittest.main()
