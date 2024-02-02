import json
import sys

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGridLayout, QPushButton, QWidget, QFileDialog, QVBoxLayout, QLabel, QComboBox,
    QLineEdit, QHBoxLayout, QTextEdit)


class JsonEditor(QMainWindow):
    def __init__(self):
        super().__init__()

        self.chessboard_buttons = None
        self.chessboard_layout = None
        self.card_dropdown = None
        self.tips_editor = None
        self.queue_input = None
        self.id_input = None
        self.name_input = None
        self.ergodic_input = None
        self.player_position_input = None

        self.json_data = {
            "tips": "",
            "player": [],
            "card": []
        }
        self.selected_card_id = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('战斗方案编辑器')

        # 主布局
        main_layout = QVBoxLayout()

        # 加载 JSON 按钮
        load_json_button = QPushButton('加载战斗方案')
        load_json_button.clicked.connect(self.load_json)
        main_layout.addWidget(load_json_button)

        # 玩家位置编辑器
        player_editor_layout = QHBoxLayout()
        self.player_position_input = QComboBox()
        # 生成棋盘上所有可能的位置
        for i in range(9):
            for j in range(7):
                self.player_position_input.addItem(f"{i + 1}-{j + 1}")
        set_player_position_button = QPushButton('设置玩家位置')
        set_player_position_button.clicked.connect(self.set_player_position)
        player_editor_layout.addWidget(QLabel('玩家位置:'))
        player_editor_layout.addWidget(self.player_position_input)
        player_editor_layout.addWidget(set_player_position_button)
        main_layout.addLayout(player_editor_layout)

        # 卡片编辑器
        card_editor_layout = QHBoxLayout()
        self.id_input = QLineEdit()
        self.name_input = QLineEdit()
        self.ergodic_input = QComboBox()
        self.ergodic_input.addItems(['true', 'false'])
        self.queue_input = QComboBox()
        self.queue_input.addItems(['true', 'false'])
        add_card_button = QPushButton('添加/更新 卡片')
        add_card_button.clicked.connect(self.add_update_card)
        delete_card_button = QPushButton('删除 卡片')
        delete_card_button.clicked.connect(self.delete_card)
        card_editor_layout.addWidget(QLabel('ID:'))
        card_editor_layout.addWidget(self.id_input)
        card_editor_layout.addWidget(QLabel('名称:'))
        card_editor_layout.addWidget(self.name_input)
        card_editor_layout.addWidget(QLabel('遍历:'))
        card_editor_layout.addWidget(self.ergodic_input)
        card_editor_layout.addWidget(QLabel('队列:'))
        card_editor_layout.addWidget(self.queue_input)
        card_editor_layout.addWidget(add_card_button)
        card_editor_layout.addWidget(delete_card_button)
        main_layout.addLayout(card_editor_layout)

        # 提示编辑器
        self.tips_editor = QTextEdit()
        self.tips_editor.setPlaceholderText('在这里编辑提示...')
        main_layout.addWidget(QLabel('提示:'))
        main_layout.addWidget(self.tips_editor)

        # 卡片下拉菜单
        self.card_dropdown = QComboBox()
        self.card_dropdown.currentIndexChanged.connect(self.on_card_selected)
        main_layout.addWidget(self.card_dropdown)

        # 棋盘布局
        self.chessboard_layout = QGridLayout()
        self.chessboard_buttons = []
        for i in range(7):
            row = []
            for j in range(9):
                btn = QPushButton('')
                btn.setFixedSize(100, 100)
                btn.clicked.connect(lambda checked, x=i, y=j: self.place_card(y, x))
                self.chessboard_layout.addWidget(btn, i, j)
                row.append(btn)
            self.chessboard_buttons.append(row)
        main_layout.addLayout(self.chessboard_layout)

        # 保存按钮
        save_button = QPushButton('保存战斗方案')
        save_button.clicked.connect(self.save_json)
        main_layout.addWidget(save_button)

        # 设置主控件
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def on_card_selected(self, index):
        if index >= 0:
            card = self.json_data['card'][index]
            self.selected_card_id = card['id']
            self.id_input.setText(str(card['id']))
            self.name_input.setText(card['name'])
            self.ergodic_input.setCurrentText(str(card['ergodic']).lower())
            self.queue_input.setCurrentText(str(card['queue']).lower())

    def add_update_card(self):
        id_ = int(self.id_input.text())
        name_ = self.name_input.text()
        ergodic_ = self.ergodic_input.currentText() == 'true'
        queue_ = self.queue_input.currentText() == 'true'
        existing_ids = [card['id'] for card in self.json_data['card']]
        if id_ in existing_ids:
            for card in self.json_data['card']:
                if card['id'] == id_:
                    card['name'] = name_
                    card['ergodic'] = ergodic_
                    card['queue'] = queue_
        else:
            self.json_data['card'].append({
                "id": id_,
                "name": name_,
                "ergodic": ergodic_,
                "queue": queue_,
                "location": []
            })
        self.refresh_card_dropdown()

    def delete_card(self):
        id_ = int(self.id_input.text())
        self.json_data['card'] = [card for card in self.json_data['card'] if card['id'] != id_]
        self.refresh_card_dropdown()

    def place_card(self, x, y):
        if self.selected_card_id is not None:
            card = next((card for card in self.json_data['card'] if card['id'] == self.selected_card_id), None)
            if card:
                location_key = f"{x + 1}-{y + 1}"
                # 如果这个位置已经有了这张卡片，那么移除它；否则添加它
                if location_key in card['location']:
                    card['location'].remove(location_key)
                else:
                    card['location'].append(location_key)
                self.refresh_chessboard()

    def set_player_position(self):
        # 获取玩家的新位置
        new_position = self.player_position_input.currentText()
        # 更新玩家位置
        self.json_data['player'] += [new_position]
        # 刷新棋盘以显示新的玩家位置
        self.refresh_chessboard()

    def save_json(self):
        self.json_data['tips'] = self.tips_editor.toPlainText()
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "保存 JSON 文件", "", "JSON Files (*.json)", options=options)
        if file_name:
            with open(file_name, 'w', encoding='utf-8') as file:
                # 确保玩家位置也被保存
                self.json_data['player'] = self.json_data.get('player', [])
                json.dump(self.json_data, file, ensure_ascii=False, indent=4)

    def load_json(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "打开 JSON 文件", "", "JSON Files (*.json)", options=options)
        if file_name:
            with open(file_name, 'r', encoding='utf-8') as file:
                self.json_data = json.load(file)
                self.tips_editor.setPlainText(self.json_data.get('tips', ''))
                self.refresh_card_dropdown()
                self.refresh_chessboard()
                self.refresh_card_dropdown()
                self.refresh_chessboard()
                # 如果有玩家位置，更新玩家位置选择器
                if self.json_data.get('player'):
                    self.player_position_input.setCurrentText(self.json_data['player'][0])

    def refresh_card_dropdown(self):
        self.card_dropdown.clear()
        for card in self.json_data['card']:
            self.card_dropdown.addItem(f"{card['id']} - {card['name']}", card['id'])
        # 设置默认选项
        self.card_dropdown.setCurrentIndex(-1)
        self.id_input.clear()
        self.name_input.clear()
        self.ergodic_input.setCurrentIndex(0)
        self.queue_input.setCurrentIndex(0)

    def refresh_chessboard(self):
        for i, row in enumerate(self.chessboard_buttons):
            for j, btn in enumerate(row):
                btn.setText('')
                location_key = f"{j + 1}-{i + 1}"
                cards_in_this_location = [card for card in self.json_data['card'] if location_key in card['location']]
                btn_text = '\n'.join(card['name'] for card in cards_in_this_location)
                btn.setText(btn_text)
                # 如果玩家在这个位置，添加 "玩家" 文字
                if location_key in self.json_data.get('player', []):
                    btn.setText(btn.text() + '\n玩家')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = JsonEditor()
    ex.show()
    sys.exit(app.exec_())
