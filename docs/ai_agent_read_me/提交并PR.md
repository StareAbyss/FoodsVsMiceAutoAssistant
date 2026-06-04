# PR 工作流

本文记录本仓库提交、发起 PR、设置元数据和合并时的固定规则。

## 标题格式

提交标题和 PR 标题使用中文 conventional commits 风格：

```text
type(模块/范围): 中文说明
```

常用 type：

- `feat`: 新增功能
- `fix`: 修复问题
- `perf`: 优化体验、性能或流程
- `build`: 构建、资源、配置、数据文件调整
- `docs`: 文档
- `refactor`: 重构
- `style`: 代码风格或杂项整理

示例：

```text
feat(合成屋): 新增独立的宝石分解功能
fix(自检): 修复自动应用模板文件时缺乏路径导致的闪退
perf(界面跳转): 加速绝大多数操作的等待间隔
build(战利品识别): 将排序图迁移至config目录
docs(开发文档): 补充模块说明
```

## PR 正文

* PR 正文使用`中文`，可以没有正文。
* 正文仅需分点简要说明PR内容，不需要对检查描述。
* 项目更喜欢用 `*` 符号分点而非 `-` 符号

## PR 编码注意事项

* `git commit -m "中文"` 本身可以正常保留 UTF-8 中文。
* 如果使用 PowerShell 调 GitHub API 创建、编辑或合并 PR，不能直接把中文 JSON 字符串交给 `Invoke-RestMethod -Body $json`。Windows PowerShell 可能按非 UTF-8 编码发送请求体，导致 PR 标题、正文、合并提交标题变成 `????` 或乱码。
* 推荐优先使用 GitHub CLI `gh pr create` / `gh pr merge`。如果必须用 PowerShell + GitHub API，JSON 请求体必须显式转为 UTF-8 字节，并设置 `charset=utf-8`：

```powershell
$json = @{ title = "fix(模块): 中文标题"; body = "* 中文正文" } | ConvertTo-Json
$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($json)
Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $bodyBytes -ContentType "application/json; charset=utf-8"
```

## PR Assignee

PR 必须设置 assignee：

```text
StareAbyss
```

## PR Labels

PR 至少选择两个 label：

1. 一个 `Git-*` 变更分类
2. 一个相关 `Module-*` 模块分类

`Git-*` 与 changelog 分类对应：

* `Git-Feat`: 新增
* `Git-Perf`: 优化
* `Git-Fix`: 修复
* `Git-Build`: 资源、配置、构建、数据文件
* `Git-Docs`: 文档

常用模块 label：

* `🧐Module-Drop`: 战利品识别模块
* `🕹️Module-UI`: 用户界面
*  `🗡️Module-Battle`: 战斗执行器
* `👀Module-MatchImg`: 通用图像识别模块
* `🧠Module-OCR`: 文字识别模块
* `✏️Module-Editor`: 战斗方案、任务序列、全局方案、配置迁移编辑器
* `🔄Module-Farmflow`: 刷关或其他重复性流程

## 分支策略

* 只提交当前任务相关文件，不混入工作区中已有的无关改动。
* 用户的Github为 `stareAbyss` 时：
  * 把 `stareAbyss` 当前所有领先提交放到云端，然后再从 `stareAbyss` 发起 PR 合并到 `main`。
  * 默认 `直接通过PR` 无需其他开发者审核

## 检查命令

项目检查优先使用项目 Python 3.12，而不是裸 `python`：

```powershell
py -3.12 ...
```

Python 文件语法检查示例：

```powershell
py -3.12 -m py_compile path\to\file.py
```

提交前应根据改动范围选择最小但有效的检查命令。
