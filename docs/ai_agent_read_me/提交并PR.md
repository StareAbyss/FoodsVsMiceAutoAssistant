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

PR 必须设置 assignee (此处为示例)：

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
  * 默认 `直接以管理员权限通过PR` 无需其他开发者审核

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

## 操作示例：只提交脏工作区中的一个文件

参考 PR `#942`：`build: 更新 2026 6.18-7.2 stage_info_online.json`。

场景：

* 当前工作区有大量无关修改和未跟踪文件。
* 本次只需要提交 `config/stage_info_online.json`。
* 当前个人分支相对 `origin/main` 有历史领先提交，不能直接从个人分支发 PR，否则会夹带旧提交。

处理方式：

1. 先做最小检查。

```powershell
py -3.12 -m json.tool config/stage_info_online.json > $null
py -3.12 -m py_compile function/core/faa/faa_action_receive_quest_rewards.py
git diff --check origin/main -- config/stage_info_online.json
```

2. 从 `origin/main` 构造只包含目标文件的干净提交。

```powershell
git fetch origin main

$tempIndex = Join-Path $env:TEMP ('faa-pr-index-' + [guid]::NewGuid().ToString('N'))
try {
    $env:GIT_INDEX_FILE = $tempIndex
    git read-tree origin/main
    $blob = git hash-object -w -- 'config/stage_info_online.json'
    git update-index --add --cacheinfo "100644,$blob,config/stage_info_online.json"
    $tree = git write-tree
    $commit = git commit-tree $tree -p origin/main -m 'build: 更新 2026 6.18-7.2 stage_info_online.json'
}
finally {
    Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempIndex -Force -ErrorAction SilentlyContinue
}

git branch -f codex/stage-info-20260618-0702 $commit
git show --stat --oneline --name-only $commit
```

3. 推送干净分支并创建 PR。

```powershell
git push -u origin codex/stage-info-20260618-0702

gh pr create `
  --base main `
  --head codex/stage-info-20260618-0702 `
  --title "build: 更新 2026 6.18-7.2 stage_info_online.json" `
  --body "## 内容
* 更新 config/stage_info_online.json，本期范围为 2026 6.18-7.2。
* 更新时间写入 2026-06-18 12:00:00。
* 补充本期悬赏关卡水面地形配置。

## 校验
* 已通过 JSON 解析校验。
* 已通过 faa_action_receive_quest_rewards.py 语法编译校验。
* 已通过 git diff --check。" `
  --assignee StareAbyss `
  --label Git-Build `
  --label "🔄Module-Farmflow"
```

4. 管理员通过并使用 merge commit 合并。

```powershell
gh pr merge 942 --merge --admin --delete-branch
git fetch origin main
gh pr view 942 --json number,title,state,url,mergeCommit,labels,assignees
```

注意：

* 这种做法不会清理或切换当前脏工作区。
* PR 的 diff 只来自临时 index 构造出的提交。
* 合并热更新、版本发布相关 PR 时优先使用 merge commit，不要 squash/rebase。
