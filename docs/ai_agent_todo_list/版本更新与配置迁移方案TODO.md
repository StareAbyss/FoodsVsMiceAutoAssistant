# 版本更新与配置迁移方案 TODO

本文记录当前版本更新系统的最终方向、已落地内容、剩余风险和后续测试方案。后续 AI 优先阅读本文件，不需要再回溯旧 `plugins/git_plus` 热更新实现。

## 当前结论

- 只有一种面向普通用户的正式更新通道，不再区分正式版 / 公测版。
- 普通用户更新目标是“带版本 tag 的 PR merge commit”。
- 开发者模式更新目标是 `main` 上高于当前版本位置的 PR merge commit。
- 不向普通用户展示普通单 parent commit。
- 不在当前运行目录原地 `git pull`、`reset --hard`、`clean` 或切换分支。
- 更新流程采用“下载到 staging -> 迁移用户数据 -> 外部 updater 替换版本区”。
- 回退通过更新前备份恢复，不通过选择旧 commit 实现。
- `.venv/`、`backups/`、`update_cache/`、`FAA-恢复到备份.bat` 是保留区，不随版本覆盖。
- 除保留区外，根目录其他内容视为版本区。未被迁移器迁移的旧版本内容可以随旧版本进入备份。
- `logs/` 不整体保留，只有迁移规则明确列出的内容才迁移。
- `FAA.exe` 是普通用户正式入口，内部只负责调用 `plugins/launcher_scripts/AppInstallRun.bat`。
- `plugins/launcher_scripts/AppInstallRun.bat` 是内部启动壳，不在根目录暴露；每次更新后由新版覆盖为正确内容。
- `plugins/launcher_scripts/AppInstallRun.ps1` 是固定安装和运行脚本，负责中文提示、环境准备和独立启动主程序。

## 已落地

- [x] 新增 `function/common/update_state.py`
  - 读取 `.git`、`update_cache/update_state.json`、`EXTRA.VERSION`。
  - 生成和维护当前安装状态。

- [x] 改造 `一键生成分发资源.py`
  - 打包时自动写入 `dist/FAA/update_cache/update_state.json`。
  - 将 `plugins/updater` 和 `FAA-恢复到备份.bat` 纳入分发资源。

- [x] 新增 `function/common/update_manifest.py`
  - 通过 GitHub API 读取版本 tag。
  - 只处理 `vX.Y.Z` 形式 tag。
  - 确认 tag 指向 PR merge commit。
  - 通过 `/commits/{sha}/pulls` 反查 PR 编号、标题、链接。
  - 支持读取 `main` 上 PR merge commit 作为开发者列表。
  - 写入 `update_cache/update_manifest_cache.json`。
  - 普通模式跳过已缓存 tag。
  - 开发者模式遇到已缓存 commit 或当前 commit 即停止翻页。
  - PR 反查结果缓存到 `pulls_by_commit`，减少重复访问。
  - 处理 GitHub rate limit、断流、连接关闭等网络异常。

- [x] 新增 `function/common/update_staging.py`
  - 从 GitHub zip archive 构建 `update_cache/staging/FAA.update.new/`。
  - 不把 `.git` 带入 staging。
  - 将源码布局转换为分发布局，例如把 `plugins/root_entries` 铺到根目录，并保留 `plugins/launcher_scripts` 中的 PowerShell 脚本本体。
  - 复用分发规则，排除不应进入分发包的配置和缓存。
  - 开始新 staging 前把旧 staging 移动到 `update_cache/failed_staging/`。
  - `failed_staging/` 最多保留 2 份。
  - 目标版本缺少 `plugins/updater` 时，从当前安装目录补入 updater。
  - staging 中自动写入目标版本的 `update_cache/update_state.json`。
  - 校验 `LICENSE`、`pyproject.toml`、`uv.lock`、`FAA.exe`、`FAA-调试模式启动.bat`、`FAA-卸除运行环境.bat`、`FAA-恢复到备份.bat`、`plugins/launcher_scripts/AppInstallRun.bat`、`plugins/launcher_scripts/AppInstallRun.ps1`、`function/`、`resource/` 等关键内容。

- [x] 新增 `function/common/update_space.py`
  - 估算当前版本区大小、staging 大小、磁盘可用空间和安全余量。
  - `.venv/`、`backups/`、`update_cache/` 不计入版本区备份大小。

- [x] 新增 `function/common/update_backup.py`
  - 列出 `backups/` 下由 updater 管理的备份。
  - 读取备份 `.update_state.json`。
  - 支持受限删除，只允许删除 `backups/` 内符合命名规则的备份目录。

