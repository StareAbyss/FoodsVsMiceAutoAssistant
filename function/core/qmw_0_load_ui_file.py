import os
import sys

from PyQt6 import uic, QtGui, QtCore, QtWidgets
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QListWidgetItem, QListWidget, QSystemTrayIcon, QMenu, QWidget, QLabel,
    QComboBox, QGroupBox, QGridLayout, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QCheckBox,
)

from function.common.get_system_dpi import get_system_dpi
from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
# noinspection PyUnresolvedReferences
from function.qrc import theme_rc, GTRONICK_rc
# 虽然ide显示上面这行没用，但实际是用来加载相关资源的，不可删除,我用奇妙的方式强制加载了
from function.widget.CusIcon import create_qt_icon
from function.widget.SearchableComboBox import SearchableComboBox


class QMainWindowLoadUI(QtWidgets.QMainWindow):
    """读取.ui文件创建类 并加上一些常用方法"""

    # 注意：
    # 若ui界面文件是个对话框，那么MyApp就必须继承 QDialog
    # 若ui界面文件是个MainWindow，那么MyApp就必须继承 QMainWindow
    def __init__(self):
        # 继承父方法
        super().__init__()

        # 加载 ui文件
        uic.loadUi(os.path.join(PATHS["root"], 'resource', 'ui', 'FAA_3.0.ui'), self)

        def init_secret_inputs() -> None:
            """统一配置密码、二级密码和礼包链接等密文输入框。"""
            icon_color = self.palette().color(QtGui.QPalette.ColorRole.Text)

            secret_inputs = (
                self.LoginQQSpacePassword1PInput,
                self.LoginQQSpacePassword2PInput,
                self.Login4399Password1PInput,
                self.Login4399Password2PInput,
                self.GetWarmGift_1P_Link,
                self.GetWarmGift_2P_Link,
                self.Level2_1P_Password,
                self.Level2_2P_Password,
            )
            for secret_input in secret_inputs:
                secret_input.setEchoMode(QLineEdit.EchoMode.Password)
                secret_input.setClearButtonEnabled(True)

                visibility_action = secret_input.addAction(
                    create_qt_icon(q_color=icon_color, mode="eye"),
                    QLineEdit.ActionPosition.TrailingPosition,
                )
                visibility_action.setCheckable(True)
                visibility_action.setToolTip("临时显示内容")

                def toggle_visibility(
                        visible: bool,
                        line_edit=secret_input,
                        action=visibility_action,
                ) -> None:
                    """切换当前密文输入框的明文显示状态。"""
                    line_edit.setEchoMode(
                        QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
                    )
                    action.setIcon(create_qt_icon(
                        q_color=icon_color,
                        mode="eye_off" if visible else "eye",
                    ))
                    action.setToolTip("隐藏内容" if visible else "临时显示内容")

                visibility_action.toggled.connect(toggle_visibility)
                secret_input.editingFinished.connect(
                    lambda action=visibility_action: action.setChecked(False)
                )

        def init_login_settings_ui() -> None:
            """创建登录设置区域，并根据一级区服切换其专用设置。"""

            content_layout = self.AdvancedSettingsArea.widget().layout()

            def resize_content_height() -> None:
                """只按内容调整高度，避免平台切换时内容区宽度跳动。"""
                current_width = self.AdvancedSettingsAreaWidget.width()
                content_layout.activate()
                self.AdvancedSettingsAreaWidget.resize(
                    current_width,
                    content_layout.sizeHint().height(),
                )

            def refresh_login_platform_ui(platform: str) -> None:
                """只显示当前一级区服需要用户填写的设置。"""
                is_4399 = platform == "4399"
                is_qq_space = platform == "QQ空间"
                self.Login4399Group.setVisible(is_4399)
                self.LoginQQSpaceServerGroup.setVisible(is_qq_space)
                self.LoginQQSpaceGroup.setVisible(is_qq_space)
                help_text = {
                    "4399": "[4399] 总是选择最近登录服务器。需要自动登录时，请填写并保存下方的 4399 账号和密码。",
                    "QQ空间": "[QQ空间] 请选择具体区服，并按需设置 QQ 登录方式。",
                    "QQ大厅": "[QQ大厅] 将直接点击开始游戏进入服务器。不支持自动登录。",
                }
                self.LoginPlatformHelpLabel.setText(help_text.get(platform, ""))
                resize_content_height()

            self.LoginSettingsGroup = QWidget(self.AdvancedSettingsAreaWidget)
            self.LoginSettingsGroup.setObjectName("LoginSettingsGroup")
            login_layout = QVBoxLayout(self.LoginSettingsGroup)
            login_layout.setContentsMargins(5, 5, 5, 5)
            login_layout.setSpacing(5)

            title_layout = QHBoxLayout()
            title_layout.addStretch(2)
            title = QLabel("登录设置")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet("font-weight: bold;")
            title_layout.addWidget(title, 1)
            title_layout.addStretch(6)
            login_layout.addLayout(title_layout)

            self.LoginPlatformHelpLabel = QLabel()
            self.LoginPlatformHelpLabel.setWordWrap(True)
            login_layout.addWidget(self.LoginPlatformHelpLabel)

            # 等待选服按钮适用于所有平台，始终展示在区服专用设置之前。
            self.OtherSettingsLayout.removeWidget(self.LoginServerWaitGroup)
            login_layout.addWidget(self.LoginServerWaitGroup)
            self.LoginServerWaitTimeInput.setValidator(
                QtGui.QIntValidator(0, 3600, self.LoginServerWaitTimeInput)
            )

            self.LoginQQSpaceServerGroup = QGroupBox("QQ空间 - 具体区服")
            self.LoginQQSpaceServerGroup.setObjectName("LoginQQSpaceServerGroup")
            qq_space_server_layout = QGridLayout(self.LoginQQSpaceServerGroup)
            qq_space_server_layout.addWidget(QLabel("选择区服"), 0, 0)
            self.LoginQQSpaceServerCombo = QComboBox()
            self.LoginQQSpaceServerCombo.setObjectName("LoginQQSpaceServerCombo")
            self.LoginQQSpaceServerCombo.addItems([
                "QQ空间服最近登录",
                "3366 1服",
                "3366 2服",
                "3366 3服",
                "3366 4服",
                "3366 5服",
                "3366 6服",
            ])
            self.LoginQQSpaceServerCombo.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            qq_space_server_layout.addWidget(self.LoginQQSpaceServerCombo, 0, 1)
            qq_space_server_layout.setColumnStretch(1, 1)
            login_layout.addWidget(self.LoginQQSpaceServerGroup)

            self.Login4399Group = QGroupBox("4399 - 账号密码登录")
            self.Login4399Group.setObjectName("Login4399Group")
            login_4399_layout = QGridLayout(self.Login4399Group)
            self.Login4399UsePasswordCheckBox = QCheckBox("找不到选服按钮时，使用账号密码登录")
            self.Login4399UsePasswordCheckBox.setObjectName("Login4399UsePasswordCheckBox")
            login_4399_layout.addWidget(self.Login4399UsePasswordCheckBox, 0, 0, 1, 2)

            for row, player in ((1, 1), (2, 2)):
                login_4399_layout.addWidget(QLabel(f"{player}P 账号"), row, 0)
                account_layout = QHBoxLayout()
                username = QLineEdit()
                username.setObjectName(f"Login4399Username{player}PInput")
                username.setPlaceholderText("4399账号")
                password = QLineEdit()
                password.setObjectName(f"Login4399Password{player}PInput")
                password.setPlaceholderText("密码")
                password.setEchoMode(QLineEdit.EchoMode.Password)
                setattr(self, f"Login4399Username{player}PInput", username)
                setattr(self, f"Login4399Password{player}PInput", password)
                account_layout.addWidget(username)
                account_layout.addWidget(password)
                login_4399_layout.addLayout(account_layout, row, 1)

            self.Login4399SaveButton = QPushButton("保存 4399 登录信息")
            self.Login4399SaveButton.setObjectName("Login4399SaveButton")
            login_4399_layout.addWidget(self.Login4399SaveButton, 3, 0, 1, 2)
            login_layout.addWidget(self.Login4399Group)

            # QQ空间的登录方式属于登录模块，移入当前区域。
            self.OtherSettingsLayout.removeWidget(self.LoginQQSpaceGroup)
            login_layout.addWidget(self.LoginQQSpaceGroup)

            # 旧 UI 使用高度为1000的占位项填充固定高度页面。内容区改为自适应高度后，
            # 这些占位项会直接形成巨大空隙，因此只保留布局本身的统一间距。
            sections = (
                self.DailyTasksSettingsGroup,
                self.ControlSettingsGroup,
                self.LoginSettingsGroup,
                self.BattleSettingsGroup,
                self.OtherSettingsGroup,
            )
            for section in sections:
                content_layout.removeWidget(section)
            for index in range(content_layout.count() - 1, -1, -1):
                if content_layout.itemAt(index).spacerItem() is not None:
                    content_layout.takeAt(index)
            for row, section in enumerate(sections):
                content_layout.addWidget(section, row, 0)
            resize_content_height()

            self.LoginPlatformCombo.currentTextChanged.connect(refresh_login_platform_ui)
            refresh_login_platform_ui(self.LoginPlatformCombo.currentText())

        # 设置窗口名称
        self.setWindowTitle("FAA - 本软件免费且开源")

        # 设置系统图标
        self.setWindowIcon(QIcon(os.path.join(PATHS["logo"], '圆角-FetDeathWing-256x-AllSize.ico')))

        # 设置显示版本号
        self.Title_Version.setText(EXTRA.VERSION)

        # 获取 dpi & zoom 仅能在类中调用
        EXTRA.ZOOM_RATE = get_system_dpi() / 96
        T_ACTION_QUEUE_TIMER.set_zoom_rate(EXTRA.ZOOM_RATE)

        # 获取系统样式(日夜)
        EXTRA.THEME = self.get_theme()

        # 获取系统样式(高亮颜色)
        EXTRA.THEME_HIGHLIGHT_COLOR = QtWidgets.QApplication.palette().color(QtGui.QPalette.ColorRole.Highlight).name()

        # 配置 进阶设置 导航栏交互
        self.adv_opt_synchronizing = None
        self.adv_opt_sections: list = []
        init_login_settings_ui()
        init_secret_inputs()
        self.replace_widgets_no_wheel()
        self.init_advanced_settings_connection()

        # 添加系统托盘功能
        self.tray_icon = None
        self.init_tray_icon()

        # 绑定最小化按钮
        self.Button_MostMinimized.clicked.connect(self.minimize_to_tray)
        #淡入动画
        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in_animation.setDuration(300)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)

    def get_theme(self):
        if self.palette().color(QtGui.QPalette.ColorRole.Window).lightness() < 128:
            return "dark"
        else:
            return "light"

    """任何ui都要设置的样式表"""

    def set_theme_common(self):
        """
        在应用皮肤样式表之前设定
        """
        # 进行特殊的无边框和阴影处理
        self.set_no_border()

        # 设置logo阴影
        self.set_logo_shadow()

        # 根据系统样式,设定开关图标
        self.set_exit_and_minimized_btn_icon()

        # 根据系统样式, 设置自定义控件的样式
        self.set_customize_widget_style()

        # 部分图片元素的加载
        self.set_image_resource()

    def set_common_theme(self):
        """
        在应用皮肤样式表之后设定
        :return:
        """

        style_sheet = self.styleSheet()

        # 增加边框
        style_sheet += "#MainFrame{border-radius: 8px; border: 1px solid #3c3d3e;} "

        style_sheet = self.styleSheet()

        # 获取当前样式表 然后在此基础上增加背景色, 根据白天黑夜主题为不同颜色
        match EXTRA.THEME:
            case "dark":
                style_sheet += "#MainFrame{background-color: #1e1e1e;}"
            case "light":
                style_sheet += "#MainFrame{background-color: #FFFFFF;}"

        self.setStyleSheet(style_sheet)

    def set_logo_shadow(self):
        effect_shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        effect_shadow.setOffset(0, 0)  # 偏移
        effect_shadow.setBlurRadius(6)  # 阴影半径
        effect_shadow.setColor(QtCore.Qt.GlobalColor.gray)  # 阴影颜色
        self.Title_Logo.setGraphicsEffect(effect_shadow)  # 将设置套用到widget窗口中

    def set_no_border(self):
        # 设置无边框窗口
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)

        # 设背景为透明
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_exit_and_minimized_btn_icon(self):
        """
        设置退出按钮和最小化按钮样式，需已获取主题
        :return:
        """
        # 根据系统样式,设定开关图标
        q_color = QtGui.QColor(240, 240, 240) if EXTRA.THEME == "dark" else QtGui.QColor(15, 15, 15)
        self.Button_Exit.setIcon(create_qt_icon(q_color=q_color, mode="x"))
        self.Button_Minimized.setIcon(create_qt_icon(q_color=q_color, mode="-"))
        self.Button_MostMinimized.setIcon(create_qt_icon(q_color=q_color, mode="v"))

    def set_customize_widget_style(self):
        # 查找所有 SearchableComboBox 实例
        searchable_comboboxes = self.findChildren(SearchableComboBox)

        # 给他们全都改一改
        for combobox in searchable_comboboxes:
            combobox.set_style(theme=EXTRA.THEME)

    def set_image_resource(self):

        # title - logo
        cus_path = os.path.join(PATHS["root"], 'resource', 'logo', '圆角-FetDeathWing-450x.png')
        cus_path = cus_path.replace("\\", "/")  # pyqt 使用正斜杠

        pixmap = QtGui.QPixmap(cus_path).scaled(
            40,
            40,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation
        )
        self.Title_Logo.setPixmap(pixmap)
        self.Title_Logo.setFixedSize(40, 40)
        self.Title_Logo.setScaledContents(True)  # 确保图片自适应控件大小

        # 背景图
        cus_path = os.path.join(PATHS["root"], 'resource', 'ui', 'firefly.png')
        cus_path = cus_path.replace("\\", "/")  # pyqt 使用正斜杠
        style_sheet = f"""
            #SkinWidget{{
            background-image: url({cus_path});
            background-repeat: no-repeat;
            background-position: center;
            background-size: contain;
            border: none;
            }}
        """

        self.SkinWidget.setStyleSheet(style_sheet)

    """仅默认ui需要设置的样式表"""

    def set_theme_default(self):

        # 初始化样式表
        self.MainFrame.setStyleSheet("")

        # 设置箭头特殊样式
        self.set_arrow_btn_icon()

        # 设置tab栏特殊样式
        self.set_tab_bar_stylesheet()

    def set_main_window_shadow(self):
        # 添加阴影
        effect_shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        effect_shadow.setOffset(0, 0)  # 偏移
        effect_shadow.setBlurRadius(8)  # 阴影半径
        effect_shadow.setColor(QtCore.Qt.GlobalColor.black)  # 阴影颜色
        self.MainFrame.setGraphicsEffect(effect_shadow)  # 将设置套用到widget窗口中

    def set_tab_bar_stylesheet(self):

        style_sheet = self.MainFrame.styleSheet()
        selected_text_color = "#FFFFFF" if EXTRA.THEME == "dark" else "#000000"

        style_sheet += f"""
            QTabBar::tab {{
                min-width: 136px;  /* 最小宽度 */
                height: 20px;
                border-style: solid;
                border-top-color: transparent;
                border-right-color: transparent;
                border-left-color: transparent;
                border-bottom-color: transparent;
                border-bottom-width: 1px;
                border-style: solid;
                color: #808086;
                padding: 3px;
                margin-left:3px;
            }}
            QTabBar::tab:selected, QTabBar::tab:last:selected, QTabBar::tab:hover {{
                border-style: solid;
                border-top-color: transparent;
                border-right-color: transparent;
                border-left-color: transparent;
                border-bottom-color: {EXTRA.THEME_HIGHLIGHT_COLOR};
                border-bottom-width: 2px;
                border-style: solid;
                color: {selected_text_color};
                padding-left: 3px;
                padding-bottom: 2px;
                margin-left:3px;
            }}
            QTabWidget::tab-bar {{
                alignment: center;
            }}
            QTabWidget::pane{{
                border:none;
            }}
            """

        self.MainFrame.setStyleSheet(style_sheet)

    def set_arrow_btn_icon(self):

        # 设置图标
        color = QtGui.QColor(240, 240, 240) if EXTRA.THEME == "dark" else QtGui.QColor(15, 15, 15)
        prev_icon = create_qt_icon(q_color=color, mode="<-")
        next_icon = create_qt_icon(q_color=color, mode="->")

        # 找到前后月份按钮
        prev_month_button = self.DateSelector.findChild(QtWidgets.QToolButton, "qt_calendar_prevmonth")
        next_month_button = self.DateSelector.findChild(QtWidgets.QToolButton, "qt_calendar_nextmonth")

        prev_month_button.setIcon(prev_icon)
        next_month_button.setIcon(next_icon)

    """重写拖动窗口"""

    def init_tray_icon(self):
        # 创建系统托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        tray_icon_path = os.path.join(PATHS["logo"], '圆角-FetDeathWing-256x-AllSize.ico')
        self.tray_icon.setIcon(QIcon(tray_icon_path))
        name=self.Name1P_Input.text()
        self.tray_icon.setToolTip(f"FAA -{name} 正在后台运行")

        # 创建托盘菜单
        tray_menu = QMenu()
        restore_action = tray_menu.addAction("一键启动")
        quit_action = tray_menu.addAction("退出程序")

        # 连接菜单动作
        restore_action.triggered.connect(self.todo_click_btn)
        quit_action.triggered.connect(self.close)

        # 设置托盘菜单
        self.tray_icon.setContextMenu(tray_menu)

        # 双击托盘图标恢复
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def minimize_to_tray(self):
        # 隐藏主窗口
        self.hide()
        self.tray_icon.showMessage(
            "FAA 已最小化",
            "程序正在后台运行",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def restore_from_tray(self):
        # 恢复窗口显示
        self.show()
        self.setWindowState(Qt.WindowState.WindowActive)

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.restore_from_tray()

    def closeEvent(self, event):
        """
        对MainWindow的函数closeEvent进行重构, 退出软件时弹窗提醒 并且结束所有进程(和内部的线程)
        """
        self.tray_icon.hide()
        event.accept()
        # 用过sys.exit(0)和sys.exit(app.exec())，但没起效果
        os._exit(0)

    # 切换最大化与正常大小
    def maxOrNormal(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # 弹出警告提示窗口确认是否要关闭
    def queryExit(self):
        QtCore.QCoreApplication.instance().exit()

    _startPos = None
    _endPos = None
    _isTracking = None

    # 移动检查
    def moveEvent(self, event):
        # 获取主屏幕几何信息
        screen_geometry = self.screen().availableGeometry()

        # 获取当前窗口几何信息
        window_geometry = self.geometry()

        # 检查窗口是否超出屏幕边界
        x = window_geometry.x()
        y = window_geometry.y()
        width = window_geometry.width()
        height = window_geometry.height()

        # 限制窗口位置
        if x < screen_geometry.left():
            x = screen_geometry.left()
        elif x + width > screen_geometry.right():
            x = screen_geometry.right() - width

        if y < screen_geometry.top():
            y = screen_geometry.top()
        elif y + height > screen_geometry.bottom():
            y = screen_geometry.bottom() - height

        # 如果位置需要调整，则重新设置位置
        if x != window_geometry.x() or y != window_geometry.y():
            self.move(x, y)

        super().moveEvent(event)

    # 鼠标移动事件
    def mouseMoveEvent(self, a0: QtGui.QMouseEvent):
        if self._startPos:
            self._endPos = a0.pos() - self._startPos
            # 移动窗口
            self.move(self.pos() + self._endPos)

    # 鼠标按下事件
    def mousePressEvent(self, a0: QtGui.QMouseEvent):
        # 根据鼠标按下时的位置判断是否在QFrame范围内
        if self.childAt(a0.pos().x(), a0.pos().y()).objectName() == "FrameTitle":
            # 判断鼠标按下的是左键
            if a0.button() == QtCore.Qt.MouseButton.LeftButton:
                self._isTracking = True
                # 记录初始位置
                self._startPos = QtCore.QPoint(a0.pos().x(), a0.pos().y())

    # 鼠标松开事件
    def mouseReleaseEvent(self, a0: QtGui.QMouseEvent):
        if a0.button() == QtCore.Qt.MouseButton.LeftButton:
            self._isTracking = False
            self._startPos = None
            self._endPos = None

    """进阶设定 导航栏交互 初始化"""

    def init_advanced_settings_connection(self):

        # 初始化同步标志
        self.adv_opt_synchronizing = False

        # 获取实际内容布局
        content_layout = self.AdvancedSettingsArea.widget().layout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(20)

        current_width = self.AdvancedSettingsAreaWidget.width()
        content_layout.activate()
        self.AdvancedSettingsAreaWidget.resize(
            current_width,
            content_layout.sizeHint().height(),
        )
        # 列表内容 -> 对应的元素
        self.adv_opt_sections = {
            "日常任务": self.DailyTasksSettingsGroup,
            "外部控制": self.ControlSettingsGroup,
            "战斗设置": self.BattleSettingsGroup,
            "登录设置": self.LoginSettingsGroup,
            "其它设置": self.OtherSettingsGroup
        }

        # 添加导航项和内容块
        for title, tar_item in self.adv_opt_sections.items():
            # 添加导航项
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, tar_item)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.AdvancedSettingsNavigationList.addItem(item)

        # 设置样式
        self.AdvancedSettingsNavigationList.setStyleSheet("""
            QListWidget::item {
                padding: 15px;
                border-bottom: 1px solid #ddd;
            }
            QListWidget::item:selected {
                background-color: #e0f0ff;
                color: #0066cc;
                font-weight: bold;
            }
        """)

        # 连接信号
        self.AdvancedSettingsNavigationList.itemClicked.connect(self.on_nav_item_clicked)
        self.AdvancedSettingsArea.verticalScrollBar().valueChanged.connect(self.on_settings_scroll)

        def open_auto_login_settings() -> None:
            """从首页跳转到进阶功能中的登录设置。"""
            self.tabWidget.setCurrentWidget(self.Tab3)
            for index in range(self.AdvancedSettingsNavigationList.count()):
                item = self.AdvancedSettingsNavigationList.item(index)
                if item.data(Qt.ItemDataRole.UserRole) is self.LoginSettingsGroup:
                    self.AdvancedSettingsNavigationList.setCurrentItem(item)
                    self.on_nav_item_clicked(item)
                    break

        self.LoginAutoSettingsButton.clicked.connect(open_auto_login_settings)


    def on_nav_item_clicked(self, item):
        if self.adv_opt_synchronizing:
            return

        # 获取关联的组件 (一个布局)
        section = item.data(Qt.ItemDataRole.UserRole)

        # 计算滚动位置（滚动到区块中间）
        scroll_bar = self.AdvancedSettingsArea.verticalScrollBar()
        widget_position = section.y()
        viewport_height = self.AdvancedSettingsArea.viewport().height()
        widget_height = section.size().height()

        # 计算目标滚动位置
        target_y = widget_position + (widget_height - viewport_height) // 2
        scroll_bar.setValue(target_y)

    def on_settings_scroll(self):

        if self.adv_opt_synchronizing:
            return

        # 获取当前滚动信息
        scroll_bar = self.AdvancedSettingsArea.verticalScrollBar()
        current_position = scroll_bar.value()
        viewport_height = self.AdvancedSettingsArea.viewport().height()
        middle_position = current_position + viewport_height // 2

        # 查找最接近的区块
        closest_item = None
        min_distance = float('inf')

        for i in range(self.AdvancedSettingsNavigationList.count()):
            item = self.AdvancedSettingsNavigationList.item(i)
            section = item.data(Qt.ItemDataRole.UserRole)

            # 计算区块中间位置
            section_top = section.y()
            section_height = section.size().height()
            section_middle = section_top + section_height // 2

            # 计算距离差值
            distance = abs(section_middle - middle_position)
            if distance < min_distance:
                min_distance = distance
                closest_item = item

        # 更新导航选中状态
        if closest_item:
            self.adv_opt_synchronizing = True
            self.AdvancedSettingsNavigationList.setCurrentItem(closest_item)
            self.AdvancedSettingsNavigationList.scrollToItem(
                closest_item,
                QListWidget.ScrollHint.PositionAtCenter
            )
            self.adv_opt_synchronizing = False

    """
    移除部分控件的鼠标操作
    """

    def replace_widgets_no_wheel(self):

        w_names = [
            "login_first",
            "login_second",
            "CusFlopTimesValueInput",
            "CusCPSValueInput",
            "CusLowestFPSValueInput",
            "CusFullBanTimeValueInput",
            "MaxBattleTimeValueInput",
            "CusAutoCarryCardValueInput",
            "AccelerateValue",
            "AccelerateCustomizeValue",
            "BattleSeniorIntervalValueInput",
            "senior_log_clean",
            "other_log_clean",
        ]
        for w_name in w_names:
            widget = getattr(self, w_name)
            widget.wheelEvent = lambda event: event.ignore()


if __name__ == "__main__":
    def main():
        # 实例化 PyQt后台管理
        app = QtWidgets.QApplication(sys.argv)

        # 实例化 主窗口
        my_main_window = QMainWindowLoadUI()

        my_main_window.show()

        # 运行主循环，必须调用此函数才可以开始事件处理
        app.exec()

        sys.exit()


    main()
