# 识图链路与高级战斗

## 模块职责

这一部分解释战斗引擎为什么能“看懂”游戏，并据此调整放卡。它主要由四段能力组成：

- 截图
- 模板匹配
- 动作节流队列
- YOLO 与高级战斗逻辑

## 关键文件/类

- `function/common/bg_img_screenshot.py`
- `function/common/bg_img_match.py`
- `function/globals/thread_action_queue.py`
- `function/yolo/onnxdetect.py`
- `function/core_battle/card_manager.py`
- `function/common/window_recorder.py`
- `function/scattered/match_ocr_text/*`

## 截图与窗口恢复

`bg_img_screenshot.py` 负责客户区截图。

### 核心特点

- 直接使用 Windows GDI 抓取窗口客户区。
- 支持全图截图和裁剪区域截图。
- 会检测图像是否“几乎全黑”。
- 如果检测到窗口最小化，并且提供了根窗口句柄，会尝试恢复窗口到非激活底层状态再重试。

### 这条逻辑的重要性

大量识图错误并不是模板本身的问题，而是窗口最小化、部分跑出屏幕、黑屏或 Flash 崩溃导致的截图异常。

## 模板匹配

`bg_img_match.py` 是图像识别基础设施。

### 能力边界

- 从截图中寻找单张模板
- 支持 Alpha 通道掩模
- 支持外部掩模图像
- 支持一次截图内匹配多个模板
- 统一返回状态码和坐标

### 实际用途

- 菜单按钮识别
- 结束标记识别
- 波次标识识别
- 卡片状态识别
- 掉落物和宝箱识别
- 各类任务和页面定位

## 动作队列

`ThreadActionQueueTimer` 是底层动作消费者。

### 职责

- 接收点击、移动、键盘事件
- 按 `CLICK_PER_SECOND` 节流执行
- 根据 DPI 缩放换算点击坐标
- 统一向目标窗口投递消息

### 为什么单独做一层

- 战斗计算和窗口点击速度不同步。
- 直接在策略线程里点击容易把 UI 和消息泵打爆。
- 统一队列可以统计积压情况，便于调参。

## YOLO 与模型推理

`onnxdetect.py` 用 `onnxruntime` 跑 `mouseV2.onnx`。

### 主要识别对象

- 特殊老鼠
- 波次标志
- 神风
- 障碍
- 暴风雪
- 冰块
- 魔塔 165 层特殊目标

### 运行特征

- 优先用 `DmlExecutionProvider`，否则退到 CPU。
- 识别结果会按需写入 `logs/yolo_output/`。
- 返回的是边界框和类别，用于高级战斗线程进一步决策。

## 高级战斗

高级战斗主要体现在 `ThreadUseSpecialCardTimer` 及其相关辅助逻辑。

### 解决的问题

- 普通循环放卡无法应对的高危目标
- 障碍/冰块等场地机制
- 对策卡自动使用
- 神风、波次爆发等特殊情况

### 关键机制

- 读取 YOLO 结果
- 刷新卡片状态
- 构建对策动作列表
- 评估障碍历史和评分矩阵
- 决定在哪个格子投入哪种特殊卡

## OCR 辅助

`function/scattered/match_ocr_text/` 和 `plugins/pak/chinese_ocr.py` 负责文本识别相关能力。

常见用途：

- 识别美食大赛任务描述
- 识别关卡名称
- 从图像辅助生成任务计划

这部分不是战斗主循环的硬依赖，但对任务自动化很重要。

## 扩展点

- 新模板匹配场景：
  - 放在 `bg_img_match.py` 的统一接口上复用
- 新识别模型：
  - 放在 `function/yolo/`，保持输入输出约定清晰
- 新高级战斗策略：
  - 直接补到 `ThreadUseSpecialCardTimer` 或拆出独立策略函数

## 常见坑

- 句柄正确但截图全黑，通常是最小化、越界或图像没刷新。
- 模板匹配阈值太高或太低都会导致误判，尤其在缩放和主题差异下更明显。
- YOLO 结果是高级战斗输入，不等于最终动作；不要把识别层和策略层混为一谈。
- 动作队列只是节流器，不负责“决定做什么”，策略问题要回到 `CardManager` 查。
