from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """
使用方法：
填入账号和密码，点击“选择文件夹”按钮，选择账号和密码的存储路径，
点击“保存登录信息”按钮，会在选择的文件夹下生产一个 QQ_account.json，这里存放着你的账号和密码。
勾选上“使用密码进行登录”，再在“一键长草”中点击“保存配置”按钮，
即可在360游戏中心自动使用密码登录游戏（无需在电脑上电脑登录QQ）。

注意：
如果你使用后想改为不需要使用密码登录方式，请取消勾选，
不用点击“保存”按钮，但需要在“一键长草”中点击“保存配置”按钮。

安全说明：
注意QQ_account.json中的密码是加密存储的，密钥为你的电脑机器码，
因此理论上来讲，即使别人拿到了你的配置文件，也无法获取到你的密码。
但为了安全起见，还是请勿将 QQ_account.json 文件发给别人
（建议不要将密码文件存到faa文件夹下，防止将文件夹传给别人时误传了QQ_account.json）

免责声明：
使用此功能的用户需明确自己在用什么，若因用户自己误操作导致密码泄露问题，FAA开发组概不负责！！！
如果您担心会出问题，请勿使用该功能

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