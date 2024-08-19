import json
import sys

from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QPushButton, QComboBox, QHBoxLayout, QLabel, QLineEdit, \
    QSpinBox, QCheckBox, QWidget, QListWidgetItem, QFileDialog, QMessageBox, QApplication, QListWidget


class TaskSequenceEditor(QMainWindow):
    def __init__(self):
        """
        初始化，完成界面布局，绑定信号与槽，初始化变量
        """
        super().__init__()
        self.TaskSequenceList = QListWidget()
        self.task_sequence_list = []

        # 常量
        self.player_list = ['1P', '2P', '1P + 2P', '2P + 1P']

        # 布局
        self.LayMain = QVBoxLayout()

        # 加载按钮
        self.ButtonLoadJson = QPushButton('加载任务序列')
        self.LayMain.addWidget(self.ButtonLoadJson)
        self.ButtonLoadJson.clicked.connect(self.load_json)

        # 列表
        self.LayMain.addWidget(self.TaskSequenceList)

        # 添加任务按钮
        self.ButtonAddTask = QPushButton('添加任务')
        self.ComboBoxTask = QComboBox()
        self.AddTaskLayout = QHBoxLayout()
        self.AddTaskLayout.addWidget(self.ButtonAddTask)
        self.AddTaskLayout.addWidget(self.ComboBoxTask)
        self.LayMain.addLayout(self.AddTaskLayout)
        self.ButtonAddTask.clicked.connect(self.add_task)

        # 保存按钮
        self.ButtonSaveJson = QPushButton('保存任务序列')
        self.LayMain.addWidget(self.ButtonSaveJson)
        self.ButtonSaveJson.clicked.connect(self.save_json)

        # 初始化控件
        self.init_combo_box()

        # 显示布局
        self.centralWidget = QWidget()
        self.centralWidget.setLayout(self.LayMain)
        self.setCentralWidget(self.centralWidget)

    def init_combo_box(self):
        """
        初始化任务选择下拉框
        """
        self.ComboBoxTask.addItem('战斗')
        self.ComboBoxTask.addItem('刷新')
        self.ComboBoxTask.addItem('清背包')

    def add_task(self):
        """
        添加任务
        """
        task_type = self.ComboBoxTask.currentText()
        task_id = len(self.task_sequence_list) + 1
        if task_type == '战斗':
            task = {
                "task_type": "战斗",
                "deck": 1,
                "max_times": 1,
                "battle_plan_1p": "00000000-0000-0000-0000-000000000000",
                "battle_plan_2p": "00000000-0000-0000-0000-000000000001",
                "dict_exit": {
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": [
                        "回到上一级",
                        "美食大赛领取"
                    ],
                    "last_time_player_b": [
                        "回到上一级",
                        "美食大赛领取"
                    ]
                },
                "stage_id": "",
                "battle_id": 1,
                "quest_card": "None",
                "need_key": True,
                "player": [
                    1
                ],
                "ban_card_list": []
            }
        else:
            task = {}
        self.task_sequence_list.append(task)
        # 生成控件行
        line_widget = self.line_manager(task, task_id)
        # 创建一个 QListWidgetItem，并将 line_widget 设置为其附加的 widget
        item = QListWidgetItem()

        # 设置 QListWidgetItem 的高度
        item.setSizeHint(line_widget.sizeHint())

        self.TaskSequenceList.addItem(item)
        self.TaskSequenceList.setItemWidget(item, line_widget)

    def line_manager(self, task: dict, task_id: int):
        """
        根据任务生成控件，单独管理列表中每一行的布局
        每一行布局分为三个部分：task id; task type; task info
        """
        line_widget = QWidget()
        line_layout = QHBoxLayout(line_widget)
        task_id_label = QLabel(str(task_id))
        task_type_label = QLabel(task['task_type'])

        line_layout.addWidget(task_id_label)
        line_layout.addWidget(task_type_label)

        task_type = task['task_type']
        if task_type == '战斗':  # 战斗任务
            # 所选关卡
            stage_input = QLineEdit()
            # 战斗次数
            battle_times_input = QSpinBox()
            battle_times_input.setMinimum(1)
            # 是否使用钥匙
            key_check_box = QCheckBox()
            # 战斗Player
            player_input = QComboBox()
            for player in self.player_list:
                player_input.addItem(player)
            # 战斗卡组
            deck_input = QSpinBox()
            deck_input.setMinimum(1)
            deck_input.setMaximum(6)
            # 战斗方案 目前是占位符
            battle_plan_input_1 = QLineEdit()
            battle_plan_input_2 = QLineEdit()

            # 添加到布局中
            line_layout.addWidget(stage_input)
            line_layout.addWidget(battle_times_input)
            line_layout.addWidget(key_check_box)
            line_layout.addWidget(player_input)
            line_layout.addWidget(deck_input)
            line_layout.addWidget(battle_plan_input_1)
            line_layout.addWidget(battle_plan_input_2)
        elif task_type == '刷新':
            pass
        elif task_type == '清背包':
            pass
        # 添加完成后，在布局的最后添加一个删除按钮
        delete_button = QPushButton('删除')
        delete_button.clicked.connect(lambda: self.delete_task(task_id))
        line_layout.addWidget(delete_button)
        return line_widget

    def load_json(self):
        """
        Load a JSON file and parse it into the task sequence list
        """
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Load Task Sequence JSON File", "", "JSON Files (*.json)",
                                                   options=options)
        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as file:
                    self.task_sequence_list = json.load(file)
                    # Here you can add code to display the content of task_sequence_list in the UI list
                    QMessageBox.information(self, "Success", "Task sequence loaded successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not load JSON file: {str(e)}")

    def save_json(self):
        """
        Save the task sequence list as a JSON file.
        """
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Task Sequence as JSON File", "", "JSON Files (*.json)",
                                                   options=options)
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as file:
                    json.dump(self.task_sequence_list, file, ensure_ascii=False, indent=4)
                    QMessageBox.information(self, "Success", "Task sequence saved successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save JSON file: {str(e)}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TaskSequenceEditor()
    window.show()
    sys.exit(app.exec_())
