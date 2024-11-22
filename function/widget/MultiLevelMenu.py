from PyQt6.QtWidgets import QPushButton, QMenu
from PyQt6.QtCore import pyqtSignal
from functools import partial


class MultiLevelMenu(QPushButton):
    """
    做成按钮的多级下拉菜单
    """
    on_selected = pyqtSignal(str, str)  # 使用 pyqtSignal 传递两个参数

    def __init__(self, title: str = '关卡选择', parent=None):
        super().__init__(title, parent)
        self.menu = QMenu(self)
        self.setMenu(self.menu)

    def add_menu(self, data, menu=None):
        if menu is None:
            menu = self.menu
        for key, value in data.items():
            sub_menu = QMenu(key, self)
            menu.addMenu(sub_menu)
            if isinstance(value, dict):
                # 如果值是字典，则递归处理为子菜单
                self.add_menu(data=value, menu=sub_menu)
            elif isinstance(value, list):
                # 如果值是列表，将每个元素(均为元组)的第一部分作为选项放入子菜单中，第二部分传递出去
                for item in value:
                    action = sub_menu.addAction(item[0])
                    action.triggered.connect(partial(self.on_item_selected, item[0], item[1]))
            else:
                print(f"不支持的值类型 '{key}': {type(value)}")

    def on_item_selected(self, text, data):
        self.setText(text)
        self.menu.close()
        self.on_selected.emit(text, data)
        print(text, data)
