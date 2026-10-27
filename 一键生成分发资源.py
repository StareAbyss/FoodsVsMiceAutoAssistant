import glob
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from function.common.update_state import write_packaged_update_state
from function.common.distribution_layout import (
    PACKAGE_FOLDERS, PACKAGE_FILES, ROOT_ENTRY_DIRECTORY, ROOT_ENTRY_FILES,
    validate_source_entries, validate_distribution,
)


IMAGE_RESOURCE_EXCEL_DATE_RE = re.compile(r"点我获取更多图像资源 (?P<date>\d{4}-\d{2}-\d{2})\.xlsx$")


def image_resource_excel_sort_key(path: Path) -> tuple[int, float, str]:
    """
    生成图像资源 Excel 的新旧排序键，无合法日期时回退到修改时间。

    Args:
        path: 待排序的 Excel 文件路径。

    Returns:
        由资源日期序号、修改时间和文件名组成的排序键。
    """
    match = IMAGE_RESOURCE_EXCEL_DATE_RE.fullmatch(path.name)
    if match:
        try:
            file_date = datetime.strptime(match.group("date"), "%Y-%m-%d").date()
            return file_date.toordinal(), path.stat().st_mtime, path.name
        except ValueError:
            pass
    return -1, path.stat().st_mtime, path.name


def find_project_root(start: Path) -> Path:
    """Use LICENSE as the project-root marker."""
    current = start.resolve()
    for path in (current, *current.parents):
        if (path / "LICENSE").is_file():
            return path
    raise FileNotFoundError(f"Cannot locate project root from {start}; LICENSE was not found.")


def remove_dist_dir(project_root: Path, dest_dir: Path) -> None:
    """只清理当前源码根目录内的发行暂存目录，拒绝指向外部的目录链接。

    Args:
        project_root: 本次打包的源码根目录。
        dest_dir: 待清理的 dist/FAA 暂存路径。

    Raises:
        ValueError: 路径不是源码根目录内的 dist/FAA。
        OSError: 目录被占用或无法删除。
    """
    resolved_dest = dest_dir.resolve()
    expected_dest = project_root.resolve() / "dist" / "FAA"

    if resolved_dest != expected_dest:
        raise ValueError(f"Refuse to clean unexpected dist path: {resolved_dest}")

    if resolved_dest.exists():
        print(f"Cleaning old dist directory: {resolved_dest}")
        shutil.rmtree(resolved_dest)


def clean_dist_dir(project_root: Path, dest_dir: Path) -> None:
    """通过受限路径检查后重新创建发行暂存目录。"""
    remove_dist_dir(project_root, dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)


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

    def add_file(self, relative_path, required=True, dest_relative=None):
        """Add one file to the copy list."""
        rel_path = self._normalize_relative(relative_path)
        full_path = self.src_dir / rel_path
        if full_path.is_file():
            self.to_move.append((full_path, self.dest_dir / (Path(dest_relative) if dest_relative is not None else rel_path)))
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


def require_existing_excel(project_root: Path, message: str) -> Path:
    latest_excel = get_latest_existing_excel_file(project_root)
    if latest_excel:
        return latest_excel
    raise FileNotFoundError(message)


def get_latest_existing_excel_file(project_root: Path):
    all_excel_files = [Path(path) for path in glob.glob(str(project_root / "点我获取更多图像资源 *.xlsx"))]
    if all_excel_files:
        latest_file = max(all_excel_files, key=image_resource_excel_sort_key)
        print(f"[OK] 使用最近的文件: {latest_file}")
        return latest_file.relative_to(project_root)

    print("Warning: 未找到任何图像资源文件")
    return None


def create_distribution_plan(project_root: Path, dest_dir: Path, latest_excel: Path | None = None) -> FileMover:
    """共用发行清单生成复制计划，缺少正式 EXE 时不清理已有输出。

    Args:
        project_root: 包含预编译正式入口及资源的源码根目录。
        dest_dir: 复制目的目录，生成计划时不创建或清理此目录。
        latest_excel: 需要额外加入计划的源码相对 Excel 路径，可省略。

    Returns:
        尚未执行复制的 FileMover 计划。

    Raises:
        FileNotFoundError: 必需源码、资源或预编译入口缺失。
    """
    validate_source_entries(project_root)
    mover = FileMover(project_root, dest_dir)
    for name in ROOT_ENTRY_FILES:
        mover.add_file(ROOT_ENTRY_DIRECTORY / name, dest_relative=name)
    for folder, destination, exclude_files, exclude_paths, exclude_suffixes in PACKAGE_FOLDERS:
        mover.add_folder(folder, dest_subdir=destination, exclude_files=exclude_files,
                         exclude_paths=exclude_paths, exclude_types=exclude_suffixes)
    for path in PACKAGE_FILES:
        mover.add_file(path)
    if latest_excel is not None:
        mover.add_file(latest_excel)
    return mover


def main():
    project_root = find_project_root(Path(__file__).parent)
    dest_dir = project_root / "dist" / "FAA"

    try:
        latest_excel = require_existing_excel(
            project_root,
            "未找到已有的图像资源 Excel，打包已中断。发布前应独立运行图像资源校验流程，"
            "完成人工审核和资源 PR 后，再从干净的发行 tag 工作树打包。",
        )
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"\n{exc}")
        raise SystemExit(1) from None

    mover = create_distribution_plan(project_root, dest_dir, latest_excel)
    clean_dist_dir(project_root, dest_dir)

    # 预览移动
    mover.preview()

    # 实际移动
    mover.run()
    validate_distribution(dest_dir)

    state_path = write_packaged_update_state(project_root, dest_dir)
    print(f"Generated update state: {state_path}")

    # 开发者打包脚本只应存在于源码工作区，不能进入普通用户发布包。
    packaging_script_in_dist = os.path.join(dest_dir, "一键生成分发资源.py")
    if os.path.exists(packaging_script_in_dist):
        os.remove(packaging_script_in_dist)
        print("Removed developer-only packaging script from distribution.")

    archive_dir = archive_dist_dir(project_root, dest_dir)
    validate_distribution(archive_dir)
    print(f"Archived distribution: {archive_dir}")
    # 归档复制和校验均成功后再清理，失败时保留现场供排查或重试。
    remove_dist_dir(project_root, dest_dir)
    print("已清理发行暂存目录。")


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
