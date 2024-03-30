import json
import sys

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGridLayout, QPushButton, QWidget, QFileDialog, QVBoxLayout, QLabel, QComboBox,
    QLineEdit, QHBoxLayout, QTextEdit, QListWidget, QMessageBox)

double_click_card_list = pyqtSignal(object)

"""
战斗方案编辑器
致谢：八重垣天知
"""


class QListWidgetDraggable(QListWidget):

    def __init__(self, drop_function):
        super(QListWidgetDraggable, self).__init__()

        # 定义数据变化函数
        self.drop_function = drop_function

        # 允许内部拖拽
        self.setDragDropMode(self.InternalMove)

    def dropEvent(self, e):
        print("拖拽事件触发")
        index_from = self.currentRow()
        super(QListWidgetDraggable, self).dropEvent(e)  # 如果不调用父类的构造方法，拖拽操作将无法正常进行
        index_to = self.currentRow()

        source_Widget = e.source()  # 获取拖入item的父组件
        items = source_Widget.selectedItems()  # 获取所有的拖入item
        item = items[0]  # 不允许多选 所以只有一个

        print("text:{} from {} to {} memory:{}".format(item.text(), index_from, index_to, self.currentRow()))

        # 执行更改函数
        self.drop_function(index_from=index_from, index_to=index_to)

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        print("鼠标点击事件触发")
        current_row = self.currentRow()
        if current_row == 0:
            # 禁止拖拽
            self.setDragDropMode(self.NoDragDrop)
        else:
            # 允许内部拖拽
            self.setDragDropMode(self.InternalMove)


