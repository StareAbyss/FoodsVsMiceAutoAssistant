# PR 工作流

本文说明提交、创建 PR、设置标签和负责人，以及合并的操作方法。
操作范围以根目录 [AGENTS.md](../../AGENTS.md) 和用户指令为准，文中的流程不代表操作授权。

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

## PR 正文

* PR 可以没有正文。
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

## 负责人和标签

PR 负责人设为 `StareAbyss`，至少选择两个 label：

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

## PR 拆分与杂项归类

按玩家可感知的功能边界拆分 PR；没有独立说明价值的维护内容集中为 `build: 杂项`，避免版本说明和 AI 上下文过于零碎。

- 文档与规划
  - 与代码功能同步编写的说明文档，必须跟随对应代码放入同一个 PR，不能为了 `docs` 类型单独拆分。
  - 不涉及代码变化的规范性补充，可以独立创建 `docs` 类型 PR。
- 测试
  - 随功能代码新增或修改的回归测试应跟随对应功能提交，但一般不需要在 PR 标题中单独体现；没有独立使用价值的零散测试整理归入 `build: 杂项`。
  - 只有具备独立入口、配置和执行能力的测试工具，才适合创建独立的 `test` 类型 PR。
- 杂项归类
  - 物品排序 DAG 的关系更新对大多数玩家不敏感，一律归入 `build: 杂项`，不单独创建 PR。
  - 仅对文件或资源文件进行批量重命名、且没有新增不同内容的文件时，一律归入 `build: 杂项`。
- 资源变更
  - 新增了不同内容的资源文件时，应根据资源意义判断是否独立创建 PR；新增放卡、准备房间或战斗相关图像通常意味着支持了更多卡片或识别场景，必须单独提交并在 PR 正文中明确说明。
  - 同一批资源同时包含批量重命名和新增内容时，应优先拆分：重命名归入 `build: 杂项`，新增资源进入对应功能或资源 PR，方便审核与回滚。
  - 新版本发布前获取到的战利品与准备房间卡片候选图片，必须先报告各自的新图片数量并等待维护者人工审核；审核通过后按资源类型分别创建 PR，不能由打包流程自动生成并夹带。
  - 准备房间卡片资源 PR 的标题必须列出本次新增资源对应的全部卡片原始名称；战利品资源 PR 的标题应明确新增资源对应的关卡或活动范围。

## 脏工作区与旧索引

本仓库可能同时存在多组未提交改动，Git 暂存索引也可能保留旧快照。普通 `git status` 出现 `MM`、`D` 时，不应立即清理或判定文件丢失。

`HEAD` 是当前提交，索引是准备提交的快照，工作区是磁盘上的文件。只推进分支引用而保留旧索引，
会让三者脱节：新提交已有、旧索引没有的文件会显示为暂存删除；已合并内容也可能显示为反向修改或 `MM`。
这些状态不等于文件丢失。不能把“引用已追平、旧索引未处理”作为本地同步完成的标准。

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

### 备份后对齐索引

只有用户明确允许取消原有暂存选择时，才能执行以下操作。它将全部现存本地改动保留为未暂存状态，
不修改磁盘文件，也不恢复原本已删除的文件。操作前核对实际仓库根目录，不能把迁移后残留的旧目录当成开发目录。

1. 记录当前分支、HEAD、原索引校验值，以及相对 HEAD 的真实改动和文件内容校验值；范围应包含未跟踪文件。
2. 确认没有正在运行的 Git 写操作。若存在 `index.lock`，先核实占用；仅在确认是遗留锁后备份移走，不能按时间或大小直接删除。
3. 清除临时 `GIT_INDEX_FILE` 设置后，备份并核验索引，再只对齐索引：

```powershell
$ErrorActionPreference = 'Stop'
if ($env:GIT_INDEX_FILE) { throw '请先退出临时索引环境' }
$indexPath = (git rev-parse --path-format=absolute --git-path index).Trim()
$backupDir = Join-Path (Split-Path -Parent $indexPath) ('local-maintenance-backups/index-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $backupDir | Out-Null
$backupIndex = Join-Path $backupDir 'index'
Copy-Item -LiteralPath $indexPath -Destination $backupIndex
if ((Get-FileHash -LiteralPath $indexPath).Hash -ne (Get-FileHash -LiteralPath $backupIndex).Hash) {
    throw '索引备份校验失败'
}
git read-tree HEAD
if ($LASTEXITCODE -ne 0) { throw '索引对齐失败，保留备份并停止' }
```

4. 用 `git diff --cached --exit-code` 确认暂存区无差异，并比较 `git write-tree` 与 `git rev-parse 'HEAD^{tree}'`。
5. 对照操作前记录，确认工作区文件清单、内容及原有删除状态不变，再报告备份位置。备份放在 Git 元数据目录，不进入 PR。

`git read-tree HEAD` 不带 `-u` 时只更新索引；禁止追加 `-u`、使用 `reset --hard`、`clean` 或批量检出覆盖本地文件。
旧索引备份只用于核对和恢复暂存选择，不是工作区文件备份；需要恢复时应先确认当前 HEAD，不能盲目覆盖新索引。

## 隔离提交示例

以下以只提交 `config/stage_info_online.json` 为例；不切换或清理原工作区，也不夹带个人分支的历史领先提交。

1. 核对完整调用链，按改动范围做最小有效验证。使用 `uv run python` 和标准库 `unittest`；项目未配置 `pytest`，不要假定裸 `python` 或 `py -3.12` 可用。

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
    $commit = git commit-tree $tree -p origin/main -m 'build(悬赏关卡): 更新悬赏关卡数据'
}
finally {
    Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempIndex -Force -ErrorAction SilentlyContinue
}

git branch -f codex/stage-info-update $commit
git show --stat --oneline --name-only $commit
```

3. 推送干净分支并创建 PR。

```powershell
git push -u origin codex/stage-info-update

gh pr create `
  --base main `
  --head codex/stage-info-update `
  --title "build(悬赏关卡): 更新悬赏关卡数据" `
  --body "* 悬赏关卡数据与本期活动一致。" `
  --assignee StareAbyss `
  --label Git-Build `
  --label "🔄Module-Farmflow"
```

多个文件全部属于当前功能时，在上述临时 index 中一次加入并执行 `git diff --cached --check`。
同一文件混有其他任务时，从 `origin/main` 生成干净文件后应用目标 patch，或只把审核过的 hunk 应用到临时 index，不能整文件加入。提交后检查：

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

用户授权合并后，使用 merge commit 保留热更新节点，不用 squash/rebase。管理员绕过审批仅在权限和授权允许时使用：

```powershell
gh pr merge <pr_number> --merge --admin --delete-branch
git fetch origin main
gh pr view <pr_number> --json number,title,state,url,mergeCommit,mergedAt
```

### 本地同步验收

* 工作区和暂存区均干净时，使用 `git merge --ff-only origin/main` 同步个人分支。
* 有本地改动时，先记录文件与暂存状态，确认 `origin/main` 是快进目标；逐项核对合并内容已在工作区，缺失内容需隔离提取，不能整文件覆盖。
* 仅推进分支引用不能替代完整同步。有真实暂存选择时保留并请求处理方向；用户允许取消暂存选择后，按“备份后对齐索引”执行。未经授权，不自行清理。
* 最终同时核对分支引用、索引和工作区：已合并内容不再显示为待提交，原有未合并改动及未跟踪文件仍在，保留暂存选择时其内容也必须正确。
* 若暂存索引尚未处理，只能报告“分支引用已追平，索引待处理”，不能声称本地状态已完全同步；不能为消除界面差异而丢弃文件或删除分支备份。
