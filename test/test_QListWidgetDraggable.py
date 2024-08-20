import sys

from PyQt6.QtWidgets import QApplication, QWidget, QListWidget, QListWidgetItem, QTextEdit, QHBoxLayout

"""
目标一： 实现一个列表ui 与 内部数据表 一一对应 且可以通过拖拽它进行直接修改
思路
1.继承重写QListWidget类, 修改构造方法, 传入一个函数
2.重写dropEvent事件, 应用该函数
3.内部数据表的修改函数定义好， 以 index 的 from 和 to 为参数

目标二：使第一个数据无法被拖动，且其他数据不能成为数据0
思路
1.第一步
在mousePressEvent的重写中, 添加当前被选中的行号为0时，禁用鼠标拖拽，保证第一个数据被选中时拖拽动作无法进行
第一个item被选中时无法拖拽，但其他数据可以拖拽到第一个
2.第二部
内部数据表的修改函数中，当被修改的 from 或 to index 为0时，根据内部数据表直接刷新ui，还原ui修改, 保证其他数据无法成为第一个
使第一个item可以进行互动，但不会产生效果
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

class Demo(QWidget):
    def __init__(self):
        super().__init__()

        # 创建一个内部数据列表，用于存储 item 的内容
        self.w_text_2 = None
        self.data_list = ["玩家", "卡片1", "卡片2", "卡片3"]
        # 创建一个属性 表示目前被选中的(正在编辑的卡片)
        self.current_card_index = 0

        # 创建 QListWidget 和 QTextEdit
        self.w_list = QListWidgetDraggable(drop_function=self.update_data)
        self.w_text_1 = QTextEdit()
        self.w_text_2 = QTextEdit()

        # 创建水平布局，并添加3个控件
        self.h_layout = QHBoxLayout()
        self.h_layout.addWidget(self.w_list)
        self.h_layout.addWidget(self.w_text_1)
        self.h_layout.addWidget(self.w_text_2)
        self.setLayout(self.h_layout)

        self.init_ui()

    def init_ui(self):

        # 为 QListWidget 添加一些 QListWidgetItem
        self.load_data_to_ui_list()

        # 为 QListWidget 的 itemDoubleClicked 信号添加槽函数
        self.w_list.itemDoubleClicked.connect(self.show_text_current)

        # 通过 QSS 设置 QListWidget 和 QTextEdit 的样式
        self.w_list.setStyleSheet("QListWidget {background-color: lightblue; font-size: 18px;}")
        self.w_text_1.setStyleSheet("QTextEdit {background-color: lightgreen; font-size: 18px;}")

        # 设置窗口标题和大小
        self.setWindowTitle("QListWidget 示例")
        self.resize(400, 300)

    def show_text_current(self, item):
        """将 QListWidgetItem 的文本属性设置为 QTextEdit 的文本"""

        text = item.text()
        self.w_text_1.setText(text)
        self.current_card_index = 0
        print("界面 当前选中文本已更新：{}".format(text))

        index = self.w_list.indexFromItem(item).row()  # list的index 是 QModelIndex 此处还需要获取到行号
        self.current_card_index = index
        print("内部 当前选中index已更新：{}".format(index))

    def show_text_data(self):
        # 刷 QListWidgetItem 的文本属性
        self.w_text_2.clear()
        texts = ""
        for text in self.data_list:
            texts += text + "\n"
        self.w_text_2.append(texts)

    def load_data_to_ui_list(self):
        """从内部数据表载入数据到ui的list"""
        self.w_list.clear()
        for data in self.data_list:
            self.w_list.addItem(
                QListWidgetItem(data))

    def update_data(self, index_from, index_to):
        """在list的drop事件中调用, 用于更新内部数据表"""
        if index_to != 0:
            data_list = self.data_list

            a2 = data_list.pop(index_from)
            data_list.insert(index_to, a2)

            print("正常操作 数据表已更新: {}".format(self.data_list))
            self.show_text_data()

        else:
            # 试图移动到第一个
            self.w_list.clear()
            self.load_data_to_ui_list()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    demo = Demo()
    demo.show()
    sys.exit(app.exec())
