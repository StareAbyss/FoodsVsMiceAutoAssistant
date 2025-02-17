from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """\
此处确定, 并输入二级密码, 将在以下位置附加 [删除道具中垃圾物品 + 兑换暗晶] 该功能.
1. < 签到 > 功能运行前.
2. < 公会任务 > 的开始和结束的奖励领取前.
3. < 领取奖励 > 功能运行前.

删除的目标物品默认均为无用技能书, 删除物品见: config / cus_images / 背包_道具_需删除的. 允许自行增删配置.
该功能会自动点击整理物品, 且仅识别第一页物品以删除.

叠甲1: 该功能新开发, 有风险! 请知道自己在做什么.
叠甲2: 开启此功能 < 一切后果 > 请玩家自负.
叠甲3: FAA完全开源, 因此您可以检查代码, 以确保您可以在本功能启用时, 自由使用本软件, 且不受到任何隐私侵害.
叠甲4: 我想不会有人"不小心"正确设置该项目.
"""


class QMWTipLevels2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('二级功能')
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
