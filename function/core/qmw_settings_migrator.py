import os
import os.path

from function.globals.loadings import loading

loading.update_progress(65,"正在加载FAA迁移工具...")
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QMessageBox, \
    QFileDialog, QHBoxLayout, QCheckBox, QGroupBox

from function.globals.get_paths import PATHS
from function.core.settings_migration import build_migration_plan, get_migration_configs, migrate_user_data


class QMWSettingsMigrator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("配置迁移工具 - 请注意查看鼠标提示信息!")
        self.setWindowIcon(QIcon(os.path.join(PATHS["logo"], '圆角-FetDeathWing-450x.png')))

        # 设定窗口初始大小 否则将无法自动对齐到上级窗口中心
        self.resize(1025, 560)

        self.configs = get_migration_configs()
        self.init_ui()

    def init_ui(self):
        # 初始化主布局
        central_widget = QWidget()
        layout_central = QVBoxLayout()
        central_widget.setLayout(layout_central)
        self.setCentralWidget(central_widget)

        # 按钮1：选择目标配置
        self.btn_select_target = QPushButton("选择目标FAA (会将此处FAA的配置文件迁移到本FAA中)")
        self.btn_select_target.clicked.connect(self.select_target_folder)
        layout_central.addWidget(self.btn_select_target)

        # 按钮2：开始迁移配置
        self.btn_start_migration = QPushButton("开始迁移")
        self.btn_start_migration.setEnabled(False)
        self.btn_start_migration.clicked.connect(self.start_migration)
        layout_central.addWidget(self.btn_start_migration)

        # 状态项列表
        self.widgets_checkbox = {}
        self.widgets_label = {}

        group_layouts = {}
        for config in self.configs:
            group_name = config.get("group", "其他")
            if group_name not in group_layouts:
                group_box = QGroupBox(group_name)
                group_layout = QVBoxLayout()
                group_box.setLayout(group_layout)
                layout_central.addWidget(group_box)
                group_layouts[group_name] = group_layout

            layout_liner = QHBoxLayout()
            group_layouts[group_name].addLayout(layout_liner)

            checkbox = QCheckBox(config["name"])
            checkbox.setFixedWidth(200)
            layout_liner.addWidget(checkbox)
            self.widgets_checkbox[config["name"]] = checkbox
            checkbox.setEnabled(False)

            if config["type"] == "folder":
                checkbox.setToolTip(
                    "文件夹迁移\n"
                    "将来源文件夹内容合并到当前 FAA 的同名文件夹。"
                )

            if config["type"] == "folder_replace":
                checkbox.setToolTip(
                    "整目录替换\n"
                    "迁移前会先清空当前 FAA 的目标文件夹，再完整复制来源文件夹。\n"
                    "适用于用户自截、背包删除/使用图片等以用户数据为准的目录。"
                )

            if config["type"] == "folder_uuid_json":
                # 鼠标提示
                checkbox.setToolTip(
                    "UUID 合并迁移\n"
                    "同 UUID 文件不迁移，保留当前 FAA 原文件。\n"
                    "UUID 不同但文件名相同会自动追加括号数字。\n"
                    "缺少 UUID 的文件会生成新 UUID；损坏 JSON 不迁移。"
                )

            label = QLabel("")
            label.setFixedWidth(800)
            layout_liner.addWidget(label)
            self.widgets_label[config["name"]] = label

    def select_target_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择目标文件夹", "")
        if folder_path:
            self.target_path = os.path.normpath(folder_path)
            self.update_labels()

    def update_labels(self):
        """更新所有 需要迁移的文件 的 状态标签"""

        if not self.target_path:
            return

        self.configs = build_migration_plan(
            source_root=self.target_path,
            target_root=PATHS["root"],
            allow_missing_target=False,
        )
        self.btn_start_migration.setEnabled(False)

        for config in self.configs:
            checkbox = self.widgets_checkbox[config["name"]]
            checkbox.setEnabled(False)
            checkbox.setChecked(False)

            self.widgets_label[config["name"]].setText(self.format_config_paths(config))

            # from 找到了 解锁对应ui
            if config.get("available"):
                checkbox.setEnabled(True)
                self.btn_start_migration.setEnabled(True)

    def start_migration(self):

        reply = QMessageBox.question(self, "确认迁移", "确定要开始迁移配置吗？")

        if reply == QMessageBox.StandardButton.Yes:

            # 锁定ui
            for config in self.configs:
                self.widgets_checkbox[config["name"]].setEnabled(False)
            self.btn_start_migration.setEnabled(False)

            # 迁移
            self.perform_migration()

    def perform_migration(self):
        """
        实际完成迁移
        """

        selected_names = {
            config["name"]
            for config in self.configs
            if self.widgets_checkbox[config["name"]].isChecked()
        }
        results = migrate_user_data(
            source_root=self.target_path,
            target_root=PATHS["root"],
            selected_names=selected_names,
            allow_missing_target=False,
        )
        for config in results:
            if config["status"] == "migrated":
                self.widgets_label[config["name"]].setText("迁移成功!")

        QMessageBox.information(
            self,
            "完成迁移全部!",
            "迁移已完成, 请不要保存配置, 直接重启FAA即可正确应用~")

    @staticmethod
    def format_config_paths(config: dict) -> str:
        return "从: {}\n到: {}".format(
            config.get("path_from", "未找到"),
            config.get("path_to", "未找到")
        )