class JsonEditor(QMainWindow):

    def __init__(self):
        super().__init__()

        """内部数据表"""
        # 数据dict
        self.json_data = {
            "tips": "",
            "player": [],
            "card": []
        }

        # 当前被选中正在编辑的项目的index
        self.current_edit_index = None

        """布局和控件放置"""

        # 主布局
        self.LayMain = QVBoxLayout()

        # 加载 JSON 按钮
        self.ButtonLoadJson = QPushButton('加载战斗方案')
        self.LayMain.addWidget(self.ButtonLoadJson)

        # 玩家位置编辑器
        self.LayPlayerEditor = QHBoxLayout()
        self.WeiPlayerPositionInput = QComboBox()

        # 生成棋盘上所有可能的位置 Item名称"x-y"
        for i in range(9):
            for j in range(7):
                self.WeiPlayerPositionInput.addItem(f"{i + 1}-{j + 1}")

        """提示编辑器"""
        self.LayMain.addWidget(QLabel('方案信息:'))

        self.WeiTipsEditor = QTextEdit()
        self.WeiTipsEditor.setPlaceholderText('在这里编辑提示文本...')
        self.LayMain.addWidget(self.WeiTipsEditor)
        """操作教学文本"""
        self.LayPrint = QHBoxLayout()
        self.LayMain.addLayout(self.LayPrint)

        self.LayPrint.addWidget(QLabel('正在编辑对象:'))

        self.WeiCurrentEdit = QLabel("无")
        self.LayPrint.addWidget(self.WeiCurrentEdit)

        self.LayPrint.addWidget(QLabel(
            '双击左侧列表, 选中对象进行编辑 | 点击格子添加到该位置, 再点一下取消位置 | 列表从上到下 是一轮放卡的优先级(人物除外)'))
        """卡片编辑器"""
        self.LayCardEditor = QHBoxLayout()
        self.LayMain.addLayout(self.LayCardEditor)

        self.LayCardEditor.addWidget(QLabel('ID:'))

        self.WeiIdInput = QLineEdit()
        self.LayCardEditor.addWidget(self.WeiIdInput)
        self.WeiIdInput.setToolTip("id代表卡在卡组中的顺序")

        self.LayCardEditor.addWidget(QLabel('名称:'))

        self.WeiNameInput = QLineEdit()
        self.LayCardEditor.addWidget(self.WeiNameInput)
        self.WeiNameInput.setToolTip("名称仅用来标识和Ban卡(美食大赛用) 一般可以乱填")

        self.LayCardEditor.addWidget(QLabel('遍历:'))

        self.WeiErgodicInput = QComboBox()
        self.WeiErgodicInput.addItems(['true', 'false'])
        self.LayCardEditor.addWidget(self.WeiErgodicInput)
        self.WeiErgodicInput.setToolTip("队列和遍历不知道是什么可以全true, 具体请参见详细文档")

        self.LayCardEditor.addWidget(QLabel('队列:'))

        self.QueueInput = QComboBox()
        self.QueueInput.addItems(['true', 'false'])
        self.LayCardEditor.addWidget(self.QueueInput)
        self.QueueInput.setToolTip("队列和遍历不知道是什么可以全true, 具体请参见详细文档")

        self.WeiAddCardButton = QPushButton('添加 一张卡片')
        self.LayCardEditor.addWidget(self.WeiAddCardButton)

        self.WeiUpdateCardButton = QPushButton('更新 选中卡片')
        self.LayCardEditor.addWidget(self.WeiUpdateCardButton)

        self.WeiDeleteCardButton = QPushButton('删除 选中卡片')
        self.LayCardEditor.addWidget(self.WeiDeleteCardButton)

        """card列表+棋盘 横向布局"""
        self.LayCardListAndCell = QHBoxLayout()
        self.LayMain.addLayout(self.LayCardListAndCell)

        """卡片列表"""
        self.WeiCardList = QListWidgetDraggable(drop_function=self.card_list_be_dropped)
        self.LayCardListAndCell.addWidget(self.WeiCardList)

        """棋盘布局"""
        self.chessboard_layout = QGridLayout()
        self.LayCardListAndCell.addLayout(self.chessboard_layout)
        # 生成棋盘布局中的元素
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

        """保存按钮"""
        self.save_button = QPushButton('保存战斗方案')
        self.LayMain.addWidget(self.save_button)

        """设置主控件"""
        self.central_widget = QWidget()
        self.central_widget.setLayout(self.LayMain)
        self.setCentralWidget(self.central_widget)

        """信号和槽函数链接"""
        # 读取josn
        self.ButtonLoadJson.clicked.connect(self.load_json)

        # 保存json
        self.save_button.clicked.connect(self.save_json)

        # 添加卡片
        self.WeiAddCardButton.clicked.connect(self.add_card)

        # 更新卡片
        self.WeiUpdateCardButton.clicked.connect(self.update_card)

        # 删除卡片
        self.WeiDeleteCardButton.clicked.connect(self.delete_card)
        # 双击列表更改当前card
        self.WeiCardList.itemDoubleClicked.connect(self.current_card_change)

        """外观"""
        self.UICss()

        """先刷新一下数据"""
        self.load_data_to_ui_list()

    def highlight_chessboard(self, card_locations):
        """根据卡片的位置list，将对应元素的按钮进行高亮"""
        # 清除所有按钮的高亮
        for row in self.chessboard_buttons:
            for btn in row:
                btn.setStyleSheet("")

        # 高亮显示选中卡片的位置
        for location in card_locations:
            x, y = map(int, location.split('-'))
            self.chessboard_buttons[y - 1][x - 1].setStyleSheet("background-color: orange;")

    def UICss(self):
        # 窗口名
        self.setWindowTitle('战斗方案编辑器')

    def current_card_change(self, item):
        """被双击后, 被选中的卡片改变了"""
        index = self.WeiCardList.indexFromItem(item).row()  # list的index 是 QModelIndex 此处还需要获取到行号

        self.current_edit_index = index

        if index == 0:
            # 玩家 直接清空它们
            self.WeiCurrentEdit.setText("玩家")
            self.WeiIdInput.clear()
            self.WeiNameInput.clear()
            self.WeiNameInput.setText("玩家")
            self.WeiErgodicInput.setCurrentIndex(0)
            self.QueueInput.setCurrentIndex(0)
            self.highlight_chessboard(self.json_data["player"])
        else:
            # 卡片
            index = index - 1  # 可能需要深拷贝？也许是被保护的特性 不需要
            card = self.json_data["card"][index]
            self.WeiCurrentEdit.setText("索引-{} 名称-{}".format(index, card["name"]))
            self.WeiIdInput.setText(str(card['id']))
            self.WeiNameInput.setText(card['name'])
            self.WeiErgodicInput.setCurrentText(str(card['ergodic']).lower())
            self.QueueInput.setCurrentText(str(card['queue']).lower())
            # 设置高亮
            self.highlight_chessboard(card["location"])

    def load_data_to_ui_list(self):
        """从 [内部数据表] 载入数据到 [ui的list]"""
        self.WeiCardList.clear()
        my_list = ["玩家"]
        for card in self.json_data["card"]:
            my_list.append(
                "遍历:{} 队列:{} ID:{} 名称:{} ".format(
                    "√" if card["ergodic"] else "X",
                    "√" if card["queue"] else "X",
                    card["id"],
                    card["name"]
                )
            )
        self.WeiCardList.addItems(my_list)
        self.current_edit_index = None  # 正在编辑者选为None
        self.WeiCurrentEdit.setText("无")
        print(my_list)

    def card_list_be_dropped(self, index_from, index_to):
        """在list的drop事件中调用, 用于更新内部数据表"""
        cards = self.json_data["card"]
        if index_to != 0:
            change_card = cards.pop(index_from - 1)
            print(change_card)
            cards.insert(index_to - 1, change_card)
            print("正常操作 内部数据表已更新: {}".format(cards))
        else:
            # 试图移动到第一个
            self.WeiCardList.clear()
            self.load_data_to_ui_list()

    def add_card(self):
        id_ = self.WeiIdInput.text()
        name_ = self.WeiNameInput.text()

        if not id_.isdigit():
            QMessageBox.information(self, "操作错误！", "卡片id必须是正整数!")
            return False
        if id_ == "" or name_ == "":
            QMessageBox.information(self, "操作错误！", "卡片id和名称必须填写不得为空!")
            return False
        self.json_data["card"].append(
            {
                "id": int(id_),
                "name": name_,
                "ergodic": bool(self.WeiErgodicInput.currentText() == 'true'),  # 转化bool
                "queue": bool(self.QueueInput.currentText() == 'true'),  # 转化bool
                "location": []
            }
        )

        self.load_data_to_ui_list()
        self.refresh_chessboard()

    def update_card(self):
        index = self.current_edit_index
        if not index:
            QMessageBox.information(self, "操作错误！", "请先选择一个对象(卡片)!")
            return False

        if index == 0:
            QMessageBox.information(self, "操作错误！", "该对象(玩家)不能编辑信息, 只能设置位置!")
            return False

        index -= 1
        self.json_data["card"][index]["id"] = int(self.WeiIdInput.text())
        self.json_data["card"][index]["name"] = self.WeiNameInput.text()
        self.json_data["card"][index]["ergodic"] = bool(self.WeiErgodicInput.currentText() == 'true')  # 转化bool
        self.json_data["card"][index]["queue"] = bool(self.QueueInput.currentText() == 'true')  # 转化bool
        self.load_data_to_ui_list()
        self.refresh_chessboard()

    def delete_card(self):
        index = self.current_edit_index
        if not index:
            QMessageBox.information(self, "操作错误！", "请先选择一个对象(卡片)!")
            return False

        if index == 0:
            QMessageBox.information(self, "操作错误！", "该对象(玩家)不能编辑信息, 只能设置位置!")
            return False

        index -= 1
        del self.json_data["card"][index]
        self.load_data_to_ui_list()
        self.refresh_chessboard()

    def place_card(self, x, y):
        if self.current_edit_index is not None:
            # 初始化 并非没有选择任何东西
            location_key = f"{x + 1}-{y + 1}"

            if self.current_edit_index == 0:
                # 当前index为玩家
                target = self.json_data["player"]
                # 如果这个位置已经有了玩家，那么移除它；否则添加它
                if location_key in target:
                    target.remove(location_key)
                else:
                    target.append(location_key)
                self.refresh_chessboard()
            else:
                # 当前index为卡片
                target = self.json_data["card"][self.current_edit_index - 1]

                # 如果这个位置已经有了这张卡片，那么移除它；否则添加它
                if location_key in target['location']:
                    target['location'].remove(location_key)
                else:
                    target['location'].append(location_key)
                self.refresh_chessboard()

    def save_json(self):
        self.json_data['tips'] = self.WeiTipsEditor.toPlainText()
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "保存 JSON 文件", "", "JSON Files (*.json)", options=options)
        if file_name:
            with open(file_name, 'w', encoding='utf-8') as file:
                # 确保玩家位置也被保存
                self.json_data['player'] = self.json_data.get('player', [])
                json.dump(self.json_data, file, ensure_ascii=False, indent=4)

    def load_json(self):
        """打开窗口 读取josn文件"""
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "打开 JSON 文件", "", "JSON Files (*.json)", options=options)
        if file_name:
            with open(file_name, 'r', encoding='utf-8') as file:
                self.json_data = json.load(file)
                self.WeiTipsEditor.setPlainText(self.json_data.get('tips', ''))

                # 初始化
                self.current_edit_index = None  # 初始化当前选中
                self.WeiCurrentEdit.setText("无")
                self.WeiIdInput.clear()
                self.WeiNameInput.clear()
                self.WeiErgodicInput.setCurrentIndex(0)
                self.QueueInput.setCurrentIndex(0)

                # 根据数据绘制视图
                self.load_data_to_ui_list()
                self.refresh_chessboard()

    def refresh_chessboard(self):
        """刷新棋盘上的文本等各种元素"""
        for i, row in enumerate(self.chessboard_buttons):
            for j, btn in enumerate(row):

                location_key = f"{j + 1}-{i + 1}"

                text = ""
                # 如果玩家在这个位置，添加 "玩家" 文字
                player_location_list = self.json_data.get('player', [])
                if location_key in player_location_list:
                    text += '\n玩家 {}'.format(player_location_list.index(location_key) + 1)

                cards_in_this_location = []
                for card in self.json_data["card"]:
                    if location_key in card['location']:
                        cards_in_this_location.append(card)

                for card in cards_in_this_location:
                    text += '\n' + card['name']
                    c_index_list = card["location"].index(location_key) + 1
                    if type(c_index_list) == "list":
                        for location_index in c_index_list:
                            text += " {}".format(location_index)
                    else:
                        text += " {}".format(c_index_list)
                btn.setText(text)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = JsonEditor()
    ex.show()
    sys.exit(app.exec_())
