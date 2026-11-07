import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tool.image_resource_pipeline.cards.paths import DEFAULT_BLACKLIST_PATH
from tool.image_resource_pipeline.cards.models import ExcelCard
from tool.image_resource_pipeline.cards.catalog import (
    build_card_prepare_room_url, parse_excel_cards, read_blacklist_names, split_blacklisted_cards,
)
from tool.image_resource_pipeline.cards.chains import build_plan, parse_evolution_chains
from tool.image_resource_pipeline.cards.reports import build_card_stage_categories, write_card_stage_categories


class CardResourceToolTest(unittest.TestCase):
    def test_blacklist_reader_preserves_names_and_exact_ids(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "blacklist.csv"
            path.write_text("名称\n未实装卡片\n0x113901e0\n", encoding="utf-8-sig")
            self.assertEqual(read_blacklist_names(path), {"未实装卡片", "0x113901e0"})

    def test_retired_smoothie_id_is_blocked_without_removing_icecream_transfer(self):
        cards = {
            item_id: ExcelCard(item_id, name, (build_card_prepare_room_url(item_id),), row)
            for row, (item_id, name) in enumerate((
                ("0x113901d0", "冰激凌"),
                ("0x113901de", "果蔬冰淇淋"),
                ("0x113901df", "极寒冰沙"),
                ("0x113901e0", "极寒冰沙"),
                ("0x11100000", "魔法棉花糖"),
            ), start=2)
        }
        active, blocked = split_blacklisted_cards(cards, read_blacklist_names(DEFAULT_BLACKLIST_PATH))
        self.assertEqual(set(active), {"0x113901d0", "0x113901de", "0x113901df"})
        self.assertEqual({row["Excel ID"] for row in blocked}, {"0x113901e0", "0x11100000"})

        compose = """
        <ComposeorUpgrade><Translate desc="果蔬冰淇淋" id="0x113901de">
            <Material><raw_item desc="冰激凌" id="0x113901d0"/></Material>
        </Translate><Translate desc="极寒冰沙" id="0x113901df">
            <Material><raw_item desc="果蔬冰淇淋" id="0x113901de"/></Material>
        </Translate></ComposeorUpgrade>
        """.encode("utf-8")
        planned, _, _, singles = build_plan(parse_evolution_chains(compose), [], active)
        self.assertEqual({card.filename for card in planned}, {
            "冰激凌-0.png", "冰激凌-1.png", "冰激凌-2.png",
        })
        self.assertEqual(singles, [])

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
            "tool.image_resource_pipeline.cards.catalog.read_xlsx_rows",
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

    def test_card_stage_categories_only_store_gold_and_fusion_exceptions(self):
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

            categories = build_card_stage_categories(rows, image_dir)
            self.assertEqual(categories, {"gold": ["雷神"], "fusion": ["融合卡"]})

            output_path = root / "card_stage_categories.json"
            write_card_stage_categories(output_path, rows, image_dir)
            loaded_categories = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded_categories, categories)
            self.assertTrue(output_path.read_text(encoding="utf-8").startswith("{\n"))


if __name__ == "__main__":
    unittest.main()
