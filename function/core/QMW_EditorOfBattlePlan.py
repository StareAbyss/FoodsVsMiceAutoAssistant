import copy
import json
import sys
import time

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGridLayout, QPushButton, QWidget, QFileDialog, QVBoxLayout, QLabel, QComboBox,
    QLineEdit, QHBoxLayout, QTextEdit, QListWidget, QMessageBox, QSpinBox, QListWidgetItem, QShortcut, QFrame)

from function.globals.extra import EXTRA_GLOBALS
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER

double_click_card_list = pyqtSignal(object)

"""
战斗方案编辑器
致谢：八重垣天知
"""


class QMWEditorOfBattlePlan(QMainWindow):

    def __init__(self):
        super().__init__()

        """字体"""
        self.my_font = None

        """内部数据表"""
        # 数据dict
        self.json_data = {
            "tips": "",
            "player": [],
            "card": []
        }

        # 当前被选中正在编辑的项目的index
        self.current_edit_index = None

        # 撤销/重做功能
        self.undo_stack = []
        self.redo_stack = []
        self.undo_shortcut = QShortcut(QKeySequence('Ctrl+Z'), self)
        self.undo_shortcut.activated.connect(self.undo)
        self.redo_shortcut = QShortcut(QKeySequence('Ctrl+Y'), self)
        self.redo_shortcut.activated.connect(self.redo)

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
            '点击左侧列表, 选中对象进行编辑 | 点击格子添加到该位置, 再点一下取消位置 | 列表从上到下 是一轮放卡的优先级(人物除外)'))
        """卡片编辑器"""
        self.LayCardEditor = QHBoxLayout()
        self.LayMain.addLayout(self.LayCardEditor)

        self.LayCardEditor.addWidget(QLabel('ID:'))

        self.WeiIdInput = QSpinBox()
        self.LayCardEditor.addWidget(self.WeiIdInput)
        self.WeiIdInput.setToolTip("id代表卡在卡组中的顺序")
        self.WeiIdInput.setRange(0, 21)

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

        self.LayCardEditor.addWidget(QLabel('幻鸡优先级:'))
        self.KunInput = QSpinBox()
        self.KunInput.setRange(0, 10)
        self.LayCardEditor.addWidget(self.KunInput)
        self.KunInput.setToolTip("卡片是否使用幻幻鸡, 0代表不使用，越高使用优先级越高")

        self.WeiAddCardButton = QPushButton('添加一张新卡')
        self.LayCardEditor.addWidget(self.WeiAddCardButton)

        self.WeiDeleteCardButton = QPushButton('删除选中卡片')
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
        self.chessboard_frames = []  # 用于存储QFrame的列表

        for i in range(7):
            row_buttons = []
            row_frames = []

            for j in range(9):
                btn = ChessButton('')
                btn.setFixedSize(100, 100)
                btn.clicked.connect(lambda checked, x=i, y=j: self.place_card(y, x))
                btn.rightClicked.connect(lambda x=i, y=j: self.remove_card(y, x))
                self.chessboard_layout.addWidget(btn, i, j)
                btn.setToolTip(f"当前位置: {j + 1}-{i + 1}")
                row_buttons.append(btn)

                # 创建QFrame作为高亮效果的载体
                frame = QFrame(self)
                frame.setFixedSize(100, 100)
                frame.setFrameShape(QFrame.StyledPanel)
                frame.setFrameShadow(QFrame.Raised)
                self.chessboard_layout.addWidget(frame, i, j)
                frame.lower()  # 确保QFrame在按钮下方
                frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # 防止遮挡按钮
                row_frames.append(frame)

            self.chessboard_buttons.append(row_buttons)
            self.chessboard_frames.append(row_frames)

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

        # 删除卡片
        self.WeiDeleteCardButton.clicked.connect(self.delete_card)
        # 单击列表更改当前card
        self.WeiCardList.itemClicked.connect(self.current_card_change)
        # id，名称,遍历，队列控件的更改都连接上更新卡片
        self.WeiIdInput.valueChanged.connect(self.update_card)
        self.WeiNameInput.textChanged.connect(self.update_card)
        self.WeiErgodicInput.currentIndexChanged.connect(self.update_card)
        self.QueueInput.currentIndexChanged.connect(self.update_card)
        self.KunInput.valueChanged.connect(self.update_card)

        """外观"""
        self.UICss()

        """先刷新一下数据"""
        self.load_data_to_ui_list()

    def highlight_chessboard(self, card_locations):
        """根据卡片的位置list，将对应元素的按钮进行高亮"""
        # 清除所有按钮的高亮
        for row in self.chessboard_frames:
            for btn in row:
                # 去除高亮
                btn.setStyleSheet("")

        # 高亮显示选中卡片的位置
        for location in card_locations:
            x, y = map(int, location.split('-'))
            # 添加背景颜色到现有样式
            self.chessboard_frames[y - 1][x - 1].setStyleSheet("background-color: rgba(255, 255, 0, 127);")

    def UICss(self):
        # 窗口名
        self.setWindowTitle('战斗方案编辑器')

    def current_card_change(self, item):
        """被单击后, 被选中的卡片改变了"""
        self.index = self.WeiCardList.indexFromItem(item).row()  # list的index 是 QModelIndex 此处还需要获取到行号

        self.current_edit_index = self.index

        # 为输入控件信号上锁，在初始化时不会触发保存
        self.WeiCurrentEdit.blockSignals(True)
        self.WeiIdInput.blockSignals(True)
        self.WeiNameInput.blockSignals(True)
        self.WeiErgodicInput.blockSignals(True)
        self.QueueInput.blockSignals(True)

        if self.index == 0:
            # 玩家 直接清空它们
            self.WeiCurrentEdit.setText("玩家")
            self.WeiIdInput.clear()
            self.WeiNameInput.clear()
            self.WeiNameInput.setText("玩家")
            self.WeiErgodicInput.setCurrentIndex(0)
            self.QueueInput.setCurrentIndex(0)
            self.KunInput.setValue(0)
            self.highlight_chessboard(self.json_data["player"])
        else:
            # 卡片
            index = self.index - 1  # 可能需要深拷贝？也许是被保护的特性 不需要
            card = self.json_data["card"][index]
            self.WeiCurrentEdit.setText("索引-{} 名称-{}".format(index, card["name"]))
            self.WeiIdInput.setValue((card['id']))
            self.WeiNameInput.setText(card['name'])
            self.WeiErgodicInput.setCurrentText(str(card['ergodic']).lower())
            self.QueueInput.setCurrentText(str(card['queue']).lower())
            self.KunInput.setValue(card.get('kun', 0))
            # 设置高亮
            self.highlight_chessboard(card["location"])

        # 解锁控件信号
        self.WeiCurrentEdit.blockSignals(False)
        self.WeiIdInput.blockSignals(False)
        self.WeiNameInput.blockSignals(False)
        self.WeiErgodicInput.blockSignals(False)
        self.QueueInput.blockSignals(False)

    def load_data_to_ui_list(self):
        """从 [内部数据表] 载入数据到 [ui的list]"""
        self.WeiCardList.clear()

        player_item = QListWidgetItem("玩家")
        self.WeiCardList.addItem(player_item)

        # 找到最长的卡片名称长度
        if self.json_data["card"]:
            max_name_length = max(len(card["name"]) for card in self.json_data["card"])

        for card in self.json_data["card"]:
            # 使用制表符或空格填充卡片名称
            padded_name = card["name"].ljust(max_name_length)

            text = "{}\tID:{} 遍历:{} 队列:{}".format(
                padded_name,
                card["id"],
                "√" if card["ergodic"] else "X",
                "√" if card["queue"] else "X"
            )
            if card.get("kun", 0):
                text += " 坤:{}".format(card["kun"])
            item = QListWidgetItem(text)
            self.WeiCardList.addItem(item)

    def card_list_be_dropped(self, index_from, index_to):
        """在list的drop事件中调用, 用于更新内部数据表"""
        cards = self.json_data["card"]
        if index_to != 0:
            # 将当前状态压入栈中
            self.append_undo_stack()

            change_card = cards.pop(index_from - 1)
            CUS_LOGGER.debug(change_card)
            cards.insert(index_to - 1, change_card)
            CUS_LOGGER.debug("正常操作 内部数据表已更新: {}".format(cards))
        else:
            # 试图移动到第一个
            self.WeiCardList.clear()
            self.load_data_to_ui_list()

    def add_card(self):
        id_ = 0
        name_ = "新的卡片"

        self.json_data["card"].append(
            {
                "id": id_,
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

        # 将当前状态压入栈中
        self.append_undo_stack()

        index -= 1
        card = self.json_data["card"][index]
        id = int(self.WeiIdInput.value())
        card["id"] = id
        card["name"] = self.WeiNameInput.text()
        card["ergodic"] = bool(self.WeiErgodicInput.currentText() == 'true')  # 转化bool
        card["queue"] = bool(self.QueueInput.currentText() == 'true')  # 转化bool
        card["kun"] = self.KunInput.value()
        self.WeiCurrentEdit.setText("索引-{} 名称-{}".format(self.index - 1, card["name"]))
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
        # 将当前状态压入栈中
        self.append_undo_stack()

        index -= 1
        del self.json_data["card"][index]
        self.load_data_to_ui_list()
        self.refresh_chessboard()

    def place_card(self, x, y):
        if self.current_edit_index is None:
            return
        # 将当前状态压入栈中
        self.append_undo_stack()
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

    def remove_card(self, x, y):
        # 将当前状态压入栈中
        self.append_undo_stack()
        # 删除当前位置上的所有卡片
        location = f"{x + 1}-{y + 1}"
        # 从玩家位置中删除
        if location in self.json_data["player"]:
            self.json_data["player"].remove(location)
        # 从卡片位置中删除
        for card in self.json_data["card"]:
            if location in card["location"]:
                card["location"].remove(location)
        # 更新界面显示
        self.refresh_chessboard()

    def save_json(self):
        self.json_data['tips'] = self.WeiTipsEditor.toPlainText()
        options = QFileDialog.Options()

        file_name, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="保存 JSON 文件",
            directory=PATHS["battle_plan"],
            filter="JSON Files (*.json)",
            options=options)

        if file_name:
            # 确保玩家位置也被保存
            self.json_data['player'] = self.json_data.get('player', [])
            # 自旋锁读写, 防止多线程读写问题
            while EXTRA_GLOBALS.file_is_reading_or_writing:
                time.sleep(0.1)
            EXTRA_GLOBALS.file_is_reading_or_writing = True  # 文件被访问
            with open(file=file_name, mode='w', encoding='utf-8') as file:
                json.dump(self.json_data, file, ensure_ascii=False, indent=4)
            EXTRA_GLOBALS.file_is_reading_or_writing = False  # 文件已解锁

    def load_json(self):
        """打开窗口 读取josn文件"""
        # 为输入控件信号上锁，在初始化时不会触发保存
        self.WeiCurrentEdit.blockSignals(True)
        self.WeiIdInput.blockSignals(True)
        self.WeiNameInput.blockSignals(True)
        self.WeiErgodicInput.blockSignals(True)
        self.QueueInput.blockSignals(True)

        options = QFileDialog.Options()

        file_name, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="打开 JSON 文件",
            directory=PATHS["battle_plan"],
            filter="JSON Files (*.json)",
            options=options)

        if file_name:

            # 自旋锁读写, 防止多线程读写问题
            while EXTRA_GLOBALS.file_is_reading_or_writing:
                time.sleep(0.1)
            EXTRA_GLOBALS.file_is_reading_or_writing = True  # 文件被访问
            with open(file=file_name, mode='r', encoding='utf-8') as file:
                self.json_data = json.load(file)
            EXTRA_GLOBALS.file_is_reading_or_writing = False  # 文件已解锁

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
            # 清除所有按钮的高亮
            for row in self.chessboard_frames:
                for btn in row:
                    # 去除高亮
                    btn.setStyleSheet("")

        # 为输入控件信号解锁
        self.WeiCurrentEdit.blockSignals(False)
        self.WeiIdInput.blockSignals(False)
        self.WeiNameInput.blockSignals(False)
        self.WeiErgodicInput.blockSignals(False)
        self.QueueInput.blockSignals(False)

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

    def append_undo_stack(self):
        # 将当前状态压入栈中
        self.undo_stack.append(copy.deepcopy(self.json_data))
        # 清空重做栈
        self.redo_stack.clear()
        # 只保留20次操作
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)

    def undo(self):
        if len(self.undo_stack) > 0:
            current_state = copy.deepcopy(self.json_data)
            self.redo_stack.append(current_state)
            self.json_data = self.undo_stack.pop()
            self.load_data_to_ui_list()
            self.refresh_chessboard()

    def redo(self):
        if len(self.redo_stack) > 0:
            current_state = copy.deepcopy(self.json_data)
            self.undo_stack.append(current_state)
            self.json_data = self.redo_stack.pop()
            self.load_data_to_ui_list()
            self.refresh_chessboard()

    def set_my_font(self, my_font):
        self.my_font = my_font
        self.setFont(self.my_font)


