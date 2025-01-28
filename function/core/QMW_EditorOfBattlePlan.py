import copy
import json
import os
import sys
import uuid

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QKeySequence, QIcon, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGridLayout, QPushButton, QWidget, QFileDialog, QVBoxLayout, QLabel, QComboBox,
    QLineEdit, QHBoxLayout, QTextEdit, QListWidget, QMessageBox, QSpinBox, QListWidgetItem, QFrame, QAbstractItemView,
    QSpacerItem, QSizePolicy, QDoubleSpinBox)

from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.widget.MultiLevelMenu import MultiLevelMenu

double_click_card_list = pyqtSignal(object)

"""
战斗方案编辑器
致谢：八重垣天知
"""


def calculate_text_width(text):
    """
    计算字符串的实际宽度，中文字符占两个字节，西文字符占一个字节。
    """
    width_c = 0
    width_e = 0
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            # 中文字符
            width_c += 1
        else:
            # 西文字符
            width_e += 1
    return width_c, width_e


def hide_layout(layout):
    """
    隐藏布局中的所有子部件
    :param layout: 要隐藏的布局对象
    """
    for i in range(layout.count()):
        item = layout.itemAt(i)
        widget = item.widget()
        if widget:
            widget.setVisible(False)  # 隐藏子部件
        else:
            hide_layout(item.layout())  # 如果是子布局，递归隐藏子布局


def show_layout(layout):
    """
    显示布局中的所有子部件
    :param layout: 要显示的布局对象
    """
    for i in range(layout.count()):
        item = layout.itemAt(i)
        widget = item.widget()
        if widget:
            widget.setVisible(True)  # 显示子部件
        else:
            show_layout(item.layout())  # 如果是子布局，递归显示子布局


