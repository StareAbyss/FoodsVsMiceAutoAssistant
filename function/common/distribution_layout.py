"""集中定义“发给用户的 FAA 包里要有什么”，供发行打包和热更新共同使用。

两个实际使用方：
    一键生成分发资源.py：从源码目录生成完整发行包。
    plugins/updater/prepare.py：在隔离进程中加载下载目标源码自己的清单，生成热更新暂存包。

两者共用以下顺序：
    1. validate_source_entries() 检查源码中的两个成品 EXE 和内置 uv 压缩包。
    2. 按 ROOT_ENTRY_FILES、PACKAGE_FOLDERS、PACKAGE_FILES 复制文件。
    3. validate_distribution() 检查生成的目录是否具备关键文件和目录。

这里维护的是清单和检查函数；实际复制、输出目录清理和版本状态写入由调用方执行。
模块只依赖 Python 标准库。热更新的当前 FAA 只下载、解压并调用目标准备入口，
不会用当前进程已导入的本清单去推断新版本应包含哪些文件。

阅读路径时要区分两个根目录：
    源码根目录：仓库目录，两个预编译 EXE 位于 plugins/root_entries/。
    成品根目录：用户解压后看到的目录，或更新替换前准备好的 staging 目录。
    例如：源码/plugins/root_entries/FAA - 快速启动.exe -> 成品/FAA - 快速启动.exe。

部分常量通过本文件内部的其他清单间接使用：
    CONFIG_EXCLUDE_* -> PACKAGE_FOLDERS -> 两个复制流程。
    REQUIRED_DISTRIBUTION_* -> validate_distribution() -> 两个检查流程。
"""

from pathlib import Path


# 正式程序的统一名称。主程序重启、更新后启动和保留区判断也会引用它们，
# 避免各个 Python 调用点分别写文件名，改名时漏掉某个入口。
LAUNCHER_EXE = "FAA - 快速启动.exe"
ENVIRONMENT_INSTALLER_EXE = "FAA - 环境安装器.exe"

# 下列路径相对于“源码根目录”。只从此目录取清单中的两个 EXE，
# 复制时直接放进“成品根目录”，不会把 plugins/root_entries 这个目录整体带给用户。
ROOT_ENTRY_DIRECTORY = Path("plugins/root_entries")
ROOT_ENTRY_FILES = (LAUNCHER_EXE, ENVIRONMENT_INSTALLER_EXE)

# uv 压缩包在源码和成品中的相对位置相同。安装器使用这一固定文件准备本地 uv，
# 清单只复制压缩包，不整体复制 launcher_scripts，因此本机的 bin 缓存不会跟进去。
UV_ARCHIVE = "plugins/launcher_scripts/uv/uv-x86_64-pc-windows-msvc.zip"

# config 中按“文件名”排除的本地内容。两个复制器都会比较文件的最后一级名称，
# 因此 settings.json 无论出现在 config 的哪一级子目录，都不会由这条目录规则复制。
# 个人配置和这些本地截图不应随维护者的工作区一起发给其他用户。
CONFIG_EXCLUDE_FILES = {
    "settings.json", "空间服登录界面_1P.png", "空间服登录界面_2P.png", "跨服远征_1p.png",
}
# 按“相对于源码根目录的完整路径”精确排除，只作用于下面这些指定图片。
# 与上面的文件名规则不同：其他目录里即使有同名文件，也不会被这些路径规则排除。
CONFIG_EXCLUDE_PATHS = {
    Path("config/cus_images/背包_装备_需使用的/任意通用包裹.png"),
    Path("config/cus_images/背包_装备_需使用的/星际酬劳.png"),
    Path("config/cus_images/背包_装备_需使用的/浮空酬劳.png"),
    Path("config/cus_images/背包_装备_需使用的/火山酬劳.png"),
    Path("config/cus_images/背包_装备_需使用的/美味酬劳.png"),
}

# 需要递归复制的目录。每一行固定有五列，两个调用方会按同样的顺序解包：
# (来源目录, 成品内的目标目录, 排除的文件名, 排除的源码相对路径, 排除的文件后缀)
#
# 来源目录相对于源码根目录，目标目录相对于成品根目录；排除规则只作用于本行。
# set() 表示这一类没有额外排除项；{".pyc"} 表示跳过 Python 编译缓存文件。
# 例如 function 这一行：把源码中的 function 递归复制到成品的 function，跳过 .pyc。
#
# 两个调用方都把这些目录视为必需目录，来源缺失时停止准备。
# 只有这里列出的目录会按目录复制；入口 EXE 和 uv ZIP 在其他清单中按文件单独复制。
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

