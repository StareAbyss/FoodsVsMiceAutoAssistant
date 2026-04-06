# 界面、配置与编辑器

## 模块职责

这一层负责把“静态 UI 文件 + 全局主题资源 + JSON 配置 + 编辑器窗口”组织成一个可操作的桌面应用。它本质上解决三件事：

- 把 `resource/ui/*.ui` 和自定义控件装配成主窗口。
- 把 `config/settings.json` 与界面状态做双向同步。
- 把战斗方案、任务序列、关卡方案等编辑器挂到主窗口服务层。

## 关键文件/类

- `function/core/qmw_0_load_ui_file.py`
  `QMainWindowLoadUI`，主窗口 UI 装配基类。
- `function/core/qmw_1_log.py`
  `QMainWindowLog`，把日志、弹窗、图像输出绑定到 UI。
- `function/core/qmw_2_load_settings.py`
  `QMainWindowLoadSettings`，配置校正、加载、保存与控件映射。
- `function/core/qmw_3_service.py`
  `QMainWindowService`，实际主窗口服务类。
- `function/core/qmw_editor_of_battle_plan.py`
  战斗方案编辑器。
- `function/core/qmw_editor_of_task_sequence.py`
  任务序列编辑器。
- `function/core/qmw_editor_of_stage_plan.py`
  全局方案/关卡方案编辑器。
- `function/core/qmw_task_plan_editor.py`
  任务计划编辑器，带 OCR 辅助。

## 主窗口继承链

- `QMainWindowLoadUI`
  - `uic.loadUi()` 加载 `resource/ui/FAA_3.0.ui`
  - 设置标题、Logo、主题、系统托盘、无边框窗口、最小化到托盘
  - 初始化导航、搜索下拉框、样式
- `QMainWindowLog`
  - 创建 `SIGNAL.PRINT_TO_UI`、`SIGNAL.IMAGE_TO_UI`、`SIGNAL.DIALOG`
  - 提供“日志输出到 UI”的统一入口
- `QMainWindowLoadSettings`
  - 保证基础配置文件和模板存在
  - 修正 `settings.json` 结构
  - 读取/保存配置
  - 在主窗口中嵌入任务序列编辑器
- `QMainWindowService`
  - 绑定按钮、附属窗口、启动/停止逻辑、定时器、路径选择、工具入口

## 配置读写

### 配置初始化

`QMainWindowLoadSettings.__init__()` 会按顺序做以下动作：

- 检查用户自截图模板是否存在，必要时从 `resource/template/` 拷贝。
- 检查 `config/settings.json` 是否存在。
  - 代码当前用 `resource/template/settings_template.json` 作为“缺文件时的引导模板”。
- 检查默认微调方案和默认战斗方案是否与模板一致。
- 用模板结构修正 `settings.json`，补全缺失字段并纠正错误类型。
  - 这一步使用的是 `resource/template/settings.json`。
- 刷新战斗方案、微调方案 UUID 映射。
- 刷新内存资源缓存。
- 读取配置到 `self.opt`，再回填到 UI。

### 配置映射方式

`qmw_2_load_settings.py` 里有两大方向的方法：

- `json_to_opt()` / `opt_to_ui_*()`
  从 JSON 载入到内存，再映射到具体控件。
- `ui_to_opt_*()` / `opt_to_json()`
  把 UI 当前状态写回 `self.opt`，再落盘。

它不是声明式配置系统，而是手写映射逻辑。好处是可控，坏处是新增字段要同步改多处。

## 主题与资源

- 字体来自 `EXTRA.Q_FONT`，由 `EXTRA.py` 在导入期加载。
- QRC 资源通过 `function/qrc/*.py` 导入。
- 窗口图标、背景图、Logo 都从 `resource/` 读取。
- 主窗口会根据系统浅色/深色主题动态调整按钮图标与一部分样式。

## 编辑器模块

### 战斗方案编辑器

- 主类：`QMWEditorOfBattlePlan`
- 作用：
  - 编辑卡组、波次变阵、插卡、铲子、宝石、逃跑、禁卡、随机换位等事件
  - 保存/加载 JSON
  - 支持撤销/重做
  - 通过棋盘视图编辑落点
- 特征：
  - 文件很大，但本质是“数据模型编辑器 + 多模式 UI”
  - 编辑结果最终落到战斗方案 JSON 数据结构

### 任务序列编辑器

- 主类：`QMWEditorOfTaskSequence`
- 作用：
  - 用可拖拽行列表编辑任务流水线
  - 为不同任务类型动态生成参数控件
  - 生成并读取任务序列 JSON
- 特征：
  - 每一行是一个任务配置视图
  - 支持战斗、领奖、签到、双暴卡、扩展脚本等多种事项

### 关卡方案编辑器

- 主类：`QMWEditorOfStagePlan`
- 作用：
  - 管理“全局方案”和“具体关卡方案”的映射
  - 为每个关卡指定卡组、战斗方案和微调方案
- 特征：
  - 默认会同步全局方案到未单独配置的关卡
  - 对运行期选择战斗方案非常关键

### 任务计划编辑器

- 主类：`TaskEditor`
- 作用：
  - 管理独立的任务计划数据
  - 可借助 OCR 从图像识别任务信息
  - 提供刷关类与强卡类参数编辑
- 特征：
  - 通过 `PATHS["db"]/tasks.db` 使用 SQLite
  - 更像独立工具，而不是主执行链的核心部分

## 扩展点

- 新增配置项：
  - 在 `resource/template/settings.json` 定义结构
  - 在 `qmw_2_load_settings.py` 增加 UI 映射
- 新增附属窗口：
  - 在 `QMainWindowService.__init__()` 中实例化并绑定按钮
- 新增编辑器功能：
  - 优先修改对应编辑器的数据模型与保存逻辑，再补 UI

## 常见坑

- 配置结构是手写映射，漏改任一方向都会导致 UI 与保存内容不一致。
- `settings` 的“缺文件引导模板”和“结构校正模板”在代码里是两个不同路径：
  - 缺文件引导用 `resource/template/settings_template.json`
  - 结构校正用 `resource/template/settings.json`
- 当前仓库快照里可见的是 `resource/template/settings.json`，因此首次自举配置文件时要特别留意模板路径是否齐全。
- `QMainWindowService` 里混合了大量窗口绑定和服务逻辑，新增功能时要注意不要把配置层和执行层搅在一起。
