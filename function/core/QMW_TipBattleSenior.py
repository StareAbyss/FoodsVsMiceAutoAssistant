from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget


class QMWTipBattleSenior(QMainWindow):
    def __init__(self):
        super().__init__(parent=None)
        self.setWindowTitle('战斗逻辑介绍')
        self.text_edit = None
        # 设置窗口大小
        self.setMinimumSize(650, 400)
        self.setMaximumSize(650, 400)
        self.initUI()

    def initUI(self):
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)  # 设置为只读模式

        text = ""
        text += "实现自动炸神风 & 电流 & 波次冰桶等超强功能\n"
        text += "叠甲1: 此功能为高级测试功能\n"
        text += "叠甲2: 启用前请阅读高级放卡md，完全理解原理后再使用\n"
        text += "叠甲3: 如未能按预期实现, 请先确保你的相关设置无误\n"

        # 插入文本
        self.text_edit.setPlainText(text)

        # 设置布局
        layout = QVBoxLayout()
        layout.addWidget(self.text_edit)

        # 设置主控件
        main_widget = QWidget()
        main_widget.setLayout(layout)

        # 将 控件注册 为 窗口主控件
        self.setCentralWidget(main_widget)
