import glob
import json
import locale
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from function.common.update_state import write_packaged_update_state


SUBPROCESS_TEXT_ENCODING = locale.getpreferredencoding(False) or "utf-8"
IMAGE_RESOURCE_DB_ENV_PREFIX = "FAA_IMAGE_RESOURCE_DB_"
IMAGE_RESOURCE_DB_LOCAL_CONFIG = "image_resource_db.local.json"


def find_project_root(start: Path) -> Path:
    """Use LICENSE as the project-root marker."""
    current = start.resolve()
    for path in (current, *current.parents):
        if (path / "LICENSE").is_file():
            return path
    raise FileNotFoundError(f"Cannot locate project root from {start}; LICENSE was not found.")


def clean_dist_dir(project_root: Path, dest_dir: Path) -> None:
    resolved_dest = dest_dir.resolve()
    expected_parent = (project_root / "dist").resolve()

    if resolved_dest != expected_parent / "FAA":
        raise ValueError(f"Refuse to clean unexpected dist path: {resolved_dest}")

    if resolved_dest.exists():
        print(f"Cleaning old dist directory: {resolved_dest}")
        shutil.rmtree(resolved_dest)

    resolved_dest.mkdir(parents=True, exist_ok=True)


def read_project_version(project_root: Path) -> str:
    """Read VERSION from EXTRA.py without importing Qt-dependent globals."""
    extra_path = project_root / "function" / "globals" / "EXTRA.py"
    version_pattern = re.compile(r'^\s*VERSION\s*=\s*["\']([^"\']+)["\']')
    for line in extra_path.read_text(encoding="utf-8-sig").splitlines():
        match = version_pattern.match(line)
        if match:
            return match.group(1)
    return "unknown"


def archive_dist_dir(project_root: Path, dest_dir: Path) -> Path:
    """Archive the generated distribution into the sibling _dist directory."""
    dist_root = project_root.parent / "_dist"
    dist_root.mkdir(parents=True, exist_ok=True)

    version = read_project_version(project_root)
    timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    archive_dir = dist_root / f"FAA-{version} {timestamp}"
    counter = 1
    while archive_dir.exists():
        counter += 1
        archive_dir = dist_root / f"FAA-{version} {timestamp} ({counter})"

    shutil.copytree(dest_dir, archive_dir)
    return archive_dir