- [x] 新增 `function/core/settings_migration.py`
  - 抽出无 UI 的迁移核心。
  - 支持 `migrate_user_data(source_root, target_root, selected_names)`。
  - 支持整文件覆盖、整目录替换、普通文件夹合并和 UUID JSON 合并。
  - 战斗方案、微调方案、任务序列均按 UUID 合并，避免旧配置覆盖新版内置方案。

- [x] 改造 `function/core/qmw_settings_migrator.py`
  - UI 迁移器复用无 UI 迁移核心。
  - UI 只负责选择目录、勾选迁移项和展示结果。
  - 重新选择来源目录时重置复选框状态。

- [x] 新增 `function/core/update_prepare.py`
  - 串联 staging 准备和配置迁移。
  - 不启动 updater，不替换当前目录。
  - 支持 `prepare_update_from_github()` 和 `prepare_update_from_archive()`。
  - 迁移报告写入 staging 内 `update_cache/migration_report.json`。

- [x] 新增 `function/core/update_apply.py`
  - 将 `plugins/updater/updater.py` 复制到 `%TEMP%/FAA-updater/`。
  - 优先使用当前 `.venv/Scripts/python.exe` 启动 updater。
  - 传入主进程 PID，让 updater 等待主进程退出后再替换。

- [x] 新增并改造 `plugins/updater/updater.py`
  - 支持 `update` 和 `restore` 两种模式。
  - update：当前版本区移动到 `backups/FAA.backup.<timestamp>/`，staging 版本区移动到根目录。
  - restore：当前版本区先移动到 `FAA.before-restore.*`，再从指定备份恢复。
  - 保留 `.venv/`、`backups/`、`update_cache/`、`FAA-恢复到备份.bat`。
  - 支持 `--wait-pid`、`--wait-timeout`。
  - 每个关键阶段写入 `update_cache/updater_state.json`。
  - 日志写入 `update_cache/updater_logs/`。
  - 更新或恢复失败时尽量回滚，并保留失败现场。

- [x] 新增 `FAA-恢复到备份.bat`
  - GUI 无法启动时可列出 `backups/` 备份。
  - 用户选择备份并二次确认后调用 updater restore。

- [x] 新增 `function/core/qmw_update_backup_manager.py`
  - 可视化管理更新备份。
  - 支持刷新、查看版本信息、删除、恢复。
  - 恢复时启动临时 updater，当前程序退出后执行。

- [x] 改造更新页 UI 和逻辑
  - [x] `resource/ui/FAA_3.0.ui` 已直接包含更新状态 label、进度 label 和 3 行按钮布局。
  - [x] 第 1 行：加载正式版更新列表 / 更新至选中的版本。
  - [x] 第 2 行：加载开发版更新列表 / 加载更多开发者更新内容。
  - [x] 第 3 行：管理更新备份 / 查看相关说明。
  - [x] `function/core/qmw_3_service.py` 接入正式版列表、开发者列表、更新准备、备份管理和说明窗口。
  - [x] 更新页显示当前版本、tag、PR、commit、分支、来源、状态。
  - [x] 更新页显示当前操作阶段和已等待秒数。
  - [x] 网络错误会转换成用户可理解的提示，例如连接断开、读取不完整、超时、DNS、证书、rate limit。
  - [x] 旧原地 Git 更新按钮和旧 Git 配置按钮已移除。

- [x] 删除旧 `plugins/git_plus` 更新模块
  - 不再依赖内置 MinGit。
  - 不再导入 `plugins.git_plus.GitSDK`。
  - 不再对当前运行目录执行原地 Git 覆写。

## 版本与 PR 规则

术语：

```text
PR merge commit = main 上形如 “Merge pull request #927 ...” 的双 parent commit
正式版本 = 打了版本 tag 的 PR merge commit
开发者版本 = main 上未必打 tag 的 PR merge commit
```

远端事实：

- 仓库：`https://github.com/StareAbyss/FoodsVsMiceAutoAssistant`
- 默认分支：`main`
- 本地开发分支通常为：`dev`
- 已抽查 tag：
  - `v3.0.2` -> PR `#895`
  - `v3.0.1` -> PR `#879`
  - `v3.0.0` -> PR `#861`
  - `v2.3.0` -> PR `#820`

仍需仓库管理员人工确认：

- [ ] `main` 是否强制通过 PR 合并。
- [ ] 是否禁止直接 push 到 `main`。
- [ ] 是否禁止 force push。
- [ ] 是否保留 `Allow merge commits`。
- [ ] 是否关闭或避免使用 `Squash merging` / `Rebase merging`。

如果继续把 PR merge commit 作为版本单位，仓库应固定使用 `Create a merge commit` 合并方式。公开 API 不能可靠确认完整分支保护设置。

## 标准更新流程

