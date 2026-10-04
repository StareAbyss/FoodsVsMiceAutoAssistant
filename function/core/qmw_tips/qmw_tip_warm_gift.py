from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """\
领取链接与你的微信账号和微信账号所绑定的美食账号关联, 此链接包含了经过加密运算的微信号作为辨识ID
此链接仅能够用于领取温馨礼包和获取平台区服, 无法获知你的具体信息和用于获知其他美食游戏内容
请勿轻易将领取链接发给他人, 他人可使用该链接, 解绑你的绑定, 导致你一个月内无法再次绑定
FAA为所有配置数据保存在本地, 请放心使用

设置方式如下：
1.微信打开美食公众号中的美食中心, 点击右上角的“...”
2.点击“复制链接”, 即可得到领取链接
3.截取链接中ID = 后面的部分
4.将链接输入FAA, 勾选激活, 将会在任务列表-签到模块自动完成"
"""


class QMWTipWarmGift(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('温馨礼包教学')
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
