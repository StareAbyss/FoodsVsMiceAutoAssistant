from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """\
米苏物流是《美食大战老鼠》关卡掉落物统计可视化平台.
该项目由 直视深渊(FAA主要作者) 和 夏夜浅酌(提拉米鼠和美食数据站作者) 协作开发
数据源, 为FAA的自动战斗 - 掉落物扫描结果
网址: https://faa.msdzls.cn/

该项目为 <纯用爱发电> 的 <民间项目, 非官方>. 服务器 / 域名 等费用均为用爱发电.
为了给予我们开发者最低限度的动力, 该功能 <不设关闭按钮>, 长期启动.
项目完全开源, 因此您可以检查代码, 以确保您可以在本功能启用时, 自由使用本软件, 且不受到任何隐私侵害.

此处设置的Link为米苏物流数据收集服务器, 以应为未来可能的域名变化.
胡乱填写导致连通性测试不通过, 将在读取ui配置时自动清空.
不填写将自动采用默认url.
url核验不通过会导致每局战斗结算时间拖长5s, 以等待请求. 故若未来域名发生变化, 请及时修改配置此项加速.

此外, 米苏物流提供关卡信息热更新服务.
以支持用户从云端自动获取最新的 悬赏/假期/漫游 关卡的 承载卡/障碍物 等信息.
用户仅需点击获取按钮, 即可完成更新~
当然, 这项工作需要长期维护, 可能有轻微的滞后性. 更新速度, 取决于社区对开发者的支持~
"""


class QMWTipMisuLogistics(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('FAA X 米苏物流')
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
