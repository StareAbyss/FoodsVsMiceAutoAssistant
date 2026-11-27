"""自动登录设置独立窗口的打开、平台切换和输入保留检查。"""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog

from function.globals.get_paths import PATHS

os.makedirs(PATHS["logs"], exist_ok=True)

from function.core.qmw_0_load_ui_file import QMainWindowLoadUI


class LoginSettingsDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(QMainWindowLoadUI, "init_tray_icon"):
            self.window = QMainWindowLoadUI()
        self.app.processEvents()

    def tearDown(self):
        self.window.LoginSettingsDialog.hide()
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()

    def test_home_button_opens_one_dialog_without_switching_main_page(self):
        original_page = self.window.tabWidget.currentWidget()
        dialog = self.window.LoginSettingsDialog

        self.window.LoginAutoSettingsButton.click()
        self.app.processEvents()
        self.assertIsInstance(dialog, QDialog)
        self.assertTrue(dialog.isWindow())
        self.assertTrue(dialog.isVisible())
        self.assertIs(self.window.tabWidget.currentWidget(), original_page)
        self.assertNotIn("登录设置", self.window.adv_opt_sections)

        self.window.LoginAutoSettingsButton.click()
        self.assertIs(self.window.LoginSettingsDialog, dialog)
        self.assertEqual(len(self.window.findChildren(QDialog, "LoginSettingsDialog")), 1)

    def test_each_platform_displays_its_own_settings(self):
        self.window.LoginAutoSettingsButton.click()
        for platform, show_4399, show_qq in (
            ("4399", True, False),
            ("QQ空间", False, True),
            ("QQ大厅", False, False),
        ):
            with self.subTest(platform=platform):
                self.window.LoginPlatformCombo.setCurrentText(platform)
                self.app.processEvents()
                self.assertEqual(self.window.Login4399Group.isVisible(), show_4399)
                self.assertEqual(self.window.LoginQQSpaceGroup.isVisible(), show_qq)
                self.assertEqual(self.window.LoginQQSpaceServerGroup.isVisible(), show_qq)
                self.assertTrue(self.window.LoginServerWaitGroup.isVisible())

    def test_closing_and_reopening_preserves_input(self):
        self.window.LoginPlatformCombo.setCurrentText("QQ空间")
        self.window.LoginAutoSettingsButton.click()
        self.window.LoginQQSpaceUsername1PInput.setText("test-account")
        self.window.LoginQQSpacePassword1PInput.setText("test-password")

        self.window.LoginSettingsDialog.close()
        self.window.LoginAutoSettingsButton.click()
        self.app.processEvents()

        self.assertEqual(self.window.LoginQQSpaceUsername1PInput.text(), "test-account")
        self.assertEqual(self.window.LoginQQSpacePassword1PInput.text(), "test-password")
        self.assertLessEqual(self.window.LoginQQSpaceUsername1PInput.height(), 30)
        self.assertLessEqual(self.window.LoginQQSpacePassword1PInput.height(), 30)


if __name__ == "__main__":
    unittest.main()
