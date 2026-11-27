from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """
说明：
刷新后，各平台的选服页面可能需要一段时间才能出现。
启用“额外等待选服按钮出现”后，FAA 会在原有加载等待之外，
按设定的最长时间反复查找所选平台的选服按钮；找到就立即点击，不会等满设定时间。

账号密码登录或头像一键登录之后，也会用同样的等待时长查找选服按钮。
该设置适用于全部平台。若平台刷新后直接进入游戏，可能会额外等待至设定时间结束。
默认关闭，启用时请按实际加载速度设置。
"""


class QMWTipServerWait(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('刷新后等待选服说明')
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
