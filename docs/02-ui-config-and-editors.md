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
- `function/core/qmw_tips/`
  集中管理 `qmw_tip_*.py` 提示窗口；主窗口服务层通过该子包导入，提示内容不在服务层维护。
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
- 同时检查战斗方案与微调方案协议：低版本尽量迁移，高版本只告警，并在加载窗口展示汇总结果。
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

### FAA视角

- 入口：主界面进阶设置左侧的“FAA视角”按钮，位于“实用小工具”和“更多工具”之间。
  实现位于 `function/core/qmw_faa_view.py`。
- 打开即实时预览所选 1P/2P 的 Flash 客户区，不需要开始录制。玩家窗口名称取 FAA 已保存的基础设置。
- “显示点击特效”显示 FAA 已实际投递的点击动画；“查看识图效果”显示模板匹配目标框、名称、匹配度及阈值。
  未达到阈值的结果显示在画面底部，不画成命中目标。高级战斗开启时还显示 YOLO 目标框和置信度。
- 识图百分比表示现有算法的模板匹配度或模型置信度，不是准确率统计。
  工具旁路读取已有结果，不为预览额外执行识图；逐像素卡片状态判断、OCR 和独立扩展脚本不在当前目标框覆盖范围内。
- 开始录制后选择 MP4 路径，默认在 `logs/recording/`；视频包含预览画面、勾选的特效及底部识图信息，无音轨，目标帧率为 20 FPS。
  停止录制后继续实时预览。录制期间锁定玩家选择，停止后可切换。
- 关闭或隐藏窗口会停止截图并完成正在录制的文件；最小化仍继续录制。
  FAA 主窗口退出前会先完成录像，避免强制退出导致 MP4 索引丢失。
- 游戏刷新后自动重新获取句柄；窗口缺失、截图为空、RGB 全黑或截图异常时显示等待提示，恢复后继续。
  `950×600` 是 FAA 坐标范围，客户区实测可能为 `950×596`；预览接受真实尺寸并按原坐标绘制，缺少边缘留底色。
  沿用 FAA 后台截图行为，最小化游戏窗口可能被恢复到非激活底层。
- 工具首次打开时才创建采集线程。关闭时清空短期观测数据，未打开时不持续截图或记录点击。
- 说明和目标标签采用较大的中文正文字体及高对比颜色；预览按当前屏幕 DPI 的实际像素绘制文字，
  避免固定录像帧二次缩放造成模糊。底部可同时显示最近 6 条识图调试信息，录像保持固定 `950×760` 尺寸。

### 公会贡献导出

- 公会管理页左侧的“导出 Excel”按钮会读取当前已加载的公会管理器数据。
- 每次只导出日历所选日期的数据，在 `logs/guild_manager/` 生成一份贡献表，
  不会生成或覆盖全部日期总表。
- 导出文件名格式为 `公会贡献数据导出_YYYY-MM-DD.xlsx`。
- 导出表只包含成员名、总贡献和周贡献，所有单元格统一使用微软雅黑字体。
- 如果同名文件正被 Excel 或 WPS 占用，界面会用中文提示用户关闭文件后重试。
- Excel 生成逻辑位于 `function/scattered/guild_contribution_exporter.py`，不依赖主窗口控件，便于独立测试。
- 原始导出功能由“小星蛋挞公会”的开发者“灼小星”提供。

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
- 完整协议检查只在 FAA 启动和用户点击打开战斗方案编辑器时执行。
- 主界面保存配置、关卡方案编辑器和任务序列编辑器只刷新 UUID 路径索引，
  不会迁移或改写战斗方案。

### 微调方案编辑器

- 主类：`QMWEditorOfTweakPlan`
- 启动 FAA 和用户手动打开编辑器时，都会扫描全部微调方案的 `meta_data.version`。
- 低版本方案会保留有效 UUID，并把可以确定语义的旧字段迁移到当前协议。
- 声明为当前版本但基础结构或字段类型异常的方案，会保留有效字段并回退异常字段。
- 高于当前协议的方案只集中提示用户升级 FAA，不由旧版编辑器写回。
- 扫描无异常时不弹窗；编辑器右上角会显示最近一次检查时间。
- 其他界面对微调方案列表的刷新只重建 UUID 路径索引，不执行迁移或修复。

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
