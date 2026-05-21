# 扩展、测试与排障

## 模块职责

这一部分涵盖三类内容：

- 扩展脚本与独立扩展 UI
- OCR 插件接入点
- 测试目录与常见故障定位

## 关键文件/类

- `function/faa_extension_main.py`
- `function/extension/extension_ui.py`
- `function/extension/extension_core.py`
- `plugins/pak/chinese_ocr.py`
- `function/scattered/match_ocr_text/`
- `test/`

## 扩展系统

### 入口

- 主程序入口：`function/faa_extension_main.py`
- UI 主体：`function/extension/extension_ui.py`
- 底层能力：`function/extension/extension_core.py`

### 设计目标

扩展系统的目标不是替代主程序，而是把 FAA 已有的窗口操作、截图和识图能力暴露给自定义脚本，让用户完成更自由的自动化。

### `extension_core.py` 提供的核心原语

- 获取窗口句柄
- 恢复最小化窗口
- 客户区截图
- 裁剪图像
- 黑屏检测
- 坐标缩放
- 鼠标点击与移动
- 字符输入

这些接口和主程序里 `common/` 下的能力相似，但更偏向脚本作者直接调用。

### `extension_ui.py`

这是一个独立的扩展脚本编辑与调度界面，包含：

- 图片路径与识图条件配置
- 点击后输入、偏移量、超时、休眠等行为参数
- 代码编辑窗口
- 定时调度器

它说明项目已经把“识图后做什么”抽象成可脚本化流程。

## OCR 插件

### 文件

- `plugins/pak/chinese_ocr.py`
- `function/scattered/match_ocr_text/`

### 作用

- `plugins/pak/chinese_ocr.py`
  - 封装 `OcrHandle`
  - 提供 `try_ocr()` 和 `try_ocr_sort()`
  - 主要作为任务计划编辑器 OCR 安装流程中的种子脚本，被复制到独立 OCR 环境后使用
- `function/scattered/match_ocr_text/`
  - 是主程序内部的字形匹配式 OCR
  - 直接服务于关卡名称识别和美食大赛任务解析

### 边界

- 外部 OCR 插件并不直接承担 FAA 主战斗链路里的文字识别。
- FAA 主流程中与比赛任务、关卡名称相关的 OCR 更依赖 `match_ocr_text/` 这套内置实现。

## `test/` 目录用途

这个目录更接近“实验脚本 + 局部验证”，不是一套严格统一的自动化测试框架。

### 可以按主题理解

- 截图与识图
  - `test_screenshot.py`
  - `test_match_pixels.py`
  - `test_screen_in_battle_all_card.py`
  - `capture_image/`
  - `capture_card_state_image/`
- 动作队列与线程
  - `test_action_queue_timer.py`
  - `test_queue_click.py`
  - `test_thread.py`
- UI/控件
  - `test_QListWidgetDraggable.py`
- 算法或任务拆分
  - `test_split_task.py`
  - `test_dag.py`
- 模型/环境
  - `test_cuda.py`
- 临时或场景验证
  - `test_大富翁.py`
  - `test_click.py`
  - `test.py`

## 常见故障与排查路径

### 截图全黑或匹配失败

优先检查：

- 游戏窗口是否最小化
- 游戏窗口是否部分跑出屏幕
- 是否锁屏或息屏导致图像不刷新
- Flash 或游戏是否崩溃

相关模块：

- `bg_img_screenshot.py`
- `bg_img_match.py`

### 点击位置不准

优先检查：

- DPI 缩放
- `EXTRA.ZOOM_RATE`
- `T_ACTION_QUEUE_TIMER.set_zoom_rate()`

相关模块：

- `get_system_dpi.py`
- `thread_action_queue.py`

### 方案或任务序列打不开

优先检查：

- JSON 是否损坏
- UUID 是否冲突
- 是否被启动期修复逻辑改写

相关模块：

- `check_battle_plan.py`
- `check_task_sequence.py`

### 战斗中放卡异常

优先检查：

- 卡片状态记忆是否学错
- 高级战斗是否误判障碍
- YOLO 输出是否异常
- 当前关卡方案是否指向了错误战斗方案

相关模块：

- `card_manager.py`
- `faa_core.py`
- `qmw_3_service.py` 中的重置卡片状态记忆功能

### OCR 结果差

优先检查：

- 图片尺寸是否合适
- 是否使用了正确的裁剪区域
- OCR 环境是否完整

相关模块：

- `plugins/pak/chinese_ocr.py`
- `qmw_task_plan_editor.py`
- `function/scattered/match_ocr_text/`

## 扩展点

- 新增扩展脚本能力：
  - 优先在 `extension_core.py` 加原语
- 新增 OCR 使用场景：
  - 先分清是主流程内置 OCR，还是工具链外部 OCR，再决定落点
- 新增测试脚本：
  - 建议按“截图/匹配/线程/UI/算法”主题归类，避免继续堆平铺脚本

## 常见坑

- 很多 `test/` 脚本更像人工验证工具，不能默认它们能被统一测试框架直接跑通。
- 扩展系统与主程序共享很多底层假设，例如窗口分辨率、句柄结构和消息投递方式。
- 插件和扩展能复用主程序能力，但不自动继承主程序的全部状态管理，需要调用方自己负责流程控制。
