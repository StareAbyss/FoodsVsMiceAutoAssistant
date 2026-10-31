# FAA 原生安装器

此目录包含 FAA 原生启动器的源码、构建和验证工具。构建生成两个程序：

- `FAA - 环境安装器.exe`：环境安装、调试启动、卸除本地运行环境、恢复备份。
- `FAA - 快速启动.exe`：快速启动入口，只使用现有环境启动并等待主窗口；启动失败时打开环境安装器。

`FAA - 快速启动.exe` 仅调用当前根目录 `.venv/Scripts/pythonw.exe -m function.faa_main` 并识别本次任务的主窗口，不运行 uv、不安装 Python、不同步依赖、不自动修复环境。缺少 Python、进程提前退出、出现“FAA 启动失败”窗口或 90 秒内未找到主窗口时，写入 `logs/launcher/startup-failure-*.txt`，并通过 `--startup-error` 打开同目录的 `FAA - 环境安装器.exe`。安装器显示错误和日志，所有安装步骤保持未开始，等待用户自行选择操作。安装器缺失或无法启动时显示明确提示和日志路径。主窗口就绪后快速入口退出，之后的运行退出不触发修复。

两个 EXE 都应放在 FAA 根目录，与 `LICENSE`、`uv.lock`、`pyproject.toml` 和 `function` 文件夹并列。程序只把自身所在目录当作 FAA 根目录，不提供目录选择。标识缺失时，界面显示红叉和缺失项，并禁用所有操作。

## 网络设置

环境安装器提供网络设置窗口，分别选择 Python 下载源和 Python 依赖包下载源。国内镜像带有“国内用户使用”标注，官方 GitHub 和 PyPI 带有“国外用户使用”标注；两个下拉框最后一项均为“自定义”。只有选中自定义时才显示网址输入框，两项可独立选择。默认源按 FAA 根目录 `pyproject.toml` 中的设置匹配。

自定义网址只在本次启动器运行期间有效，不写入项目配置，也不主动写入启动日志。外部工具返回的原始错误内容可能包含本机路径等信息，分享日志前请先检查。

## 正式安装器

操作下拉框包含三项，左侧步骤和右侧交互会随选择切换：

- **准备环境并启动 FAA**：六个步骤为检查安装文件、准备安装工具、安装 Python、同步运行依赖、检测运行环境、启动 FAA。环境检测统一在依赖同步完成后执行。普通模式确认本次启动任务的主窗口出现后自动关闭安装器，FAA 独立运行。识别范围包含同一 Windows Job 中的 Python 子进程，兼容虚拟环境的启动跳板。失败时保留已完成步骤和错误详情，可重试；依赖、检测或启动错误还可以选择修复依赖。
- **卸除运行环境**：显示四个步骤：确认范围、检查进程、卸除本地环境、核对结果。在主页面确认后，只删除 `plugins/launcher_scripts/bin` 和 `.venv`；配置、用户数据、全局 uv、缓存与全局 Python 保留。占用进程会在页面中列出，可重新检测或确认结束所列进程后继续。删除使用 Windows API，拒绝删除范围外的目录，也不会沿目录链接遍历到外部数据。
- **恢复到备份**：主页面按修改时间从新到旧列出 `backups/FAA.backup.*` 与 `backups/FAA.before-restore.*`，显示版本、备份时间、类型及大小。选择“备份详情”可查看目录名、版本、Tag、PR、提交哈希、大小和完整路径，版本优先读取 `.update_state.json`，记录缺失时从备份源码读取。六个步骤为选择备份、检查条件、备份当前版本、恢复文件、准备并检测环境、启动 FAA。程序文件和配置随所选版本恢复；当前版本会先备份，所选备份、运行环境、安装器和当前日志保留。恢复失败会回滚；文件已恢复但环境或启动失败时，重试环境准备与检测，不重复恢复版本文件。

备份页提供“删除备份”，单独确认后只删除选中的受管目录，不要求勾选恢复确认框。不完整备份也可以清理，但不能执行恢复。删除期间在主页面显示状态，结束后刷新列表；最后一份备份删除后禁用详情、删除和恢复操作。程序拒绝把 `backups` 或备份根目录的目录链接作为操作目标；统计大小和删除时不沿内部链接遍历外部数据。

三个操作都在主界面内显示阶段、日志和错误，不使用 BAT 或 PS1 运行入口，也不弹出额外控制台。恢复逻辑来自 `plugins/updater/updater.py`，在构建时嵌入 EXE，运行时释放到 `update_cache/launcher/` 并由 Python 隐藏执行。执行阶段和日志回传主界面。文件移动和回滚期间不能关闭安装器或强制取消任务。