```text
1. 更新页读取本地 update_manifest_cache.json 和 update_state.json。
2. 用户点击刷新时访问 GitHub。
3. 普通模式读取 tag 并解析为 PR merge commit。
4. 开发者模式分页读取 main commits 并过滤 PR merge commit。
5. 用户选择目标版本。
6. 校验目标 commit 是否高于当前 commit。
7. 下载目标 tag/commit zip 到 update_cache/staging_work/。
8. 构建 update_cache/staging/FAA.update.new/。
9. 校验 staging 完整性。
10. 执行配置迁移：当前根目录 -> staging 新版本目录。
11. 写入迁移报告和空间评估。
12. 用户二次确认。
13. 复制 updater 到 %TEMP%/FAA-updater/。
14. 主程序启动 updater 并退出。
15. updater 等待主程序退出。
16. updater 备份当前版本区。
17. updater 把 staging 版本区移动到根目录。
18. updater 启动 FAA.exe。
19. 新版启动流程通过 uv sync --locked --no-dev 修正普通用户运行环境。
```

禁止流程：

```text
删除当前根目录 -> 移动新版进来
```

原因：容易误删 `.venv/`、`backups/`、`update_cache/`、`FAA-恢复到备份.bat`。

## 迁移规则现状

迁移系统采用白名单规则。只有本节列出的用户数据会进入新版 staging；其余版本区文件会随旧版本进入 `backups/`，不会自动进入新版。

### 整文件覆盖

这些文件以来源 FAA 为准，直接覆盖目标 FAA 的同路径文件：

- [x] `config/settings.json`
  - 兼容旧路径：`config/opt_main.json`
  - 该文件仍是整文件覆盖；启动时再由模板补全缺失字段和修正类型。
- [x] `config/stage_plan.json`
- [x] `config/stage_info_extra.json`

### UI 分组

配置迁移工具 UI 使用 `QGroupBox` 分为四组：

- `配置文件`
  - `配置文件 - 核心`
  - `配置文件 - 关卡全局方案`
  - `配置文件 - 自定义关卡信息`
- `用户自定义图像`
  - `用户自截`
  - `背包道具 - 需删除`
  - `背包装备 - 需使用`
- `方案与任务`
  - `战斗方案`
  - `微调方案`
  - `自定义任务序列`
- `其他用户数据`
  - `公会管理器数据`
  - `战斗方案 - 未激活`

### 整目录替换

这些目录以来源 FAA 为准。每个目录独立显示为一个迁移选项；迁移前先清空目标目录，再完整复制来源目录：

- [x] `config/cus_images/用户自截/`
  - 兼容旧路径：`resource/image/common/用户自截/`
- [x] `config/cus_images/背包_道具_需删除的/`
- [x] `config/cus_images/背包_装备_需使用的/`

整目录替换只在来源目录存在时执行；来源目录不存在时不会清空目标目录。

### UUID JSON 合并

常用迁移项按以下顺序展示，并按 UUID 合并，不再按文件名覆盖：

- [x] `battle_plan/`
- [x] `tweak_plan/`
- [x] `task_sequence/`

其他迁移项放入 `其他用户数据` 分组：

- [x] `battle_plan_not_active/`

通用规则：

- 同 UUID：不迁移来源文件，保留目标 FAA 原文件。
- 默认 UUID：不迁移，保留目标 FAA 内置方案。
- UUID 不同但文件名相同：迁移来源文件，并在文件名后追加 ` (1)`、` (2)` 等数字，保留两者。
- 来源文件缺少 UUID：按对应类型的现有 UUID 生成逻辑生成新 UUID，再迁移。
- 来源目录内部 UUID 撞车：第一个合法文件保留原 UUID；后续同 UUID 文件生成新 UUID 后迁移。
- 来源 JSON 损坏或结构无法识别：不迁移，并在迁移报告中记录。
- 目标 JSON 损坏：不作为有效 UUID 参与去重，不主动删除。

UUID 读取位置：

- 战斗方案：`meta_data.uuid`，兼容旧版顶层 `uuid`。
- 微调方案：`meta_data.uuid`。
- 任务序列：第一项的 `meta_data.uuid`。

### 普通文件夹合并

- [x] `logs/guild_manager/**`
  - 用于保留公会管理器数据。
  - 当前仍是普通合并复制，不清空目标目录。

### 暂不迁移

以下内容暂不进入迁移白名单：

- [x] `resource/db/tasks.db`
- [x] `cus_extension_addon_script/**`
- [x] 扩展插件产生的用户数据
- [x] `logs/` 下除 `logs/guild_manager/**` 外的日志、截图、录屏、识别失败样本和统计产物
- [x] `.git/`、`.venv/`、`backups/`、`update_cache/` 等更新保留区或开发目录

仍需细化：

- [ ] `settings.json` 后续是否升级为字段级迁移，避免旧整文件覆盖新版默认配置。
- [ ] 迁移后生成更详细的引用校验报告，检查 `stage_plan`、`task_sequence` 引用的战斗方案 / 微调方案 UUID 是否存在。
- [ ] 更新流程是否允许用户在更新前勾选迁移内容，待定。