class QListWidgetDraggable(QListWidget):

    def __init__(self, drop_function):
        super(QListWidgetDraggable, self).__init__()

        # 定义数据变化函数
        self.drop_function = drop_function

        # 允许内部拖拽
        self.setDragDropMode(self.InternalMove)

    def dropEvent(self, e):
        CUS_LOGGER.debug("拖拽事件触发")
        index_from = self.currentRow()
        super(QListWidgetDraggable, self).dropEvent(e)  # 如果不调用父类的构造方法，拖拽操作将无法正常进行
        index_to = self.currentRow()

        source_Widget = e.source()  # 获取拖入item的父组件
        items = source_Widget.selectedItems()  # 获取所有的拖入item
        item = items[0]  # 不允许多选 所以只有一个

        CUS_LOGGER.debug("text:{} from {} to {} memory:{}".format(item.text(), index_from, index_to, self.currentRow()))

        # 执行更改函数
        self.drop_function(index_from=index_from, index_to=index_to)

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        current_row = self.currentRow()
        if current_row == 0:
            # 禁止拖拽
            self.setDragDropMode(self.NoDragDrop)
        else:
            # 允许内部拖拽
            self.setDragDropMode(self.InternalMove)


class ChessButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            # 发出自定义的右键点击信号
            self.rightClicked.emit()
        else:
            super().mousePressEvent(event)

    rightClicked = pyqtSignal()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = QMWEditorOfBattlePlan()
    ex.show()
    sys.exit(app.exec_())
