from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """\
施工ing
"""


class QMWTipEditorOfBattlePlan(QMainWindow):
    def __init__(self):
        super().__init__(parent=None)
        self.setWindowTitle('战斗方案 & 战斗方案编辑器介绍')
        self.text_edit = None

        # 设置窗口大小
        self.setFixedSize(850, 400)
        self.initUI()

    def initUI(self):
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)  # 设置为只读模式

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
