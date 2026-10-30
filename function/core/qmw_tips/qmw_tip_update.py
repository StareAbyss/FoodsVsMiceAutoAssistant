"""更新与备份说明窗口。

该窗口只承载说明文本，不参与更新流程本身，避免用户在更新页误解
正式版、开发版、备份和恢复之间的关系。
"""

from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget


text = """\
一. 更新列表

    * 加载正式版更新列表
        * 只显示带版本 tag 的发行版本。
        * 普通用户优先使用这个入口，风险最低。

    * 加载开发版更新列表
        * 显示 main 分支上的 PR 合并提交。
        * 这些提交用于开发和排查问题，不保证每一个提交都能直接运行。

    * 加载更多开发者更新内容
        * 继续向更早的 PR 合并提交翻页。
        * 已经找到需要的提交后，不需要继续加载。

二. 更新执行

    * 更新至选中的版本
        * 下载前先根据当前版本大小初步评估磁盘空间。
        * 会先下载目标版本到 update_cache 中的临时目录。
        * 源码转发行、文件校验和配置迁移均在隔离进程中使用目标版本自己的规则。
        * 准备后按实际体积复核空间，确认后启动目标版本的外部 updater。
        * 主程序退出后重新构建候选版本并迁移最终保存的数据，再备份和替换版本区。
        * 更新完成后请自行运行新版 FAA - 环境安装器.exe，准备环境后启动 FAA。

    * 更新前会检查磁盘空间。
        * 至少需要容纳新版本目录和更新前备份。
        * 空间不足时会停止替换，避免把当前目录更新到一半。

三. 备份和恢复

    * 每次替换前会把当前版本区放入 backups。
    * backups、update_cache 和 .venv 不随版本覆盖。
    * 普通更新会替换为目标版本的环境安装器，旧安装器随旧版本进入备份。
    * 使用 FAA - 环境安装器.exe 的“恢复到备份”页面查看备份详情、删除或恢复指定备份。
    * 安装器恢复前会另存当前版本；恢复失败时尝试回滚，并保留安装器和当前日志。

四. 注意事项

    * 当前版本状态会显示本地记录的版本 tag、PR、commit 等信息。
    * 如果状态缺失，通常说明旧版本没有写入 update_state.json，或正在开发环境中运行。
    * 更新系统不会保留未被迁移器纳入规则的普通版本区文件。
"""


class QMWTipUpdate(QMainWindow):
    """展示版本更新和备份恢复规则的只读说明窗口。"""

    def __init__(self):
        """初始化说明窗口尺寸、标题和只读文本区域。"""
        super().__init__(parent=None)
        self.setWindowTitle("更新与备份说明")
        self.text_edit = None
        self.setFixedSize(760, 460)
        self.initUI()

    def initUI(self):
        """构建说明窗口的 QTextEdit 主控件。"""
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(text)

        layout = QVBoxLayout()
        layout.addWidget(self.text_edit)

        main_widget = QWidget()
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
