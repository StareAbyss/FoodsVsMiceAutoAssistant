"""卡片名称选择 Demo 的解析规则回归测试。"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QFontMetrics, QPalette

from test.card_name_selector_demo.demo import (
    PRIMARY_TEXT_ROLE,
    SECONDARY_TEXT_ROLE,
    SHRINK_LINE_ROLE,
    CardCatalog,
    CardNameSelectorDemo,
    CompactCardItemDelegate,
)


class CardCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = CardCatalog()

    def test_card_type_uses_configured_priority_and_existing_images(self):
        result = self.catalog.parse("海星")
        self.assertEqual(result.kind, "type")
        self.assertTrue(result.targets)
        self.assertEqual(result.targets[0], "仙人球海星刺身-2")
        self.assertTrue(all(self.catalog.card_path(name) for name in result.targets))

    def test_fuzzy_name_expands_from_high_to_low_stage(self):
        result = self.catalog.parse("炭烧海星")
        self.assertEqual(result.kind, "fuzzy")
        self.assertEqual(result.targets, ("炭烧海星-2", "炭烧海星-1", "炭烧海星-0"))

    def test_precise_name_keeps_only_selected_stage(self):
        result = self.catalog.parse("炭烧海星-1")
        self.assertEqual(result.kind, "precise")
        self.assertEqual(result.targets, ("炭烧海星-1",))

    def test_missing_resource_is_unresolved(self):
        result = self.catalog.parse("绝对不存在的卡片")
        self.assertEqual(result.kind, "unresolved")
        self.assertEqual(result.targets, ())

    def test_search_card_type_by_child_card(self):
        results = self.catalog.filter_card_types("花火龙")
        self.assertTrue(any(card_type.canonical_name == "产火" for card_type in results))

    def test_search_concrete_card_uses_resource_base_name(self):
        results = self.catalog.filter_cards("仙人球海星")
        self.assertTrue(any(card.base_name == "仙人球海星刺身" for card in results))

    def test_minimal_category_table_distinguishes_gold_and_fusion_labels(self):
        self.assertEqual(self.catalog.cards["雷神"].chain_kind, "gold")
        self.assertEqual(self.catalog.cards["雷神"].stage_label(3), "终转")
        self.assertEqual(self.catalog.cards["仙人球海星刺身"].chain_kind, "fusion")
        self.assertEqual(self.catalog.cards["仙人球海星刺身"].stage_label(1), "深融")

    def test_manual_card_images_are_discovered_without_metadata_entry(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            image_dir = root / "准备房间"
            image_dir.mkdir()
            (image_dir / "用户自制卡-0.png").touch()
            (image_dir / "用户自制卡-2.png").touch()
            (image_dir / "用户自制卡-4.png").touch()
            card_type_path = root / "card_type.json"
            card_type_path.write_text("[]", encoding="utf-8")

            catalog = CardCatalog(
                card_type_path=str(card_type_path),
                image_dir=str(image_dir),
                category_path=str(root / "missing_categories.json"),
            )

            result = catalog.parse("用户自制卡")
            self.assertEqual(result.kind, "fuzzy")
            self.assertEqual(result.targets, ("用户自制卡-4", "用户自制卡-2", "用户自制卡-0"))
            self.assertEqual(catalog.cards["用户自制卡"].stage_label(0), "不转")
            self.assertEqual(catalog.cards["用户自制卡"].stage_label(4), "终转")


class CardNameSelectorInteractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = CardNameSelectorDemo()

    def tearDown(self):
        self.window.close()

    def test_type_click_writes_type_name_to_input(self):
        first_item = self.window.catalog_list.item(0)
        expected_name = first_item.data(256)
        self.window._choose_catalog_item(first_item)
        self.assertEqual(self.window.name_input.text(), expected_name)
        self.assertEqual(self.window.catalog.parse(expected_name).kind, "type")

    def test_type_tooltip_only_contains_other_aliases(self):
        first_item = self.window.catalog_list.item(0)
        self.assertIn("其他别名：", first_item.toolTip())
        self.assertNotIn("配置成员", first_item.toolTip())

    def test_card_and_stage_click_update_same_input(self):
        self.window.mode_combo.setCurrentIndex(1)
        self.window.search_input.setText("仙人球海星刺身")
        card_item = self.window.catalog_list.item(0)
        self.window._choose_catalog_item(card_item)
        self.assertEqual(self.window.name_input.text(), "仙人球海星刺身")

        precise_item = self.window.stage_list.item(2)
        self.window._choose_stage(precise_item)
        self.assertEqual(self.window.name_input.text(), "仙人球海星刺身-1")
        self.assertEqual(self.window.catalog.parse(self.window.name_input.text()).kind, "precise")

    def test_uses_faa_font_without_forcing_qt_style_sheet(self):
        from function.globals import EXTRA

        self.assertEqual(self.window.font().family(), EXTRA.Q_FONT.family())
        self.assertEqual(self.window.styleSheet(), "")

    def test_compact_labels_match_editor_wording(self):
        self.assertEqual(self.window.status_badge.text(), "解析结果")
        self.assertFalse(hasattr(self.window, "normalized_label"))
        self.assertIn("个可识别候选", self.window.result_count_label.text())
        selector_title = next(
            label for label in self.window.findChildren(type(self.window.status_badge))
            if label.text() == "卡片选择"
        )
        self.assertEqual(self.window.status_badge.font().pointSize(), selector_title.font().pointSize())
        self.assertGreaterEqual(
            self.window.parsed_list.height(),
            self.window.parsed_list.gridSize().height() * 2 + 10,
        )
        self.assertFalse(self.window.status_detail.wordWrap())

    def test_parsed_preview_has_no_number_and_fits_column_width(self):
        first_item = self.window.parsed_list.item(0)
        first_line = first_item.text().splitlines()[0]
        self.assertFalse(first_line.startswith("1. "))
        fitted_font = CompactCardItemDelegate.fit_font(
            first_line,
            self.window.parsed_list.font(),
            self.window.parsed_list.gridSize().width() - 4,
        )
        self.assertLessEqual(
            QFontMetrics(fitted_font).horizontalAdvance(first_line),
            self.window.parsed_list.gridSize().width() - 4,
        )
        self.assertEqual(
            self.window.parsed_list.gridSize().width(),
            self.window.catalog_list.gridSize().width(),
        )

    def test_stage_label_keeps_default_font_when_precise_name_shrinks(self):
        self.window.mode_combo.setCurrentIndex(1)
        self.window.search_input.setText("仙人球海星刺身")
        self.window._choose_catalog_item(self.window.catalog_list.item(0))
        fusion_item = self.window.stage_list.item(1)
        self.assertEqual(fusion_item.data(PRIMARY_TEXT_ROLE), "初融")
        self.assertEqual(fusion_item.data(SHRINK_LINE_ROLE), 2)
        self.assertEqual(fusion_item.data(SECONDARY_TEXT_ROLE), "仙人球海星刺身-0")

    def test_delegate_item_rect_uses_configured_grid_size(self):
        self.window.show()
        self.app.processEvents()
        item_rect = self.window.catalog_list.visualItemRect(self.window.catalog_list.item(0))
        grid_size = self.window.catalog_list.gridSize()
        self.assertGreaterEqual(item_rect.width(), grid_size.width() - 2)
        self.assertGreaterEqual(item_rect.height(), grid_size.height() - 2)

    def test_two_main_panels_follow_the_same_window_width(self):
        self.window.show()
        self.app.processEvents()
        self.assertEqual(self.window.result_panel.width(), self.window.selector_panel.width())

    def test_stage_panel_is_exactly_two_columns_wide(self):
        self.window.mode_combo.setCurrentIndex(1)
        self.window.search_input.setText("仙人球海星刺身")
        self.window._choose_catalog_item(self.window.catalog_list.item(0))
        self.window.show()
        self.app.processEvents()

        expected_width = self.window._grid_view_width(self.window.stage_list, 2) + 16
        self.assertEqual(self.window.stage_panel.width(), expected_width)
        first_rect = self.window.stage_list.visualItemRect(self.window.stage_list.item(0))
        second_rect = self.window.stage_list.visualItemRect(self.window.stage_list.item(1))
        third_rect = self.window.stage_list.visualItemRect(self.window.stage_list.item(2))
        self.assertEqual(first_rect.y(), second_rect.y())
        self.assertGreater(third_rect.y(), first_rect.y())

    def test_battle_plan_editor_dialog_embeds_selector_and_keeps_update_callback(self):
        from function.core.qmw_editor_of_battle_plan import InfoEditorOfCards

        changed_names = []
        dialog = None

        def record_change():
            changed_names.append(dialog.WidgetNameInput.text())

        try:
            dialog = InfoEditorOfCards({"name": "海星"}, record_change)
            dialog.show()
            self.app.processEvents()
            self.assertIs(dialog.WidgetNameInput, dialog.CardNameSelector.name_input)
            self.assertEqual(dialog.WidgetNameInput.text(), "海星")
            self.assertEqual((dialog.width(), dialog.height()), (860, 820))

            dialog.CardNameSelector.mode_combo.setCurrentIndex(1)
            dialog.CardNameSelector.search_input.setText("仙人球海星刺身")
            self.app.processEvents()
            dialog.CardNameSelector._choose_catalog_item(dialog.CardNameSelector.catalog_list.item(0))
            self.app.processEvents()
            self.assertEqual(changed_names[-1], "仙人球海星刺身")
        finally:
            if dialog is not None:
                dialog.close()

    def test_open_plan_warning_reports_unresolved_cards_without_modifying_names(self):
        from function.core.qmw_editor_of_battle_plan import QMWEditorOfBattlePlan

        cards = [
            SimpleNamespace(card_id=1, name="海星"),
            SimpleNamespace(card_id=2, name="炭烧海星-1"),
            SimpleNamespace(card_id=3, name="无法识别的测试卡"),
        ]
        editor = SimpleNamespace(battle_plan=SimpleNamespace(cards=cards))

        unresolved_cards = QMWEditorOfBattlePlan.find_unresolved_plan_cards(editor)
        self.assertEqual(unresolved_cards, [(3, "无法识别的测试卡")])

        with patch(
                "function.core.qmw_editor_of_battle_plan.QMessageBox.warning"
        ) as warning:
            QMWEditorOfBattlePlan.show_unresolved_card_warning(editor, unresolved_cards)

        warning.assert_called_once()
        self.assertIn("ID 3：无法识别的测试卡", warning.call_args.args[2])
        self.assertEqual([card.name for card in cards], ["海星", "炭烧海星-1", "无法识别的测试卡"])

    def test_follows_application_palette_change(self):
        original_palette = QPalette(self.app.palette())
        try:
            dark_palette = QPalette(original_palette)
            dark_palette.setColor(QPalette.ColorRole.Window, QColor("#202124"))
            dark_palette.setColor(QPalette.ColorRole.WindowText, QColor("#f1f3f4"))
            dark_palette.setColor(QPalette.ColorRole.Base, QColor("#292a2d"))
            dark_palette.setColor(QPalette.ColorRole.Text, QColor("#f1f3f4"))
            self.app.setPalette(dark_palette)
            self.app.processEvents()
            self.assertEqual(
                self.window.palette().color(QPalette.ColorRole.Window),
                QColor("#202124"),
            )
        finally:
            self.app.setPalette(original_palette)
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
