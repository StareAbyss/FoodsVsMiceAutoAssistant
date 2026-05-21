# 数据格式与配置约定

## 模块职责

这一部分说明项目运行时依赖的几类核心数据：

- 主配置 `settings.json`
- 战斗方案 `battle_plan/*.json`
- 微调方案 `tweak_plan/*.json`
- 任务序列 `task_sequence/*.json`
- 关卡信息配置 `stage_info*.json`
- 运行日志与输出目录

## 关键文件/类

- `resource/template/settings.json`
- `function/core/qmw_2_load_settings.py`
- `function/scattered/class_battle_plan_v3d0.py`
- `function/scattered/check_battle_plan.py`
- `function/scattered/check_task_sequence.py`
- `function/scattered/read_json_to_stage_info.py`
- `config/stage_plan.json`

## `settings.json`

### 职责

主配置文件，承载主窗口绝大多数状态，包括：

- 账号与基础设置
- 定时计划
- 当前方案
- 高级设置
- 加速
- 温馨礼包
- 二级密码
- 高级战斗设置
- 日志设置
- 登录设置
- 强卡器联动
- 皮肤
- QQ 登录信息

### 代码约定

- UI 实际读写的是 `config/settings.json`
- `qmw_2_load_settings.py` 里有两条模板相关路径：
  - 缺文件引导使用 `resource/template/settings_template.json`
  - 结构补全与类型纠正使用 `resource/template/settings.json`
- 当前仓库快照里能直接看到的是后者，因此首次生成配置文件时要特别留意前者是否存在

## 战斗方案

### 存放位置

- `battle_plan/`
  正常战斗方案
- `battle_plan_not_active/`
  不参与 FAA 读取的存档区

### v3 数据模型

`class_battle_plan_v3d0.py` 中定义了核心 dataclass：

- `MetaData`
  - `uuid`
  - `tips`
  - `player_position`
  - `version`
- `Card`
  - `card_id`
  - `name`
- `Event`
  - `trigger`
  - `action`

常见动作类型：

- `loop_use_cards`
- `insert_use_card`
- `insert_use_gem`
- `shovel`
- `ban_card`
- `escape`
- `random_single_card`
- `random_multi_card`

### 校验与迁移

启动时会执行 `fresh_and_check_all_battle_plan()`：

- 检查 JSON 是否能解析
- 读取 `meta_data.version`
- 如果还是 v2，尝试自动迁移到 v3
- 修复 UUID 冲突
- 更新 `EXTRA.BATTLE_PLAN_UUID_TO_PATH`

## 微调方案

### 存放位置

- `tweak_plan/`

### 作用

微调方案不是完整战斗方案，而是附加行为控制。运行时会和关卡方案、战斗方案一起参与决策。

### 校验

启动时 `fresh_and_check_all_tweak_plan()` 会：

- 检查 JSON
- 修复 UUID 冲突
- 更新 `EXTRA.TWEAK_BATTLE_PLAN_UUID_TO_PATH`

## 任务序列

### 存放位置

- `task_sequence/`

### 结构特征

任务序列文件是一个列表，第一项通常是：

- `meta_data.uuid`
- `meta_data.version`

后续每项描述一个任务节点和其参数。

### 校验

`fresh_and_check_all_task_sequence()` 会：

- 确保文件是合法列表
- 自动插入 `meta_data`
- 自动生成或修复 UUID
- 修复重复 UUID
- 更新 `EXTRA.TASK_SEQUENCE_UUID_TO_PATH`

## 关卡信息配置

### 主要文件

- `config/stage_info_extra.json`
- `config/stage_info_online.json`
- `config/stage_info.json`
- `config/stage_plan.json`

### 读取优先级

`read_json_to_stage_info()` 的优先级是：

1. `stage_info_extra.json`
2. `stage_info_online.json`
3. `stage_info.json`
4. `default`

### `stage_plan.json`

它不是关卡静态信息，而是“关卡到方案”的映射文件，决定某个关卡默认用哪个卡组、战斗方案和微调方案。

## 资源与日志目录

### 输入型目录

- `config/cus_images/`
  用户自定义识图模板。
- `resource/image/`
  内建识图模板。
- `resource/model/`
  ONNX 模型。

### 输出型目录

- `logs/chests_image/`
- `logs/loots_image/`
- `logs/match_failed/`
- `logs/result_json/`
- `logs/yolo_output/`
- `logs/guild_manager/`
- `logs/recording/`

这些目录在 `get_paths.py` 导入时就会自动检查和创建。

## 扩展点

- 新增战斗方案字段：
  - 先改 `class_battle_plan_v3d0.py`
  - 再改编辑器与运行时解析
- 新增主配置字段：
  - 先改模板
  - 再改 `qmw_2_load_settings.py`
- 新增关卡属性：
  - 先改 `stage_info*.json`
  - 再改 `read_json_to_stage_info()` 的解释逻辑

## 常见坑

- UUID 映射表是在启动期刷新的，手改 JSON 后若不重新加载，内存态可能还是旧值。
- 任务序列和战斗方案都带自动修复逻辑，运行时看到文件被改写通常不是 bug，而是启动期校正。
- `stage_plan.json` 和 `stage_info.json` 职责不同：
  - 前者决定“用哪个方案”
  - 后者描述“这个关卡本身是什么属性”