class FileMover:
    def __init__(self, src_dir: Path, dest_dir: Path):
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self.to_move = []

    @staticmethod
    def _normalize_relative(relative_path) -> Path:
        return Path(relative_path)

    def add_file(self, relative_path, required=True):
        """Add one file to the copy list."""
        rel_path = self._normalize_relative(relative_path)
        full_path = self.src_dir / rel_path
        if full_path.is_file():
            self.to_move.append((full_path, self.dest_dir / rel_path))
            return

        message = f"Missing required file: {rel_path}"
        if required:
            raise FileNotFoundError(message)
        print(f"Warning: {message}; skipped.")

    def add_folder(self, target, exclude_files=None, exclude_paths=None, exclude_types=None, dest_subdir=None, required=True):
        """
        Add a folder and its files to the copy list.

        If dest_subdir is set, the folder contents are copied into that destination
        subdirectory without preserving the target folder name itself.
        """
        target_path = self._normalize_relative(target)
        source_root = self.src_dir / target_path
        if not source_root.is_dir():
            message = f"Missing required folder: {target_path}"
            if required:
                raise FileNotFoundError(message)
            print(f"Warning: {message}; skipped.")
            return

        exclude_files = set(exclude_files or [])
        exclude_paths = {str(self._normalize_relative(path)) for path in (exclude_paths or [])}
        exclude_types = set(exclude_types or [])

        for root, _dirs, files in os.walk(source_root):
            root_path = Path(root)
            rel_to_target = root_path.relative_to(source_root)

            if dest_subdir is not None:
                dest_root = Path(dest_subdir) / rel_to_target if str(rel_to_target) != "." else Path(dest_subdir)
            else:
                dest_root = root_path.relative_to(self.src_dir)

            for file_name in files:
                source_file = root_path / file_name
                rel_path_for_exclude = str(source_file.relative_to(self.src_dir))

                if file_name in exclude_files:
                    continue
                if rel_path_for_exclude in exclude_paths:
                    continue
                if source_file.suffix in exclude_types:
                    continue

                self.to_move.append((source_file, self.dest_dir / dest_root / file_name))

    def preview(self):
        print(f"准备复制文件: {len(self.to_move)} 个")
        print(f"来源目录: {self.src_dir}")
        print(f"目标目录: {self.dest_dir}")

    @staticmethod
    def _print_progress(current: int, total: int, prefix: str) -> None:
        if total <= 0:
            print(f"{prefix}: 0/0")
            return

        width = 32
        ratio = current / total
        filled = int(width * ratio)
        bar = "#" * filled + "-" * (width - filled)
        sys.stdout.write(f"\r{prefix}: [{bar}] {current}/{total} {ratio:6.2%}")
        sys.stdout.flush()
        if current >= total:
            sys.stdout.write("\n")

    def run(self):
        total = len(self.to_move)
        if total == 0:
            print("没有需要复制的文件。")
            return

        print("开始复制文件...")
        update_interval = max(1, total // 100)
        for index, (src, dest) in enumerate(self.to_move, start=1):
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            if index == 1 or index == total or index % update_interval == 0:
                self._print_progress(index, total, "复制进度")
        print("文件复制完成。")


def has_image_resource_db_config(project_root: Path) -> bool:
    required_keys = ("HOST", "USER", "PASSWORD", "DATABASE")
    if all(os.getenv(f"{IMAGE_RESOURCE_DB_ENV_PREFIX}{key}") for key in required_keys):
        return True

    config_path = project_root / IMAGE_RESOURCE_DB_LOCAL_CONFIG
    if not config_path.is_file():
        return False

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False

    return all(
        config.get(key.lower()) or config.get(f"{IMAGE_RESOURCE_DB_ENV_PREFIX}{key}")
        for key in required_keys
    )


def require_existing_excel(project_root: Path, message: str) -> Path:
    latest_excel = get_latest_existing_excel_file(project_root)
    if latest_excel:
        return latest_excel
    raise FileNotFoundError(message)


def get_latest_excel_file(project_root: Path):
    """
    Generate and locate the latest image-resource Excel file.

    This file is optional for packaging. Failures are reported as warnings and
    the package generation continues.
    """
    excel_script = project_root / "tool" / "get_game_images_from_xiaye_db.py"

    print("\n" + "=" * 60)
    print("正在获取最新的图像资源文件...")
    print("=" * 60)

    try:
        if not excel_script.is_file():
            print(f"Warning: Excel generator not found: {excel_script}")
            return require_existing_excel(
                project_root,
                "没有数据库密码和 Excel 图像资源，打包已中断。请先提交或放置 `点我获取更多图像资源 *.xlsx`，"
                "或尝试和夏夜申请获得数据库密码。",
            )

        if not has_image_resource_db_config(project_root):
            latest_excel = require_existing_excel(
                project_root,
                "没有数据库密码和 Excel 图像资源，打包已中断。请先提交或放置 `点我获取更多图像资源 *.xlsx`，"
                "或尝试和夏夜申请获得数据库密码。",
            )
            print("未找到图像资源数据库密码。可以尝试和夏夜申请获得数据库密码。")
            print("现已使用内置 Excel 做图像资源校对。")
            return latest_excel

        print(f"执行脚本: {excel_script}")
        result = subprocess.run(
            [sys.executable, str(excel_script)],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding=SUBPROCESS_TEXT_ENCODING,
            errors="replace",
            timeout=60,
        )

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("警告:", result.stderr)

        if result.returncode != 0:
            print(f"Warning: 图像资源脚本执行失败，返回码: {result.returncode}")
            latest_excel = require_existing_excel(
                project_root,
                "获取最新 Excel 失败，且未找到内置 Excel 图像资源，打包已中断。",
            )
            print("获取最新 Excel 失败，现已使用内置 Excel 做图像资源校对。")
            return latest_excel

        today = datetime.now().strftime("%Y-%m-%d")
        expected_file = project_root / f"点我获取更多图像资源 {today}.xlsx"

        if expected_file.exists():
            print(f"[OK] 找到最新文件: {expected_file}")
            return expected_file.relative_to(project_root)

        print(f"Warning: 未找到今天生成的文件: {expected_file.name}")
        return require_existing_excel(
            project_root,
            "未找到今天生成的 Excel，也未找到内置 Excel 图像资源，打包已中断。",
        )

    except subprocess.TimeoutExpired:
        print("Warning: 图像资源脚本执行超时，将使用已有的最近文件")
        return require_existing_excel(project_root, "获取最新 Excel 超时，且未找到内置 Excel 图像资源，打包已中断。")
    except FileNotFoundError:
        raise
    except Exception as exc:
        print(f"Warning: 获取图像资源文件时出错: {exc}")
        return require_existing_excel(project_root, "获取最新 Excel 出错，且未找到内置 Excel 图像资源，打包已中断。")


def get_latest_existing_excel_file(project_root: Path):
    all_excel_files = glob.glob(str(project_root / "点我获取更多图像资源 *.xlsx"))
    if all_excel_files:
        latest_file = Path(max(all_excel_files, key=os.path.getmtime))
        print(f"[OK] 使用最近的文件: {latest_file}")
        return latest_file.relative_to(project_root)

    print("Warning: 未找到任何图像资源文件")
    return None


def run_card_prepare_room_resource_tool(project_root: Path, latest_excel) -> None:
    """
    Run the prepare-room card image resource generator before packaging.

    The generator writes mismatch CSVs and downloads missing images. It is a
    packaging helper, so network or CDN failures are reported as warnings and
    the package build continues with the existing local resources.
    """
    tool_script = project_root / "tool" / "card_resource" / "get_card_resource_tool.py"
    if not tool_script.is_file():
        print(f"Warning: Card resource tool not found: {tool_script}")
        return

    command = [
        sys.executable,
        str(tool_script),
        "--output",
        str(project_root / "resource" / "image" / "card" / "准备房间"),
        "--report-dir",
        str(project_root / "resource_other" / "图像资源_卡片准备房间_最新资源"),
    ]
    if latest_excel:
        command.extend(["--excel", str(project_root / latest_excel)])

    print("\n" + "=" * 60)
    print("正在更新准备房间卡片图像资源...")
    print("=" * 60)

    try:
        result = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding=SUBPROCESS_TEXT_ENCODING,
            errors="replace",
            timeout=300,
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("警告:", result.stderr)
        if result.returncode != 0:
            print(f"Warning: 准备房间卡片资源工具执行失败，返回码: {result.returncode}")
    except subprocess.TimeoutExpired:
        print("Warning: 准备房间卡片资源工具执行超时，将使用已有资源继续打包")
    except Exception as exc:
        print(f"Warning: 更新准备房间卡片图像资源时出错: {exc}")


def main():
    project_root = find_project_root(Path(__file__).parent)
    dest_dir = project_root / "dist" / "FAA"

    try:
        latest_excel = get_latest_excel_file(project_root)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"\n{exc}")
        raise SystemExit(1) from None

    run_card_prepare_room_resource_tool(project_root, latest_excel)
    clean_dist_dir(project_root, dest_dir)

    # 初始化 FileMover 实例
    mover = FileMover(
        src_dir=project_root,
        dest_dir=dest_dir,
    )

    # 添加文件夹及其排除列表
    mover.add_folder(
        target="config",
        exclude_files=[
            "settings.json",
            "空间服登录界面_1P.png",
            "空间服登录界面_2P.png",
            "跨服远征_1p.png",
        ],
        exclude_paths=[
            "config/cus_images/背包_装备_需使用的/任意通用包裹.png",
            "config/cus_images/背包_装备_需使用的/星际酬劳.png",
            "config/cus_images/背包_装备_需使用的/浮空酬劳.png",
            "config/cus_images/背包_装备_需使用的/火山酬劳.png",
            "config/cus_images/背包_装备_需使用的/美味酬劳.png",
        ],
    )

    mover.add_folder(target="plugins/root_entries", dest_subdir=".")
    mover.add_folder(target="plugins/launcher_scripts")

    mover.add_folder(target="function")

    mover.add_folder(target="plugins/pak")
    mover.add_folder(target="plugins/updater")
    mover.add_folder(target="battle_plan")
    mover.add_folder(target="battle_plan_not_active")
    mover.add_folder(target="md_img")
    mover.add_folder(target="task_sequence")
    mover.add_folder(target="tweak_plan")
    mover.add_folder(target="resource",exclude_types=[".pyc"],)

    # 添加文件或文件夹
    tar_files = [
        "新手入门 看我!!! 看我!!! 看我!!!.txt",
        "FAA-支持性检测, 仅限Win10+.bat",
        "LICENSE",
        "README.md",
        "README - 高级放卡.md",
        "致谢名单.md",
        "致谢名单.png",
        "FAA-恢复到备份.bat",
        "config/item_ranking_dag_graph.json",
        ".python-version",
        "pyproject.toml",
        "uv.lock",
    ]

    # 添加最新的图像资源Excel文件
    if latest_excel:
        tar_files.append(latest_excel)
        print(f"\n[OK] 已添加图像资源文件到打包列表: {latest_excel}")
    else:
        print("\nWarning: 未找到图像资源文件，将跳过此文件")

    for tar_file in tar_files:
        mover.add_file(tar_file)

    # 预览移动
    mover.preview()

    # 实际移动
    mover.run()

    state_path = write_packaged_update_state(project_root, dest_dir)
    print(f"Generated update state: {state_path}")

    # 开发者打包脚本只应存在于源码工作区，不能进入普通用户发布包。
    packaging_script_in_dist = os.path.join(dest_dir, "一键生成分发资源.py")
    if os.path.exists(packaging_script_in_dist):
        os.remove(packaging_script_in_dist)
        print("Removed developer-only packaging script from distribution.")

    archive_dir = archive_dist_dir(project_root, dest_dir)
    print(f"Archived distribution: {archive_dir}")


r"""
我需要完成一个文件迁移打包器，包含以下功能：
* 输入源目录和目标目录
* 根据源目录的相对路径，设置配置，包括以下
    * add_file 函数 直接根据相对路径加入移动列表
    * add_folder 函数 直接根据相对路径遍历内部所有子文件夹和文件，加入移动列表
        * 该函数需要支持 exclude_paths  exclude_files exclude_types 三个参数 参数为list
        * exclude_paths 根据相对路径排除文件 比如我在"config"路径中 可通过 "config/cus_images/背包_装备_需使用的/任意通用包裹.png"准确排除这个文件
        * exclude_files 根据文件名称 + 文件后缀名排除 比如 "致谢名单.png"
        * exclude_types 根据文件后缀名排除 比如 ".pyc"
* preview 函数 预览移动 输出样例
    Would copy:
    '.\config\cus_images\一些常用的图标\浮空岛酬劳.png' -> '..\_ExeWorkSpace\dist\FAA\config\cus_images\一些常用的图标\浮空岛酬劳.png'
* run 函数 实际移动 输出样例
    Copied:
    '.\LICENSE -> ..\_ExeWorkSpace\dist\FAA\LICENSE'
"""

if __name__ == "__main__":
    main()
