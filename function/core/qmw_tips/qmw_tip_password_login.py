from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """\
如何使用密码登录
在 QQ 空间或 4399 的设置中勾选密码登录，并填写所用角色的账号和密码。
刷新游戏时，FAA 会先查找选服入口，找不到入口时才尝试密码登录。取消勾选即可关闭密码登录。

何时保存登录信息
密码登录开关会自动保存。填写账号和密码时，输入暂留在界面中，避免把未填完的内容写入凭据文件。
填好后点击「保存登录信息」，即可立即保存 QQ 空间、4399 的登录信息以及二级密码。
点击「执行序列」或「启动定时任务」时也会先保存凭据。已激活的定时任务继续使用激活时的凭据。

凭据存在哪里
账号和密码统一保存在 config/login_credentials.json，其中密码使用本机机器码加密。
请勿分享这个文件。换电脑后如果无法读取原有密码，请重新填写并保存。
"""


class QMWTipPasswordLogin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("密码登录说明")
        self.setFixedSize(850, 400)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(text)

        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.addWidget(self.text_edit)
        self.setCentralWidget(main_widget)
