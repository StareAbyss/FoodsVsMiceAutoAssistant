import glob
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from function.common.update_state import write_packaged_update_state


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
        for src, dest in self.to_move:
            print(f"Would copy: {src} -> {dest}")

    def run(self):
        for src, dest in self.to_move:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"Copied: {src} -> {dest}")


def get_latest_excel_file(project_root: Path):
    """
    Generate and locate the latest image-resource Excel file.

    This file is optional for packaging. Failures are reported as warnings and
    the package generation continues.
    """
    excel_script = project_root / "card_image_url_get.py"

    print("\n" + "=" * 60)
    print("正在获取最新的图像资源文件...")
    print("=" * 60)

    try:
        if not excel_script.is_file():
            print(f"Warning: Excel generator not found: {excel_script}")
            return None

        print(f"执行脚本: {excel_script}")
        result = subprocess.run(
            [sys.executable, str(excel_script)],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("警告:", result.stderr)

        if result.returncode != 0:
            print(f"Warning: 图像资源脚本执行失败，返回码: {result.returncode}")
            return None

        today = datetime.now().strftime("%Y-%m-%d")
        expected_file = project_root / f"点我获取更多图像资源 {today}.xlsx"

        if expected_file.exists():
            print(f"✓ 找到最新文件: {expected_file}")
            return expected_file.relative_to(project_root)

        print(f"Warning: 未找到今天生成的文件: {expected_file.name}")
        return get_latest_existing_excel_file(project_root)

    except subprocess.TimeoutExpired:
        print("Warning: 图像资源脚本执行超时，将使用已有的最近文件")
        return get_latest_existing_excel_file(project_root)
    except Exception as exc:
        print(f"Warning: 获取图像资源文件时出错: {exc}")
        return get_latest_existing_excel_file(project_root)


def get_latest_existing_excel_file(project_root: Path):
    all_excel_files = glob.glob(str(project_root / "点我获取更多图像资源 *.xlsx"))
    if all_excel_files:
        latest_file = Path(max(all_excel_files, key=os.path.getmtime))
        print(f"✓ 使用最近的文件: {latest_file}")
        return latest_file.relative_to(project_root)

    print("Warning: 未找到任何图像资源文件")
    return None


def main():
    project_root = find_project_root(Path(__file__).parent)
    dest_dir = project_root / "dist" / "FAA"

    latest_excel = get_latest_excel_file(project_root)
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

    mover.add_folder(target="plugins/uv",dest_subdir=".",)

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
        "FAA支持性检测, 仅限Win10+.bat",
        "LICENSE",
        "README.md",
        "README - 高级放卡.md",
        "致谢名单.md",
        "致谢名单.png",
        "恢复到备份.bat",
        "config/item_ranking_dag_graph.json",
        ".python-version",
        "pyproject.toml",
        "uv.lock",
    ]

    # 添加最新的图像资源Excel文件
    if latest_excel:
        tar_files.append(latest_excel)
        print(f"\n[✓] 已添加图像资源文件到打包列表: {latest_excel}")
    else:
        print("\n[⚠] 未找到图像资源文件，将跳过此文件")

    for tar_file in tar_files:
        mover.add_file(tar_file)

    # 预览移动
    mover.preview()

    # 实际移动
    mover.run()

    state_path = write_packaged_update_state(project_root, dest_dir)
    print(f"Generated update state: {state_path}")


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
