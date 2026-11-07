# 资源数据快照

这里保留三种最新快照：`点我获取更多图像资源 YYYY-MM-DD_HH-MM-SS.xlsx`、`compose YYYY-MM-DD_HH-MM-SS.xml`、`CardFusion YYYY-MM-DD_HH-MM-SS.xml`。`tasks.db` 与这些快照互不干扰。

相关资源流程启动时调用 `tool.image_resource_pipeline.sources.snapshots.ensure_snapshots()`；同一进程内每种资源至多尝试更新一次，包括失败的尝试，后续只读取该次结果。每种文件独立下载／导出并校验，成功后替换旧快照，随后只清理本目录同类的旧快照；失败则保留并读取本目录已有快照。缺少快照且获取失败时报告不可用，不读取或复制根目录 Excel。

手动刷新三种资源：`python -m tool.image_resource_pipeline.sources`。只刷新 Excel：`python -m tool.image_resource_pipeline.sources --excel-only`。两种入口均在本目录发布带时间戳的快照，导出暂存文件也只写在本目录下。自动读取、显式 `--excel`、发行打包和更新暂存均只使用本目录的 Excel。

指定 `--excel` 时，该轮工具不刷新 Excel，以免替换快照时删除已选输入；XML 仍按各工具流程更新。

数据库连接信息仅从项目根目录 `image_resource_db.local.json` 读取，与启动命令的当前目录无关。不通过命令行或环境变量提供凭据；本地 JSON 必须由 Git 忽略，不能复制到本目录或发行包。XML 来自游戏 CDN。
