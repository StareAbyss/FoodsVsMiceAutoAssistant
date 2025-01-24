import sys
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QListWidget,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QListWidgetItem,
    QStyle,
    QProxyStyle,
    QStyleOptionComboBox,
    QLabel,
    QMainWindow,
    QWidget,
)
from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtGui import QPainter, QIcon


class SearchableComboBox(QComboBox):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.addItems(items)

        # 在组合框中添加搜索图标
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)  # 将行编辑设置为只读
        self.lineEdit().setPlaceholderText("点击搜索...")

        # 自定义样式以绘制搜索图标
        self.setStyle(CustomComboBoxStyle())

    def mousePressEvent(self, event):
        """处理鼠标按下事件以打开搜索对话框。"""
        # 单击组合框时打开搜索对话框
        if self.is_search_icon_clicked(event.pos()):
            self.open_search_dialog()
        else:
            super().mousePressEvent(event)

    def is_search_icon_clicked(self, pos: QPoint) -> bool:
        """检查是否单击了搜索图标区域。"""
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        icon_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxArrow, self
        )
        return icon_rect.contains(pos)

    def open_search_dialog(self):
        """打开搜索对话框并更新组合框。"""
        dialog = SearchDialog([self.itemText(i) for i in range(self.count())], self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_item:
            self.setCurrentText(dialog.selected_item)


class CustomComboBoxStyle(QProxyStyle):
    """自定义样式以向组合框添加搜索图标。"""

    def drawComplexControl(self, control, option, painter, widget):
        if control == QStyle.ComplexControl.CC_ComboBox:
            # 绘制原始组合框
            super().drawComplexControl(control, option, painter, widget)

            # 在箭头区域绘制搜索图标
            icon = widget.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
            arrow_rect = self.subControlRect(
                QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxArrow, widget
            )
            icon_rect = QRect(
                arrow_rect.left() - 12, arrow_rect.top() + 4, arrow_rect.width() - 8, arrow_rect.height() - 8
            )
            icon.paint(painter, icon_rect)

        else:
            super().drawComplexControl(control, option, painter, widget)


class SearchDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("搜索并选择项目")
        self.resize(400, 300)

        self.selected_item = None

        # 布局
        layout = QVBoxLayout(self)

        # 搜索栏
        self.search_bar = QLineEdit(self)
        self.search_bar.setPlaceholderText("输入关键字搜索...")
        layout.addWidget(self.search_bar)

        # 列表小部件以显示项目
        self.list_widget = QListWidget(self)
        self.list_widget.addItems(items)
        layout.addWidget(self.list_widget)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(button_box)

        # 连接信号
        self.search_bar.textChanged.connect(self.filter_items)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)

    def filter_items(self, text):
        """根据搜索文本过滤列表小部件中的项目。"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def on_item_double_clicked(self, item):
        """处理双击以选择一个项目。"""
        self.selected_item = item.text()
        self.accept()

    def accept(self):
        """处理对话框接受。"""
        selected_items = self.list_widget.selectedItems()
        if selected_items:
            self.selected_item = selected_items[0].text()
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("自定义 ComboBox 搜索示例")
        self.resize(300, 200)

        # 主布局
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 自定义 ComboBox
        self.combo_box = SearchableComboBox([f"选项 {i}" for i in range(1, 51)], self)
        layout.addWidget(self.combo_box)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
