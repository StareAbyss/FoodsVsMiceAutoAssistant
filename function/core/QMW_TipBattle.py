from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget



class QMWTipBattle(QMainWindow):
    def __init__(self):
        super().__init__(parent=None)
        self.setWindowTitle('战斗逻辑介绍')
        self.text_edit = None
        # 设置窗口大小
        self.setMinimumSize(650, 400)
        self.setMaximumSize(650, 400)
        self.initUI()
        # 设置主窗口无边框
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

    def initUI(self):
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)  # 设置为只读模式

        text = ""
        text += "自动识别 + 放置功能\n"
        text += "以下卡片仅需提前置于卡组末尾并保存, 战斗中将识别其位置并依据一定逻辑放置, 无需配置.\n"
        text += "\n"
        text += "承载卡\n"
        text += "1. 在FAA中, 除自建房战斗中的所有关卡, 均适配有全自动的承载卡放置.\n"
        text += "2. 支持所有转职的木盘子/棉花糖/麦芽糖/魔法软糖/苏打气泡, 暂不支持盘盘鸡&猫猫盘.\n"
        text += "3. 双人战斗时, 两个角色将平分承载卡任务.\n"
        text += "\n"
        text += "极寒冰沙\n"
        text += "1. 在所有卡片均进入冷却(或放满被锁定)时自动放置.\n"
        text += "2. 在双人战斗时, 会自动错开放置.\n"
        text += "3. 需火苗数>=1000.\n"
        text += "\n"
        text += "幻幻鸡\n"
        text += "1. 仅支持同时携带一张该类卡片(含转职和创造神).\n"
        text += "2. 将根据战斗方案中为每张卡片设置的优先级 (坤参数) 进行自动复制, 坤参数为0不复制, 否则坤参数越高被复制优先级越高, 同优先级取卡片顺序.\n"
        text += "3. 需火苗数>=1000.\n"



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