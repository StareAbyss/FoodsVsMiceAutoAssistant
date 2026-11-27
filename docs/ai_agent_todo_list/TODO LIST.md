# 项目优化 TODO

> 本文件记录当前项目中“不合理且值得显著优化”的事项，方便后续逐项处理并划掉。

## 2026-05-17 复查记录

- 直接执行 `python` / `git` 在当前 AI 工具 shell 中仍然找不到，说明 PATH 问题对 AI 进程仍可能存在；使用 `docs/ai_agent_read_me/基本信息.md` 中记录的绝对路径可以正常调用。
- `F:\My RTE\Python\Venv\FoodsVsMousesAutoAssistant\Scripts\python.exe --version` 正常，版本为 `Python 3.12.5`。
- `D:\Program Files\Git\cmd\git.exe --version` 正常，版本为 `git version 2.48.1.windows.1`。
- 当前虚拟环境复查时仍未安装 `pytest`，`importlib.util.find_spec("pytest")` 返回 `False`；已新增 `requirements-dev.txt`，但尚未实际安装。
- 已执行 `python -m compileall -q function test`，结果通过，说明当前 Python 文件没有语法级编译错误。
- 当前 `logs/` 体积约 119MB，之前约 1.17GB 的大录屏文件已经不在当前目录中；容量症状缓解，但自动清理/轮转机制仍建议补。
- P0 中 `get_paths.py` 导入即执行目录检查的问题已处理；`loadings.py` 导入即创建 Qt 对象、`thread_with_exception.py` 强制线程异常注入仍存在。
- `.editorconfig` 已新增，编码/换行/缩进规则已落地；但已有 README/docs 是否全部按 UTF-8 重新保存，仍可后续逐个确认。

## P0：优先处理

- [ ] 去掉 `function/globals/loadings.py` 的导入副作用。
  - 当前 import 时直接创建 `QApplication` 和 `LoadingWindow`。
  - 建议把 `QApplication` 创建移动到 `function/faa_main.py` 的 `main()` 中。
  - 目标：普通模块导入时不自动创建 UI 对象。

- [ ] 优化线程停止方式，减少强制杀线程。
  - `function/common/thread_with_exception.py` 使用 `PyThreadState_SetAsyncExc` 强行给线程抛异常。
  - 建议统一改成 `threading.Event`、`QThread.requestInterruption()` 或现有 `_event_stop` 风格。
  - 目标：避免线程在锁、文件写入、OpenCV、Win32 调用中被强行中断导致状态不一致。

## P1：维护性优化

- [ ] 拆分超大核心文件。
  - `function/core/todo.py` 约 3000 行。
  - `function/core/faa/faa_core.py` 约 2800 行。
  - `function/core/qmw_editor_of_battle_plan.py` 约 2500 行。
  - `function/core_battle/card_manager.py` 约 1600 行。
  - 建议先按职责拆分，不做一次性大重构。

- [ ] 给 `ThreadTodo` 相关任务建立更清晰的任务分层。
  - 可拆成：任务调度、日常任务、战斗任务、奖励/掉落、外部程序联动。
  - 目标：降低 `todo.py` 修改风险。

- [ ] 给战斗方案、任务序列、关卡信息增加数据校验层。
  - 当前大量 JSON 由 UI 和运行逻辑直接读取。
  - 建议使用 dataclass / dacite / schema 校验，集中处理缺字段、旧版本迁移、类型错误。
  - 目标：避免配置文件异常时在深层运行逻辑里报错。

- [ ] 整理 `function/scattered/`。
  - 该目录包含很多重要业务工具，但命名表达为“零散”。
  - 建议逐步移动到更明确的包，例如 `validators/`、`stage/`、`ocr/`、`task/`。

- [ ] 统一路径处理方式。
  - 目前大量代码使用 `PATHS["root"] + "\\xxx"`。
  - 建议新代码优先使用 `pathlib.Path` 或 `os.path.join`。
  - 目标：减少中文路径、空格路径、打包路径带来的问题。

## P2：安全和稳定性

- [ ] 降低扩展脚本中 `exec()` 的风险。
  - `function/extension/extension_core.py` 会执行配置中的 Python 代码。
  - 如果保留该能力，应明确标注“仅执行本地可信脚本”。
  - 可考虑改为动作白名单 / DSL / 受限 API，而不是任意 Python。

- [ ] 清理生产代码中的调试 `print()`。
  - 部分核心模块和工具模块仍有直接 `print()`。
  - 建议统一走 `CUS_LOGGER` 或 UI 信号输出。
  - 目标：减少打包后控制台噪声，方便日志分级。

- [ ] 为网络请求增加统一封装。
  - 当前多处直接使用 `requests.get/post`。
  - 建议统一超时、重试、错误提示、代理/网络不可用处理。
  - 目标：外部服务异常时不影响主流程稳定性。

- [ ] 为录屏、截图、日志写入增加异常保护和空间检查。
  - 写大文件前检测磁盘剩余空间。
  - 录屏文件按时间/大小轮转。
  - 目标：避免日志目录占满磁盘。

## P3：仓库和开发体验

- [ ] 完善开发环境说明。
  - 建议 README 或 docs 里补充普通开发者如何创建/激活虚拟环境。

- [x] 增加开发依赖文件。
  - 已新增 `requirements-dev.txt`。
  - 当前包含运行依赖引用 `-r requirements.txt` 和 `pytest>=8.0,<9.0`。
  - 注意：该文件只声明依赖，不代表当前虚拟环境已经安装 pytest。

- [ ] 增加基础 CI 或本地检查脚本。
  - 推荐最小检查：
    - `python -m compileall -q function test`
    - `python -m pytest -q`
  - 当前已用项目 venv 跑过 `compileall`，结果通过。

- [x] 隔离已确认无用的大二进制和生成文件。
  - 根目录约 65MB 的独立识图编辑器已移入不受 Git 追踪的 `resource_other/`。
  - 已删除不再被当前界面使用的 `function/qrc/test_rc.py`。
  - 后续新增的大二进制应放入 Release 或改为按需下载。

- [ ] 完善 `.gitignore`。
  - 建议确认忽略：`logs/`、录屏、临时截图、`*.pyc`、`__pycache__/`、IDE 文件、大型本地生成产物。
  - 注意不要误忽略需要随项目分发的资源图。

- [ ] 复查并必要时重存已有 README 和 docs 文档编码。
  - `.editorconfig` 只能约束后续编辑行为，不会自动转换历史文件。
  - 后续可逐个确认 README 和 docs 是否已按 UTF-8 保存。

## P4：可选优化

- [ ] 对图像资源建立索引或缓存元数据。
  - 当前资源文件数量较多，启动期或运行期全量扫描可能变慢。
  - 可考虑生成资源清单，按需加载。

- [ ] 给核心图像识别函数补充小型回归测试。
  - 重点覆盖模板匹配、mask、中文路径读取、最小化窗口截图恢复逻辑。

- [ ] 给战斗方案编辑器增加保存前校验。
  - 保存前检查 UUID、字段类型、卡片名、波次配置、坐标范围。
  - 目标：减少运行时才发现配置错误。

- [x] 梳理测试目录的提交边界和生成物路径。
  - 正式回归测试、可复现诊断脚本和最小夹具继续由 Git 追踪。
  - 本地研究产物统一写入对应测试旁边的 `output/`，并按文件类型忽略。
  - 测试目录规范见 `test/README.md`。
