# 微调方案编辑器 Demo

该 Demo 用于评审“战斗方案编辑器”的微调方案扩展界面，不会修改正式编辑器代码。

运行：

```powershell
uv run python -m test.tweak_plan_editor_demo.demo
```

加载指定方案：

```powershell
uv run python -m test.tweak_plan_editor_demo.demo --plan "tweak_plan/开启录制.json"
```

生成离屏评审截图：

```powershell
uv run python -m test.tweak_plan_editor_demo.demo --screenshot "test/tweak_plan_editor_demo/output/demo.png"
```

分别评审亮色与暗色主题：

```powershell
uv run python -m test.tweak_plan_editor_demo.demo --theme light --screenshot "test/tweak_plan_editor_demo/output/demo-light.png"
uv run python -m test.tweak_plan_editor_demo.demo --theme dark --screenshot "test/tweak_plan_editor_demo/output/demo-dark.png"
```

运行数据模型测试：

```powershell
uv run python -m unittest test.tweak_plan_editor_demo.test_model test.tweak_plan_editor_demo.test_appearance -v
```

## FAA 外观一致性

- 使用主框体相同的 `EXTRA.Q_FONT`，不再单独指定微软雅黑。
- 使用 FAA 的统一窗口图标。
- 不强制指定 `Fusion`、`Windows` 等 Qt Style，默认继承系统原生 Style 与 `QApplication.palette()`。
- 下拉框、整数微调框、输入框、普通按钮和分组框不套用 QSS，保留 PyQt 原生箭头、微调按钮、边框与交互状态。
- 默认“跟随 FAA（系统）”，继承系统的亮暗层级，但会把红色等系统强调色替换为中性灰选中颜色。
- “亮色预览”和“暗色预览”只用于独立 Demo 评审；正式接入主框体后应继续继承主程序 Palette。
- 普通按钮、焦点框、状态徽章和校验提示均使用中性灰阶，不传播系统强调色。
- 仅“从外部导入 JSON”和“保存”通过控件调色板使用低饱和度蓝色文字，保留原生按钮外观。
- 所有标题、分组、按钮和状态文字均使用 FAA 字体的常规字重，不显式加粗。

## 交互约定

- 所有可缺省布尔字段使用下拉菜单，明确提供“缺省 (默认:…)”“是”“否”三项；括号中的值取自只读 `!默认.json`。
- “浏览方案”下拉框选择后立即切换，不再需要额外点击“加载所选”。
- “新建”复制 `!默认`，生成新 UUID、清空说明，以“新的方案”“新的方案 (2)”递增命名并立即保存到微调方案文件夹。
- “保存”写回当前方案；“删除”确认后通过 `QFile.moveToTrash()` 移入系统回收站，回收站操作失败时不会永久删除。
- 新建、切换、保存、删除和导入成功后，会在“从外部导入 JSON”右侧使用使用者色表 3 的绿色短暂提示，数秒后渐隐；底部旧状态文字已移除。
- 只修改方案名称再保存时会重命名原 JSON 并保留 UUID；名称编辑结束时立即拦截非法或重复名称并恢复原名称，保存前仍进行第二次防冲突检查。
- “从外部导入 JSON”复制到微调方案文件夹；UUID 无冲突时保持不变，冲突时生成新 UUID 并明确提示。
- 编辑器初始化和保存时都会扫描 UUID 冲突；固定内置 UUID 优先保留，发生冲突的普通方案自动换用 UUID1。
- 随机间隔区分“继承 (默认:…)”“明确关闭”和“使用随机范围”，可保留现有稀疏 JSON 的语义。
- 放卡后的随机间隔在编辑界面中使用整数毫秒，避免无意义的多位小数；JSON 使用 `cd_after_use_random: {active, range}` 聚合启用状态和秒数范围，加载和导出时自动换算。
- 录制玩家的“继承默认”项同样显示 `!默认.json` 中当前生效的玩家窗口。
- 录制配置聚合为 `recording: {active, timestamp, player}`，不读取已废弃的平铺字段。
- 未识别的 `meta_data` 字段会原样保留，便于后续增加选项。
- 自动辅助卡使用正向的 `enable_auto_card` 字段；旧 `ban_state` 与微调咖啡粉选项已移除。卡组数量限制触发的原有自动 Ban 咖啡粉逻辑不受影响。
- 自动承载已从一般辅助卡中独立为 `auto_mat_card`；`enabled` 控制自动承载，`use_first` 默认开启供 0 费承载优先建立地形，关闭后保留战斗方案首卡优先。
- 已废弃的 `enable_auto_card.mat` 与 `mat_card_first` 不参与读取。
- 战斗方案直接写入自动卡，或 card type 展开结果包含该卡时，不再重复携带、识别或注入自动动作。
- 创造神、幻幻鸡和美味计时器仅在方案存在正数 `kun` 复制目标时参与自动携带与使用。
- UUID、格式版本和上次编辑 FAA 版本统一使用 PyQt 原生灰色禁用态，不可点击或编辑；新方案使用战斗方案编辑器相同的 `uuid.uuid1()` 规则。
- 5 份内置方案使用固定 UUID；全零 UUID 的 `!默认` 是只读基准，不能编辑、保存或删除。加载默认方案不再弹窗，提示栏会说明其他方案的缺省/继承项取自该方案。
- “格式版本”永久只读；加载时展示方案原值，创建、修改或保存后自动更新为 `EXTRA.TWEAK_PLAN_VERSION`。
- `meta_data.faa_version` 记录上次编辑时 FAA 的 `EXTRA.VERSION`，界面只读展示为“上次编辑时FAA的版本号：”。

## 当前选项与源码接入

| JSON 字段 | 界面选项 | 当前实现 |
| --- | --- | --- |
| `senior_setting` | 启用高级战斗 | 已接入；还需要全局“自动高级战斗”开关同时开启。 |
| `cd_after_use_random` | 放卡后的随机间隔 | 已接入；使用 `{active, range}` 明确控制启用状态和秒数范围，并调整战斗检测轮次。 |
| `recording.active` | 开启战斗录制 | 已接入；战斗开始后启动、执行器退出后停止。 |
| `recording.timestamp` | 添加日期与时间遮挡 | 已接入；录制帧左上角绘制白底日期与时间。 |
| `recording.player` | 录制 1P / 2P 窗口 | 已接入；单人战斗选择 2P 存在风险。 |
| `auto_mat_card.enabled` | 启用承载卡 | 已接入自动携带与智能铺设；方案已包含时不重复加入。 |
| `auto_mat_card.use_first` | 优先使用承载卡（0费承载专用） | 默认开启；关闭后战斗方案首卡先于自动承载执行，适配需要 25 火苗的低练度承载。 |
| `enable_auto_card.icecream` | 启用极寒冰沙 | 已接入自动携带与最低优先级使用；方案已包含时不重复加入。 |
| `enable_auto_card.god` | 启用创造神 | 要求正数 `kun` 目标拥有完整 3×3 安全中心；只越位复制中心格，不推进原卡队列，遍历开启时可复制多个安全中心。 |
| `enable_auto_card.ikun` | 启用幻幻鸡 | 仅存在正数 `kun` 目标且方案未包含时自动携带、识别和使用。 |
| `enable_auto_card.timer` | 启用美味计时器 | 默认关闭；放在最高正数 `kun` 目标的首格，循环和遍历均关闭，优先级仅高于自动冰沙；仅二转按 3×1 范围向棋盘内侧偏移。 |
