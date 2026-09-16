import glob
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from function.common.update_state import write_packaged_update_state


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
