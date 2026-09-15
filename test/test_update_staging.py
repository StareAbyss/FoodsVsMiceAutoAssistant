import tempfile
import unittest
import zipfile
from pathlib import Path

from function.common.update_staging import StagingError, extract_single_root


class UpdateStagingExtractionTest(unittest.TestCase):

    def test_extract_strips_github_archive_root_with_full_commit(self):
        archive_root = f"FoodsVsMiceAutoAssistant-{'a' * 40}"
        explanation_name = "这是一个用于验证深目录解压时不会叠加仓库名和完整提交哈希的超长说明文件名.txt"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            archive_path = temp_root / "archive.zip"
            extract_root = temp_root / "update_cache" / "staging_work" / "source"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    f"{archive_root}/battle_plan_not_active/{explanation_name}",
                    "文件夹说明",
                )

            source_root = extract_single_root(archive_path, extract_root)

            explanation_path = source_root / "battle_plan_not_active" / explanation_name
            self.assertEqual(source_root, extract_root)
            self.assertEqual(explanation_path.read_text(encoding="utf-8"), "文件夹说明")
            self.assertFalse((extract_root / archive_root).exists())

    def test_extract_rejects_multiple_archive_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            archive_path = temp_root / "archive.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("root-a/LICENSE", "a")
                archive.writestr("root-b/LICENSE", "b")

            with self.assertRaisesRegex(StagingError, "Expected one archive root directory, got 2"):
                extract_single_root(archive_path, temp_root / "source")


if __name__ == "__main__":
    unittest.main()
