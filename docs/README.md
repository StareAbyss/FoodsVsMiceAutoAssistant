# FAA 开发文档

这组文档面向两类读者：

- 维护者：需要快速理解系统骨架、主流程、关键线程和关键数据。
- 二开开发者：需要找到战斗方案、任务序列、扩展脚本、OCR 和识图相关入口。

## 阅读顺序

1. [系统总览](./01-system-overview.md)
2. [界面、配置与编辑器](./02-ui-config-and-editors.md)
3. [运行时编排与 FAA 核心](./03-runtime-and-faa.md)
4. [战斗引擎](./battle/01-battle-flow.md)
5. [数据格式](./04-data-formats.md)
6. [扩展、测试与排障](./05-extension-test-and-troubleshooting.md)

## 文档地图

- [01-system-overview.md](./01-system-overview.md)
  说明项目定位、目录分层、启动链路和全局初始化。
- [02-ui-config-and-editors.md](./02-ui-config-and-editors.md)
  说明主窗口继承链、UI 资源加载、配置读写、编辑器模块。
- [03-runtime-and-faa.md](./03-runtime-and-faa.md)
  说明 `QMainWindowService`、`ThreadTodo`、定时执行、`FAA` 核心对象。
- [battle/01-battle-flow.md](./battle/01-battle-flow.md)
  说明战斗生命周期、战斗方案解析、`CardManager` 主流程。
- [battle/02-recognition-and-advanced.md](./battle/02-recognition-and-advanced.md)
  说明截图、模板匹配、动作队列、YOLO、高级战斗。
- [04-data-formats.md](./04-data-formats.md)
  说明配置、战斗方案、任务序列、关卡信息和日志目录的数据约定。
- [05-extension-test-and-troubleshooting.md](./05-extension-test-and-troubleshooting.md)
  说明扩展接口、OCR 插件、测试目录和常见故障。

## 仓库模块地图

- `function/`
  项目主代码。绝大多数业务逻辑都在这里。
- `config/`
  运行期配置与用户自定义图片。
- `battle_plan/`、`tweak_plan/`
  战斗方案和微调方案 JSON。
- `task_sequence/`
  自定义任务序列 JSON。
- `resource/`
  UI、图像模板、模型、主题、模板文件。
- `plugins/`
  OCR 等外挂式功能。
- `test/`
  实验脚本、验证脚本、局部模块测试。
- `python_loader/`
  打包/运行时随附的 Python/OpenCV 装载内容，不是核心业务代码。
- `upx/`
  打包相关第三方工具。

## 术语表

- `FAA`
  项目的核心自动化对象，负责游戏窗口操作、战斗和日常功能。
- `ThreadTodo`
  主执行线程，负责按配置串起日常、刷图、任务序列等事项。
- `CardManager`
  战斗执行器，负责把战斗方案转成实际放卡动作。
- `BattlePlan`
  战斗方案数据模型，描述卡组、事件和动作。
- `Tweak Plan`
  微调方案，给战斗方案追加局部行为开关或细节修正。
- `Stage Info`
  关卡静态信息，包含地图属性、承载卡、任务卡等。
- `Task Sequence`
  自定义事项流水线，描述要按什么顺序执行哪些任务。

## 阅读建议

- 如果你要改主窗口、配置或编辑器，从 [界面、配置与编辑器](./02-ui-config-and-editors.md) 开始。
- 如果你要改执行链路、定时器或事项编排，从 [运行时编排与 FAA 核心](./03-runtime-and-faa.md) 开始。
- 如果你要改自动放卡、识图或高级战斗，从 [战斗引擎](./battle/01-battle-flow.md) 开始。
- 如果你要加新方案、新任务类型或新扩展，先看 [数据格式](./04-data-formats.md) 和 [扩展、测试与排障](./05-extension-test-and-troubleshooting.md)。
