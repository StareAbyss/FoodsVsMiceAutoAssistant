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
* 发起 PR 前先获取最新 `origin/main`，功能分支必须以它为父提交。
* 不直接把脏的 `stareAbyss` 整体推送为 PR；应使用临时 index 或临时 worktree 构造只包含当前功能的提交。
* 同一个文件包含多项任务时，只提交当前功能对应的 hunk，不能整文件加入。
* 一个完整功能需要代码、配置、资源、生成器和测试共同闭环时，可以在同一 PR 中提交这些文件。
* 用户指定标题或标题后半部分时，优先原样采用，不自行缩写。
* 用户的 GitHub 为 `StareAbyss` 时，默认直接以管理员权限审核并使用 merge commit 合并，无需再次询问用户是否通过。

## 脏工作区与旧索引

本仓库可能同时存在多组未提交改动，Git 暂存索引也可能保留旧快照。普通 `git status` 出现 `MM`、`D` 时，不应立即清理或判定文件丢失。

真实改动审计优先使用临时 index：

```powershell
$tempIndex = Join-Path $env:TEMP ('faa-audit-' + [guid]::NewGuid().ToString('N') + '.index')
try {
    $env:GIT_INDEX_FILE = $tempIndex
    git read-tree HEAD
    git -c core.quotepath=false status --short --untracked-files=all
}
finally {
    Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempIndex -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath ($tempIndex + '.lock') -Force -ErrorAction SilentlyContinue
}
```

注意：

* 未经用户明确允许，不执行 `git reset`、批量 `git restore --staged` 或其他暂存索引清理。
* PR 审核比较使用 `origin/main..功能分支`，不要使用可能受旧索引影响的无参数 `git diff`。
* 若要确认工作区文件与某提交是否一致，比较 `git rev-parse HEAD:<path>` 和 `git hash-object --path=<path> -- <path>`。

## 检查命令

项目检查优先使用 uv 管理的项目 Python，而不是裸 `python` 或假定系统存在 `py -3.12`：

```powershell
uv run python ...
```

Python 文件语法检查示例：

```powershell
uv run python -m py_compile path\to\file.py
```

项目默认使用标准库 `unittest`，当前没有把 `pytest` 作为开发依赖。提交前应根据改动范围选择最小但有效的检查命令，并核对完整调用链。

## 操作示例：只提交脏工作区中的一个文件

参考 PR `#942`：`build: 更新 2026 6.18-7.2 stage_info_online.json`。

场景：

* 当前工作区有大量无关修改和未跟踪文件。
* 本次只需要提交 `config/stage_info_online.json`。
* 当前个人分支相对 `origin/main` 有历史领先提交，不能直接从个人分支发 PR，否则会夹带旧提交。

处理方式：

1. 先做最小检查。

```powershell
uv run python -m json.tool config/stage_info_online.json > $null
uv run python -m py_compile function/core/faa/faa_action_receive_quest_rewards.py
git diff --check origin/main -- config/stage_info_online.json
```

2. 从 `origin/main` 构造只包含目标文件的干净提交。

```powershell
git fetch origin main

$tempIndex = Join-Path $env:TEMP ('faa-pr-index-' + [guid]::NewGuid().ToString('N'))
try {
    $env:GIT_INDEX_FILE = $tempIndex
    git read-tree origin/main
    git add -- 'config/stage_info_online.json'
    $tree = git write-tree
    $commit = git commit-tree $tree -p origin/main -m 'build(悬赏关卡): 更新 2026 6.18-7.2 stage_info_online.json'
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
  --title "build(悬赏关卡): 更新 2026 6.18-7.2 stage_info_online.json" `
  --body "* 更新 config/stage_info_online.json，本期范围为 2026 6.18-7.2。
* 更新时间写入 2026-06-18 12:00:00。
* 补充本期悬赏关卡水面地形配置。" `
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
* 需要进入热更新节点列表的 PR 使用 merge commit，不要 squash/rebase。

## 多文件和同文件分块提交

如果多个目标文件全部属于当前功能，可以在临时 index 中一次加入：

```powershell
git read-tree origin/main
git add -- path/to/code.py path/to/config.json path/to/test.py
git diff --cached --check
```

如果目标文件还包含其他任务的修改，不能执行整文件 `git add`。应从 `origin/main` 生成干净文件后应用目标 patch，或只把经过审核的 hunk 应用到临时 index。提交后必须检查：

```powershell
git diff --check origin/main..codex/功能分支
git diff --name-status origin/main..codex/功能分支
git diff origin/main..codex/功能分支 -- path/to/mixed_file.py
```

## GitHub 审核与本地同步

创建 PR 后应在 GitHub 侧再次核对文件、标签和可合并状态：

```powershell
gh pr view <pr_number> --json number,title,state,url,files,labels,assignees,mergeable,statusCheckRollup
gh pr diff <pr_number> --name-only
```

网络超时后先按 head 分支查询是否已经创建 PR，再重试，避免重复创建：

```powershell
gh pr list --state all --head codex/功能分支 --json number,title,state,url
```

合并完成后：

```powershell
git fetch origin main
gh pr view <pr_number> --json number,title,state,url,mergeCommit,mergedAt
```

工作区干净时使用 `git merge --ff-only origin/main` 同步个人分支。工作区较脏或索引保留旧快照时，不得为了同步而 reset/clean；只有确认 `origin/main` 是当前分支的快进、合并内容已在工作区且文件哈希正确后，才可以只更新分支引用并保留索引。
