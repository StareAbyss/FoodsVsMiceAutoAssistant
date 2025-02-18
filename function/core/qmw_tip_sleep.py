from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """
说明：
由于空间服在刷新后会有短暂的黑屏时间，如果网络条件较差，这个黑屏时间就会比较长，这样会导致faa在自动登录或选服时失败，
因此新增了这个功能，用来在刷新后进行一段时间的休眠。

如果勾选了“刷新后额外休眠”，faa将在点击刷新按钮、登录成功后分别休眠一段时间，以确保成功登录并选服。

具体的休眠时间请根据自己的情况自行设置，默认的5秒不一定对所有人都适用，建议使用时自己测试一下效果。
"""
class QMWTipQQlogin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('QQ空间密码登录教学')
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