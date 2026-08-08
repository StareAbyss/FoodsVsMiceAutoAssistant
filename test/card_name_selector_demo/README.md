# 卡片名称选择器 Demo

该 Demo 用于独立验证战斗方案编辑器“卡组编辑”中已经实装的卡片名称解析与可视化选择交互。

运行：

```powershell
uv run python -m test.card_name_selector_demo.demo
```

指定初始名称：

```powershell
uv run python -m test.card_name_selector_demo.demo --input "炭烧海星-2"
```

功能范围：

* 顶部名称输入实时区分卡片类型、基础卡名、固定转职名和无法解析的名称。
* 解析结果只展示 `resource/image/card/准备房间/` 中真实存在的图片。
* 默认按 `config/card_type.json` 浏览类型，可按类型别名或子卡片名称检索。
* 切换到“按具体卡片”后，可按基础名称或真实进化名称检索。
* “智能选最高”写入基础卡名；具体阶段写入 `基础卡名-数字`。
* 普通卡、金卡和融合卡分别显示对应的阶段文案。
* 复用 FAA 的 `EXTRA.Q_FONT`，且不强制指定 Qt Style 或固定浅色 QSS，可跟随系统原生样式与调色板。
