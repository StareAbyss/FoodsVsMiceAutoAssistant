from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget
from function.globals.loadings import loading
loading.update_progress(70,"正在加载妙妙小提示...")
text = """\
该功能将尝试点击 *360游戏大厅右上角的变速按钮* 两次以进行短时间加速.

使用说明:
1. 将加速按钮调至360游戏大厅的工具栏中! 否则将导致战斗开局长时间等待乱放人物 / 战斗结束后迟迟不翻牌.
2. 填写加速倍率: 需在360游戏大厅手动设定好, 在游戏内启用加速, 并关闭一次后, 再填入此处. 
3. 初次尝试推荐 200% - 300%. 这是比较稳定的数值.

效果: 
开始战斗后加速: 85% 成功率 等倍率缩短游戏出怪间隔. 100% 不影响奖励和任务完成. 
结算等待时加速：100% 成功率 缩短等待时间.

游戏原理:
游戏只检测, 完成时间是否偏移超过 1s. 开启加速时间够短, 不会影响奖励. 即:  (加速倍率-1) * 加速时长 < 1000ms
但游戏开局开启锅加速后, 即使之后关闭了加速, 本局游戏中出怪间隔仍会被加速. (对此作者表示: Flash 很神奇吧)

FAA实现原理:
开启后将根据上述规则, 为用户自动计算加速持续时长. 为游戏内对应时长 / 运行倍率 - 50ms.
若开启自定义持续时间, 将覆盖FAA自动计算得出的时间, 采用用的时间. 吓设置会导致无奖励! 请仔细阅读上述原理!

注意:
1. 任何操作都一定误差.
2. 任何操作都受点击频率限制.
这便是自动计算的时间, 会减去50ms的原因.
但由于有的用户想要尝试 1000%的极限加速, 考虑延时, 需手动调整加速时长. 
故给出了自定义持续时间的设置项, 并允许用户填写高加速倍率数值.
"""


class QMWTipAccelerateSettings(QMainWindow):
    def __init__(self):
        super().__init__(parent=None)
        self.setWindowTitle('加速功能介绍')
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