# 需要单独复制的固定文件，来源路径和成品路径保持一致。
# 整个 config 已在 PACKAGE_FOLDERS 中处理，其中的普通配置文件无需在这里重复列举。
# 日期变化的图像资源 Excel 由调用方选择后补入，因此也不写成这里的固定文件名。
PACKAGE_FILES = (
    "新手入门 看我!!! 看我!!! 看我!!!.txt",
    "LICENSE",
    "README.md",
    "README - 高级放卡.md",
    "致谢名单.md",
    "致谢名单.png",
    ".python-version",
    "pyproject.toml",
    "uv.lock",
    UV_ARCHIVE,
)

# 成品的关键文件检查清单，路径均相对于“成品根目录”。
# 它和上面的复制清单职责不同：复制清单决定带上哪些内容，这里决定缺什么就必须报错。
# 此处检查启动、依赖准备和更新所需的关键文件，不逐个检查全部方案、图片或文档。
# *ROOT_ENTRY_FILES 会把两个正式 EXE 的名字展开到本清单，确保入口也接受非空文件检查。
REQUIRED_DISTRIBUTION_FILES = (
    "LICENSE",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    *ROOT_ENTRY_FILES,
    UV_ARCHIVE,
    "plugins/updater/updater.py",
    "function/faa_main.py",
)
# 目录单独检查类型：这些位置必须是目录，不能是同名文件。
# 对目录检查存在性和类型；对上面的关键文件还会检查大小是否大于零。
REQUIRED_DISTRIBUTION_DIRECTORIES = ("function", "resource")


def validate_source_entries(source_root: Path) -> None:
    """在开始复制之前，确认源码中已准备好正式 EXE 和内置 uv 包。

    调用方先执行此检查，再清理或创建输出目录。这样即使忘了编译 EXE，
    也会先提示缺失项，避免清掉已有发行目录后才发现无法完成打包。
    其他源码、资源和说明文件的缺失，由复制流程的必需项检查处理。

    此阶段使用源码布局：EXE 从 plugins/root_entries/ 检查，uv ZIP 保持固定相对路径。
    检查范围是文件类型和非空大小；成功时正常返回，失败时一次列出全部缺失项。

    Args:
        source_root: 待打包或准备更新的源码根目录，包含 plugins/root_entries/ 等目录。

    Raises:
        FileNotFoundError: 两个正式 EXE 或 uv ZIP 中有文件缺失、为空，或被同名目录代替。
    """
    root = Path(source_root)
    required = [ROOT_ENTRY_DIRECTORY / name for name in ROOT_ENTRY_FILES] + [Path(UV_ARCHIVE)]
    missing = [str(path) for path in required if not (root / path).is_file() or (root / path).stat().st_size == 0]
    if missing:
        raise FileNotFoundError("缺少原生发行入口或安装工具，请先构建正式 EXE 并准备内置 uv 包：" + "、".join(missing))


def validate_distribution(root: Path) -> None:
    """在复制完成后，检查成品是否具备启动和准备依赖所需的关键路径。

    本地打包在生成发行目录及复制归档后调用；热更新在准备好的 staging 上调用。
    此时两个 EXE 应已放到成品根目录，所以按用户最终看到的布局检查。

    REQUIRED_DISTRIBUTION_FILES 中的项目必须是非空文件，目录不能冒充文件；
    REQUIRED_DISTRIBUTION_DIRECTORIES 中的项目必须是目录。
    成功时正常返回；失败时一次列出全部不符合要求的路径，由调用方中止后续操作。

    Args:
        root: 已复制完成的发行根目录、发行归档根目录或热更新暂存根目录。

    Raises:
        ValueError: 必需文件缺失或为空，或者必需目录不存在。
    """
    root = Path(root)
    missing = [path for path in REQUIRED_DISTRIBUTION_FILES
               if not (root / path).is_file() or (root / path).stat().st_size == 0]
    missing += [path for path in REQUIRED_DISTRIBUTION_DIRECTORIES if not (root / path).is_dir()]
    if missing:
        raise ValueError("发行目录不完整，缺少有效文件或目录：" + "、".join(missing))
