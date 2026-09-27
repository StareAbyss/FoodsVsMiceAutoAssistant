import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LoginPlatformSettingsTest(unittest.TestCase):
    def test_default_settings_and_resource_groups(self):
        settings = json.loads(
            (ROOT / "resource" / "template" / "settings.json").read_text(encoding="utf-8")
        )
        self.assertEqual(settings["login_settings"]["platform"], "4399")
        self.assertEqual(settings["login_settings"]["qq_space_server"], 0)
        self.assertEqual(settings["4399_login_info"], {"use_password": False})
        self.assertNotIn("path", settings["qq_login_info"])
        self.assertNotIn("password", settings["level_2"]["1p"])

        credentials = json.loads(
            (ROOT / "resource" / "template" / "login_credentials.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(credentials), {"qq", "4399", "level_2"})

        login_root = ROOT / "resource" / "image" / "common" / "登录"
        self.assertTrue((login_root / "通用" / "小号列表.png").is_file())
        self.assertTrue((login_root / "QQ空间" / "密码登录.png").is_file())
        self.assertTrue((login_root / "QQ大厅" / "1_我最近玩过的服务器_QQ大厅.png").is_file())
        self.assertTrue((login_root / "4399" / "4399_用户名.png").is_file())
        self.assertFalse((login_root / "3366").exists())


if __name__ == "__main__":
    unittest.main()