“额外设置”包含“调试启动：保留日志窗口”。开启后，使用无控制台的 Python 进程启动 FAA，并把标准输出、异常和退出码持续显示在安装器中。FAA 就绪后保留并展开日志；关闭安装器只停止日志显示，FAA 继续运行。“运行详情”的“放大”按钮让日志占据右侧主要区域，“收起”恢复步骤卡片。

普通启动与恢复后的普通启动都自动退出安装器；调试模式、卸除完成页和启动失败页面保留。加载窗口及本次启动任务之外的 FAA 窗口不作为启动成功的依据；任务内出现“FAA 启动失败”窗口时优先保留错误页面。

安装会同步当前 FAA 根目录的 `.venv`，建议在独立发行包副本中使用，避免移除源码开发环境的开发依赖。在源码目录开始安装时会再次提示。

安装器的 Python 默认下载源及依赖包下载源从 `pyproject.toml` 读取。选择包内默认依赖源时执行 `uv sync --locked --no-dev --python 3.12`；选择其他源时，先使用 `uv export --locked --offline --no-dev --no-emit-project` 导出锁定版本和 hash，再执行 `uv --no-config pip sync --require-hashes --strict --default-index <所选源>`。替换下载源不会重新解析依赖，也不会改写 `pyproject.toml` 或 `uv.lock`。临时清单位于 `update_cache/launcher/`，任务结束后清理。

## 统一运行环境检测

安装和恢复备份共用 `runtime_probe.py`，统一在依赖就绪、启动 FAA 主窗口之前检测。安装文件的早期检查仅服务于安装准备，不执行另一套兼容性检测。检测脚本内嵌于 EXE，释放到当前根目录的 `update_cache/launcher/`，通过所属 `.venv` 的隐藏 Python 进程执行，结束后删除。

| 检测项 | 实际验证内容 | 失败影响 |
| --- | --- | --- |
| Windows 与 Python | Windows build ≥ 19041；64 位 Python 与 `.python-version` 一致；系统 DXCore、D3D12 DLL 可加载 | 必需，暂停启动 |
| 启动资源与目录写入 | 主入口、编译的 Qt 资源、两个主要 UI、默认配置 JSON、基础图像目录；根目录、config、logs、update_cache 可写 | 必需，暂停启动 |
| 锁定依赖版本 | `pyproject.toml` 的直接运行依赖均有安装元数据，版本属于 `uv.lock`；不要求开发依赖 | 必需，暂停启动 |
| Qt 图形界面 | Qt Windows 平台、隐藏窗口初始化、Qt 编译资源导入与 UI 自定义控件解析 | 必需，暂停启动 |
| 图像读取与识别 | NumPy/OpenCV/Pillow 加载，实际读取一张包内 PNG，并运行小型模板匹配 | 必需，暂停启动 |
| 后台操作与本地加密 | pywin32、COM、桌面句柄 API 和内存中的 AES 往返校验 | 必需，暂停启动 |
| 方案、表格与网络组件 | 实际导入方案、表格、进程、几何、网络及 WMI 等项目依赖 | 必需，暂停启动 |
| ONNX 基础推理组件 | ONNX Runtime 原生组件可加载，CPU 推理后端可用 | 必需，暂停启动 |
| 高级识图模型与 GPU | `mouseV2.onnx` 可加载，DirectML 会话实际初始化；缺少 GPU 后端时尝试 CPU 加载模型 | 可选，提示高级识图或加速的影响 |
| WMI 凭据绑定能力 | WMI 系统查询能响应，不采集硬件标识 | 可选，提示设备凭据绑定可能受限 |
| 特殊卡片求解器 | PuLP 的 CBC 求解器文件可访问，不实际求解战斗方案 | 可选，提示对应方案计算的影响 |
| 截图 OCR 扩展 | `plugins/pak/model.py` 或 `model/__init__.py` 入口存在；不初始化外部 OCR 模型 | 可选，提示截图识别方案的影响 |

每组在独立隐藏进程中执行并有超时限制，原生扩展崩溃不会直接结束安装器。界面显示“检测中、通过、失败、提示”，选择项目可查看原因及建议，完整异常可在运行详情中查看和保存。必需项失败时不能跳过，处理后可重试或修复依赖。仅有可选能力提示时，用户阅读后点击“继续启动 FAA”。恢复后的启动使用相同规则。