## 已知风险

- [ ] 迁移清单不完整导致用户数据没有进入新版 staging。
- [ ] `settings.json` 整文件覆盖可能覆盖新版默认配置。
- [x] `task_sequence` 按文件名覆盖，可能覆盖新版内置任务。
- [ ] 仓库合并策略变化后，PR merge commit 不再稳定存在。
- [ ] GitHub 网络质量不稳定，刷新列表或下载 archive 可能失败。
- [ ] 当前更新流程还缺少完整端到端人工演练。

已处理的高风险点：

- [x] 主程序运行中替换自身导致 Windows 文件占用。
- [x] 下载成功但迁移失败留下半成品目录。
- [x] 替换成功但新版无法启动，没有回滚入口。
- [x] Git 拉取可变 branch HEAD 导致用户之间版本不一致。
- [x] 磁盘空间不足导致备份或替换中途失败。
- [x] GitHub API rate limit 导致无法刷新远端列表。
- [x] 清理根目录时误删保留区。
- [x] updater 从 FAA 根目录运行导致 cwd 占用。
- [x] `.venv` 保留但未执行新版 `uv sync --locked --no-dev`。
- [x] 上次 staging 半成品被误当作本次更新结果。

## 与旧热更新 commit 的关系

3 月前后 syfoud 的旧热更新提交主要包含：

- `function/core/git_update_manager.py`
- `function/core/qmw_3_service.py`
- `resource/ui/FAA_3.0.ui`
- `plugins/git_plus/**`

旧方案核心是内置 MinGit，并在当前运行目录执行原地 Git 初始化、拉取、切换和覆写。该方向已经被新方案替代。

当前状态：

- [x] `plugins/git_plus/**` 已删除。
- [x] `plugins.git_plus.GitSDK` 引用已清空。
- [x] 旧 Git 配置按钮已清理。
- [x] `.ui` 中隐藏的旧更新按钮残留已清理。
- [x] `git_update_manager.py` 保留文件名，但职责已改为 GitHub tag/PR worker。
- [x] `qmw_3_service.py` 保留更新入口，但逻辑已改为新 staging/updater 流程。

结论：旧热更新 commit 中仍值得保留的是“更新入口”和“重启入口”的业务位置，不保留旧原地 Git 更新实现。

## 待测试

基础检查：

- [ ] `uv run python -m py_compile function/common/update_manifest.py function/common/update_staging.py function/common/update_state.py function/common/update_backup.py function/common/update_space.py function/core/git_update_manager.py function/core/settings_migration.py function/core/update_prepare.py function/core/update_apply.py function/core/qmw_update_backup_manager.py plugins/updater/updater.py function/core/qmw_3_service.py`
- [ ] 启动主程序，确认更新页控件显示正常。
- [ ] 点击“查看相关说明”，确认说明窗口可打开。
- [ ] 点击“管理更新备份”，确认备份管理窗口可打开。

离线/低风险测试：

- [ ] 用本地 archive 调用 `prepare_update_from_archive()`，确认 staging 构建成功。
- [ ] 检查 staging 不包含 `.git`。
- [ ] 检查 staging 包含 `FAA.exe`、`FAA-调试模式启动.bat`、`FAA-卸除运行环境.bat`、`FAA-恢复到备份.bat`、`plugins/launcher_scripts/AppInstallRun.bat`、`plugins/launcher_scripts/AppInstallRun.ps1`、`pyproject.toml`、`uv.lock`、`function/`、`resource/`。
- [ ] 检查 staging 内 `update_cache/update_state.json` 正确写入目标版本。
- [ ] 检查 staging 内 `update_cache/migration_report.json` 正确记录迁移结果。

真实流程测试：

- [ ] 刷新正式版更新列表。
- [ ] 刷新开发版更新列表。
- [ ] 加载更多开发者更新内容。
- [ ] 选择一个目标版本并准备 staging，但在二次确认时取消，确认当前目录未被替换。
- [ ] 在测试副本中执行完整 update，确认备份、替换、启动入口均正常。
- [ ] 在测试副本中执行 restore，确认可恢复到指定备份。
- [ ] 模拟 GitHub 断流、超时、rate limit，确认 UI 提示可理解。

## 待决策

1. 用户可勾选迁移内容时，哪些项目默认勾选？
2. 是否允许更新界面提供“仅准备 staging，不执行替换”的开发调试按钮？
3. 是否需要 CI 或维护脚本预生成云端 `update_manifest.json`？
4. `tweak_plan/**` 和扩展插件数据的迁移边界如何定义？
5. 更新失败后的 `failed_staging/` 是否只保留 2 份，还是提供 UI 管理入口？
