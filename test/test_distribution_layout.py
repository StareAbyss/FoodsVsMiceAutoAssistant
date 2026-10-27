"""在隔离目录核对发行打包与热更新的共用布局，不创建正式发行包。"""

import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from function.common.distribution_layout import (
    PACKAGE_FILES, PACKAGE_FOLDERS, ROOT_ENTRY_DIRECTORY, ROOT_ENTRY_FILES, UV_ARCHIVE,
    ENVIRONMENT_INSTALLER_EXE, LAUNCHER_EXE, validate_source_entries,
)
from function.common.update_staging import (
    StagingError, build_distribution_from_source, validate_staging,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("faa_distribution_packager", ROOT / "一键生成分发资源.py")
packager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packager)


class DistributionLayoutTests(unittest.TestCase):
    """实际复制文件，并验证入口完整性、文件白名单和清理边界。"""

    def fixture(self, root):
        """生成最小源码布局，额外放入不应进入发行包的开发与运行缓存文件。"""
        def write(relative, content=b"fixture"):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        for folder, *_ in PACKAGE_FOLDERS:
            write(Path(folder) / "fixture.txt")
        for relative in PACKAGE_FILES:
            write(relative)
        for name in ROOT_ENTRY_FILES:
            write(ROOT_ENTRY_DIRECTORY / name, name.encode("utf-8"))
        write("function/faa_main.py", b"pass\n")
        write("plugins/updater/updater.py", b"pass\n")
        write("config/settings.json", b"personal settings")
        write("config/cus_images/背包_装备_需使用的/任意通用包裹.png", b"excluded")
        write("plugins/root_entries/extra-entry.exe", b"unlisted executable")
        write("plugins/root_entries/obsolete.bat", b"obsolete")
        write("plugins/root_entries/build.ps1", b"developer tool")
        write("plugins/launcher_scripts/obsolete.ps1", b"obsolete")
        write("plugins/launcher_scripts/bin/uv.exe", b"local cache")
        write("tool/faa_launcher/build.ps1", b"developer tool")
        write(".git/HEAD", b"source only")
        excel = Path("resource/db/点我获取更多图像资源 2026-10-27.xlsx")
        write(excel)
        return excel

    def test_packaging_and_staging_copy_identical_whitelisted_layout(self):
        with tempfile.TemporaryDirectory(prefix="FAA 共用发行布局 ") as directory:
            base = Path(directory)
            source, release, staging = base / "source", base / "release", base / "staging"
            excel = self.fixture(source)
            with contextlib.redirect_stdout(io.StringIO()):
                packager.create_distribution_plan(source, release, excel).run()
            build_distribution_from_source(source, staging)
            validate_staging(release)
            validate_staging(staging)

            def contents(root):
                """以相对路径和实际内容比较两种生成路径。"""
                return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}

            self.assertEqual(contents(release), contents(staging))
            self.assertEqual((release / LAUNCHER_EXE).read_bytes(), LAUNCHER_EXE.encode("utf-8"))
            self.assertEqual((release / ENVIRONMENT_INSTALLER_EXE).read_bytes(), ENVIRONMENT_INSTALLER_EXE.encode("utf-8"))
            self.assertTrue((release / UV_ARCHIVE).is_file())
            self.assertFalse(any(path.suffix in {".bat", ".ps1"} for path in release.rglob("*")))
            self.assertFalse((release / "plugins/launcher_scripts/bin").exists())
            self.assertFalse((release / "extra-entry.exe").exists())
            self.assertFalse((release / "config/settings.json").exists())
            self.assertFalse((release / ".git").exists())

    def test_missing_source_exe_fails_before_replacing_existing_output(self):
        with tempfile.TemporaryDirectory(prefix="FAA 缺失入口保护 ") as directory:
            root = Path(directory)
            source = root / "source"
            excel = self.fixture(source)
            (source / ROOT_ENTRY_DIRECTORY / ENVIRONMENT_INSTALLER_EXE).unlink()
            output = source / "dist/FAA"
            output.mkdir(parents=True)
            marker = output / "keep.txt"
            marker.write_text("previous output", encoding="utf-8")
            with patch.object(packager, "find_project_root", return_value=source), patch.object(packager, "require_existing_excel", return_value=excel):
                with self.assertRaisesRegex(FileNotFoundError, ENVIRONMENT_INSTALLER_EXE):
                    packager.main()
            self.assertEqual(marker.read_text(encoding="utf-8"), "previous output")
            with self.assertRaisesRegex(StagingError, ENVIRONMENT_INSTALLER_EXE):
                build_distribution_from_source(source, root / "staging")
            self.assertFalse((root / "staging").exists())

    def test_successful_packaging_archives_then_cleans_only_staging(self):
        """只有归档完成并通过发行校验后才删除暂存，源码与其他 dist 文件保留。"""
        with tempfile.TemporaryDirectory(prefix="FAA 发行暂存清理 ") as directory:
            base = Path(directory)
            source = base / "source"
            excel = self.fixture(source)
            extra = source / "function/globals/EXTRA.py"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text('VERSION = "v0.0.1"\n', encoding="utf-8")
            staging = source / "dist/FAA"
            retained = source / "dist/other/keep.txt"
            retained.parent.mkdir(parents=True)
            retained.write_text("keep", encoding="utf-8")
            with patch.object(packager, "find_project_root", return_value=source), \
                    patch.object(packager, "require_existing_excel", return_value=excel), \
                    patch.object(packager, "write_packaged_update_state", return_value=staging / "update_state.json"), \
                    contextlib.redirect_stdout(io.StringIO()):
                packager.main()
            self.assertFalse(staging.exists())
            archive = next((base / "_dist").iterdir())
            packager.validate_distribution(archive)
            self.assertEqual((archive / LAUNCHER_EXE).read_bytes(), LAUNCHER_EXE.encode("utf-8"))
            self.assertEqual(retained.read_text(encoding="utf-8"), "keep")
            self.assertTrue((source / ROOT_ENTRY_DIRECTORY / LAUNCHER_EXE).is_file())

    def test_archive_failure_preserves_staging(self):
        with tempfile.TemporaryDirectory(prefix="FAA 归档失败保留 ") as directory:
            source = Path(directory) / "source"
            excel = self.fixture(source)
            staging = source / "dist/FAA"
            with patch.object(packager, "find_project_root", return_value=source), \
                    patch.object(packager, "require_existing_excel", return_value=excel), \
                    patch.object(packager, "write_packaged_update_state", return_value=staging / "update_state.json"), \
                    patch.object(packager, "archive_dist_dir", side_effect=OSError("归档复制失败")), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(OSError, "归档复制失败"):
                    packager.main()
            packager.validate_distribution(staging)

    def test_cleanup_refuses_paths_outside_staging(self):
        with tempfile.TemporaryDirectory(prefix="FAA 暂存清理边界 ") as directory:
            source = Path(directory) / "source"
            other = source / "dist/other"
            other.mkdir(parents=True)
            marker = other / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaises(ValueError):
                packager.remove_dist_dir(source, other)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_both_exes_are_required_as_files(self):
        with tempfile.TemporaryDirectory(prefix="FAA 入口文件校验 ") as directory:
            root = Path(directory)
            source = root / "source"
            self.fixture(source)
            for name in ROOT_ENTRY_FILES:
                with self.subTest(entry=name):
                    destination = root / name.replace(".exe", "")
                    build_distribution_from_source(source, destination)
                    (destination / name).unlink()
                    with self.assertRaisesRegex(StagingError, name):
                        validate_staging(destination)
                    (destination / name).mkdir()
                    with self.assertRaisesRegex(StagingError, name):
                        validate_staging(destination)

    def test_missing_or_empty_uv_archive_blocks_packaging(self):
        with tempfile.TemporaryDirectory(prefix="FAA uv 包校验 ") as directory:
            source = Path(directory)
            self.fixture(source)
            (source / UV_ARCHIVE).write_bytes(b"")
            with self.assertRaisesRegex(FileNotFoundError, "uv-x86_64"):
                validate_source_entries(source)

if __name__ == "__main__":
    unittest.main()