检测不访问外网、不要求提前打开游戏、不执行游戏截图或点击、不读取账号密码、不解析个人配置，也不要求 CUDA、.NET 或单独安装 VC++ 运行库。它验证启动所需的组件与代表性资源，不能替代实际游戏任务测试或完整资源校验。根目录不再提供独立的支持性检测 BAT，发行包和更新暂存包均不再复制它。

## 系统依赖

各构建变体的文件图标与窗口图标统一使用 `resource/logo/圆角-FetDeathWing-256x-AllSize.ico`，对应原图 `圆角-FetDeathWing-450x.png`，包含 16、32、48、64、128 和 256 像素尺寸。构建时将图标临时复制到 ASCII 文件名后嵌入资源，避免旧版资源编译器无法读取中文路径；构建结束清理临时文件。

- 成品为 x64 原生 C++ 程序，目标系统为 Windows 10 2004 及以上或 Windows 11。
- 图形界面使用 Win32 原生控件和系统 GDI+，不使用 .NET、Qt、Electron 或 WebView2。
- MinGW-w64 构建静态链接 GCC/C++ 支持库；最终 EXE 使用 Windows 自带 DLL，包括 `msvcrt.dll`，不要求另装 VC++ Redistributable。
- 安装另外调用 FAA 包内的 uv 和 Windows 的 `tar.exe`。恢复工具使用本地虚拟环境或 PATH 中可用的 Python；FAA 主程序仍需要 Python 及锁定依赖。
- 安装器不负责版本查询和热更新；FAA 原有更新流程仍由 `plugins/updater/` 管理。

## 构建

