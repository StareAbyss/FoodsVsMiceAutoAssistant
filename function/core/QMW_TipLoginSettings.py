from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """\
◆ 功能介绍 ◆

该功能将在启动前后, 开关360游戏大厅的对应窗口.
多FAA挂机不会影响其他FAA管理的游戏窗口.

作用：
1. 最大程度的节省您的系统资源. 
2. 如果您需要 *同时* 使用以下功能, 这是 *唯一* 方案
* 功能
    * 使用微端网址.
    * 每周四不想上号重启360游戏大厅.
    * 使用日氪功能.
* 原因
    * 游戏周四维护期间, 4399微端用户刷新游戏后, 将被强制重定向至常规4399网址.
    * 不同的网址导致游戏窗口的布局发生变化, 很可能导致原本处于居中位置的Flash窗口被挤到360窗口外. 导致无法正常运行.
    * 日氪功能要求Flash窗口大小和360窗口大小几乎一致, 导致您无法通过调整滚动条来优化上述问题.

◆ 前置准备 ◆

由于360游戏大厅在您添加游戏时, 会从1开始为游戏编码PID, 只增不减. 
即使删除了之前的游戏, PID仍会继续增加. 因此您需要打开的游戏PID为你添加过的游戏的次数. 您亦无法通过任何常规手段修改已添加游戏的PID.

FAA仅打开PID为1的游戏, 即添加的第一款游戏.
如果您在下载360游戏大厅后, 添加的第一款游戏即为您需要打开的游戏, 那么恭喜, 您的前置准备已经完成!

否则, 您需要重置360游戏大厅的配置, 并重新添加第一款游戏.
注意：这将初始化您的360游戏大厅. 包括注册的游戏和账号数据.
 
1. 备份账号密码数据, 备份登录网址. 关闭360游戏大厅.
2. 前往资源管理器路径 'C:\\Users\\Administrator\\AppData\\Roaming\\360Game5\\data\\default' 文件夹.
3. 里面的内容删干净, 包括360Game.db, db_backup. 这将初始化您的360游戏大厅. 包括注册的游戏和账号数据.
4. 重新开启360游戏大厅, 重新添加您的第一款游戏.

之后, 您将可以正常使用该功能.

◆ 正式配置 ◆

这非常简单
1. 启动您的360游戏大厅, 启动对应的游戏, 登录对应账号.
2. 点击 "一键获取-路径及账号序号".
3. 记得保存保存保存. 重要的事情说三遍.
之后您就可以尽情体验啦~

◆ 关于管理员权限 ◆

如果您的操作系统非单账户, 且并非管理员身份(Administrator)登录, 可能导致下述问题:
1. 上文中的资源管理器路径可能有所变化. 
2. 权限不足导致功能失败.
该问题的来源, 是由于国内混乱的盗版Windows系统安装方法. 
请自行查阅网上资料, 或寻求人工智能解决该问题. 
不要因该问题, 求助群聊管理或反馈至开发者, 这不属于我们能处理的问题.
"""


class QMWTipLoginSettings(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('关于登录选项')
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
