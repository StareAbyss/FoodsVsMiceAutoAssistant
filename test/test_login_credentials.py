import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from function.core.login_credentials import load_login_credentials, save_login_credentials


class LoginCredentialsTest(unittest.TestCase):
    @patch("function.core.login_credentials.encrypt_data", side_effect=lambda value: f"encrypted:{value}")
    @patch("function.core.login_credentials.decrypt_data", side_effect=lambda value: value.removeprefix("encrypted:"))
    def test_credentials_round_trip_in_one_file(self, _decrypt, _encrypt):
        credentials = {
            "qq": {
                "1p": {"username": "qq-1", "password": "qq-password-1"},
                "2p": {"username": "qq-2", "password": "qq-password-2"},
            },
            "4399": {
                "1p": {"username": "4399-1", "password": "4399-password-1"},
                "2p": {"username": "4399-2", "password": "4399-password-2"},
            },
            "level_2": {
                "1p": {"password": "level-2-1"},
                "2p": {"password": "level-2-2"},
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "config" / "login_credentials.json"
            save_login_credentials(file_path, credentials)

            stored = json.loads(file_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["qq"]["1p"]["password"], "encrypted:qq-password-1")
            self.assertEqual(stored["level_2"]["2p"]["password"], "encrypted:level-2-2")
            self.assertEqual(load_login_credentials(file_path), credentials)

    @patch("function.core.login_credentials.encrypt_data", side_effect=lambda value: f"encrypted:{value}")
    @patch("function.core.login_credentials.decrypt_data", side_effect=lambda value: value.removeprefix("encrypted:"))
    def test_first_load_migrates_legacy_files_and_level_2(self, _decrypt, _encrypt):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy_dir = root / "legacy"
            legacy_dir.mkdir()
            (legacy_dir / "QQ_account.json").write_text(
                json.dumps({
                    "1p": {"username": "qq-user", "password": "encrypted:qq-password"},
                    "2p": {"username": "", "password": ""},
                }),
                encoding="utf-8",
            )
            settings = {
                "qq_login_info": {"path": str(legacy_dir)},
                "4399_login_info": {"path": ""},
                "level_2": {
                    "1p": {"active": True, "password": "secondary"},
                    "2p": {"active": False, "password": ""},
                },
            }
            file_path = root / "config" / "login_credentials.json"

            credentials = load_login_credentials(file_path, legacy_settings=settings)

            self.assertEqual(credentials["qq"]["1p"]["username"], "qq-user")
            self.assertEqual(credentials["qq"]["1p"]["password"], "qq-password")
            self.assertEqual(credentials["level_2"]["1p"]["password"], "secondary")
            self.assertTrue(file_path.is_file())


if __name__ == "__main__":
    unittest.main()
