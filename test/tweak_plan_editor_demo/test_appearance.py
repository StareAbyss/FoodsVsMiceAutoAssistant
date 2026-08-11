"""微调方案编辑器 Demo 的 FAA 外观接入测试。"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QSpinBox,
)

from function.widget.CardNameSelector import apply_faa_application_style
from test.tweak_plan_editor_demo.demo import (
    TweakPlanEditorDemo,
    create_neutralized_palette,
    create_theme_preview_palette,
)
from test.tweak_plan_editor_demo.model import TweakPlanDraft


class TweakPlanAppearanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.original_palette = QPalette(cls.app.palette())
        apply_faa_application_style(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.app.setPalette(cls.original_palette)

    def setUp(self):
        self.app.setPalette(self.original_palette)
        self.window = TweakPlanEditorDemo(show_default_notice=False)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.setPalette(self.original_palette)
        self.app.processEvents()

    def test_uses_same_font_as_faa_main_window(self):
        from function.globals import EXTRA

        self.assertEqual(self.window.font().family(), EXTRA.Q_FONT.family())
        self.assertEqual(self.window.font().pointSize(), EXTRA.Q_FONT.pointSize())

    def test_dark_preview_updates_application_and_window_palette(self):
        self.window.set_theme_mode("dark")
        self.app.processEvents()

        expected = QColor("#202124")
        self.assertEqual(
            self.app.palette().color(QPalette.ColorRole.Window),
            expected,
        )
        self.assertEqual(
            self.window.palette().color(QPalette.ColorRole.Window),
            expected,
        )
        self.assertIn("#202124", self.window.styleSheet())

    def test_switching_back_to_system_restores_initial_palette(self):
        original_window_color = self.original_palette.color(QPalette.ColorRole.Window)
        self.window.set_theme_mode("dark")
        self.window.set_theme_mode("system")
        self.app.processEvents()

        self.assertEqual(
            self.app.palette().color(QPalette.ColorRole.Window),
            original_window_color,
        )

    def test_light_and_dark_palettes_have_expected_contrast(self):
        light = create_theme_preview_palette("light")
        dark = create_theme_preview_palette("dark")

        self.assertGreater(light.color(QPalette.ColorRole.Window).lightness(), 128)
        self.assertLess(dark.color(QPalette.ColorRole.Window).lightness(), 128)

    def test_unknown_theme_is_rejected(self):
        with self.assertRaises(ValueError):
            create_theme_preview_palette("neon")

    def test_system_accent_is_replaced_with_neutral_highlight(self):
        system_palette = QPalette(self.original_palette)
        system_palette.setColor(QPalette.ColorRole.Window, QColor("#F3F3F3"))
        system_palette.setColor(QPalette.ColorRole.Highlight, QColor("#FF0000"))

        neutral = create_neutralized_palette(system_palette)

        self.assertEqual(
            neutral.color(QPalette.ColorRole.Highlight),
            QColor("#6B7280"),
        )
        self.assertNotEqual(
            neutral.color(QPalette.ColorRole.Highlight),
            QColor("#FF0000"),
        )

    def test_demo_style_does_not_force_bold_font(self):
        self.assertNotIn("font-weight", self.window.styleSheet())

    def test_native_qt_controls_are_not_overridden_by_qss(self):
        style_sheet = self.window.styleSheet()
        for native_widget in (
            "QComboBox",
            "QSpinBox",
            "QLineEdit",
            "QPlainTextEdit",
            "QPushButton",
            "QGroupBox",
        ):
            self.assertNotIn(native_widget, style_sheet)

    def test_save_and_import_buttons_use_native_palette(self):
        self.assertEqual(self.window.save_button.objectName(), "")
        self.assertEqual(self.window.import_button.objectName(), "")
        for button in (self.window.save_button, self.window.import_button):
            for group in (
                QPalette.ColorGroup.Active,
                QPalette.ColorGroup.Inactive,
                QPalette.ColorGroup.Disabled,
            ):
                self.assertEqual(
                    button.palette().color(group, QPalette.ColorRole.ButtonText),
                    self.window.new_button.palette().color(
                        group,
                        QPalette.ColorRole.ButtonText,
                    ),
                )

    def test_optional_booleans_use_explicit_dropdowns(self):
        selector = self.window.senior_selector
        self.assertEqual(
            [selector.combo.itemText(index) for index in range(selector.combo.count())],
            ["缺省 (默认:否)", "是", "否"],
        )
        self.assertEqual(self.window.findChildren(QCheckBox), [])

        selector.set_value(True)
        self.assertIs(self.window._collect_draft().senior_setting, True)
        selector.set_value(False)
        self.assertIs(self.window._collect_draft().senior_setting, False)
        selector.set_value(None)
        self.assertIsNone(self.window._collect_draft().senior_setting)

    def test_inherited_options_show_values_from_default_plan(self):
        self.assertEqual(
            self.window.random_mode_combo.itemText(0),
            "继承 (默认:关闭)",
        )
        self.assertEqual(
            self.window.recording_player_combo.itemText(0),
            "继承 (默认:1P)",
        )
        for key, selector in self.window.auto_card_selectors.items():
            self.assertEqual(
                selector.combo.itemText(0),
                "缺省 (默认:否)" if key == "timer" else "缺省 (默认:是)",
            )
        self.assertNotIn("coffee", self.window.auto_card_selectors)
        self.assertIn("timer", self.window.auto_card_selectors)
        self.assertNotIn("mat", self.window.auto_card_selectors)
        self.assertEqual(
            self.window.auto_mat_card_enabled_selector.combo.itemText(0),
            "缺省 (默认:是)",
        )
        self.assertEqual(
            self.window.auto_mat_card_first_selector.combo.itemText(0),
            "缺省 (默认:是)",
        )

    def test_mat_card_first_uses_requested_chinese_tristate_dropdown(self):
        selector = self.window.auto_mat_card_first_selector
        self.assertIn(
            "优先使用承载卡（0费承载专用）",
            [label.text() for label in selector.findChildren(QLabel)],
        )
        selector.set_value(False)
        self.assertIs(self.window._collect_draft().auto_mat_card_first, False)

    def test_editor_groups_match_user_facing_categories(self):
        groups = {
            group.title(): group
            for group in self.window.findChildren(QGroupBox)
        }
        self.assertIn("自动承载", groups)
        self.assertIn("自动辅助卡片", groups)
        self.assertIn("战斗节奏", groups)
        self.assertIn("高级战斗", groups)
        self.assertIn("战斗录制", groups)
        self.assertIs(
            self.window.auto_mat_card_enabled_selector.parentWidget(),
            groups["自动承载"],
        )
        self.assertIs(
            self.window.auto_mat_card_first_selector.parentWidget(),
            groups["自动承载"],
        )
        self.assertIs(
            self.window.senior_selector.parentWidget(),
            groups["高级战斗"],
        )
        self.assertGreater(
            groups["高级战斗"].y(),
            groups["自动辅助卡片"].y(),
        )
        self.assertGreater(
            groups["战斗录制"].y(),
            groups["高级战斗"].y(),
        )

    def test_helper_text_uses_user_color_scheme_level_nine(self):
        from function.globals import EXTRA

        theme = (
            "dark"
            if self.window.palette().color(QPalette.ColorRole.Window).lightness() < 128
            else "light"
        )
        expected = f"#{EXTRA.get_user_text_color(9, theme)}".lower()
        helper_size = max(8, self.window.font().pointSize() - 1)
        self.assertIn(
            f"QLabel#helperText {{ color: {expected}; font-size: {helper_size}pt; }}",
            self.window.styleSheet(),
        )

    def test_preview_is_narrow_and_does_not_show_developer_audit(self):
        group_titles = [
            group.title()
            for group in self.window.findChildren(QGroupBox)
        ]
        self.assertNotIn("当前源码接入状态", group_titles)

        left_width, right_width = self.window.main_splitter.sizes()
        self.assertGreater(left_width, right_width * 2)

    def test_option_groups_are_single_column_and_window_is_compact(self):
        self.assertEqual((self.window.width(), self.window.height()), (1080, 840))
        self.assertEqual(
            (self.window.minimumWidth(), self.window.minimumHeight()),
            (960, 680),
        )

        option_groups = [
            [
                self.window.recording_selector,
                self.window.timestamp_selector,
                self.window.recording_player_row,
            ],
            [
                self.window.auto_mat_card_enabled_selector,
                self.window.auto_mat_card_first_selector,
            ],
            list(self.window.auto_card_selectors.values()),
        ]
        for widgets in option_groups:
            y_positions = [widget.y() for widget in widgets]
            self.assertEqual(y_positions, sorted(set(y_positions)))

    def test_toolbar_uses_immediate_library_workflow_and_has_tooltips(self):
        self.assertFalse(hasattr(self.window, "load_button"))
        self.assertEqual(self.window.new_button.text(), "新建")
        self.assertEqual(self.window.save_button.text(), "保存")
        self.assertEqual(self.window.delete_button.text(), "删除")
        self.assertEqual(self.window.import_button.text(), "从外部导入 JSON…")
        for widget in (
            self.window.plan_selector,
            self.window.new_button,
            self.window.save_button,
            self.window.delete_button,
            self.window.import_button,
        ):
            self.assertTrue(widget.toolTip())
        self.assertGreater(
            self.window.operation_status_label.x(),
            self.window.import_button.x(),
        )

    def test_success_status_uses_green_level_three_and_starts_fade(self):
        from function.globals import EXTRA

        self.window.set_theme_mode("dark")
        self.window._show_operation_status("已保存：测试方案.json")
        self.assertTrue(self.window.operation_status_label.isVisible())
        self.assertEqual(
            self.window.operation_status_label.palette().color(
                QPalette.ColorRole.WindowText
            ).name(),
            f"#{EXTRA.get_user_text_color(3, 'dark')}".lower(),
        )
        self.window._fade_operation_status()
        self.assertEqual(self.window.operation_status_animation.endValue(), 0.0)

    def test_loading_default_uses_notice_bar_without_popup_or_footer_hints(self):
        with patch(
            "function.core.qmw_editor_of_tweak_plan.QMessageBox.information"
        ) as information:
            self.window._load_path(self.window.tweak_plan_dir / "!默认.json")
            self.app.processEvents()

        information.assert_not_called()
        self.assertIn("将继承此方案的对应项", self.window.read_only_notice.text())
        self.assertFalse(hasattr(self.window, "status_label"))
        label_texts = [
            label.text()
            for label in self.window.findChildren(QLabel)
        ]
        self.assertFalse(
            any(text.startswith("继承项会在括号内显示") for text in label_texts)
        )

    def test_new_plan_copies_default_saves_and_adds_sequence_on_name_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            tweak_dir = Path(directory)
            default_source = self.window.tweak_plan_dir / "!默认.json"
            (tweak_dir / "!默认.json").write_bytes(default_source.read_bytes())
            window = TweakPlanEditorDemo(tweak_dir, show_default_notice=False)

            window._new_plan()
            first_data = json.loads(
                (tweak_dir / "新的方案.json").read_text(encoding="utf-8")
            )
            window._new_plan()
            second_path = tweak_dir / "新的方案 (2).json"
            second_data = json.loads(second_path.read_text(encoding="utf-8"))

            self.assertEqual(first_data["meta_data"]["tips"], "")
            self.assertEqual(second_data["meta_data"]["tips"], "")
            self.assertNotEqual(
                first_data["meta_data"]["uuid"],
                second_data["meta_data"]["uuid"],
            )
            self.assertEqual(window.current_path, second_path)
            self.assertEqual(
                window.operation_status_label.text(),
                "已新建：新的方案 (2).json",
            )
            window.close()

    def test_import_keeps_uuid_unless_conflicting_then_warns_and_replaces_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tweak_dir = root / "tweak"
            tweak_dir.mkdir()
            default_source = self.window.tweak_plan_dir / "!默认.json"
            (tweak_dir / "!默认.json").write_bytes(default_source.read_bytes())
            conflict_uuid = "00000000-0000-0000-0000-000000000099"
            (tweak_dir / "已有方案.json").write_text(
                json.dumps({"meta_data": {"uuid": conflict_uuid}}),
                encoding="utf-8",
            )
            external_path = root / "外部方案.json"
            external_path.write_text(
                json.dumps({"meta_data": {"uuid": conflict_uuid}}),
                encoding="utf-8",
            )
            window = TweakPlanEditorDemo(tweak_dir, show_default_notice=False)

            with patch(
                "function.core.qmw_editor_of_tweak_plan.QFileDialog.getOpenFileName",
                return_value=(str(external_path), "JSON 文件 (*.json)"),
            ), patch(
                "function.core.qmw_editor_of_tweak_plan.QMessageBox.warning"
            ) as warning:
                window._import_plan()

            imported_data = json.loads(
                (tweak_dir / "外部方案.json").read_text(encoding="utf-8")
            )
            new_uuid = imported_data["meta_data"]["uuid"]
            self.assertNotEqual(new_uuid, conflict_uuid)
            message = warning.call_args.args[2]
            self.assertEqual(
                message,
                f"微调方案【外部方案】(UUID:{conflict_uuid})与另一方案 "
                f"【已有方案】(UUID:{conflict_uuid}) 发生冲突，你导入的方案已修改UUID为：{new_uuid}",
            )
            self.assertEqual(
                window.operation_status_label.text(),
                "已导入：外部方案.json",
            )
            window.close()

    def test_uuid_conflicts_are_repaired_during_scan_and_save(self):
        with tempfile.TemporaryDirectory() as directory:
            tweak_dir = Path(directory)
            default_source = self.window.tweak_plan_dir / "!默认.json"
            (tweak_dir / "!默认.json").write_bytes(default_source.read_bytes())
            window = TweakPlanEditorDemo(tweak_dir, show_default_notice=False)
            conflict_uuid = "00000000-0000-0000-0000-000000000088"
            for name in ("方案A", "方案B"):
                (tweak_dir / f"{name}.json").write_text(
                    json.dumps({"meta_data": {"uuid": conflict_uuid}}),
                    encoding="utf-8",
                )

            messages = window._repair_uuid_conflicts()
            repaired_b = json.loads(
                (tweak_dir / "方案B.json").read_text(encoding="utf-8")
            )["meta_data"]["uuid"]
            self.assertEqual(len(messages), 1)
            self.assertNotEqual(repaired_b, conflict_uuid)

            window._load_plan_list()
            window._load_path(tweak_dir / "方案B.json")
            window.uuid_input.setText(conflict_uuid)
            with patch(
                "function.core.qmw_editor_of_tweak_plan.QMessageBox.warning"
            ) as warning:
                window._save_plan()
            saved_uuid = json.loads(
                (tweak_dir / "方案B.json").read_text(encoding="utf-8")
            )["meta_data"]["uuid"]
            self.assertNotEqual(saved_uuid, conflict_uuid)
            warning.assert_called_once()
            window.close()

    def test_delete_confirms_and_uses_system_recycle_bin(self):
        with tempfile.TemporaryDirectory() as directory:
            tweak_dir = Path(directory)
            default_source = self.window.tweak_plan_dir / "!默认.json"
            (tweak_dir / "!默认.json").write_bytes(default_source.read_bytes())
            plan_path = tweak_dir / "待删除.json"
            plan_path.write_text(
                json.dumps({
                    "meta_data": {
                        "uuid": "00000000-0000-0000-0000-000000000077"
                    }
                }),
                encoding="utf-8",
            )
            window = TweakPlanEditorDemo(tweak_dir, show_default_notice=False)
            window._load_path(plan_path)

            with patch(
                "function.core.qmw_editor_of_tweak_plan.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ), patch(
                "function.core.qmw_editor_of_tweak_plan.QFile.moveToTrash",
                return_value=True,
            ) as move_to_trash:
                window._delete_plan()

            move_to_trash.assert_called_once_with(str(plan_path))
            self.assertEqual(window.current_path, tweak_dir / "!默认.json")
            self.assertEqual(
                window.operation_status_label.text(),
                "已移入回收站：待删除.json",
            )
            window.close()

    def test_name_only_save_renames_path_and_preserves_uuid(self):
        with tempfile.TemporaryDirectory() as directory:
            tweak_dir = Path(directory)
            default_source = self.window.tweak_plan_dir / "!默认.json"
            (tweak_dir / "!默认.json").write_bytes(default_source.read_bytes())
            old_uuid = "00000000-0000-0000-0000-000000000066"
            old_path = tweak_dir / "原名称.json"
            old_path.write_text(
                json.dumps({"meta_data": {"uuid": old_uuid}}),
                encoding="utf-8",
            )
            window = TweakPlanEditorDemo(tweak_dir, show_default_notice=False)
            window._load_path(old_path)
            window.file_name_input.setText("新名称")
            window._save_plan()

            new_path = tweak_dir / "新名称.json"
            self.assertFalse(old_path.exists())
            self.assertTrue(new_path.is_file())
            self.assertEqual(window.current_path, new_path)
            self.assertEqual(
                json.loads(new_path.read_text(encoding="utf-8"))["meta_data"]["uuid"],
                old_uuid,
            )
            self.assertEqual(
                window.operation_status_label.text(),
                "已保存：新名称.json",
            )
            window.close()

    def test_duplicate_name_is_rejected_and_restored_before_save(self):
        with tempfile.TemporaryDirectory() as directory:
            tweak_dir = Path(directory)
            default_source = self.window.tweak_plan_dir / "!默认.json"
            (tweak_dir / "!默认.json").write_bytes(default_source.read_bytes())
            for index, name in enumerate(("方案A", "方案B"), start=1):
                (tweak_dir / f"{name}.json").write_text(
                    json.dumps({
                        "meta_data": {
                            "uuid": f"00000000-0000-0000-0000-{index:012d}"
                        }
                    }),
                    encoding="utf-8",
                )
            window = TweakPlanEditorDemo(tweak_dir, show_default_notice=False)
            window._load_path(tweak_dir / "方案A.json")
            window.file_name_input.setText("方案B")

            with patch(
                "function.core.qmw_editor_of_tweak_plan.QMessageBox.warning"
            ) as warning:
                accepted = window._validate_current_plan_name()

            self.assertFalse(accepted)
            self.assertEqual(window.file_name_input.text(), "方案A")
            self.assertTrue((tweak_dir / "方案A.json").is_file())
            self.assertTrue((tweak_dir / "方案B.json").is_file())
            self.assertIn("名称已恢复为【方案A】", warning.call_args.args[2])
            window.close()

    def test_random_interval_editor_uses_integer_milliseconds_but_json_uses_seconds(self):
        self.assertIsInstance(self.window.random_min_spin, QSpinBox)
        self.assertEqual(self.window.random_min_spin.suffix(), " ms")
        self.window.random_mode_combo.setCurrentIndex(
            self.window.random_mode_combo.findData("range")
        )
        self.window.random_min_spin.setValue(55)
        self.window.random_max_spin.setValue(275)

        draft = self.window._collect_draft()
        self.assertEqual(draft.random_interval_min, 0.055)
        self.assertEqual(draft.random_interval_max, 0.275)
        self.assertEqual(
            draft.to_mapping()["meta_data"]["cd_after_use_random"],
            {"active": True, "range": [0.055, 0.275]},
        )

        self.window._apply_draft(
            TweakPlanDraft(
                random_interval_mode="range",
                random_interval_min=0.123,
                random_interval_max=0.456,
            ),
            "毫秒换算测试",
        )
        self.assertEqual(self.window.random_min_spin.value(), 123)
        self.assertEqual(self.window.random_max_spin.value(), 456)

    def test_uuid_is_read_only_and_new_plan_uses_uuid1(self):
        import uuid

        self.assertTrue(self.window.uuid_input.isReadOnly())
        with tempfile.TemporaryDirectory() as directory:
            tweak_dir = Path(directory)
            default_source = self.window.tweak_plan_dir / "!默认.json"
            (tweak_dir / "!默认.json").write_bytes(default_source.read_bytes())
            window = TweakPlanEditorDemo(
                tweak_plan_dir=tweak_dir,
                show_default_notice=False,
            )
            window._new_plan()
            self.assertEqual(uuid.UUID(window.uuid_input.text()).version, 1)
            self.assertTrue((tweak_dir / "新的方案.json").is_file())
            window.close()
        self.assertTrue(self.window.version_input.isReadOnly())
        self.assertTrue(self.window.faa_version_input.isReadOnly())
        self.assertFalse(self.window.uuid_input.isEnabled())
        self.assertFalse(self.window.version_input.isEnabled())
        self.assertFalse(self.window.faa_version_input.isEnabled())

    def test_built_in_plan_displays_its_fixed_uuid(self):
        self.window._load_path(self.window.tweak_plan_dir / "高级战斗.json")
        self.assertEqual(
            self.window.uuid_input.text(),
            "00000000-0000-0000-0000-000000000001",
        )
        self.assertEqual(self.window.plan_selector.currentText(), "高级战斗")

    def test_all_zero_default_plan_is_read_only(self):
        self.window._load_path(self.window.tweak_plan_dir / "!默认.json")

        self.assertFalse(self.window.plan_editable)
        self.assertTrue(self.window.file_name_input.isReadOnly())
        self.assertFalse(self.window.file_name_input.isEnabled())
        self.assertTrue(self.window.version_input.isReadOnly())
        self.assertTrue(self.window.tips_input.isReadOnly())
        self.assertFalse(self.window.tips_input.isEnabled())
        self.assertFalse(self.window.senior_selector.combo.isEnabled())
        self.assertFalse(self.window.save_button.isEnabled())
        self.assertFalse(self.window.delete_button.isEnabled())
        self.assertTrue(self.window.read_only_notice.isVisible())

    def test_new_plan_leaves_default_read_only_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            tweak_dir = Path(directory)
            default_source = self.window.tweak_plan_dir / "!默认.json"
            (tweak_dir / "!默认.json").write_bytes(default_source.read_bytes())
            window = TweakPlanEditorDemo(
                tweak_plan_dir=tweak_dir,
                show_default_notice=False,
            )
            window._new_plan()

            self.assertTrue(window.plan_editable)
            self.assertFalse(window.file_name_input.isReadOnly())
            self.assertTrue(window.file_name_input.isEnabled())
            self.assertFalse(window.tips_input.isReadOnly())
            self.assertTrue(window.tips_input.isEnabled())
            self.assertTrue(window.senior_selector.combo.isEnabled())
            self.assertTrue(window.save_button.isEnabled())
            self.assertTrue(window.delete_button.isEnabled())
            self.assertFalse(window.read_only_notice.isVisible())
            window.close()

    def test_default_read_only_notice_uses_information_dialog(self):
        with patch(
            "function.core.qmw_editor_of_tweak_plan.QMessageBox.information"
        ) as information:
            self.window._show_default_read_only_notice()

        information.assert_called_once()
        title = information.call_args.args[1]
        message = information.call_args.args[2]
        self.assertEqual(title, "默认方案仅供查阅")
        self.assertIn("不能编辑、保存或删除", message)

    def test_editing_updates_format_and_faa_versions_from_extra(self):
        from function.globals import EXTRA

        self.window.plan_editable = True
        self.window._apply_draft(
            TweakPlanDraft(version="0.1", faa_version="v0.0.0"),
            "旧方案",
        )
        self.window._set_plan_editable(True)
        self.assertEqual(self.window.version_input.text(), "0.1")
        self.assertEqual(self.window.faa_version_input.text(), "v0.0.0")

        self.window.senior_selector.set_value(True)
        self.app.processEvents()

        self.assertEqual(self.window.version_input.text(), EXTRA.TWEAK_PLAN_VERSION)
        self.assertEqual(self.window.faa_version_input.text(), EXTRA.VERSION)


if __name__ == "__main__":
    unittest.main()
