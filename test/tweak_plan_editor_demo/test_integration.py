"""微调方案编辑器正式入口与系统原生主题的集成检查。"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

from PyQt6.QtWidgets import QApplication

from function.core.qmw_editor_of_tweak_plan import QMWEditorOfTweakPlan


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class TweakPlanMainWindowIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_advanced_tools_navigation_has_tweak_editor_after_battle_editor(self):
        root = ElementTree.parse(REPOSITORY_ROOT / "resource/ui/FAA_3.0.ui").getroot()
        layout = root.find(".//layout[@name='Tab3LeftLayout1']")
        self.assertIsNotNone(layout)
        widget_names = [
            widget.get("name")
            for item in layout.findall("item")
            if (widget := item.find("widget")) is not None
        ]
        battle_index = widget_names.index("OpenEditorOfBattlePlan_Button")
        self.assertEqual(
            widget_names[battle_index + 1],
            "OpenEditorOfTweakPlan_Button",
        )
        self.assertNotIn("OpenPerformanceAnalysis_Button", widget_names)

    def test_main_window_uses_native_system_theme_without_forced_selector(self):
        root = ElementTree.parse(REPOSITORY_ROOT / "resource/ui/FAA_3.0.ui").getroot()
        self.assertIsNone(root.find(".//widget[@name='ThemeModeComboBox']"))
        self.assertIsNone(root.find(".//widget[@name='ThemeSelectionWidget']"))
        settings = json.loads(
            (REPOSITORY_ROOT / "resource/template/settings.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("theme_mode", settings)

    def test_formal_editor_hides_demo_only_theme_preview(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tweak_dir = Path(temp_dir)
            shutil.copy(
                REPOSITORY_ROOT / "resource/template/!默认.json",
                tweak_dir / "!默认.json",
            )
            window = QMWEditorOfTweakPlan(tweak_plan_dir=tweak_dir)
            self.assertEqual(window.windowTitle(), "微调方案编辑器")
            self.assertTrue(window.demo_badge.isHidden())
            self.assertTrue(window.theme_label.isHidden())
            self.assertTrue(window.theme_selector.isHidden())
            window.close()


if __name__ == "__main__":
    unittest.main()