在 PowerShell 中使用 MinGW-w64：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tool/faa_launcher/build.ps1 -Cxx 'D:\Tools\mingw64\bin\g++.exe' -Variant Both
```

构建产物默认复制到项目根目录，`-OutputDirectory` 可指定成品输出目录。中间文件放在 `dist/faa_launcher/build-随机标识/` 下的独立工作目录；全部编译和成品复制成功后自动清理本次工作目录，失败时保留并输出位置。清理不删除自定义成品目录或其他失败构建；不能删除的文件会明确提示。`-Variant Installer` 或 `-Variant Launcher` 可单独构建一个版本。也可以设置 `FAA_CXX` 或在当前终端 PATH 中提供编译器。MinGW 编译器目录中需要 `windres.exe`。MSVC 构建需要开发者命令行中的 `cl.exe` 和 Windows SDK `rc.exe`。

构建普通入口和正式安装器同时更新 `plugins/root_entries/FAA - 快速启动.exe` 与 `plugins/root_entries/FAA - 环境安装器.exe`，按 `function/common/distribution_layout.py` 的入口白名单复制到用户根目录。普通热更新部署目标版本的安装器；备份恢复保留正在运行的安装器。

## 已发布旧版本的自动更新过渡

#1055 的本地更新器按固定旧文件名复制和校验源码，更新后也固定启动 `FAA.exe`。源码归档保留满足这些旧路径要求的少量过渡文件；`plugins/root_entries/FAA.exe` 是正式快速入口的同一份二进制别名，不是第三个正式产品。正常发行和新版热更新按白名单只复制两个正式 EXE，不携带旧名称入口或过渡 BAT、PS1；内部过渡代码位于 `plugins/updater/`。

旧更新器首次完成替换后，新原生入口会识别旧更新交接，并在缓存内运行自身副本完成收尾。界面显示获取源码、读取新版规则、迁移原始数据、备份替换等阶段，日志直接显示在窗口中，不打开额外控制台。

过渡需要重新下载首次选定的精确 commit 源码，并从首次更新前的原始备份迁移用户数据。不能把已经被旧迁移规则改写过的中间安装目录当作纯净源码或原始数据。原始备份和目标提交固定记录在 `update_cache/legacy_bridge/state.json`；失败时保留此记录供重试，不改选另一个提交或中间备份。

GitHub 更新列表和源码下载先使用 Python 系统默认可信证书与已有 certifi 公共 CA。Windows 上证书校验或证书包加载失败时，经标准库 ctypes 调用系统 WinHTTP/Schannel 验证同一请求，并使用系统策略允许的证书链缓存和 AIA 补链；下载阶段显示系统验证进度。该重试不增加运行依赖、不自行导入根证书或更改系统策略、不关闭校验；缓存和证书链维护由 Windows 按既有策略处理。系统仍拒绝的证书继续中止下载；详细异常保留在日志中，原始备份和重试记录保留。

系统重试沿用显式 HTTP 代理或 Windows 自动代理；遇到不支持的代理协议或嵌入式认证会明确提示，不绕过代理。下载按块读取，跳转只能使用 HTTPS，跨站跳转不传递认证头。超时和普通 HTTP 错误沿用原来的重试与限流处理。安装器中的 Python 和依赖包下载源不影响 GitHub 源码下载，uv、Git 和浏览器不会自动继承此 Python 请求入口。

目标准备进程写入 `update_protocol=1`，用于区分已按目标规则完成的更新与旧更新器交接，避免下次正常启动再次迁移。没有旧更新交接记录的全新安装不会进入过渡。#1056 起已使用正式入口白名单的旧更新器也由正式快速入口识别交接，无需依赖旧名称 `FAA.exe`。

更新完成后收起旧名称入口和带专用标记的过渡脚本，根目录保持正式布局；状态、日志和临时原生程序位于 `update_cache`。界面提示用户自行运行目标版环境安装器，不自动启动 FAA 或安装依赖。

旧用户必须选择包含此过渡支持的新版本。历史 commit 的源码包内容不会被当前改动改变，直接选择不含支持的历史节点仍可能报错。

## 验证

回归测试使用两个正式 EXE，在隔离目录中执行。

```powershell
.venv\Scripts\python.exe -m unittest test.faa_launcher.test_launcher test.faa_launcher.test_maintenance test.faa_launcher.test_startup test.faa_launcher.test_runtime_probe test.faa_launcher.test_entry -v
.venv\Scripts\python.exe -m unittest test.test_update_target_rules test.faa_launcher.test_update_legacy -v
.venv\Scripts\python.exe tool/faa_launcher/verify_pe.py "FAA - 环境安装器.exe"
.venv\Scripts\python.exe tool/faa_launcher/verify_pe.py "FAA - 快速启动.exe"
```

自动检查覆盖 Windows DLL 导入和 CLR 头、中文参数、隐藏子进程和取消，以及本机 HTTP 源中的锁定版本和 hash 验证。原生卸除会实际处理隔离环境的占用进程和目录；恢复测试实际运行内嵌工具，并覆盖安装器保留、复制失败回滚与备份中断归还文件。所有文件操作与测试包安装均在临时目录中执行，不访问外网，也不改动维护者现有 `.venv`。

普通入口回归通过仅记录调用的 uv 和安装器夹具，验证真实进程交接、失败报告、只打开一次修复工具和主窗口就绪后的退出处理；夹具用本机 C# 编译器构建，不构成产品运行依赖。启动回归测试使用隔离 Python 环境和屏幕外的原生窗口，验证普通启动自动退出、调试日志保留、错误与加载窗口识别，以及安装器退出后主进程继续运行，不启动真实 FAA 或游戏任务。

环境检测测试覆盖必需项失败、可选项继续、原生组件崩溃、超时、协议异常和锁定版本不符，并在隔离目录实际执行 EXE 内嵌检测。该测试通过隔离环境的 `.pth` 复用当前开发环境依赖，不安装或修改开发依赖。

`test.faa_launcher.test_build_cleanup` 在独立源码副本中验证构建成功后的中间文件清理、自定义成品与其他失败现场保留；实际编译测试通过 `FAA_CXX` 选择编译器。

更新规则集成测试刻意让目标源码新增文件、改变排除项和目录映射，并增加旧版不知道的数据迁移规则，验证当前进程的模块缓存不会代替目标规则。还覆盖确认期间配置变化、最终迁移失败重试、目标更新脚本交接和安装器版本替换。旧版过渡测试从 Git 固定提交读取真实 #1055、#1056、#1057 更新模块，使用本地源码 ZIP 隔离网络，验证首次备份取数、目标规则收尾及根目录兼容文件清理。原生入口交接另用隔离 Python 夹具验证，不启动真实 FAA 或游戏。

## 文件

- `launcher.cpp`：原生界面、根目录检查、快速启动和环境安装器操作入口。
- `launcher_core.cpp`、`launcher_core.h`：子进程、路径、编码、配置读取、校验与错误分类。
- `launcher_maintenance.cpp`、`launcher_maintenance.h`：本地环境的进程识别、受限删除和备份目录校验。
- `runtime_probe.py`：依赖安装完成后的统一运行环境检测，通过独立进程隔离原生组件故障。
- `launcher.manifest`、`launcher.rc`：DPI、系统控件主题、权限和版本资源。
- `build.ps1`：构建并打包两个 EXE。
- `verify_pe.py`：只读检查最终 EXE 的 DLL 导入。

正式 EXE、uv ZIP 和运行资源的打包与暂存校验统一由 `function/common/distribution_layout.py` 定义。入口按文件白名单复制；源码中的其他入口文件、运行时脚本和本地 bin 缓存不进入正式包。开发用构建 PS1 保留在 tool 目录。
