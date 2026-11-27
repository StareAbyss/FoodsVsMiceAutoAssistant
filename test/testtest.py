import sys
import json
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, pyqtSignal


class CardList(QListWidget):
    def __init__(self, cards):
        super().__init__()
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.load_cards(cards)

    def load_cards(self, cards):
        self.clear()
        for card in sorted(cards, key=lambda x: x["card_id"]):
            item = QListWidgetItem(card["name"])
            item.setData(Qt.ItemDataRole.UserRole, card)
            self.addItem(item)


class EventEditor(QDialog):
    data_updated = pyqtSignal()

    def __init__(self, event, actions, parent=None):
        super().__init__(parent)
        self.event = event
        self.actions = actions
        self.setWindowTitle("事件编辑器")
        self.setMinimumSize(600, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Trigger编辑
        self.trigger_group = QGroupBox("触发器")
        self.init_trigger_ui()
        layout.addWidget(self.trigger_group)

        # Action编辑
        self.action_group = QGroupBox("动作")
        self.init_action_ui()
        layout.addWidget(self.action_group)

        # 按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.save_changes)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.setLayout(layout)

    def init_trigger_ui(self):
        layout = QFormLayout()
        self.trigger_type = QComboBox()
        self.trigger_type.addItems(["wave"])
        layout.addRow("类型:", self.trigger_type)

        # Wave参数
        self.wave_id = QSpinBox()
        self.wave_time = QSpinBox()
        layout.addRow("Wave ID:", self.wave_id)
        layout.addRow("时间:", self.wave_time)

        # 加载数据
        trigger = self.event["event_data"]["trigger"]
        self.trigger_type.setCurrentText(trigger["type"])
        args = trigger["args"]
        self.wave_id.setValue(args.get("wave_id", 0))
        self.wave_time.setValue(args.get("time", 0))

        self.trigger_group.setLayout(layout)

    def init_action_ui(self):
        layout = QVBoxLayout()
        self.action_list = QListWidget()
        self.action_list.itemDoubleClicked.connect(self.edit_action)
        layout.addWidget(self.action_list)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self.add_action)
        remove_btn = QPushButton("删除")
        remove_btn.clicked.connect(self.remove_action)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)

        layout.addLayout(btn_layout)
        self.action_group.setLayout(layout)
        self.load_actions()

    def load_actions(self):
        self.action_list.clear()
        for action in self.event["event_data"]["action_data"]:
            item = QListWidgetItem(f"{action['type']} (ID: {action['actions_id']})")
            item.setData(Qt.ItemDataRole.UserRole, action)
            self.action_list.addItem(item)

    def add_action(self):
        dialog = ActionEditor(self.actions, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_action = dialog.get_action()
            self.event["event_data"]["action_data"].append(new_action)
            self.load_actions()

    def remove_action(self):
        row = self.action_list.currentRow()
        if row >= 0:
            del self.event["event_data"]["action_data"][row]
            self.load_actions()

    def edit_action(self, item):
        row = self.action_list.row(item)
        action = self.event["event_data"]["action_data"][row]
        dialog = ActionEditor(self.actions, self, action)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.event["event_data"]["action_data"][row] = dialog.get_action()
            self.load_actions()

    def save_changes(self):
        # 更新trigger数据
        trigger_type = self.trigger_type.currentText()
        self.event["event_data"]["trigger"] = {
            "type": trigger_type,
            "args": {
                "wave_id": self.wave_id.value(),
                "time": self.wave_time.value()
            }
        }
        self.data_updated.emit()
        self.accept()


class ActionEditor(QDialog):
    def __init__(self, actions, parent=None, action=None):
        super().__init__(parent)
        self.actions = actions
        self.action = action or {"type": "shovel", "actions_id": 0}
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["shovel", "sleep", "execute_card", "place_card"])
        self.type_combo.currentTextChanged.connect(self.update_ids)
        layout.addRow("类型:", self.type_combo)

        self.id_combo = QComboBox()
        layout.addRow("ID:", self.id_combo)

        # 初始化数据
        self.type_combo.setCurrentText(self.action["type"])
        self.update_ids(self.action["type"])
        if self.action:
            self.id_combo.setCurrentText(str(self.action["actions_id"]))

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

        self.setLayout(layout)

    def update_ids(self, action_type):
        self.id_combo.clear()
        if action_type in self.actions:
            ids = [str(a["action_id"]) for a in self.actions[action_type]]
            self.id_combo.addItems(ids)

    def get_action(self):
        return {
            "type": self.type_combo.currentText(),
            "actions_id": int(self.id_combo.currentText())
        }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data = {
            "cards": [],
            "events": [],
            "actions": {}
        }
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("JSON编辑器")
        self.setGeometry(100, 100, 800, 600)

        main_widget = QWidget()
        layout = QVBoxLayout()

        # 卡片列表
        self.card_list = CardList(self.data["cards"])
        layout.addWidget(self.card_list)

        # 事件列表
        self.event_list = QListWidget()
        self.event_list.itemDoubleClicked.connect(self.open_event_editor)
        layout.addWidget(self.event_list)

        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

    def load_data(self, data):
        self.data = data
        self.card_list.load_cards(data["cards"])
        self.load_events()

    def load_events(self):
        self.event_list.clear()
        for event in sorted(self.data["events"], key=lambda x: x["event_id"]):
            item = QListWidgetItem(f"事件 {event['event_id']}")
            item.setData(Qt.ItemDataRole.UserRole, event)
            self.event_list.addItem(item)

    def open_event_editor(self, item):
        event = item.data(Qt.ItemDataRole.UserRole)
        editor = EventEditor(event, self.data["actions"], self)
        editor.data_updated.connect(self.load_events)
        editor.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 示例数据
    sample_data = {
        "player_positions": [],
        "meta_data": {
            "uuid": "",
            "tips": ""
        },
        "cards": [
            {"card_id": 1, "name": "花火龙"},
            {"card_id": 2, "name": "海星"},
            {"card_id": 3, "name": "冰桶炸弹"}
        ],
        "actions": {
            "place_card": [{"action_id": 0}, {"action_id": 1}],
            "execute_card": [{"action_id": 0}],
            "sleep": [{"action_id": 0}],
            "shovel": [{"action_id": 0}]
        },
        "events": [
            {
                "event_id": 0,
                "event_data": {
                    "trigger": {
                        "type": "wave",
                        "args": {"wave_id": 0, "time": 0}
                    },
                    "action_data": [
                        {"type": "shovel", "actions_id": 0},
                        {"type": "sleep", "actions_id": 0}
                    ]
                }
            }
        ]
    }

    window = MainWindow()
    window.load_data(sample_data)
    window.show()
    sys.exit(app.exec())
