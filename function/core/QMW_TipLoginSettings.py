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
    * 游戏周四维护期间, 4399微端网址刷新游戏后, 将被强制重定向至4399常规网址.
    * 不同的网址将导致游戏窗口的布局发生变化, 很可能使得原本处于居中位置的Flash窗口被挤到360窗口外. 进而无法正常运行.
    * 日氪功能要求Flash窗口大小和360窗口大小几乎一致, 导致您无法通过调整滚动条来优化上述问题.

◆ 前置准备 ◆

每当您于360游戏大厅在您添加游戏小号, 其会从1开始为游戏小号编码GAID, 只增不减且不复用. 
即使删除了之前的游戏, GAID仍会继续增加. 您目前无法通过清空360游戏大厅的用户数据以外的任何手段, 修改使用过的GAID.
为获取GAID. 您需要进行如下操作.

1. 开启需要被自动启用的小号.
2. 在360游戏大厅中, 点击"工具栏 - 更多 - 放到桌面".
3. 找到桌面被添加的图片, 右键"属性".
4. 找到"快捷方式"标签栏.
5. 找到"目标"行. 找到类似下文部分: -action:opengame -gid:1 -gaid:1
6. -gaid:x 中的x即为GAID.
7. 删除该快捷方式. 目的仅是获取GAID.

◆ 正式配置 ◆

这非常简单
1. 启动您的360游戏大厅, 启动对应的游戏, 登录对应账号.
2. 点击 "一键获取-游戏路径".
3. 输入每个小号的GAID. 如果仅用于启动一个小号, 2P的GAID可以随便填.
4. 保存. 
之后您就可以尽情体验啦~

◆ 关于多FAA ◆

如果您启用了两个及以上的FAA的开关游戏大厅功能. 请阅读本段.

问题: 360游戏大厅启动同一游戏第一个小号窗口名称为＂游戏名＂, 更多小号为＂小号名 | 游戏名＂. 在自动开关游戏大厅后如果定时同时启动多个FAA, 将造成混乱.

解决方案: 我们提供两套解决方案, 您可以任选其一.
A. 在360里面第一个号留空占位，长期开启, 占住没有小号名的第一个窗口.
B. 轮次启动的多个FAA中，指定一个FAA第一个启动（所有定时时间往前一分钟），且其1P角色在FAA中注册的小号名为空.

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
