import os
import os.path

from function.globals.loadings import loading

loading.update_progress(65,"正在加载FAA迁移工具...")
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QMessageBox, \
    QFileDialog, QHBoxLayout, QCheckBox

from function.globals.get_paths import PATHS
from function.core.settings_migration import build_migration_plan, get_migration_configs, migrate_user_data


class QMWSettingsMigrator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("配置迁移工具 - 请注意查看鼠标提示信息!")
        self.setWindowIcon(QIcon(os.path.join(PATHS["logo"], '圆角-FetDeathWing-450x.png')))

        # 设定窗口初始大小 否则将无法自动对齐到上级窗口中心
        self.resize(1025, 435)

        self.configs = get_migration_configs()
        self.init_ui()

    def init_ui(self):
        # 初始化主布局
        central_widget = QWidget()
        layout_central = QVBoxLayout()
        central_widget.setLayout(layout_central)
        self.setCentralWidget(central_widget)

        # 按钮1：选择目标配置
        self.btn_select_target = QPushButton("选择目标配置")
        self.btn_select_target.clicked.connect(self.select_target_folder)
        layout_central.addWidget(self.btn_select_target)

        # 按钮2：开始迁移配置
        self.btn_start_migration = QPushButton("开始迁移配置")
        self.btn_start_migration.setEnabled(False)
        self.btn_start_migration.clicked.connect(self.start_migration)
        layout_central.addWidget(self.btn_start_migration)

        # 状态项列表
        self.widgets_checkbox = {}
        self.widgets_label = {}

        for config in self.configs:
            layout_liner = QHBoxLayout()
            layout_central.addLayout(layout_liner)

            checkbox = QCheckBox(config["name"])
            checkbox.setFixedWidth(200)
            layout_liner.addWidget(checkbox)
            self.widgets_checkbox[config["name"]] = checkbox
            checkbox.setEnabled(False)

            if config["type"] == "folder":
                checkbox.setToolTip(
                    "文件夹迁移\n"
                    "将会**覆盖**当前配置中的同名文件夹!"
                )

            if config["type"] == "folder_json_only":
                checkbox.setToolTip(
                    "文件夹迁移\n"
                    "仅迁移.json文件\n"
                    "将**覆盖**当前配置中的同名文件夹!\n"
                    "如需保留FAA更新的内置方案不被旧方案取代, 请手动复制粘贴迁移,并重启FAA"
                )

            if config["type"] == "folder_battle_plan":
                # 鼠标提示
                checkbox.setToolTip(
                    "战斗方案迁移 会直接覆盖同uuid的所有方案!\n"
                    "如果方案没有uuid, 则不会被复制!"
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

            self.widgets_label[config["name"]].setText(
                "从: {}\n到: {}".format(
                    config.get("path_from", "未找到"),
                    config.get("path_to", "未找到")
                )
            )

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
