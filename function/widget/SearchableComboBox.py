import sys

from PyQt6.QtCore import QRect, QPoint, QPropertyAnimation, QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QListWidget,
    QDialog,
    QVBoxLayout,
    QStyle,
    QProxyStyle,
    QStyleOptionComboBox,
    QLabel,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QSpacerItem,
    QSizePolicy
)


class SearchableComboBox(QComboBox):
    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        if items:
            self.addItems(items)
        self.setStyle(CustomComboBoxStyle())

    def mousePressEvent(self, event):
        if self.is_search_icon_clicked(event.pos()):
            self.open_search_dialog()
        else:
            super().mousePressEvent(event)

    def is_search_icon_clicked(self, pos: QPoint) -> bool:
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        search_icon_rect = self.get_search_icon_rect(option)
        return search_icon_rect.contains(pos)

    def get_search_icon_rect(self, option):
        style = self.style()
        arrow_rect = style.subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self
        )
        icon_size = 16
        margin = 4
        return QRect(
            arrow_rect.left() - icon_size - margin,
            arrow_rect.center().y() - icon_size // 2,
            icon_size,
            icon_size
        )

    def open_search_dialog(self):
        dialog = SearchDialog([self.itemText(i) for i in range(self.count())], self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_item:
            self.setCurrentText(dialog.selected_item)


class CustomComboBoxStyle(QProxyStyle):
    def drawComplexControl(self, control, option, painter, widget):
        super().drawComplexControl(control, option, painter, widget)
        if control == QStyle.ComplexControl.CC_ComboBox:
            arrow_rect = self.subControlRect(
                QStyle.ComplexControl.CC_ComboBox,
                option,
                QStyle.SubControl.SC_ComboBoxArrow,
                widget
            )
            search_icon_rect = widget.get_search_icon_rect(option)
            icon = self.standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
            icon.paint(painter, search_icon_rect)


class TitleBar(QWidget):
    windowMoved = pyqtSignal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)  # 减小高度
        self.mouse_pos = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 去除边距
        layout.setSpacing(0)

        # 关闭按钮样式优化
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self.parent().reject)
        self.close_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                color: #999999;
                border: none;
                background: transparent;
            }
            QPushButton:hover {
                color: #ff4444;
            }
        """)

        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        layout.addWidget(self.close_btn)

        # 标题栏背景透明化处理
        self.setStyleSheet("""
            TitleBar {
                background: transparent;
            }
        """)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.mouse_pos:
            delta = event.globalPosition().toPoint() - self.mouse_pos
            self.windowMoved.emit(delta)
            self.mouse_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.mouse_pos:
            delta = event.globalPosition().toPoint() - self.mouse_pos
            self.windowMoved.emit(delta)
            self.mouse_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)


class SearchDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(400, 400)
        self.selected_item = None

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(0)

        # 自定义标题栏
        self.title_bar = TitleBar(self)
        self.title_bar.windowMoved.connect(self.move_window)
        main_layout.addWidget(self.title_bar)

        # 内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # 搜索框
        self.search_bar = QLineEdit(placeholderText="输入搜索关键词...")
        self.search_bar.setClearButtonEnabled(True)

        # 列表
        self.list_widget = QListWidget()
        self.list_widget.addItems(items)

        # 空状态提示
        self.empty_label = QLabel("没有找到匹配项")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()

        content_layout.addWidget(self.search_bar)
        content_layout.addWidget(self.list_widget)
        content_layout.addWidget(self.empty_label)

        main_layout.addWidget(content_widget)

        # 信号连接
        self.search_bar.textChanged.connect(self.filter_items)
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        self.list_widget.itemClicked.connect(self.select_item)

        # 样式设置
        self.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #4dabf7;
            }
            QListWidget {
                border: 1px solid #ced4da;
                border-radius: 4px;
                background: white;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f1f3f5;
            }
            QListWidget::item:hover {
                background: #f8f9fa;
            }
            QListWidget::item:selected {
                background: #e7f5ff;
                color: #1864ab;
            }
        """)

    def move_window(self, delta):
        self.move(self.pos() + delta)

    def filter_items(self, text):
        visible_count = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            match = text.lower() in item.text().lower()
            item.setHidden(not match)
            if match:
                visible_count += 1
        self.empty_label.setVisible(visible_count == 0)

    def select_item(self):
        if selected := self.list_widget.currentItem():
            self.selected_item = selected.text()
            self.accept()

    def accept_selection(self):
        if selected := self.list_widget.currentItem():
            self.selected_item = selected.text()
        super().accept()

    def paintEvent(self, event):
        """添加窗口阴影效果"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(0, 0, 0, 30))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("现代化搜索组合框示例")
        self.resize(600, 400)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(40, 40, 40, 40)

        self.combo_box = SearchableComboBox([f"选项 {i:03d}" for i in range(1, 101)])
        layout.addWidget(QLabel("请选择项目:"))
        layout.addWidget(self.combo_box)
        layout.addStretch()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())