class QMWEditorOfBattlePlan(QMainWindow):

    def __init__(self, func_open_tip):
        super().__init__()

        """内部数据表和功能参数"""

        # 获取全部关卡信息
        with open(file=PATHS["config"] + "//stage_info.json", mode="r", encoding="UTF-8") as file:
            self.stage_info_all = json.load(file)

        # 当前选择的关卡的信息
        self.stage_info = {}

        # 当前子方案, 例如 默认 波次变阵方案 两个参数确定
        self.current_wave = 0
        self.sub_plan = []

        # 数据dict
        self.json_data = {
            "tips": "",
            "player": [],
            "card": {
                "default": [],
                "wave": {
                    "1": [],
                    "2": [],
                    "3": [],
                    "4": [],
                    "5": [],
                    "6": [],
                    "7": [],
                    "8": [],
                    "9": [],
                    "10": [],
                    "11": [],
                    "12": [],
                    "13": []
                },
            "timer_plan": {
                "wave": {},
                "gem": {}
            }
            }
        }

        # 复制粘贴功能
        self.be_copied_wave_id = None

        # 当前被选中正在编辑的项目的index
        self.current_card_index = None
        self.current_time_put_index= None

        # 撤销/重做功能
        self.undo_stack = []
        self.redo_stack = []
        self.undo_shortcut = QShortcut(QKeySequence('Ctrl+Z'), self)
        self.redo_shortcut = QShortcut(QKeySequence('Ctrl+Y'), self)
        self.undo_shortcut.activated.connect(self.undo)
        self.redo_shortcut.activated.connect(self.redo)

        self.mode=1#模式1是常规遍历队列式放卡，模式二为定时放卡
        self.change = True

        # 加载Json文件
        self.file_path = None

        """布局和控件放置"""

        # 主布局 - 竖直布局
        self.LayMain = QVBoxLayout()

        def init_ui_lay_tip():
            """提示编辑器"""

            self.WidgetTipsEditor = QTextEdit()
            self.WidgetTipsEditor.setPlaceholderText('在这里编辑提示文本...')
            self.LayMain.addWidget(self.WidgetTipsEditor)
            # self.WidgetTipsEditor.setMaximumHeight(100)

        def init_ui_layout_bottom():
            """
            下方主要布局 横向 包括三块 各种详细参数编辑 Card列表 棋盘
            """

            self.LayoutMainBottom = QHBoxLayout()
            self.LayMain.addLayout(self.LayoutMainBottom)

            def init_ui_lay_left():
                """
                左侧布局，竖向布局，包括波次编辑，放卡动作参数编辑，方案保存读取
                """
                self.LayLeft = QVBoxLayout()
                self.LayoutMainBottom.addLayout(self.LayLeft)


                def init_ui_lay_left_top():
                    # 关卡选择按钮(多级列表)
                    self.WidgetStageSelector = MultiLevelMenu(title="选择关卡, 显示障碍")
                    self.LayLeft.addWidget(self.WidgetStageSelector)

                    # 教学按钮
                    WidgetCourseButton = QPushButton('点击打开教学')
                    WidgetCourseButton.clicked.connect(func_open_tip)
                    self.LayLeft.addWidget(WidgetCourseButton)

                    # 点击切换放卡编辑模式
                    self.ModeChangeButton = QPushButton('点击切换放卡编辑模式')
                    self.LayLeft.addWidget(self.ModeChangeButton)

                def init_ui_lay_wave_editor():
                    """波次编辑器"""

                    self.LayWaveEditor = QVBoxLayout()
                    self.LayLeft.addLayout(self.LayWaveEditor)

                    title_label = QLabel('切换波次')
                    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                    self.LayWaveEditor.addWidget(title_label)

                    for v_index in range(3):
                        lay_line = QHBoxLayout()
                        for h_index in range(5):
                            i = v_index * 5 + h_index
                            if i != 14:
                                button = QPushButton(f"{i}")
                                button.setObjectName(f"changeWaveButton_{i}")
                                button.clicked.connect(
                                    lambda checked, wave=i: (
                                        self.click_wave_button(be_clicked_button_id=wave)
                                    )
                                )
                                button.setToolTip(f"切换到第{i}波方案")
                            else:
                                button = QPushButton(f"-")
                            button.setFixedWidth(45)
                            lay_line.addWidget(button)
                        self.LayWaveEditor.addLayout(lay_line)

                    # 添加复制按钮
                    self.copy_wave_button = QPushButton('复制')
                    self.copy_wave_button.clicked.connect(self.copy_wave_plan)
                    self.copy_wave_button.setToolTip(f"复制当前选中波次方案, 保存到剪切板")

                    # 添加粘贴按钮 锁定 不可使用
                    self.paste_wave_button = QPushButton('粘贴')
                    self.paste_wave_button.clicked.connect(self.paste_wave_plan)
                    self.paste_wave_button.setEnabled(False)
                    self.copy_wave_button.setToolTip(f"将剪切板中的方案, 粘贴到当前选中波次")

                    # 应用到全部
                    self.apply_to_all_button = QPushButton('应用到全部')
                    self.apply_to_all_button.clicked.connect(self.apply_to_all_wave_plan)
                    self.apply_to_all_button.setToolTip("复制当前选中波次方案, 粘贴到全部波次")

                    # 创建水平布局，来容纳按钮
                    LayWaveAction = QHBoxLayout()
                    LayWaveAction.addWidget(self.copy_wave_button)
                    LayWaveAction.addWidget(self.paste_wave_button)
                    LayWaveAction.addWidget(self.apply_to_all_button)
                    self.LayLeft.addLayout(LayWaveAction)

                def init_ui_lay_card_editor():
                    """单组放卡操作 - 状态编辑器"""

                    self.LayCardEditor = QVBoxLayout()
                    self.LayLeft.addLayout(self.LayCardEditor)

                    title_label = QLabel('放卡操作参数设定')
                    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                    self.LayCardEditor.addWidget(title_label)

                    self.WidgetAddCardButton = QPushButton('新增一组放卡操作')
                    self.LayCardEditor.addWidget(self.WidgetAddCardButton)

                    # ID
                    label = QLabel('ID')

                    self.WidgetIdInput = QSpinBox()
                    self.WidgetIdInput.setFixedWidth(140)
                    self.WidgetIdInput.setToolTip("id代表卡在卡组中的顺序")
                    self.WidgetIdInput.setRange(1, 21)

                    layout = QHBoxLayout()
                    layout.addWidget(label)
                    layout.addWidget(self.WidgetIdInput)
                    self.LayCardEditor.addLayout(layout)

                    # 名称
                    label = QLabel('名称')

                    self.WidgetNameInput = QLineEdit()
                    self.WidgetNameInput.setFixedWidth(140)
                    self.WidgetNameInput.setToolTip(
                        "名称标识是什么卡片\n"
                        "手动带卡: 能让用户看懂该带啥就行.\n"
                        "自动带卡: 需要遵从命名规范, 请查看右上角教学或相关文档."
                    )

                    layout = QHBoxLayout()
                    layout.addWidget(label)
                    layout.addWidget(self.WidgetNameInput)
                    self.LayCardEditor.addLayout(layout)

                    # 遍历
                    tooltips = "队列和遍历不知道是什么可以全true, 具体请参见详细文档"
                    label = QLabel('遍历')
                    label.setToolTip(tooltips)

                    self.WidgetErgodicInput = QComboBox()
                    self.WidgetErgodicInput.setFixedWidth(140)
                    self.WidgetErgodicInput.addItems(['true', 'false'])
                    self.WidgetErgodicInput.setToolTip(tooltips)

                    layout = QHBoxLayout()
                    layout.addWidget(label)
                    layout.addWidget(self.WidgetErgodicInput)
                    self.LayCardEditor.addLayout(layout)

                    # 队列
                    tooltips = "队列和遍历不知道是什么可以全true, 具体请参见详细文档"
                    label = QLabel('队列')
                    label.setToolTip(tooltips)

                    self.WidgetQueueInput = QComboBox()
                    self.WidgetQueueInput.setFixedWidth(140)
                    self.WidgetQueueInput.addItems(['true', 'false'])
                    self.WidgetQueueInput.setToolTip(tooltips)

                    layout = QHBoxLayout()
                    layout.addWidget(label)
                    layout.addWidget(self.WidgetQueueInput)
                    self.LayCardEditor.addLayout(layout)

                    # 幻鸡优先级
                    tooltips = "卡片使用幻幻鸡复制的优先级, 0代表不使用，值越高则使用优先级越高"
                    label = QLabel('幻鸡优先级')
                    label.setToolTip(tooltips)

                    self.WidgetKunInput = QSpinBox()
                    self.WidgetKunInput.setFixedWidth(140)
                    self.WidgetKunInput.setRange(0, 9)
                    self.WidgetKunInput.setToolTip(tooltips)

                    layout = QHBoxLayout()
                    layout.addWidget(label)
                    layout.addWidget(self.WidgetKunInput)
                    self.LayCardEditor.addLayout(layout)

                    # 删卡

                    self.WidgetDeleteCardButton = QPushButton('删除选中放卡操作')
                    self.LayCardEditor.addWidget(self.WidgetDeleteCardButton)
                def init_ui_lay_card_editor_time_mode():
                    """单组放卡操作 - 状态编辑器"""
                    self.LayTimeCardEditor = QVBoxLayout()
                    self.LayLeft.addLayout(self.LayTimeCardEditor)
                    title_label = QLabel('定时放卡操作参数设定')
                    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                    self.LayTimeCardEditor.addWidget(title_label)

                    self.WidgetAddTimePutCardButton = QPushButton('新增单个定时放卡操作')
                    self.LayTimeCardEditor.addWidget(self.WidgetAddTimePutCardButton)

                    # ID
                    label = QLabel('ID')

                    self.WidgetIdInput2 = QSpinBox()
                    self.WidgetIdInput2.setFixedWidth(140)
                    self.WidgetIdInput2.setToolTip("id代表卡在卡组中的顺序")
                    self.WidgetIdInput2.setRange(1, 21)

                    layout = QHBoxLayout()
                    layout.addWidget(label)
                    layout.addWidget(self.WidgetIdInput2)
                    self.LayTimeCardEditor.addLayout(layout)

                    # 名称
                    label = QLabel('名称')

                    self.WidgetNameInput2 = QLineEdit()
                    self.WidgetNameInput2.setFixedWidth(140)
                    self.WidgetNameInput2.setToolTip(
                        "名称标识是什么卡片\n"
                        "能让用户看懂该带啥就行.\n"
                    )

                    layout = QHBoxLayout()
                    layout.addWidget(label)
                    layout.addWidget(self.WidgetNameInput2)
                    self.LayTimeCardEditor.addLayout(layout)
                    # 放卡时间
                    tooltips = "识别到对应波次后，会在对应秒数后放置卡片"
                    label = QLabel('放卡时间')
                    label.setToolTip(tooltips)

                    self.WidgetTimeInput =  QDoubleSpinBox()
                    self.WidgetTimeInput.setFixedWidth(140)
                    self.WidgetTimeInput.setToolTip(tooltips)
                    self.WidgetTimeInput.setRange(0, 9999)

                    layout = QHBoxLayout()
                    layout.addWidget(label)
                    layout.addWidget(self.WidgetTimeInput)
                    self.LayTimeCardEditor.addLayout(layout)

                    #前铲
                    tooltips = "是否会在放卡的前0.5秒铲除该点以腾出位置放卡"
                    label = QLabel('前铲')
                    label.setToolTip(tooltips)

                    self.WidgetShovelFrontInput = QComboBox()
                    self.WidgetShovelFrontInput.setFixedWidth(140)
                    self.WidgetShovelFrontInput.addItems(['true', 'false'])
                    self.WidgetShovelFrontInput.setToolTip(tooltips)
                    self.WidgetShovelFrontInput.setCurrentIndex(1)

                    layout = QHBoxLayout()
                    layout.addWidget(label)
                    layout.addWidget(self.WidgetShovelFrontInput)
                    self.LayTimeCardEditor.addLayout(layout)

                    # 后铲
                    tooltips = "是否会在指定的秒数后铲除该点"
                    label = QLabel('后铲')
                    label.setToolTip(tooltips)

                    self.WidgetShovelBackInput = QComboBox()
                    self.WidgetShovelBackInput.setFixedWidth(140)
                    self.WidgetShovelBackInput.addItems(['true', 'false'])
                    self.WidgetShovelBackInput.setToolTip(tooltips)
                    self.WidgetShovelBackInput.setCurrentIndex(1)

                    layout = QHBoxLayout()
                    layout.addWidget(label)
                    layout.addWidget(self.WidgetShovelBackInput)
                    self.LayTimeCardEditor.addLayout(layout)

                    # 放卡时间
                    tooltips = "放置卡片后，几秒后铲除"
                    label = QLabel('后铲时间')
                    label.setToolTip(tooltips)

                    self.WidgetBackTimeInput = QDoubleSpinBox()
                    self.WidgetBackTimeInput.setFixedWidth(140)
                    self.WidgetBackTimeInput.setToolTip(tooltips)
                    self.WidgetBackTimeInput.setRange(0, 9999)

                    layout = QHBoxLayout()
                    layout.addWidget(label)
                    layout.addWidget(self.WidgetBackTimeInput)
                    self.LayTimeCardEditor.addLayout(layout)

                    # 删除单个操作

                    self.WidgetDeleteTimePutCardButton = QPushButton('删除选中放卡操作')
                    self.LayTimeCardEditor.addWidget(self.WidgetDeleteTimePutCardButton)


                def init_ui_lay_save_and_load():
                    """加载和保存按钮"""

                    title_label = QLabel('方案加载与保存')
                    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐

                    self.current_plan_name_label = QLabel("当前方案名:无")
                    self.current_plan_uuid_label = QLabel("当前方案UUID:无")

                    self.ButtonLoadJson = QPushButton('加载')

                    self.ButtonSave = QPushButton('保存')
                    self.ButtonSave.setEnabled(False)

                    self.ButtonSaveAs = QPushButton('另存为')

                    # 创建水平布局，来容纳保存和另存为按钮
                    LaySaveBottom = QHBoxLayout()
                    LaySaveBottom.addWidget(self.ButtonLoadJson)
                    LaySaveBottom.addWidget(self.ButtonSave)
                    LaySaveBottom.addWidget(self.ButtonSaveAs)

                    # 创建垂直布局 放本栏title后水平布局按钮
                    LaySave = QVBoxLayout()
                    LaySave.addWidget(title_label)
                    LaySave.addWidget(self.current_plan_name_label)
                    LaySave.addWidget(self.current_plan_uuid_label)
                    LaySave.addLayout(LaySaveBottom)

                    # 添加到总左侧布局
                    self.LayLeft.addLayout(LaySave)

                def create_vertical_spacer():
                    # 竖向弹簧
                    return QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

                def create_vertical_line():
                    # 横向分割线
                    separator = QFrame()
                    separator.setFrameShape(QFrame.Shape.HLine)
                    separator.setFrameShadow(QFrame.Shadow.Sunken)
                    return separator

                init_ui_lay_left_top()
                self.LayLeft.addItem(create_vertical_spacer())
                self.LayLeft.addWidget(create_vertical_line())
                self.LayLeft.addItem(create_vertical_spacer())
                init_ui_lay_wave_editor()
                self.LayLeft.addItem(create_vertical_spacer())
                self.LayLeft.addWidget(create_vertical_line())
                self.LayLeft.addItem(create_vertical_spacer())
                init_ui_lay_card_editor()
                init_ui_lay_card_editor_time_mode()
                hide_layout(self.LayTimeCardEditor)
                self.LayLeft.addItem(create_vertical_spacer())
                self.LayLeft.addWidget(create_vertical_line())
                self.LayLeft.addItem(create_vertical_spacer())
                init_ui_lay_save_and_load()

            def init_ui_lay_card_list():
                """卡片列表"""
                self.WidgetCardList = QListWidgetDraggable(drop_function=self.card_list_be_dropped)
                self.LayoutMainBottom.addWidget(self.WidgetCardList)
                self.WidgetCardList.setMaximumWidth(260)  # 经过验证的完美数字
            def init_ui_lay_time_put_card_list():
                """定时放卡单元列表"""
                self.WidgetTimePutList = QListWidgetDraggable(drop_function=self.card_list_be_dropped)
                self.LayoutMainBottom.addWidget(self.WidgetTimePutList)
                self.WidgetTimePutList.setMaximumWidth(260)  # 经过验证的完美数字

            def init_ui_lay_chessboard():
                """棋盘布局"""
                self.chessboard_layout = QGridLayout()
                self.LayoutMainBottom.addLayout(self.chessboard_layout)

                # 生成棋盘布局中的元素
                self.chessboard_buttons = []
                self.chessboard_frames = []  # 用于存储QFrame的列表

                for i in range(7):
                    row_buttons = []
                    row_frames = []

                    for j in range(9):
                        # 创建按钮部分
                        btn = ChessButton('')

                        btn.clicked.connect(lambda checked, x=i, y=j: self.place_card(y, x))
                        btn.rightClicked.connect(lambda x=i, y=j: self.remove_card(y, x))
                        self.chessboard_layout.addWidget(btn, i, j)
                        btn.setToolTip(f"当前位置: {j + 1}-{i + 1}")
                        row_buttons.append(btn)

                        btn.setFixedSize(80, 80)

                        # 创建QFrame作为高亮效果的载体
                        frame = QFrame(self)

                        frame.setFrameShadow(QFrame.Shadow.Raised)
                        self.chessboard_layout.addWidget(frame, i, j)
                        frame.lower()  # 确保QFrame在按钮下方
                        frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)  # 防止遮挡按钮

                        # 尽可能让宽和高占满剩余空间
                        # frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                        frame.setFixedSize(80, 80)

                        row_frames.append(frame)

                    self.chessboard_buttons.append(row_buttons)
                    self.chessboard_frames.append(row_frames)

            init_ui_lay_left()
            init_ui_lay_card_list()
            init_ui_lay_chessboard()
            init_ui_lay_time_put_card_list()
            self.WidgetTimePutList.setVisible(False)

        init_ui_lay_tip()
        init_ui_layout_bottom()

        # 设置主控件
        self.central_widget = QWidget()
        self.central_widget.setLayout(self.LayMain)
        self.setCentralWidget(self.central_widget)



        def connect_signal_and_slot():
            """信号和槽函数链接"""

            # 读取json
            self.ButtonLoadJson.clicked.connect(self.open_battle_plan)

            # 保存json
            self.ButtonSaveAs.clicked.connect(self.save_json)
            self.ButtonSave.clicked.connect(self.save_json)

            # 关卡选择
            self.WidgetStageSelector.on_selected.connect(self.stage_changed)

            # 添加卡片
            self.WidgetAddCardButton.clicked.connect(self.add_card)
            #添加定时放卡操作进入备选槽
            self.WidgetAddTimePutCardButton.clicked.connect(self.add_time_put)

            # 删除卡片
            self.WidgetDeleteCardButton.clicked.connect(self.delete_card)
            self.WidgetDeleteTimePutCardButton.clicked.connect(self.delete_time_put)

            # 单击列表更改当前card
            self.WidgetCardList.itemClicked.connect(self.current_card_change)
            self.WidgetTimePutList.itemClicked.connect(self.current_time_put_change)

            # id，名称,遍历，队列控件的更改都连接上更新卡片
            self.WidgetIdInput.valueChanged.connect(self.update_card)
            self.WidgetNameInput.textChanged.connect(self.update_card)
            self.WidgetErgodicInput.currentIndexChanged.connect(self.update_card)
            self.WidgetQueueInput.currentIndexChanged.connect(self.update_card)
            self.WidgetKunInput.valueChanged.connect(self.update_card)
            #定时放卡相关变动函数绑定
            self.WidgetIdInput2.valueChanged.connect(self.update_time_put)
            self.WidgetNameInput2.textChanged.connect(self.update_time_put)
            self.WidgetTimeInput.valueChanged.connect(self.update_time_put)
            self.WidgetBackTimeInput.valueChanged.connect(self.update_time_put)
            self.WidgetShovelFrontInput.currentIndexChanged.connect(self.update_time_put)
            self.WidgetShovelBackInput.currentIndexChanged.connect(self.update_time_put)


            self.ModeChangeButton.clicked.connect(self.change_edit_mode)

        connect_signal_and_slot()

        def setup_main_window():
            """外观"""

            # 窗口名
            self.setWindowTitle('FAA - 战斗方案编辑器 - 鼠标悬停在按钮&输入框可以查看许多提示信息')

            # 设置窗口图标
            self.setWindowIcon(QIcon(PATHS["logo"] + "\\圆角-FetDeathWing-450x.png"))

            # 设定窗口初始大小 否则将无法自动对齐到上级窗口中心
            self.setFixedSize(1280, 720)

            # 不继承 系统缩放 (高DPI缩放)
            QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

        setup_main_window()

        # 初始化关卡选择
        self.init_stage_selector()

        # 初始选中的波次按钮
        self.click_wave_button(be_clicked_button_id=0)

        # 根据初始数据, 刷新全部UI外观
        self.fresh_all_ui()

        # 初始加载 禁用部分输入控件
        self.input_widget_enabled(mode=False)

    """波次相关"""

    def get_wave_plan_by_id(self, index: int):
        """返回json_data的对应部分"""
        if index == 0:
            return self.json_data["card"]["default"]
        elif index <= 13:
            return self.json_data["card"]["wave"][str(index)]
        else:
            CUS_LOGGER.error(f"[战斗方案编辑器] 致命错误, 波次越位")
    def get_time_wave_plan(self):
        """返回timer_plan"""
        try:
            if "wave" in self.json_data["card"]["timer_plan"]:
                time_plan= self.json_data["card"]["timer_plan"]["wave"]
                return time_plan
            else:
                return None
        except:
            CUS_LOGGER.warning(f"[战斗方案编辑器] 定时放卡路径不存在,可能为旧方案")
            return None


    def click_wave_button(self, be_clicked_button_id: int):

        CUS_LOGGER.debug(f"[战斗方案编辑器] [界面交互] 波次按钮编号 {be_clicked_button_id}, 被点击")

        """点击波次按钮"""
        self.change_wave(be_clicked_button_id)

        # 修改当前选中波次按钮的文本内容并还原其他按钮的内容
        self.fresh_wave_button_text(be_clicked_button_id=int(be_clicked_button_id))

    def fill_blank_wave(self):
        """加载时, 将空白波次的方案设定为自动继承状态"""

        CUS_LOGGER.debug("[战斗方案编辑器] [加载方案] 开始填充空白的波次方案")

        wave_data = self.json_data["card"]["wave"]

        for wave in range(14):

            if wave == 0:
                wave_plan = self.json_data["card"]["default"]
            else:
                wave_plan = self.json_data["card"]["wave"].get(str(wave))

            if wave_plan is None:
                # 如果缺失，深拷贝波次更小中最大的方案
                existing_waves = [int(w) for w in wave_data.keys() if w]
                if existing_waves:
                    smaller_waves = [w for w in existing_waves if w < int(wave)]
                    # print(f"波次: {wave}, 更低的以下波次有方案:{smaller_waves}")
                    if smaller_waves:
                        max_smaller_wave = str(max(smaller_waves))
                        wave_data[str(wave)] = copy.deepcopy(wave_data[max_smaller_wave])
                        CUS_LOGGER.debug(
                            f"[战斗方案编辑器] [加载方案] 波次: {wave}, 已从波次{max_smaller_wave}完成继承")
                        continue
                    else:
                        # 如果没有更小的波次方案，则使用默认方案
                        wave_data[str(wave)] = copy.deepcopy(self.json_data["card"]["default"])
                        CUS_LOGGER.debug(f"[战斗方案编辑器] [加载方案] 波次: {wave}, 已从波次0完成继承")
                        continue
                else:
                    # 如果没有任何现有波次，则使用默认方案
                    wave_data[str(wave)] = copy.deepcopy(self.json_data["card"]["default"])
                    CUS_LOGGER.debug(f"[战斗方案编辑器] [加载方案] 波次: {wave}, 已从波次0完成继承")
                    continue
            else:
                CUS_LOGGER.debug(f"[战斗方案编辑器] [加载方案] 波次: {wave}, 文件已包含")

    def refresh_wave_button_color(self):
        """
        扫描已有的波次方案, 如果方案和上一波次相同, 颜色不变, 否则颜色取色list中+1
        list为一个彩虹渐变色，包含总计7档颜色，透明度为 100/256
        :return:
        """
        # color_list = [
        #     (255, 0, 0),  # 红色
        #     (255, 165, 0),  # 橙色
        #     (255, 255, 0),  # 黄色
        #     (0, 255, 0),  # 绿色
        #     (0, 0, 255),  # 蓝色
        #     (75, 0, 130),  # 靛色
        #     (148, 0, 211),  # 紫色
        # ]

        color_list = [
            (255, 0, 0),
            (30, 144, 255),
        ]

        last_plan = self.get_wave_plan_by_id(0)
        color_list_index = 0
        for wave in range(14):
            cursor_plan = self.get_wave_plan_by_id(wave)

            if cursor_plan != last_plan:
                color_list_index = (color_list_index + 1) % len(color_list)  # 循环使用颜色列表

            r, g, b = color_list[color_list_index]
            color_with_alpha = f"rgba({r}, {g}, {b}, 0.4)"

            button = self.findChild(QPushButton, f"changeWaveButton_{wave}")
            button.setStyleSheet(f"background-color: {color_with_alpha}")
            last_plan = cursor_plan


    def change_edit_mode(self):
        if self.mode==1:
            self.mode=2
            self.ModeChangeButton.setText("当前为定时放卡编辑模式")
            hide_layout(self.LayCardEditor)
            show_layout(self.LayTimeCardEditor)
            self.WidgetTimePutList.setVisible(True)
            self.setFixedSize(1400, 720)
        else:
            self.mode=1
            self.ModeChangeButton.setText("当前为队列遍历编辑模式")
            hide_layout(self.LayTimeCardEditor)
            show_layout(self.LayCardEditor)
            self.WidgetTimePutList.setVisible(False)
            self.setFixedSize(1280, 720)
        self.fresh_all_ui()

    def change_wave(self, wave: int):

        # 更新当前波次参数
        self.current_wave = wave

        # 切换方案
        self.sub_plan = self.get_wave_plan_by_id(index=wave)

        self.time_wave_plan = self.get_time_wave_plan()

        # 去除选中的卡片
        self.current_card_index = None

        # 加载数据
        self.fresh_all_ui()

    def copy_wave_plan(self):

        self.be_copied_wave_id = copy.deepcopy(self.current_wave)

        # 复制后 允许其粘贴
        self.paste_wave_button.setEnabled(True)

        CUS_LOGGER.debug(f"[战斗方案编辑器] 已复制波次, 编号:{self.be_copied_wave_id}")

    def paste_wave_plan(self):

        be_copied_wave_plan = copy.deepcopy(self.get_wave_plan_by_id(self.be_copied_wave_id))

        #
        self.sub_plan.clear()  # 清空当前的sub_plan
        self.sub_plan.extend(be_copied_wave_plan)  # 将新的波次计划添加到sub_plan中

        self.fresh_all_ui()

        CUS_LOGGER.debug(f"[战斗方案编辑器] 已粘贴波次, 编号: {self.be_copied_wave_id} -> {self.current_wave}")

    def apply_to_all_wave_plan(self):
        for i in range(14):
            if i == self.current_wave:
                continue
            self.get_wave_plan_by_id(i).clear()
            self.get_wave_plan_by_id(i).extend(copy.deepcopy(self.sub_plan))

        # 仅需变色波次按钮颜色
        self.refresh_wave_button_color()

        CUS_LOGGER.debug(f"[战斗方案编辑器] 波次:{self.current_wave}方案已应用到所有波次")

    def fresh_wave_button_text(self, be_clicked_button_id: int):
        for wave in range(14):
            button = self.findChild(QPushButton, f"changeWaveButton_{wave}")
            if wave == be_clicked_button_id:
                button.setText(f">> {wave} <<")
            else:
                button.setText(f"{wave}")

    """数据变化->UI变化 大礼包, 懒得找对应部分直接全调用一遍总没错"""

    def fresh_all_ui(self):
        """
        全部视图重绘
        如果懒得给每个动作精细划分应当调用哪个UI变化函数, 那么全都变一下总是没错（
        """

        # 重绘 UI的放卡动作列表
        self.load_data_to_ui_list()
        self.load_data_to_ui_list2()

        # 重绘 UI棋盘网格
        self.refresh_chessboard()

        # 刷新波次按钮颜色
        self.refresh_wave_button_color()

        # 刷新棋盘高亮
        self.highlight_chessboard()

    """放卡动作列表操作"""

    def current_card_change(self, item):
        """被单击后, 被选中的卡片改变了"""

        # list的index 是 QModelIndex 此处还需要获取到行号
        self.current_card_index = self.WidgetCardList.indexFromItem(item).row()

        # 为输入控件信号上锁，在初始化时不会触发保存
        self.input_widget_lock(True)

        if self.current_card_index == 0:
            # 玩家
            self.WidgetIdInput.clear()
            self.WidgetNameInput.setText("玩家")
            self.WidgetErgodicInput.setCurrentIndex(0)
            self.WidgetQueueInput.setCurrentIndex(0)
            self.WidgetKunInput.clear()
            # 禁用部分输入控件
            self.input_widget_enabled(mode=False)

        else:
            # 卡片
            index = self.current_card_index - 1  # 可能需要深拷贝？也许是被保护的特性 不需要
            card = self.sub_plan[index]
            # self.WCurrentCard.setText("索引-{} 名称-{}".format(index, card["name"]))
            self.WidgetIdInput.setValue((card['id']))
            self.WidgetIdInput2.setValue((card['id']))
            self.WidgetNameInput.setText(card['name'])
            self.WidgetNameInput2.setText(card['name'])
            self.WidgetErgodicInput.setCurrentText(str(card['ergodic']).lower())
            self.WidgetQueueInput.setCurrentText(str(card['queue']).lower())
            self.WidgetKunInput.setValue(card.get('kun', 0))
            # 解锁部分输入控件
            self.input_widget_enabled(mode=True)

        # 解锁控件信号
        self.input_widget_lock(False)

        # 高亮棋盘
        self.highlight_chessboard()
    def current_time_put_change(self, item):
        """被单击后, 被选中的卡片改变了"""

        # list的index 是 QModelIndex 此处还需要获取到行号
        self.current_time_put_index = self.WidgetTimePutList.indexFromItem(item).row()
        self.change=True

        # 为输入控件信号上锁，在初始化时不会触发保存
        self.input_widget_lock(True)

        plan = self.time_wave_plan[str(self.current_wave)][self.current_time_put_index]
        self.WidgetIdInput2.setValue((plan['cid']))
        self.WidgetNameInput2.setText(plan['name'])
        self.WidgetTimeInput.setValue(plan['time'])
        self.WidgetBackTimeInput.setValue(plan['back_shovel_time'])
        self.WidgetShovelFrontInput.setCurrentText(str(plan['front_shovel']).lower())
        self.WidgetShovelBackInput.setCurrentText(str(plan['back_shovel']).lower())
        self.change = False

        # 解锁部分输入控件
        self.input_widget_enabled(mode=True)

        # 解锁控件信号
        self.input_widget_lock(False)
        self.fresh_all_ui()


    def load_data_to_ui_list(self):
        """从 [内部数据表] 载入数据到 [ui的放卡动作列表]"""

        self.WidgetCardList.clear()


        player_item = QListWidgetItem("玩家")
        self.WidgetCardList.addItem(player_item)

        if not self.sub_plan:
            return

        # 根据中文和西文分别记录最高宽度
        name_max_width_c = 0
        name_max_width_e = 0
        for card in self.sub_plan:
            width_c, width_e = calculate_text_width(card["name"])
            name_max_width_c = max(name_max_width_c, width_c)
            name_max_width_e = max(name_max_width_e, width_e)

        # 找到最长的id长度
        max_id_length = 1
        if self.sub_plan:
            max_id_length = max(len(str(card["id"])) for card in self.sub_plan)

        for card in self.sub_plan:

            # 根据中文和西文 分别根据距离相应的最大宽度的差值填充中西文空格
            width_c, width_e = calculate_text_width(card["name"])
            padded_name = str(card["name"])
            padded_name += "\u2002" * (name_max_width_e - width_e)  # 半宽空格
            padded_name += '\u3000' * (name_max_width_c - width_c)  # 表意空格(方块字空格)

            padded_id = str(card["id"]).ljust(max_id_length)

            text = "{}  ID:{}  遍历:{}  队列:{}".format(
                padded_name,
                padded_id,
                "√" if card["ergodic"] else "X",
                "√" if card["queue"] else "X"
            )

            if card.get("kun", 0):
                text += "  坤:{}".format(card["kun"])

            item = QListWidgetItem(text)
            self.WidgetCardList.addItem(item)
    def load_data_to_ui_list2(self):
        """从 [内部数据表] 载入数据到 [ui的放卡动作列表]"""

        self.WidgetTimePutList.clear()

        if not self.time_wave_plan or str(self.current_wave) not in self.time_wave_plan:
            return

        # 根据中文和西文分别记录最高宽度
        name_max_width_c = 0
        name_max_width_e = 0
        for time_plan in self.time_wave_plan[str(self.current_wave)]:
            width_c, width_e = calculate_text_width(time_plan["name"])
            name_max_width_c = max(name_max_width_c, width_c)
            name_max_width_e = max(name_max_width_e, width_e)

        # 找到最长的id长度
        max_id_length = 1
        if self.time_wave_plan[str(self.current_wave)]:
            max_id_length = max(len(str(time_plan["cid"])) for time_plan in self.time_wave_plan[str(self.current_wave)])

        for time_plan in self.time_wave_plan[str(self.current_wave)]:

            # 根据中文和西文 分别根据距离相应的最大宽度的差值填充中西文空格
            width_c, width_e = calculate_text_width(time_plan["name"])
            padded_name = str(time_plan["name"])
            padded_name += "\u2002" * (name_max_width_e - width_e)  # 半宽空格
            padded_name += '\u3000' * (name_max_width_c - width_c)  # 表意空格(方块字空格)

            padded_id = str(time_plan["cid"]).ljust(max_id_length)

            text = "{}  ID:{} 时间:{}s 前后铲:{} {} ".format(
                padded_name,
                padded_id,
                time_plan["time"],
                "√" if time_plan["front_shovel"] else "X",
                "√" if time_plan["back_shovel"] else "X"
            )


            item = QListWidgetItem(text)
            self.WidgetTimePutList.addItem(item)

    def card_list_be_dropped(self, index_from, index_to):
        """在list的drop事件中调用, 用于更新内部数据表"""
        cards = self.sub_plan
        if index_to != 0:
            # 将当前状态压入栈中
            self.append_undo_stack()

            change_card = cards.pop(index_from - 1)
            CUS_LOGGER.debug(change_card)
            cards.insert(index_to - 1, change_card)
            CUS_LOGGER.debug("正常操作 内部数据表已更新: {}".format(cards))
            # 刷新波次上色
            self.refresh_wave_button_color()
        else:
            # 试图移动到第一个
            self.WidgetCardList.clear()
            self.load_data_to_ui_list()

    """放卡动作属性编辑"""

    def input_widget_lock(self, mode: bool):
        """
        是否锁定卡片属性输入控件
        """
        self.WidgetIdInput.blockSignals(mode)
        self.WidgetNameInput.blockSignals(mode)
        self.WidgetErgodicInput.blockSignals(mode)
        self.WidgetQueueInput.blockSignals(mode)
        self.WidgetKunInput.blockSignals(mode)

    def input_widget_enabled(self, mode: bool):
        self.WidgetIdInput.setEnabled(mode)
        self.WidgetNameInput.setEnabled(mode)
        self.WidgetErgodicInput.setEnabled(mode)
        self.WidgetQueueInput.setEnabled(mode)
        self.WidgetKunInput.setEnabled(mode)
        self.WidgetDeleteCardButton.setEnabled(mode)

    def add_card(self):

        ids_list = [card["id"] for card in self.sub_plan]
        for i in range(1, 22):
            if i not in ids_list:
                id_ = i
                break
        else:
            QMessageBox.information(self, "操作错误！", "卡片ID已用完, 无法再添加新卡片!")
            return

        name_ = "新的卡片"

        self.sub_plan.append(
            {
                "id": id_,
                "name": name_,
                "ergodic": bool(self.WidgetErgodicInput.currentText() == 'true'),  # 转化bool
                "queue": bool(self.WidgetQueueInput.currentText() == 'true'),  # 转化bool
                "location": []
            }
        )

        self.fresh_all_ui()
    def add_time_put(self):
        try:
            if str(self.current_wave) not in self.time_wave_plan:
                self.time_wave_plan[str(self.current_wave)] = [{
                        "cid": self.WidgetIdInput2.value(),
                        "name": self.WidgetNameInput2.text(),
                        "time": self.WidgetTimeInput.value(),
                        "back_shovel_time": self.WidgetBackTimeInput.value(),
                        "front_shovel": bool(self.WidgetShovelFrontInput.currentText() == 'true'),  # 转化bool
                        "back_shovel": bool(self.WidgetShovelBackInput.currentText() == 'true'),  # 转化bool
                        "location": ""
                    }]
            else:
                self.time_wave_plan[str(self.current_wave)].append(
                    {
                        "cid": self.WidgetIdInput2.value(),
                        "name": self.WidgetNameInput2.text(),
                        "time": self.WidgetTimeInput.value(),
                        "back_shovel_time": self.WidgetBackTimeInput.value(),
                        "front_shovel": bool(self.WidgetShovelFrontInput.currentText() == 'true'),  # 转化bool
                        "back_shovel": bool(self.WidgetShovelBackInput.currentText() == 'true'),  # 转化bool
                        "location": ""
                    }
                )
        except:
            QMessageBox.information(self, "操作错误！", "请添加至备选槽时填写所有参数")
            return

        self.fresh_all_ui()

    def delete_card(self):
        """
        选中一组放卡操作后, 点击按钮, 删除它
        :return: None
        """

        if not self.current_card_index:
            QMessageBox.information(self, "操作错误！", "请先选择一个对象(卡片)!")
            return False

        if self.current_card_index == 0:
            QMessageBox.information(self, "操作错误！", "该对象(玩家)不能编辑信息, 只能设置位置!")
            return False
        # 将当前状态压入栈中
        self.append_undo_stack()

        del self.sub_plan[self.current_card_index - 1]

        # 清空选中的卡片
        self.current_card_index = None

        self.fresh_all_ui()
    def delete_time_put(self):
        """
        选中一组定时放卡操作后, 点击按钮, 删除它
        :return: None
        """

        if not self.current_time_put_index:
            if self.current_time_put_index!=0:
                QMessageBox.information(self, "操作错误！", "请先选择一个对象(定时放卡)!")
                return False

        # 将当前状态压入栈中
        self.append_undo_stack()

        del self.time_wave_plan[str(self.current_wave)][self.current_time_put_index]

        # 清空选中的卡片
        self.current_time_put_index = None

        self.fresh_all_ui()

    def update_card(self):
        """
        在UI上编辑更新一组放卡操作的状态后
        将该操作同步到内部数据表
        并刷新到左侧列表和棋盘等位置
        :return: None
        """

        if not self.current_card_index:
            QMessageBox.information(self, "操作错误！", "请先选择一个对象(卡片)!")
            return False

        if self.current_card_index == 0:
            QMessageBox.information(self, "操作错误！", "该对象(玩家)不能编辑信息, 只能设置位置!")
            return False

        # 将当前状态压入栈中
        self.append_undo_stack()

        card = self.sub_plan[self.current_card_index - 1]
        card["id"] = int(self.WidgetIdInput.value())
        card["name"] = self.WidgetNameInput.text()
        card["ergodic"] = bool(self.WidgetErgodicInput.currentText() == 'true')  # 转化bool
        card["queue"] = bool(self.WidgetQueueInput.currentText() == 'true')  # 转化bool
        card["kun"] = self.WidgetKunInput.value()

        self.fresh_all_ui()
    def update_time_put(self):
        """
        在UI上编辑更新一组定时放卡操作的状态后
        将该操作同步到内部数据表
        并刷新到左侧列表和棋盘等位置
        :return: None
        """

        if not self.current_time_put_index:
            if self.current_time_put_index!=0:
                return False
        if self.change:#点击对应的定时放卡导致的变更不予受理
            return False
        # 将当前状态压入栈中
        self.append_undo_stack()

        time_plan = self.time_wave_plan[str(self.current_wave)][self.current_time_put_index]
        time_plan["cid"] = int(self.WidgetIdInput2.value())
        time_plan["name"] = self.WidgetNameInput2.text()
        time_plan["time"] = int(self.WidgetTimeInput.value())
        time_plan["back_shovel_time"] = int(self.WidgetBackTimeInput.value())
        time_plan["front_shovel"] = bool(self.WidgetShovelFrontInput.currentText() == 'true')  # 转化bool
        time_plan["back_shovel"] = bool(self.WidgetShovelBackInput.currentText() == 'true') # 转化bool

        self.fresh_all_ui()
    """棋盘操作"""

    def place_card(self, x, y):
        """
        选中一组放卡操作后, 为该操作添加一个放置位置
        :return: None
        """
        if self.mode==1:#遍历队列模式
            if self.current_card_index is None:
                return
            # 将当前状态压入栈中
            self.append_undo_stack()
            # 初始化 并非没有选择任何东西
            location_key = f"{x + 1}-{y + 1}"
            if self.current_card_index == 0:
                # 当前index为玩家
                target = self.json_data["player"]
                # 如果这个位置已经有了玩家，那么移除它；否则添加它
                if location_key in target:
                    target.remove(location_key)
                else:
                    target.append(location_key)
            else:
                # 当前index为卡片
                target = self.sub_plan[self.current_card_index - 1]
                # 如果这个位置已经有了这张卡片，那么移除它；否则添加它
                if location_key in target['location']:
                    target['location'].remove(location_key)
                else:
                    target['location'].append(location_key)
            self.refresh_chessboard()
            self.refresh_wave_button_color()
        else:
            if self.current_time_put_index is None:
                return
            # 将当前状态压入栈中
            self.append_undo_stack()
            # 初始化 并非没有选择任何东西
            location_key = f"{x + 1}-{y + 1}"
            target = self.time_wave_plan[str(self.current_wave)][self.current_time_put_index]
            target["location"]=location_key
            self.refresh_chessboard()
            self.refresh_wave_button_color()

    def remove_card(self, x, y):
        """
        选中一组放卡操作后, 点击去除一个操作
        :param x:
        :param y:
        :return:
        """
        if self.mode == 1:  # 遍历队列模式
            # 将当前状态压入栈中
            self.append_undo_stack()
            # 删除当前位置上的所有卡片
            location = f"{x + 1}-{y + 1}"
            # 从玩家位置中删除
            if location in self.json_data["player"]:
                self.json_data["player"].remove(location)
            # 从卡片位置中删除
            for card in self.sub_plan:
                if location in card["location"]:
                    card["location"].remove(location)

            self.refresh_chessboard()
            self.refresh_wave_button_color()
        else:
            # 将当前状态压入栈中
            self.append_undo_stack()
            # 删除当前位置上的所有卡片
            location = f"{x + 1}-{y + 1}"
            # 移除此位置的所有定时放卡计划
            for time_plan in self.time_wave_plan[str(self.current_wave)]:
                if time_plan["location"]==location:
                    time_plan["location"] = ""

            self.refresh_chessboard()
            self.refresh_wave_button_color()

    def refresh_chessboard(self):
        """刷新棋盘上的文本等各种元素"""

        def truncate_text(text, max_width=4):
            """
            设西文宽度0.5 中文宽度1 如果 card name 超过了宽度8 就只显示宽度为8的部分字符 加 ..
            :param text:
            :param max_width:
            :return:
            """
            width_c, width_e = calculate_text_width(text)
            total_width = width_c + width_e

            if total_width <= max_width:
                return text

            truncated_text = ''
            current_width = 0

            for char in text:
                if '\u4e00' <= char <= '\u9fff':
                    char_width = 1
                else:
                    char_width = 0.5

                if current_width + char_width > max_width - 1.0:  # 留出空间给 ..
                    truncated_text += '..'
                    break

                truncated_text += char
                current_width += char_width

            return truncated_text

        for i, row in enumerate(self.chessboard_buttons):
            for j, btn in enumerate(row):

                location_key = f"{j + 1}-{i + 1}"

                text_block = []
                if self.mode==1:
                    # 如果玩家在这个位置，添加 "玩家" 文字
                    player_location_list = self.json_data.get('player', [])
                    if location_key in player_location_list:
                        text_block.append('玩家 {}'.format(player_location_list.index(location_key) + 1))

                    cards_in_this_location = []
                    for card in self.sub_plan:
                        if location_key in card['location']:
                            cards_in_this_location.append(card)

                    for card in cards_in_this_location:
                        # 名称
                        text = truncate_text(text=card['name'])
                        # 编号
                        c_index_list = card["location"].index(location_key) + 1
                        if type(c_index_list) is list:
                            for location_index in c_index_list:
                                text += " {}".format(location_index)
                        else:
                            text += " {}".format(c_index_list)
                        text_block.append(text)
                else:
                    if str(self.current_wave) not in self.time_wave_plan:
                        return
                    for time_plan in self.time_wave_plan[str(self.current_wave)]:
                        if time_plan["location"]==location_key:
                            text_block.append("{} {}s".format(truncate_text(text=time_plan["name"]),time_plan["time"]))

                # 用\n连接每一个block
                btn.setText("\n".join(text_block))

    def highlight_chessboard(self):
        """根据卡片的位置list，将对应元素的按钮进行高亮"""

        # 清除所有按钮的高亮
        for row in self.chessboard_frames:
            for frame in row:
                frame.setStyleSheet("")

        # 记录所有被选中的格子
        selected_cells = set()

        # 还没有选中任何卡片 直接返回
        if self.current_card_index is not None:

            if self.current_card_index == 0:
                current_card_locations = self.json_data["player"]
            else:
                current_card_locations = self.sub_plan[self.current_card_index - 1]["location"]

            for location in current_card_locations:
                x, y = map(int, location.split('-'))
                selected_cells.add((x, y))
                # 如果是选中的卡片 蓝色
                self.chessboard_frames[y - 1][x - 1].setStyleSheet("background-color: rgba(30, 144, 255, 100);")

        # 还没有选中任何关卡 直接返回
        if self.stage_info:
            obstacle = self.stage_info.get("obstacle", [])
            if obstacle:  # 障碍物，在frame上显示红色
                for location in obstacle:  # location格式为："y-x"
                    x, y = map(int, location.split("-"))
                    if (x, y) in selected_cells:
                        # 如果是被选中的格子，设置为紫色 警告
                        self.chessboard_frames[y - 1][x - 1].setStyleSheet("background-color: rgba(145, 44, 238, 100);")
                    else:
                        # 否则设置为红色 代表障碍位置
                        self.chessboard_frames[y - 1][x - 1].setStyleSheet("background-color: rgba(255, 0, 0, 100);")

    """储存战斗方案"""

    def save_json(self):
        """
        保存方法，拥有保存和另存为两种功能，还能创建uuid
        """

        def clear_sub_plan():
            """清理和默认方案完全相同的波次方案"""
            # 收集需要移除的键
            keys_to_remove = []
            current_sub_plan = self.json_data["card"]["default"]
            for wave, sub_plan in self.json_data["card"]["wave"].items():
                if sub_plan == current_sub_plan:
                    keys_to_remove.append(wave)
                else:
                    current_sub_plan = sub_plan

            # 移除收集到的键
            for wave in keys_to_remove:
                self.json_data["card"]["wave"].pop(wave)
            if "timer_plan" in self.json_data["card"]:
                for wave, timer_plans in self.json_data["card"]["timer_plan"]["wave"].items():
                    timer_plans[:] = [timer_plan for timer_plan in timer_plans if timer_plan["location"] != ""]#没有标注位置的定时放卡舍弃
                    self.json_data["card"]["timer_plan"][wave]=timer_plans

        def sort_wave_plan():
            """按照key值的int格式来进行一次排序, 让json_data中的波次方案dict变得有序"""
            wave_data = self.json_data["card"]["wave"]
            sorted_keys = sorted(wave_data.keys(), key=lambda x: int(x))
            sorted_dict = {k: wave_data[k] for k in sorted_keys}
            self.json_data["card"]["wave"] = sorted_dict
            for wave, timer_plans in self.json_data["card"]["timer_plan"]["wave"].items():
                sorted_timeplans = sorted(timer_plans, key=lambda x: x['time'],reverse=True)
                # 如果需要将排序后的结果重新赋值给原列表，可以使用以下代码
                self.json_data["card"]["timer_plan"][wave] = sorted_timeplans

        sort_wave_plan()
        clear_sub_plan()

        is_save_as = self.sender() == self.ButtonSaveAs

        def warning_save_enable(uuid):

            if not uuid in ["00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000001"]:
                return True

            text = (
                "FAA部分功能(美食大赛/公会任务)依赖这两份默认方案(1卡组-通用-1P & 1卡组-通用-2P)运行.\n"
                "你确定要保存并修改他们吗! 这可能导致相关功能出现错误!"
            )
            response = QMessageBox.question(
                self,
                "高危操作！",
                text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if response == QMessageBox.StandardButton.No:
                return False
            else:
                return True

        self.json_data['tips'] = self.WidgetTipsEditor.toPlainText()

        if is_save_as:
            # 保存为
            new_file_path, _ = QFileDialog.getSaveFileName(
                parent=self,
                caption="保存 JSON 文件",
                directory=PATHS["battle_plan"],
                filter="JSON Files (*.json)"
            )
        else:
            # 保存
            new_file_path = self.file_path
            if not self.file_path:
                # 保存, 提示用户还未选择任何战斗方案
                QMessageBox.information(self, "禁止虚空保存！", "请先选择一个战斗方案!")
                return

        if not os.path.exists(new_file_path):
            # 这里是保存新文件的情况, 需要一个新的uuid
            self.json_data["uuid"] = str(uuid.uuid1())

        else:
            # 覆盖现有文件的情况
            with EXTRA.FILE_LOCK:
                with open(file=new_file_path, mode='r', encoding='utf-8') as file:
                    tar_uuid = json.load(file).get('uuid', None)

            if not tar_uuid:
                # 被覆盖的目标没有uuid 生成uuid
                self.json_data["uuid"] = str(uuid.uuid1())

            else:
                # 高危uuid需要确定
                if not warning_save_enable(uuid=tar_uuid):
                    return
                # 被覆盖的目标有uuid 使用存在的uuid
                self.json_data["uuid"] = tar_uuid

        # 确保玩家位置也被保存
        self.json_data['player'] = self.json_data.get('player', [])

        # 确保文件名后缀是.json
        new_file_path = os.path.splitext(new_file_path)[0] + '.json'

        # 保存
        with EXTRA.FILE_LOCK:
            with open(file=new_file_path, mode='w', encoding='utf-8') as file:
                json.dump(self.json_data, file, ensure_ascii=False, indent=4)

        # 打开新建 or 覆盖掉的文件
        self.load_json(file_path=new_file_path)

        self.re_init_battle_plan_opened()

        self.ButtonSave.setEnabled(True)

    """打开战斗方案"""

    def open_battle_plan(self):

        file_name = self.open_json()

        if file_name:
            self.load_json(file_path=file_name)

            self.re_init_battle_plan_opened()

            self.ButtonSave.setEnabled(True)

    def open_json(self):
        """打开窗口 打开json文件"""

        file_name, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="打开 JSON 文件",
            directory=PATHS["battle_plan"],
            filter="JSON Files (*.json)")

        return file_name

    def load_json(self, file_path):
        """读取对应的json文件"""

        with EXTRA.FILE_LOCK:
            with open(file=file_path, mode='r', encoding='utf-8') as file:
                self.json_data = json.load(file)

        self.WidgetTipsEditor.setPlainText(self.json_data.get('tips', ''))

        self.file_path = file_path  # 当前方案路径

        # 获取当前方案的名称
        current_plan_name = os.path.basename(file_path).replace(".json", "")
        CUS_LOGGER.debug(f"[战斗方案编辑器] [加载方案] 开始读取:{current_plan_name}")

        self.current_plan_name_label.setText(f"当前方案名:{current_plan_name}")
        self.current_plan_uuid_label.setText(f"{self.json_data.get('uuid', '无')}")

    def re_init_battle_plan_opened(self):
        """在读取方案后, 填充该方案空白部分, 并初始化大量控件"""

        # 填充空白波次
        self.fill_blank_wave()

        # 初始化当前选中
        self.current_card_index = None

        # 初始化 放卡动作 状态编辑器
        self.input_widget_lock(True)
        self.WidgetIdInput.clear()
        self.WidgetIdInput2.clear()
        self.WidgetNameInput.clear()
        self.WidgetNameInput2.clear()
        self.WidgetTimeInput.clear()
        self.WidgetBackTimeInput.clear()
        self.WidgetShovelFrontInput.setCurrentIndex(1)
        self.WidgetShovelBackInput.setCurrentIndex(1)
        self.WidgetErgodicInput.setCurrentIndex(0)
        self.WidgetQueueInput.setCurrentIndex(0)
        self.WidgetKunInput.clear()
        self.input_widget_lock(False)

        # 回到波次0方案 并载入方案波次
        self.click_wave_button(be_clicked_button_id=0)

        # 刷新全部视图
        self.fresh_all_ui()

        # 解锁部分输入控件
        self.input_widget_enabled(mode=False)

    """撤回/重做"""

    def append_undo_stack(self):
        # 将当前状态压入栈中
        self.undo_stack.append(copy.deepcopy(self.json_data))
        # 清空重做栈
        self.redo_stack.clear()
        # 只保留20次操作
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)

    def undo(self):
        """撤销"""
        if len(self.undo_stack) > 0:
            current_state = copy.deepcopy(self.json_data)
            self.redo_stack.append(current_state)
            self.json_data = self.undo_stack.pop()
            self.fresh_all_ui()

    def redo(self):
        """重做"""
        if len(self.redo_stack) > 0:
            current_state = copy.deepcopy(self.json_data)
            self.undo_stack.append(current_state)
            self.json_data = self.redo_stack.pop()

            self.fresh_all_ui()

    def set_my_font(self, my_font):
        """用于继承字体, 而不需要多次读取"""
        self.setFont(my_font)

    def init_stage_selector(self):
        """
        多层菜单
        初始化关卡选择，从stage_info或更多内容里导入关卡，选择后可以显示障碍物或更多内容
        菜单使用字典，其值只能为字典或列表。键值对中的键恒定为子菜单，而值为选项；列表中元素只能是元组，为关卡名，关卡id
        """
        stage_dict = {}
        for type_id, stage_info_1 in self.stage_info_all.items():
            if type_id in ["default", "name", "tooltip", "update_time"]:
                continue
            type_name = stage_info_1["name"]
            stage_dict[type_name] = {}

            for sub_type_id, stage_info_2 in stage_info_1.items():
                if sub_type_id in ["name", "tooltip"]:
                    continue
                sub_type_name = stage_info_2["name"]
                stage_dict[type_name][sub_type_name] = []

                for stage_id, stage_info_3 in stage_info_2.items():
                    if stage_id in ["name", "tooltip"]:
                        continue
                    stage_name = stage_info_3["name"]
                    stage_code = f"{type_id}-{sub_type_id}-{stage_id}"
                    stage_dict[type_name][sub_type_name].append((stage_name, stage_code))

        self.WidgetStageSelector.add_menu(data=stage_dict)

    """更改当前关卡"""

    def stage_changed(self, stage: str, stage_id: str):
        """
        根据stage_info，使某些格子显示成障碍物或更多内容
        stage为关卡名，暂时不知道有啥用
        stage_id的格式为：XX-X-X
        """
        id0, id1, id2 = stage_id.split("-")
        self.stage_info = self.stage_info_all[id0][id1][id2]

        # 高亮棋盘
        self.highlight_chessboard()


