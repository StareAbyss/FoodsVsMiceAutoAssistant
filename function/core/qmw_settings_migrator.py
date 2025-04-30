import json
import os.path
import shutil

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QMessageBox, \
    QFileDialog, QHBoxLayout, QCheckBox

from function.globals.get_paths import PATHS


class QMWSettingsMigrator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("配置迁移工具 - 请注意查看鼠标提示信息!")
        self.setWindowIcon(QIcon(PATHS["logo"] + "\\圆角-FetDeathWing-450x.png"))

        # 设定窗口初始大小 否则将无法自动对齐到上级窗口中心
        self.resize(1025, 435)

        # 需要迁移的配置项 的 名称, 和可能存在的位置.
        self.configs = [
            {
                "name": "配置文件 - 核心",
                "type": "file",
                "locations": [
                    os.path.join("config", "settings.json"),
                    os.path.join("config", "opt_main.json"),
                ],
            },
            {
                "name": "配置文件 - 关卡全局方案",
                "type": "file",
                "locations": [
                    os.path.join("config", "stage_plan.json"),
                ],
            },
            {
                "name": "用户自截 - 空间服登录界面_1P",
                "type": "file",
                "locations": [
                    os.path.join("config", "cus_images", "用户自截", "空间服登录界面_1P.png"),
                    os.path.join("resource", "image", "common", "用户自截", "空间服登录界面_1P.png"),
                ],
            },
            {
                "name": "用户自截 - 空间服登录界面_2P",
                "type": "file",
                "locations": [
                    os.path.join("config", "cus_images", "用户自截", "空间服登录界面_2P.png"),
                    os.path.join("resource", "image", "common", "用户自截", "空间服登录界面_2P.png"),
                ],
            },
            {
                "name": "用户自截 - 跨服远征_1P",
                "type": "file",
                "locations": [
                    os.path.join("config", "cus_images", "用户自截", "跨服远征_1p.png"),
                    os.path.join("config", "cus_images", "用户自截", "跨服远征_1P.png"),
                    os.path.join("resource", "image", "common", "用户自截", "跨服远征_1p.png"),
                    os.path.join("resource", "image", "common", "用户自截", "跨服远征_1P.png")
                ],
            },
            {
                "name": "战斗方案",
                "type": "folder_battle_plan",
                "locations": [
                    os.path.join("battle_plan"),
                ],
            },
            {
                "name": "战斗方案 - 未激活",
                "type": "folder_battle_plan",
                "locations": [
                    os.path.join("battle_plan_not_active"),
                ],
            },
            {
                "name": "公会管理器数据",
                "type": "folder",
                "locations": [
                    os.path.join("logs", "guild_manager"),
                ],
            },
            {
                "name": "自定义任务序列",
                "type": "folder_json_only",
                "locations": [
                    os.path.join("task_sequence"),
                ],
            },
        ]
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

        for config in self.configs:

            # from path
            for location in config["locations"]:
                path = os.path.join(self.target_path, location)
                if os.path.exists(path):
                    config["path_from"] = path
                    break

            # to path
            for location in config["locations"]:
                path = os.path.join(PATHS["root"], location)
                if os.path.exists(path):
                    config["path_to"] = path
                    break

            self.widgets_label[config["name"]].setText(
                "从: {}\n到: {}".format(
                    config.get("path_from", "未找到"),
                    config.get("path_to", "未找到")
                )
            )

            # from 找到了 解锁对应ui
            if config.get("path_from") and config.get("path_to"):
                self.widgets_checkbox[config["name"]].setEnabled(True)
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

        def process_json_files(folder_from, folder_to):
            """
            处理两个文件夹中的 .json 文件，并根据 uuid 进行分类和迁移。

            :param folder_from: 文件夹 A 的路径
            :param folder_to: 文件夹 B 的路径
            """

            # 这些uuid值 总是不迁移
            default_uuids = [
                "00000000-0000-0000-0000-000000000000",
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002"
            ]

            # 查找所有 .json 文件
            files_a = [f for f in os.listdir(folder_from) if f.endswith('.json')]
            files_b = [f for f in os.listdir(folder_to) if f.endswith('.json')]

            # 读取所有文件并记录 uuid 值
            uuids_a = {}
            for file in files_a:
                file_path = os.path.join(folder_from, file)
                with open(file_path, mode='r', encoding='utf-8') as f:
                    data = json.load(f)

                uuid = data.get('uuid', None)
                if not uuid:
                    uuid = data.get('meta_data', {}).get('uuid', None)
                if not uuid:
                    continue
                if uuid in default_uuids:
                    continue

                uuids_a[uuid] = file

            uuids_b = {}
            for file in files_b:
                file_path = os.path.join(folder_to, file)
                with open(file_path, mode='r', encoding='utf-8') as f:
                    data = json.load(f)

                uuid = data.get('uuid', None)
                if not uuid:
                    uuid = data.get('meta_data', {}).get('uuid', None)
                if not uuid:
                    continue
                if uuid in default_uuids:
                    continue

                uuids_b[uuid] = file

            # 分类 uuid 值
            common_uuids = set(uuids_a.keys()) & set(uuids_b.keys())  # 共有的uuid
            unique_uuids_a = set(uuids_a.keys()) - set(uuids_b.keys())  # 仅A中有的uuid

            # 处理文件
            for uuid in common_uuids:
                file_a = uuids_a[uuid]
                file_b = uuids_b[uuid]
                file_path_a = os.path.join(folder_from, file_a)
                file_path_b = os.path.join(folder_to, file_b)

                # 读取文件 A 的内容
                with open(file_path_a, mode='r', encoding='utf-8') as f:
                    data_a = json.load(f)

                # 写入文件 B
                with open(file_path_b, mode='w', encoding='utf-8') as f:
                    json.dump(data_a, f, ensure_ascii=False, indent=4)

            for uuid in unique_uuids_a:
                file_a = uuids_a[uuid]
                file_path_a = os.path.join(folder_from, file_a)
                file_path_b = os.path.join(folder_to, file_a)

                # 复制文件 A 到文件 B
                shutil.copy(file_path_a, file_path_b)

        def one_config_migration(config):

            path_from = config.get("path_from")
            path_to = config.get("path_to")

            if not path_from:
                return
            if not path_to:
                return
            if not self.widgets_checkbox[config["name"]].isChecked():
                return

            if config["type"] == "file":
                shutil.copyfile(path_from, path_to)

            if config["type"] == "folder":
                shutil.copytree(path_from, path_to, dirs_exist_ok=True)

            if config["type"] == "folder_json_only":
                def ignore_non_json_files(dir, files):
                    """忽略非 .json 文件"""
                    return [f for f in files if not f.endswith('.json')]

                shutil.copytree(path_from, path_to, dirs_exist_ok=True, ignore=ignore_non_json_files)

            if config["type"] == "folder_battle_plan":
                process_json_files(folder_from=path_from, folder_to=path_to)

            self.widgets_label[config["name"]].setText(f"迁移成功!")

        # 迁移逻辑
        for config in self.configs:
            one_config_migration(config)

        QMessageBox.information(
            self,
            "完成迁移全部!",
            "迁移已完成, 请不要保存配置, 直接重启FAA即可正确应用~")
