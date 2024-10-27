from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """\
高级战斗（特殊对策卡）

使用 神经网络图像识别技术 + 线性规划
实现 自动炸神风 & 电流 & 波次冰桶等 超强功能

叠甲1: 此功能为高级测试功能
叠甲2: 启用前请阅读高级放卡md，完全理解原理后再使用
叠甲3: 如未能按预期实现, 请先确保你的相关设置无误

1.所有高级放卡的卡片除护罩外不会被正常使用,具体卡片类别看目录/resource/image/card/特殊对策卡,如果非要按照常规卡使用可以删去对应图片
2.高级放卡须先启用对应功能方可使用
3.需战斗中火苗数>=1000.
4.高级放卡（特殊对策卡）会根据制订的放卡策略执行，用什么炸弹需要在策略中指定，但除开草扇冰桶外无需设置点位
5.高级放卡（特殊对策卡）放置的炸弹及其点位是根据线性规划计算出的最优解，目标优化函数为火苗
"""


class QMWTipBattleSenior(QMainWindow):
    def __init__(self):
        super().__init__(parent=None)
        self.setWindowTitle('高级战斗介绍')
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