class QListWidgetDraggable(QListWidget):

    def __init__(self, drop_function):
        super(QListWidgetDraggable, self).__init__()

        # 定义数据变化函数
        self.drop_function = drop_function

        # 允许内部拖拽
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def dropEvent(self, e):
        CUS_LOGGER.debug("拖拽事件触发")
        index_from = self.currentRow()
        super(QListWidgetDraggable, self).dropEvent(e)  # 如果不调用父类的构造方法，拖拽操作将无法正常进行
        index_to = self.currentRow()

        source_Widget = e.source()  # 获取拖入item的父组件
        items = source_Widget.selectedItems()  # 获取所有的拖入item
        item = items[0]  # 不允许多选 所以只有一个

        CUS_LOGGER.debug("text:{} from {} to {} memory:{}".format(item.text(), index_from, index_to, self.currentRow()))

        # 执行更改函数
        self.drop_function(index_from=index_from, index_to=index_to)

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        current_row = self.currentRow()
        if current_row == 0:
            # 禁止拖拽
            self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        else:
            # 允许内部拖拽
            self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)


class ChessButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            # 发出自定义的右键点击信号
            self.rightClicked.emit()
        else:
            super().mousePressEvent(event)

    rightClicked = pyqtSignal()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = QMWEditorOfBattlePlan()
    ex.show()
    sys.exit(app.exec())
