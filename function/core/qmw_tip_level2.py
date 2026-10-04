from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """\
此处确定, 并输入二级密码, 将激活 < 删除垃圾 > 和 < 兑换暗晶 > 功能的使用.
以允许您手动添加该事项.

在 < 签到开始前 > / < 公会任务结束, 领取奖励前 > 将自动附加 < 删除垃圾 > 功能.

请先在游戏中设置二级密码，再在 FAA 中填写正确密码。
优先通过暗晶商店触发二级输入框；未弹框时，进入防御卡背包点击一次整理作为后备。
只有识别到密码框且输入后确认框消失，才会继续任务；验证失败会停止任务并弹窗提醒。
未设置二级密码或已解锁时，后备触发可能直接整理卡片背包，相关后果由用户自行承担。

删除的目标物品默认均为无用技能书, 删除物品见: config / cus_images / 背包_道具_需删除的. 允许自行增删配置.
该功能会自动点击整理物品, 且仅识别第一页物品以删除.

叠甲1: 该功能有潜在风险! 请知道自己在做什么.
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
