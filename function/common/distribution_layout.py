"""正式发行包和热更新暂存包共用的文件布局，不加载 FAA 界面或运行配置。"""

from pathlib import Path


LAUNCHER_EXE = "FAA - 快速启动.exe"
ENVIRONMENT_INSTALLER_EXE = "FAA - 环境安装器.exe"
ROOT_ENTRY_DIRECTORY = Path("plugins/root_entries")
ROOT_ENTRY_FILES = (LAUNCHER_EXE, ENVIRONMENT_INSTALLER_EXE)
UV_ARCHIVE = "plugins/launcher_scripts/uv/uv-x86_64-pc-windows-msvc.zip"

CONFIG_EXCLUDE_FILES = {
    "settings.json", "空间服登录界面_1P.png", "空间服登录界面_2P.png", "跨服远征_1p.png",
}
CONFIG_EXCLUDE_PATHS = {
    Path("config/cus_images/背包_装备_需使用的/任意通用包裹.png"),
    Path("config/cus_images/背包_装备_需使用的/星际酬劳.png"),
    Path("config/cus_images/背包_装备_需使用的/浮空酬劳.png"),
    Path("config/cus_images/背包_装备_需使用的/火山酬劳.png"),
    Path("config/cus_images/背包_装备_需使用的/美味酬劳.png"),
}

# 入口 EXE 和 uv 压缩包按文件复制，避免混入未列入清单的程序、构建脚本或本机 bin 缓存。
PACKAGE_FOLDERS = (
    ("config", Path("config"), CONFIG_EXCLUDE_FILES, CONFIG_EXCLUDE_PATHS, set()),
    ("function", Path("function"), set(), set(), {".pyc"}),
    ("plugins/pak", Path("plugins/pak"), set(), set(), set()),
    ("plugins/updater", Path("plugins/updater"), set(), set(), set()),
    ("battle_plan", Path("battle_plan"), set(), set(), set()),
    ("battle_plan_not_active", Path("battle_plan_not_active"), set(), set(), set()),
    ("md_img", Path("md_img"), set(), set(), set()),
    ("task_sequence", Path("task_sequence"), set(), set(), set()),
    ("tweak_plan", Path("tweak_plan"), set(), set(), set()),
    ("resource", Path("resource"), set(), set(), {".pyc"}),
)

PACKAGE_FILES = (
    "新手入门 看我!!! 看我!!! 看我!!!.txt", "LICENSE", "README.md", "README - 高级放卡.md",
    "致谢名单.md", "致谢名单.png", "config/item_ranking_dag_graph.json",
    ".python-version", "pyproject.toml", "uv.lock", UV_ARCHIVE,
)

REQUIRED_DISTRIBUTION_FILES = (
    "LICENSE", "pyproject.toml", "uv.lock", ".python-version", *ROOT_ENTRY_FILES,
    UV_ARCHIVE, "plugins/updater/updater.py", "function/faa_main.py",
)
REQUIRED_DISTRIBUTION_DIRECTORIES = ("function", "resource")


def validate_source_entries(source_root: Path) -> None:
    """复制前检查编译产物和 uv 包，缺失时不清理已有发行目录。

    Args:
        source_root: 包含 plugins/root_entries 的待发行源码根目录。

    Raises:
        FileNotFoundError: 正式 EXE 或 uv ZIP 缺失、为空或不是文件。
    """
    root = Path(source_root)
    required = [ROOT_ENTRY_DIRECTORY / name for name in ROOT_ENTRY_FILES] + [Path(UV_ARCHIVE)]
    missing = [str(path) for path in required if not (root / path).is_file() or (root / path).stat().st_size == 0]
    if missing:
        raise FileNotFoundError("缺少原生发行入口或安装工具，请先构建正式 EXE 并准备内置 uv 包：" + "、".join(missing))


def validate_distribution(root: Path) -> None:
    """验证用户根目录布局中的必需文件和目录，不能用同名目录冒充文件。

    Args:
        root: 已复制完成的发行根目录或热更新暂存根目录。

    Raises:
        ValueError: 必需文件缺失或为空，或者必需目录不存在。
    """
    root = Path(root)
    missing = [path for path in REQUIRED_DISTRIBUTION_FILES
               if not (root / path).is_file() or (root / path).stat().st_size == 0]
    missing += [path for path in REQUIRED_DISTRIBUTION_DIRECTORIES if not (root / path).is_dir()]
    if missing:
        raise ValueError("发行目录不完整，缺少有效文件或目录：" + "、".join(missing))
