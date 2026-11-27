# 图像资源自动流水线

本包负责原始数据获取、候选解析和识别模板生成。数据库凭据仍只读取项目根目录的 `image_resource_db.local.json`，不存入本包、资源目录或发行包。

## 命令入口

从项目根目录运行：

```powershell
# 原始数据：Excel、compose、CardFusion
uv run python -m tool.image_resource_pipeline.sources

# 只刷新 Excel
uv run python -m tool.image_resource_pipeline.sources --excel-only

# 战利品：获取、名单排序、失败样本建议、正式模板同步及候选清理
uv run python -m tool.image_resource_pipeline.loot

# 准备房间卡片：解析进化、融合链路并生成图片及类别配置
uv run python -m tool.image_resource_pipeline.cards --skip-excel-update
```

战利品只读预览使用 `loot --dry-run`；`loot --offline` 仍会同步和清理图片，只是不联网。卡片 `--dry-run` 不下载或写正式图片及类别配置，但仍按原流程刷新 XML 并生成候选报告。

可选战利品诊断入口：`python -m tool.image_resource_pipeline.loot.diagnostics`、`python -m tool.image_resource_pipeline.loot.compare`、`python -m tool.image_resource_pipeline.loot.classify`。

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `common/paths.py` | 开发工具项目根目录与 db 路径 |
| `common/snapshot_files.py` | 只读快照索引、文件名日期排序和显式路径校验 |
| `common/excel.py` | 两套流程共用的 Excel 读取 |
| `common/download.py`、`common/files.py` | 共用下载重试、本地复制、CSV 与原子替换 |
| `sources/snapshots.py` | 快照刷新、校验、失败回退与同类旧快照清理 |
| `sources/xiaye.py` | 独立数据库导出工作进程；不调用上层编排 |
| `loot/__main__.py`、`loot/workflow.py` | 战利品参数入口和整轮流程 |
| `loot/classification.py`、`loot/matching.py`、`loot/sync.py` | ID 分类、失败证据、名单与正式资源同步 |
| `cards/catalog.py`、`cards/models.py`、`cards/chains.py` | 卡片目录、数据结构、进化与融合链 |
| `cards/workflow.py`、`cards/reports.py` | 卡片生成编排、链路报告与选择器元数据 |

依赖方向为“命令入口 → 流程编排 → 解析/匹配/文件操作”。快照管理在带超时的隔离子进程中运行 `sources.xiaye`；导出器仅依赖路径与数据库访问，不反向调用快照管理。

`function/common/loot_policy.py` 由工具与 FAA 运行时共用，继续保留在运行时代码中。运行时自动采集卡片状态图的 `function/core_battle/card.py` 不属于离线资源流水线。

## 数据与产出位置

- `resource/db/`：三种最新原始快照；不读取或回退项目根目录的 Excel。
- `resource/image/item/`：战利品人工黑白名单、自动未分类名单和正式模板。
- `resource/image/card/准备房间/`：正式卡片图片。
- `config/card_stage_categories.json`：卡片选择器的金卡、融合卡类别配置。
- `resource_other/`：未分类战利品候选、下载与分析报告。
- `logs/match_failed/loots/`：只读的历史失败样本。
- `cards/card_prepare_room_card_blacklist.csv`：开发阶段使用的卡片未实装规则。

战利品执行细则见 [战利品名单与失败样本规范](loot/README.md)。卡片流程保持原有生成行为：默认直接更新正式卡片目录和类别配置，发布前仍需人工审核。发行打包不导入本工具包或联网获取资源。
