import copy
import json
import os
import sys
import uuid
from typing import List

from PyQt6.QtCore import pyqtSignal, Qt, QPoint
from PyQt6.QtGui import QKeySequence, QIcon, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGridLayout, QPushButton, QWidget, QFileDialog, QVBoxLayout, QLabel, QComboBox,
    QLineEdit, QHBoxLayout, QTextEdit, QListWidget, QMessageBox, QSpinBox, QListWidgetItem, QFrame, QAbstractItemView,
    QSpacerItem, QSizePolicy, QDoubleSpinBox, QDialog)

from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.scattered.class_battle_plan_v3d0 import json_to_obj, TriggerWaveTimer, \
    ActionLoopUseCards, ActionInsertUseCard, ActionUseGem, Event, BattlePlan, obj_to_json, Card, MetaData, \
    CardLoopConfig
from function.widget.MultiLevelMenu import MultiLevelMenu

double_click_card_list = pyqtSignal(object)

"""
战斗方案编辑器
致谢：八重垣天知

说明:
FAA 战斗方案协议 v3.0
参考 类 BattlePlan.
编辑器逻辑中, 希望用户不关注Card的具体情况. 仅以ID标识
故, 采取以下处理方式.
1. 加载时 将所有已有事件 完成内联(触发器/动作/卡片)
2. 根据触发器和动作的类型分类, 读取到不同的self属性中.
    * 普通 - 循环放卡
        * Trigger.type == "wave_timer", Trigger.time = 0;
        * Action.type == "loop_use_cards" 
        * 注: 虽然理论可行, 但不需要在编辑器加入, 非波次刚开始时, 变化循环放卡的策略的编辑项.
    * 时间线 - 插队放卡
        * Trigger.type == "wave_timer"
        * Action.type == "insert_use_card"
    * 时间线 - 宝石放置
        * Trigger.type == "wave_timer"
        * Action.type == "use_gem" 
3. 保存时 反内联保存
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
    :param layout: 要隐藏的布局对象（QLayout）
    """
    if not layout:
        return

    # 遍历布局中的每个子项
    for i in range(layout.count()):
        item = layout.itemAt(i)
        widget = item.widget()
        # 如果是 QListWidget，直接隐藏
        if isinstance(widget, QListWidget):
            widget.setVisible(False)
        # 普通控件则隐藏
        elif widget:
            widget.setVisible(False)
        # 处理子布局
        else:
            sub_layout = item.layout()
            if sub_layout:
                hide_layout(sub_layout)  # 递归隐藏子布局


def show_layout(layout):
    """
    显示布局中的所有子部件
    :param layout: 要显示的布局对象（QLayout）
    """
    if not layout:
        return

    for i in range(layout.count()):
        item = layout.itemAt(i)
        widget = item.widget()
        if isinstance(widget, QListWidget):
            widget.setVisible(True)
        elif widget:
            widget.setVisible(True)
        else:
            sub_layout = item.layout()
            if sub_layout:
                show_layout(sub_layout)  # 递归显示子布局


def create_vertical_spacer():
    """
    竖向弹簧
    """
    return QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)


def create_vertical_line():
    """
    横向分割线
    """
    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setFrameShadow(QFrame.Shadow.Sunken)
    return separator


class QMWEditorOfBattlePlan(QMainWindow):

    def __init__(self, func_open_tip):
        super().__init__()

        """布局和控件放置"""

        # 主布局 - 竖直布局
        self.LayMain = QVBoxLayout()

        self.LayTimelineActionList = None
        self.LayNormalActionList = None

        self.ButtonModeChange = None
        self.LabelEditorMode = None
        self.ButtonLoadJson = None
        self.ButtonSave = None
        self.ButtonSaveAs = None

        self.ButtonCopyWave = None
        self.ButtonPasteWave = None
        self.ButtonApplyToAll = None

        self.ButtonPlayer = None
        self.ButtonAddNormalAction = None
        self.ButtonDeleteNormalAction = None
        self.ListNormalActions = None

        self.ButtonAddTimelineAction = None
        self.ButtonDeleteTimelineAction = None
        self.ListTimelineActions = None

        self.EditorAction = None

        self.TextEditTips = None

        self.WidgetStageSelector = None

        self.chessboard_buttons = None
        self.chessboard_frames = None

        self.LabelCurrentBattlePlanFileName = None
        self.LabelCurrentBattlePlanUUID = None

        def init_ui_lay_tip():
            """提示编辑器"""

            self.TextEditTips = QTextEdit()
            self.TextEditTips.setPlaceholderText('在这里编辑提示文本...')
            self.LayMain.addWidget(self.TextEditTips)

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

                    # 分割线
                    self.LayLeft.addWidget(create_vertical_line())

                    # 点击切换放卡编辑模式
                    self.ButtonModeChange = QPushButton('点击切换编辑模式')
                    self.LayLeft.addWidget(self.ButtonModeChange)

                    # 当前模式
                    self.LabelEditorMode = QLabel('当前模式 - 常规循环放卡编辑')
                    self.LabelEditorMode.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                    self.LayLeft.addWidget(self.LabelEditorMode)

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
                    self.ButtonCopyWave = QPushButton('复制')
                    self.ButtonCopyWave.clicked.connect(self.copy_wave_plan)
                    self.ButtonCopyWave.setToolTip(f"复制当前选中波次方案, 保存到剪切板")

                    # 添加粘贴按钮 锁定 不可使用
                    self.ButtonPasteWave = QPushButton('粘贴')
                    self.ButtonPasteWave.clicked.connect(self.paste_wave_plan)
                    self.ButtonPasteWave.setEnabled(False)
                    self.ButtonCopyWave.setToolTip(f"将剪切板中的方案, 粘贴到当前选中波次")

                    # 应用到全部
                    self.ButtonApplyToAll = QPushButton('应用到全部')
                    self.ButtonApplyToAll.clicked.connect(self.apply_to_all_wave_plan)
                    self.ButtonApplyToAll.setToolTip("复制当前选中波次方案, 粘贴到全部波次")

                    # 创建水平布局，来容纳按钮
                    LayWaveAction = QHBoxLayout()
                    LayWaveAction.addWidget(self.ButtonCopyWave)
                    LayWaveAction.addWidget(self.ButtonPasteWave)
                    LayWaveAction.addWidget(self.ButtonApplyToAll)
                    self.LayLeft.addLayout(LayWaveAction)

                def init_ui_lay_save_and_load():
                    """加载和保存按钮"""

                    title_label = QLabel('方案加载与保存')
                    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐

                    self.LabelCurrentBattlePlanFileName = QLabel("当前方案名:无")
                    self.LabelCurrentBattlePlanUUID = QLabel("当前方案UUID:无")

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
                    LaySave.addWidget(self.LabelCurrentBattlePlanFileName)
                    LaySave.addWidget(self.LabelCurrentBattlePlanUUID)
                    LaySave.addLayout(LaySaveBottom)

                    # 添加到总左侧布局
                    self.LayLeft.addLayout(LaySave)

                init_ui_lay_left_top()

                # self.LayLeft.addItem(create_vertical_spacer())
                self.LayLeft.addWidget(create_vertical_line())
                # self.LayLeft.addItem(create_vertical_spacer())

                init_ui_lay_wave_editor()

                # self.LayLeft.addItem(create_vertical_spacer())
                self.LayLeft.addWidget(create_vertical_line())
                self.LayLeft.addItem(create_vertical_spacer())

                self.LayLeft.addItem(create_vertical_spacer())
                self.LayLeft.addWidget(create_vertical_line())
                # self.LayLeft.addItem(create_vertical_spacer())

                init_ui_lay_save_and_load()

            def init_ui_lay_normal_actions():
                """常规操作列表"""

                # 竖向布局
                self.LayNormalActionList = QVBoxLayout()
                self.LayoutMainBottom.addLayout(self.LayNormalActionList)

                # title_label = QLabel('普通放卡编辑')
                # title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                # self.LayNormalActionList.addWidget(title_label)

                title_label = QLabel('左键-选中放卡   右键-编辑参数')
                title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                self.LayNormalActionList.addWidget(title_label)

                self.ButtonPlayer = QPushButton('玩家位置')
                self.LayNormalActionList.addWidget(self.ButtonPlayer)

                self.ButtonAddNormalAction = QPushButton('新增一组放卡操作')
                self.LayNormalActionList.addWidget(self.ButtonAddNormalAction)

                self.ButtonDeleteNormalAction = QPushButton('删除选中放卡操作')
                self.LayNormalActionList.addWidget(self.ButtonDeleteNormalAction)

                # 列表控件
                self.ListNormalActions = QListWidgetDraggable()
                self.ListNormalActions.setMaximumWidth(260)  # 经过验证的完美数字
                self.LayNormalActionList.addWidget(self.ListNormalActions)

            def init_ui_lay_timeline_actions():
                """定时操作列表"""

                # 竖向布局
                self.LayTimelineActionList = QVBoxLayout()
                self.LayoutMainBottom.addLayout(self.LayTimelineActionList)

                # title_label = QLabel('定时操作')
                # title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                # self.LayTimelineActionList.addWidget(title_label)

                title_label = QLabel('左键-选中放卡   右键-编辑参数')
                title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                self.LayTimelineActionList.addWidget(title_label)

                self.ButtonAddTimelineAction = QPushButton('新增定时放卡操作')
                self.LayTimelineActionList.addWidget(self.ButtonAddTimelineAction)

                self.ButtonDeleteTimelineAction = QPushButton('删除定时放卡操作')
                self.LayTimelineActionList.addWidget(self.ButtonDeleteTimelineAction)

                # 列表控件
                self.ListTimelineActions = QListWidgetDraggable()
                self.ListTimelineActions.setMaximumWidth(260)  # 经过验证的完美数字
                self.LayTimelineActionList.addWidget(self.ListTimelineActions)

            def init_ui_lay_chessboard():
                """棋盘布局"""
                self.chessboard_layout = QGridLayout()
                self.LayoutMainBottom.addLayout(self.chessboard_layout)

                # 设置行列间距
                self.chessboard_layout.setSpacing(1)

                # 生成棋盘布局中的元素
                self.chessboard_buttons = []
                self.chessboard_frames = []  # 用于存储QFrame的列表

                for i in range(7):
                    row_buttons = []
                    row_frames = []

                    for j in range(9):
                        # 创建QFrame作为高亮效果的载体
                        frame = QFrame(self)

                        frame.setFrameShadow(QFrame.Shadow.Raised)
                        self.chessboard_layout.addWidget(frame, i, j)
                        frame.lower()  # 确保QFrame在按钮下方
                        frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)  # 防止遮挡按钮

                        # 尽可能让宽和高占满剩余空间
                        frame.setFixedSize(85, 85)

                        row_frames.append(frame)

                        # 创建按钮部分
                        btn = ChessButton('')

                        btn.clicked.connect(lambda checked, x=i, y=j: self.left_click_card_pos(y, x))
                        btn.rightClicked.connect(lambda x=i, y=j: self.right_click_card_pos(y, x))
                        self.chessboard_layout.addWidget(btn, i, j, alignment=Qt.AlignmentFlag.AlignCenter)
                        btn.setToolTip(f"当前位置: {j + 1}-{i + 1}")
                        row_buttons.append(btn)

                        btn.setFixedSize(80, 80)

                    self.chessboard_buttons.append(row_buttons)
                    self.chessboard_frames.append(row_frames)

            init_ui_lay_left()
            init_ui_lay_normal_actions()
            init_ui_lay_timeline_actions()
            init_ui_lay_chessboard()

            # 隐藏定时操作列表
            hide_layout(self.LayTimelineActionList)

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
            self.ButtonAddNormalAction.clicked.connect(self.add_loop_use_cards_one_card)
            # 添加定时放卡操作进入备选槽
            self.ButtonAddTimelineAction.clicked.connect(self.add_insert_use_card)

            # 删除卡片
            self.ButtonDeleteNormalAction.clicked.connect(self.delete_loop_use_cards_one_card)
            self.ButtonDeleteTimelineAction.clicked.connect(self.delete_insert_use_card)

            # 左键 -> 删除目标 / 位置编辑 / 高亮
            # 右键 -> 信息编辑
            self.ListNormalActions.itemClicked.connect(self.be_edited_loop_use_cards_one_card_change)
            self.ListNormalActions.moveRequested.connect(self.event_list_be_moved)
            self.ListNormalActions.editRequested.connect(self.show_edit_window)

            self.ListTimelineActions.itemClicked.connect(self.be_edited_insert_use_card_change)
            self.ListTimelineActions.moveRequested.connect(self.event_list_be_moved)
            self.ListTimelineActions.editRequested.connect(self.show_edit_window)

            self.ButtonPlayer.clicked.connect(self.click_player_button)

            self.ButtonModeChange.clicked.connect(self.change_edit_mode)

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

        # 获取全部关卡信息
        with open(file=PATHS["config"] + "//stage_info.json", mode="r", encoding="UTF-8") as file:
            self.stage_info_all = json.load(file)
        # 当前选择的关卡的信息
        self.stage_info = {}

        """UI状态"""

        # 模式1 - 是常规遍历队列式放卡, 模式2 - 为定时放卡
        self.editing_mode = 1

        # 当前编辑内容
        self.be_edited_player = False
        self.be_edited_wave_id = 0
        self.be_edited_loop_use_cards_one_card_index = None
        self.be_edited_insert_use_card_index = None
        # 剪切板
        self.be_copied_loop_use_cards_event_wave_id = None

        """内部数据表"""

        # 初始化主类 - 包含基础元数据和0波数据
        self.battle_plan: BattlePlan = BattlePlan(
            meta_data=MetaData(uuid="", tips="", player_position=[]),
            cards=[],
            events=[Event(trigger=TriggerWaveTimer(wave_id=0, time=0), action=ActionLoopUseCards(cards=[]))]
        )

        # 根据事件类型分类的事件子类
        self.insert_use_gem_events: List[Event] = []
        self.insert_use_card_events: List[Event] = []
        self.loop_use_cards_events: List[Event] = []

        # 数据主类初始化处理
        self.init_battle_plan()

        """功能数据"""

        # 撤销/重做功能
        self.undo_stack = []
        self.redo_stack = []
        self.undo_shortcut = QShortcut(QKeySequence('Ctrl+Z'), self)
        self.redo_shortcut = QShortcut(QKeySequence('Ctrl+Y'), self)
        self.undo_shortcut.activated.connect(self.undo)
        self.redo_shortcut.activated.connect(self.redo)

        # 加载Json文件
        self.file_path = None

        # 初始化关卡选择
        self.init_stage_selector()

        # 初始选中的波次按钮
        self.click_wave_button(be_clicked_button_id=0)

        # 根据初始数据, 刷新全部UI外观
        self.fresh_all_ui()

        # 初始化方案加载

    """波次相关"""

    def click_wave_button(self, be_clicked_button_id: int):

        CUS_LOGGER.debug(f"[战斗方案编辑器] [界面交互] 波次按钮编号 {be_clicked_button_id}, 被点击")

        """点击波次按钮"""
        self.change_wave(be_clicked_button_id)

        # 修改当前选中波次按钮的文本内容并还原其他按钮的内容
        self.fresh_wave_button_text(be_clicked_button_id=int(be_clicked_button_id))

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

        last_action = next(event.action for event in self.loop_use_cards_events if event.trigger.wave_id == 0)

        color_list_index = 0
        for wave in range(14):
            cursor_action = next(event.action for event in self.loop_use_cards_events if event.trigger.wave_id == wave)

            if cursor_action != last_action:
                color_list_index = (color_list_index + 1) % len(color_list)  # 循环使用颜色列表

            r, g, b = color_list[color_list_index]
            color_with_alpha = f"rgba({r}, {g}, {b}, 0.4)"

            button = self.findChild(QPushButton, f"changeWaveButton_{wave}")
            button.setStyleSheet(f"background-color: {color_with_alpha}")
            last_action = cursor_action

    def change_edit_mode(self):

        if self.editing_mode == 1:
            self.editing_mode = 2
            self.LabelEditorMode.setText("当前模式 - 定时放卡编辑")
            hide_layout(self.LayNormalActionList)
            show_layout(self.LayTimelineActionList)
            self.ButtonCopyWave.setEnabled(False)
            self.ButtonPasteWave.setEnabled(False)
            self.ButtonApplyToAll.setEnabled(False)

            # 取消正在编辑玩家
            self.be_edited_player = False
            self.ButtonPlayer.setText("玩家位置")
            self.be_edited_loop_use_cards_one_card_index = None

        elif self.editing_mode == 2:
            self.editing_mode = 1
            self.LabelEditorMode.setText("当前模式 - 常规循环放卡编辑")
            hide_layout(self.LayTimelineActionList)
            show_layout(self.LayNormalActionList)
            self.ButtonCopyWave.setEnabled(True)
            self.ButtonPasteWave.setEnabled(True)
            self.ButtonApplyToAll.setEnabled(True)
            self.be_edited_insert_use_card_index = None

        self.fresh_all_ui()

    def change_wave(self, wave: int):

        self.be_edited_wave_id = wave

        # 去除选中
        self.be_edited_player = False
        self.ButtonPlayer.setText("玩家位置")
        self.be_edited_insert_use_card_index = None
        self.be_edited_loop_use_cards_one_card_index = None

        # 关闭放卡动作编辑框
        self.close_edit_window()

        # 重载UI
        self.fresh_all_ui()

    def copy_wave_plan(self):
        """复制"""

        # 仅在模式1中允许复制
        if self.editing_mode != 1:
            return

        self.be_copied_loop_use_cards_event_wave_id = copy.deepcopy(self.be_edited_wave_id)

        # 复制后 允许其粘贴
        self.ButtonPasteWave.setEnabled(True)

        CUS_LOGGER.debug(
            f"[战斗方案编辑器] 已复制循环放卡事件, 波次编号: {self.be_copied_loop_use_cards_event_wave_id}")

    def paste_wave_plan(self):

        # 仅在模式1中允许粘贴
        if self.editing_mode != 1:
            return

        from_event = next(
            e for e in self.loop_use_cards_events
            if e.trigger.wave_id == self.be_copied_loop_use_cards_event_wave_id
        )

        to_event = next(
            e for e in self.loop_use_cards_events
            if e.trigger.wave_id == self.be_edited_wave_id
        )

        to_event.action = copy.deepcopy(from_event.action)

        self.fresh_all_ui()

        CUS_LOGGER.debug(
            f"[战斗方案编辑器] 已粘贴波次, 编号: {self.be_copied_loop_use_cards_event_wave_id} -> {self.be_edited_wave_id}")

    def apply_to_all_wave_plan(self):
        """应用到全部"""

        # 仅在模式1中允许复制到全部
        if self.editing_mode != 1:
            return

        to_action = next(e.action for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
        for e in self.loop_use_cards_events:
            if e.trigger.wave_id == self.be_edited_wave_id:
                continue
            e.action = copy.deepcopy(to_action)

        # 仅需变色波次按钮颜色
        self.refresh_wave_button_color()

        CUS_LOGGER.debug(f"[战斗方案编辑器] 波次:{self.be_edited_wave_id}方案已应用到所有波次")

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
        self.load_data_to_ui_list_mode_1()
        self.load_data_to_ui_list_mode_2()

        # 重绘 UI棋盘网格
        self.refresh_chessboard()

        # 刷新波次按钮颜色
        self.refresh_wave_button_color()

        # 刷新棋盘高亮
        self.highlight_chessboard()

    """放卡动作列表操作"""

    def click_player_button(self):

        # 用 -1 代表正在编辑玩家位置
        self.be_edited_player = True
        self.ButtonPlayer.setText(">> 玩家位置 <<")
        self.be_edited_loop_use_cards_one_card_index = None

        self.highlight_chessboard()

    def be_edited_loop_use_cards_one_card_change(self, item):
        """被单击后, 被选中的卡片改变了"""

        # 不再编辑玩家位置
        self.be_edited_player = False
        self.ButtonPlayer.setText("玩家位置")

        # list的index 是 QModelIndex 此处还需要获取到行号
        self.be_edited_loop_use_cards_one_card_index = self.ListNormalActions.indexFromItem(item).row()

        # 高亮棋盘
        self.highlight_chessboard()

        print(f"编辑 - 位置 - 普通动作编辑 目标改变: {self.be_edited_loop_use_cards_one_card_index}")

    def be_edited_insert_use_card_change(self, item):
        """被单击后, 被选中的卡片改变了"""

        # list的index 是 QModelIndex 此处还需要获取到行号
        self.be_edited_insert_use_card_index = self.ListTimelineActions.indexFromItem(item).row()

        # 高亮棋盘
        self.highlight_chessboard()

        print(f"编辑 - 位置 - 定时动作编辑 目标改变: {self.be_edited_insert_use_card_index}")

    def load_data_to_ui_list_mode_1(self):
        """从 [内部数据表] 载入数据到 [ui的放卡动作列表]"""

        if self.editing_mode != 1:
            return

        self.ListNormalActions.clear()

        current_event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)

        # 根据中文和西文分别记录最高宽度
        name_max_width_c = 0
        name_max_width_e = 0
        for a_card in current_event.action.cards:
            card_name = next(c.name for c in self.battle_plan.cards if c.card_id == a_card.card_id)
            width_c, width_e = calculate_text_width(card_name)
            name_max_width_c = max(name_max_width_c, width_c)
            name_max_width_e = max(name_max_width_e, width_e)

        if not current_event.action.cards:
            return

        # 找到最长的id长度
        max_id_length = max(len(str(a_card.card_id)) for a_card in current_event.action.cards)

        for a_card in current_event.action.cards:

            card_name = next(c.name for c in self.battle_plan.cards if c.card_id == a_card.card_id)

            # 根据中文和西文 分别根据距离相应的最大宽度的差值填充中西文空格
            width_c, width_e = calculate_text_width(card_name)
            padded_name = str(card_name)
            padded_name += "\u2002" * (name_max_width_e - width_e)  # 半宽空格
            padded_name += '\u3000' * (name_max_width_c - width_c)  # 表意空格(方块字空格)

            padded_id = str(a_card.card_id).ljust(max_id_length)

            text = "{}  ID:{}  遍历:{}  队列:{}".format(
                padded_name,
                padded_id,
                "√" if a_card.ergodic else "X",
                "√" if a_card.queue else "X"
            )

            if a_card.kun:
                text += "  坤:{}".format(a_card.kun)

            item = QListWidgetItem(text)
            self.ListNormalActions.addItem(item)

    def load_data_to_ui_list_mode_2(self):
        """从 [内部数据表] 载入数据到 [ui的放卡动作列表]"""

        if self.editing_mode != 2:
            return

        self.ListTimelineActions.clear()

        events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]

        # 根据中文和西文分别记录最高宽度
        name_max_width_c = 0
        name_max_width_e = 0
        for event in events:
            card_name = next(c.name for c in self.battle_plan.cards if c.card_id == event.action.card_id)
            width_c, width_e = calculate_text_width(card_name)
            name_max_width_c = max(name_max_width_c, width_c)
            name_max_width_e = max(name_max_width_e, width_e)

        # 找到最长的id长度
        if not events:
            return
        max_id_length = max(len(str(event.action.card_id)) for event in events)

        for event in events:
            # 根据中文和西文 分别根据距离相应的最大宽度的差值填充中西文空格
            card_name = next(c.name for c in self.battle_plan.cards if c.card_id == event.action.card_id)
            width_c, width_e = calculate_text_width(card_name)
            padded_name = str(card_name)
            padded_name += "\u2002" * (name_max_width_e - width_e)  # 半宽空格
            padded_name += '\u3000' * (name_max_width_c - width_c)  # 表意空格(方块字空格)

            padded_id = str(event.action.card_id).ljust(max_id_length)

            text = "{}s {}  ID:{} 先铲{} 放后{}s 后铲{} ".format(
                event.trigger.time,
                padded_name,
                padded_id,
                "√" if event.action.before_shovel else "X",
                event.action.after_shovel_time,
                "√" if event.action.after_shovel else "X"
            )

            item = QListWidgetItem(text)
            self.ListTimelineActions.addItem(item)

    def event_list_be_moved(self, index_from, index_to):
        """在list的drop事件中调用, 用于更新内部数据表"""

        # 将当前状态压入栈中
        self.append_undo_stack()

        if self.editing_mode == 1:
            current_event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
            cards = current_event.action.cards

            tar_card = cards.pop(index_from)
            cards.insert(index_to, tar_card)

            CUS_LOGGER.debug(tar_card)
            CUS_LOGGER.debug("当前波次 循环放卡 数据已更新: {}".format(cards))

            self.load_data_to_ui_list_mode_1()

        if self.editing_mode == 2:
            events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]
            tar_event = events.pop(index_from)
            self.insert_use_card_events.remove(tar_event)
            self.insert_use_card_events.insert(index_to, tar_event)

            CUS_LOGGER.debug(tar_event)
            CUS_LOGGER.debug("当前波次 插入放卡 数据已更新: {}".format(self.insert_use_card_events))

            self.load_data_to_ui_list_mode_2()

        # 刷新波次上色
        self.refresh_wave_button_color()

    """放卡动作属性编辑"""

    def close_edit_window(self):
        if hasattr(self, "edit_window"):
            self.edit_window.close()

    def show_edit_window(self, list_item):

        self.close_edit_window()

        # 创建新窗口 个路径模式不同

        if self.editing_mode == 1:

            print("即将显示 常规动作编辑窗口 索引 - ", self.be_edited_loop_use_cards_one_card_index)

            event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
            a_card = event.action.cards[self.be_edited_loop_use_cards_one_card_index]
            o_card = next(o_card for o_card in self.battle_plan.cards if o_card.card_id == a_card.card_id)
            data = {
                "id": a_card.card_id,
                "name": o_card.name,
                "ergodic": a_card.ergodic,
                "queue": a_card.queue,
                "kun": a_card.kun
            }
            self.EditorAction = LoopUseCardsOneCardInfoEditor(
                data=data,
                func_update=self.update_loop_use_cards_one_card_info
            )

        else:

            print("即将显示 定时动作编辑窗口 索引 - ", self.be_edited_insert_use_card_index)

            events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]
            event = events[self.be_edited_insert_use_card_index]
            o_card = next(o_card for o_card in self.battle_plan.cards if o_card.card_id == event.action.card_id)
            data = {
                "card_id": event.action.card_id,
                "name": o_card.name,
                "time": event.trigger.time,
                "before_shovel": event.action.before_shovel,
                "after_shovel": event.action.after_shovel,
                "after_shovel_time": event.action.after_shovel_time
            }

            self.EditorAction = InsertUseCardInfoEditor(
                data=data,
                func_update=self.update_insert_use_card_info
            )

        # 计算显示位置
        global_pos = self.ListNormalActions.viewport().mapToGlobal(
            self.ListNormalActions.visualItemRect(list_item).topRight()
        )
        self.EditorAction.move(global_pos + QPoint(20, 0))

        # 完成显示
        # self.card_action_editor.show()

        # 事件循环!~
        self.EditorAction.exec()

    def add_loop_use_cards_one_card(self):

        event = next(event for event in self.loop_use_cards_events if event.trigger.wave_id == self.be_edited_wave_id)
        cards = event.action.cards
        ids_list = [card.card_id for card in cards]
        for i in range(1, 22):
            if i not in ids_list:
                id_ = i
                break
        else:
            id_ = 1
            QMessageBox.information(self, "注意！", "若您完全理解为什么是'动作列表' 而非 '卡片列表', 请继续操作")

        cards.append(
            CardLoopConfig(
                card_id=id_,
                ergodic=True,
                queue=True,
                location=[],
                kun=0
            )
        )

        self.fresh_all_ui()

    def add_insert_use_card(self):

        self.insert_use_card_events.append(
            Event(
                trigger=TriggerWaveTimer(
                    wave_id=self.be_edited_wave_id,
                    time=0
                ),
                action=ActionInsertUseCard(
                    card_id=1,
                    after_shovel_time=0,
                    before_shovel=False,
                    after_shovel=False,
                    location=""
                )
            )
        )

        self.fresh_all_ui()

    def delete_loop_use_cards_one_card(self):
        """
        选中一组放卡操作后, 点击按钮, 删除它
        :return: None
        """

        if self.be_edited_loop_use_cards_one_card_index is None:
            QMessageBox.information(self, "操作错误！", "请先选择一个对象(卡片)!")
            return False

        # 将当前状态压入栈中
        self.append_undo_stack()

        event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
        cards = event.action.cards
        del cards[self.be_edited_loop_use_cards_one_card_index]

        # 清空选中的卡片
        self.be_edited_loop_use_cards_one_card_index = None

        self.fresh_all_ui()

    def delete_insert_use_card(self):
        """
        选中一组定时放卡操作后, 点击按钮, 删除它
        :return: None
        """

        if self.be_edited_insert_use_card_index is None:
            QMessageBox.information(self, "操作错误！", "请先选择一个对象(定时放卡)!")
            return False

        # 将当前状态压入栈中
        self.append_undo_stack()

        events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]
        event = events[self.be_edited_insert_use_card_index]
        self.insert_use_card_events.remove(event)

        # 清空选中的卡片
        self.be_edited_insert_use_card_index = None

        self.fresh_all_ui()

    def update_loop_use_cards_one_card_info(self):
        """
        在UI上编辑更新一组放卡操作的状态后
        将该操作同步到内部数据表
        并刷新到左侧列表和棋盘等位置
        :return: None
        """

        print("即将更新 当前波次的 循环用卡中 被选中卡片的数据, 索引: ", self.be_edited_loop_use_cards_one_card_index)

        # 将当前状态压入栈中
        self.append_undo_stack()

        cards = next(e.action.cards for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
        a_card = cards[self.be_edited_loop_use_cards_one_card_index]
        o_card = next(o_card for o_card in self.battle_plan.cards if o_card.card_id == a_card.card_id)

        ui_value = int(self.EditorAction.WidgetIdInput.value())
        if a_card.card_id != ui_value:
            a_card.card_id = ui_value
            card_name = next(o_card.name for o_card in self.battle_plan.cards if o_card.card_id == a_card.card_id)
            self.EditorAction.WidgetNameInput.setText(card_name)
            self.fresh_all_ui()
            return

        ui_value = self.EditorAction.WidgetNameInput.text()
        if o_card.name != ui_value:
            o_card.name = ui_value
            self.fresh_all_ui()
            return

        ui_value = bool(self.EditorAction.WidgetErgodicInput.currentText() == 'true')
        if a_card.ergodic != ui_value:
            a_card.ergodic = ui_value
            self.fresh_all_ui()
            return

        ui_value = bool(self.EditorAction.WidgetQueueInput.currentText() == 'true')
        if a_card.queue != ui_value:
            a_card.queue = ui_value
            self.fresh_all_ui()
            return

        ui_value = self.EditorAction.WidgetKunInput.value()
        if a_card.kun != ui_value:
            a_card.kun = ui_value
            self.fresh_all_ui()
            return

    def update_insert_use_card_info(self):
        """
        在UI上编辑更新一组定时放卡操作的状态后
        将该操作同步到内部数据表
        并刷新到左侧列表和棋盘等位置
        :return: None
        """

        print("即将更新 当前波次的 定时用卡中 被选中卡片的数据, 索引: ", self.be_edited_insert_use_card_index)

        # 将当前状态压入栈中
        self.append_undo_stack()

        events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]
        e = events[self.be_edited_insert_use_card_index]
        o_card = next(o_card for o_card in self.battle_plan.cards if o_card.card_id == e.action.card_id)

        ui_value = int(self.EditorAction.WidgetIdInput2.value())
        if e.action.card_id != ui_value:
            e.action.card_id = ui_value
            card_name = next(o_card.name for o_card in self.battle_plan.cards if o_card.card_id == e.action.card_id)
            self.EditorAction.WidgetNameInput2.setText(card_name)
            self.fresh_all_ui()
            return

        ui_value = self.EditorAction.WidgetNameInput2.text()
        if o_card.name != ui_value:
            o_card.name = ui_value
            self.fresh_all_ui()
            return

        ui_value = float(self.EditorAction.WidgetTimeInput.value())
        if e.trigger.time != ui_value:
            e.trigger.time = ui_value
            self.fresh_all_ui()
            return

        ui_value = bool(self.EditorAction.WidgetBeforeShovelInput.currentText() == 'true')
        if e.action.before_shovel != ui_value:
            e.action.before_shovel = ui_value
            self.fresh_all_ui()
            return

        ui_value = bool(self.EditorAction.WidgetAfterShovelInput.currentText() == 'true')
        if e.action.after_shovel != ui_value:
            e.action.after_shovel = ui_value
            self.fresh_all_ui()
            return

        ui_value = int(self.EditorAction.WidgetAfterTimeInput.value())
        if e.action.after_shovel_time != ui_value:
            e.action.after_shovel_time = ui_value
            self.fresh_all_ui()
            return

    """棋盘操作"""

    def left_click_card_pos(self, x, y):
        """
        选中一组放卡操作后, 为该操作添加一个放置位置
        :return: None
        """

        # 初始化格子key
        location_key = f"{x + 1}-{y + 1}"
        # 将当前状态压入栈中
        self.append_undo_stack()

        # 遍历队列模式
        if self.editing_mode == 1:

            if self.be_edited_player:

                # 将当前状态压入栈中
                self.append_undo_stack()

                # 当前index为玩家
                target = self.battle_plan.meta_data.player_position
                # 如果这个位置已经有了玩家，那么移除它；否则添加它
                if location_key in target:
                    target.remove(location_key)
                else:
                    target.append(location_key)

            elif self.be_edited_loop_use_cards_one_card_index is not None:

                # 将当前状态压入栈中
                self.append_undo_stack()

                # 当前index为卡片
                event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
                target = event.action.cards[self.be_edited_loop_use_cards_one_card_index]
                # 如果这个位置已经有了这张卡片，那么移除它；否则添加它
                if location_key in target.location:
                    target.location.remove(location_key)
                else:
                    target.location.append(location_key)

        # 定时放卡模式
        if self.editing_mode == 2 and self.be_edited_insert_use_card_index is not None:
            # 将当前状态压入栈中
            self.append_undo_stack()

            events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]
            event = events[self.be_edited_insert_use_card_index]
            event.action.location = "" if event.action.location == location_key else location_key

        self.refresh_chessboard()
        self.refresh_wave_button_color()
        self.highlight_chessboard()

    def right_click_card_pos(self, x, y):
        """
        清空一个格子在当前模式下所有的放卡操作
        :param x:
        :param y:
        :return:
        """

        # 初始化格子key
        location_key = f"{x + 1}-{y + 1}"
        # 将当前状态压入栈中
        self.append_undo_stack()

        if self.editing_mode == 1:

            if self.be_edited_player:
                # 从玩家位置中删除
                if location_key in self.battle_plan.meta_data.player_position:
                    self.battle_plan.meta_data.player_position.remove(location_key)
            else:
                # 从卡片位置中删除
                event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
                cards = event.action.cards
                for card in cards:
                    if location_key in card.location:
                        card.location.remove(location_key)

        if self.editing_mode == 2:

            # 移除此位置的所有定时放卡计划
            events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]
            for event in events:
                if event.action.location == location_key:
                    event.action.location = ""

        self.refresh_chessboard()
        self.refresh_wave_button_color()
        self.highlight_chessboard()

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

                # 这一个格子的 坐标
                this_location = f"{j + 1}-{i + 1}"

                text_block = []

                if self.editing_mode == 1:

                    # 如果玩家在这个位置，添加 "玩家" 文字

                    player_location_list = self.battle_plan.meta_data.player_position
                    if this_location in player_location_list:
                        text_block.append('玩家 {}'.format(player_location_list.index(this_location) + 1))

                    # 遍历这个格子有放置的卡片

                    cards_in_this_location = []

                    events = self.loop_use_cards_events
                    event = next((e for e in events if e.trigger.wave_id == self.be_edited_wave_id), None)
                    a_cards = event.action.cards if event else []

                    for a_card in a_cards:
                        if this_location in a_card.location:
                            cards_in_this_location.append(a_card)

                    for a_card in cards_in_this_location:
                        # 名称
                        o_card = next(c for c in self.battle_plan.cards if c.card_id == a_card.card_id)
                        text = truncate_text(text=o_card.name)
                        # 编号
                        c_index_list = a_card.location.index(this_location) + 1
                        text += " {}".format(c_index_list)
                        text_block.append(text)

                if self.editing_mode == 2:

                    for event in self.insert_use_card_events:
                        if event.trigger.wave_id != self.be_edited_wave_id:
                            continue
                        if event.action.location == this_location:
                            card_name = next(
                                c.name for c in self.battle_plan.cards if c.card_id == event.action.card_id)
                            text_block.append(f"{card_name} {event.trigger.time}s")

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

        if self.editing_mode == 1:

            current_card_locations = []


            if self.be_edited_player:
                current_card_locations = self.battle_plan.meta_data.player_position
            else:
                if self.be_edited_loop_use_cards_one_card_index is not None:
                    event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
                    a_card = event.action.cards[self.be_edited_loop_use_cards_one_card_index]
                    current_card_locations = a_card.location

            for location in current_card_locations:
                x, y = map(int, location.split('-'))
                selected_cells.add((x, y))
                # 如果是选中的卡片 蓝色
                self.chessboard_frames[y - 1][x - 1].setStyleSheet("background-color: rgba(30, 144, 255, 150);")

        if self.editing_mode == 2:

            if self.be_edited_insert_use_card_index is not None:

                events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]
                event = events[self.be_edited_insert_use_card_index]
                location = event.action.location

                if location:
                    x, y = map(int, location.split('-'))
                    selected_cells.add((x, y))
                    # 如果是选中的卡片 蓝色
                    self.chessboard_frames[y - 1][x - 1].setStyleSheet("background-color: rgba(30, 144, 255, 150);")

        # 还没有选中任何关卡 直接返回
        if self.stage_info:
            obstacle = self.stage_info.get("obstacle", [])
            if obstacle:  # 障碍物，在frame上显示红色
                for location in obstacle:  # location格式为："y-x"
                    x, y = map(int, location.split("-"))
                    if (x, y) in selected_cells:
                        # 如果是被选中的格子，设置为紫色 警告
                        self.chessboard_frames[y - 1][x - 1].setStyleSheet(
                            "background-color: rgba(145, 44, 238, 150);")
                    else:
                        # 否则设置为红色 代表障碍位置
                        self.chessboard_frames[y - 1][x - 1].setStyleSheet(
                            "background-color: rgba(255, 0, 0, 150);")

    """储存战斗方案"""

    def save_json(self):
        """
        保存方法，拥有保存和另存为两种功能，还能创建uuid
        """

        def clear_redundant():
            """
            根据三重规则 清理方案
            1. 清理和上一波方案相同的所有 常规遍历放卡
            2. 清理所有没有被使用的卡片
            3. 清理没有标注位置的定时放卡
            """

            # 根据规则1 收集
            wave_ids_to_remove = []
            current_action = next((e.action for e in self.loop_use_cards_events if e.trigger.wave_id == 0), None)
            for wave_id in range(1, 14):
                wave_action = next((e.action for e in self.loop_use_cards_events if e.trigger.wave_id == wave_id), None)
                if wave_action == current_action:
                    wave_ids_to_remove.append(wave_id)
                else:
                    current_action = wave_action

            # 根据规则1 移除 (反向索引)
            self.loop_use_cards_events = [
                event
                for event in self.loop_use_cards_events
                if event.trigger.wave_id not in wave_ids_to_remove
            ]

            # 根据规则2 收集
            used_card_ids = []
            for event in self.battle_plan.events:
                # 遍历放卡
                if type(event.action) is ActionLoopUseCards:
                    for card_used in event.action.cards:
                        if card_used.card_id not in used_card_ids:
                            used_card_ids.append(card_used.card_id)
                # 插入放卡
                if type(event.action) is ActionInsertUseCard:
                    if event.action.card_id not in used_card_ids:
                        used_card_ids.append(event.action.card_id)
            # 根据规则2 移除
            self.battle_plan.cards = [
                card
                for card in self.battle_plan.cards
                if card.card_id in used_card_ids
            ]

            # 根据规则3 直接反向遍历 完成删除
            for i in reversed(range(len(self.insert_use_card_events))):
                if self.insert_use_card_events[i].action.location == "":
                    del self.insert_use_card_events[i]  # 按索引删除，不影响未遍历的元素

        clear_redundant()

        def view_to_obj_battle_plan():
            """
            将修改的视图放回战斗方案中 以反序列化
            :return:
            """
            self.battle_plan.events.clear()
            self.battle_plan.events.extend(copy.deepcopy(event) for event in self.loop_use_cards_events)
            self.battle_plan.events.extend(copy.deepcopy(event) for event in self.insert_use_card_events)
            self.battle_plan.events.extend(copy.deepcopy(event) for event in self.insert_use_gem_events)

        view_to_obj_battle_plan()

        is_save_as = self.sender() == self.ButtonSaveAs

        def warning_save_enable(uuid):

            warning_uuids = ["00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000001"]
            if uuid not in warning_uuids:
                return True

            text = ("FAA部分功能(美食大赛/公会任务)依赖这两份默认方案(1卡组-通用-1P & 1卡组-通用-2P)运行.\n"
                    "你确定要保存并修改他们吗! 这可能导致相关功能出现错误!")
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

        self.battle_plan.meta_data.tips = self.TextEditTips.toPlainText()

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
            self.battle_plan.meta_data.uuid = str(uuid.uuid1())

        else:
            # 覆盖现有文件的情况
            with EXTRA.FILE_LOCK:
                with open(file=new_file_path, mode='r', encoding='utf-8') as file:
                    tar_uuid = json.load(file).get('meta_data', {}).get('uuid', None)

            if not tar_uuid:
                # 被覆盖的目标没有uuid 生成uuid
                self.battle_plan.meta_data.uuid = str(uuid.uuid1())

            else:
                # 高危uuid需要确定
                if not warning_save_enable(uuid=tar_uuid):
                    return
                # 被覆盖的目标有uuid 使用存在的uuid
                self.battle_plan.meta_data.uuid = tar_uuid

        # 确保文件名后缀是.json
        new_file_path = os.path.splitext(new_file_path)[0] + '.json'

        # 转化为json
        json_data = obj_to_json(self.battle_plan)

        # 排序一下cards
        json_data["cards"].sort(key=lambda x: x["card_id"])

        # 保存
        with EXTRA.FILE_LOCK:
            with open(file=new_file_path, mode='w', encoding='utf-8') as file:
                json.dump(json_data, file, ensure_ascii=False, indent=4)

        # 打开新建 or 覆盖掉的文件
        self.load_json(file_path=new_file_path)

        self.init_battle_plan()

        self.ButtonSave.setEnabled(True)

    """打开战斗方案"""

    def open_battle_plan(self):

        file_name = self.open_json()

        if file_name:
            result = self.load_json(file_path=file_name)
            if result:
                self.init_battle_plan()
                self.ButtonSave.setEnabled(True)
            else:
                QMessageBox.critical(
                    self, "JSON文件格式错误",
                    "战斗方案解析失败!!!\n"
                    "\n"
                    "可能原因1 - 方案版本过低\n"
                    "该版本的战斗方案编辑器, 仅支持战斗方案v3.0数据格式 (对应FAA v2.2.0+).\n"
                    "FAA自带战斗方案跨版本升级机制, 支持新特性的同时保留原有数据.\n"
                    "重启FAA v2.2.0+, 将自动对battle_plan文件夹中的战斗方案, 启用升级.\n"
                    "当前版本 可将 v2.0方案 (对应FAA v2.0.0 - v2.1.2) 升级到 v3.0方案 \n"
                    "\n"
                    "更低版本的v1.0方案 (对应FAA v1.x.x版本) 请使用 FAA v2.0.0 - v2.1.2\n"
                    "升级至 v2.0方案 后, 再使用当前版本升级至 v3.0方案, 两步完成升级.\n"
                    "\n"
                    "部分远古版本战斗方案则无法再完成升级, 不再进行过度的向下兼容, 请重新构筑.\n"
                    "\n"
                    "可能原因2 - 使用记事本等工具手动进行错误修改, 请删除对应战斗方案重新编写.\n"
                )

    def open_json(self):
        """打开窗口 打开json文件"""

        file_name, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="打开 JSON 文件",
            directory=PATHS["battle_plan"],
            filter="JSON Files (*.json)")

        return file_name

    def load_json(self, file_path) -> bool:
        """
        读取对应的json文件, 几乎总是要接着 init_battle_plan()
        """

        with EXTRA.FILE_LOCK:
            with open(file=file_path, mode='r', encoding='utf-8') as file:
                json_dict = json.load(file)

        try:
            battle_plan = json_to_obj(json_dict)
        except Exception:
            return False

        # 序列化为类! 加入光荣的进化!
        self.battle_plan = battle_plan

        self.TextEditTips.setPlainText(self.battle_plan.meta_data.tips)

        # 储存当前方案路径
        self.file_path = file_path

        # 获取当前方案的名称
        current_plan_name = os.path.basename(file_path).replace(".json", "")
        CUS_LOGGER.debug(f"[战斗方案编辑器] [加载方案] 开始读取:{current_plan_name}")

        self.LabelCurrentBattlePlanFileName.setText(f"当前方案名:{current_plan_name}")
        self.LabelCurrentBattlePlanUUID.setText(f"{self.battle_plan.meta_data.uuid}")

        return True

    def init_battle_plan(self):
        """
        在读取方案后
        0. 按照需求 进行分类, 方便之后展开工作
        1. 填充该方案空白部分
        2. 并初始化大量控件
        """

        # 类型1 波次变阵
        self.loop_use_cards_events: List[Event] = [
            event for event in self.battle_plan.events
            if (type(event.trigger) is TriggerWaveTimer and
                event.trigger.time == 0 and
                type(event.action) is ActionLoopUseCards)
        ]

        # 类型2 波次定时插卡
        self.insert_use_card_events: List[Event] = [
            event for event in self.battle_plan.events
            if (isinstance(event.trigger, TriggerWaveTimer) and
                isinstance(event.action, ActionInsertUseCard))
        ]

        # 类型3 波次定时宝石
        self.insert_use_gem_events: List[Event] = [
            event for event in self.battle_plan.events
            if (isinstance(event.trigger, TriggerWaveTimer) and
                isinstance(event.action, ActionUseGem))
        ]

        # 填充构造所有波次的 变阵操作 保存的时候再去掉重复项
        self.fill_blank_wave()

        # 填充构造所有卡牌 保存时去掉没有被使用的项
        self.fill_blank_card()

        # 初始化当前选中
        self.editing_mode = 1
        self.be_edited_wave_id = 0
        self.be_edited_loop_use_cards_one_card_index = None
        self.be_edited_insert_use_card_index = None
        self.be_copied_loop_use_cards_event_wave_id = None
        self.be_edited_player = False
        self.ButtonPlayer.setText("玩家位置")

        # 回到波次0方案 并载入方案波次
        self.click_wave_button(be_clicked_button_id=0)

        # 刷新全部视图
        self.fresh_all_ui()

    def fill_blank_wave(self):
        """
        加载时, 将空白波次的方案设定为自动继承状态
        :return: 是否成功加载方案, 为False 则 方案有严重问题 需要立刻中止
        """

        CUS_LOGGER.debug("[战斗方案编辑器] [加载方案] 填充循环放卡方案的空白波次, 开始")

        existing_wave_ids = [w.trigger.wave_id for w in self.loop_use_cards_events]

        if 0 not in existing_wave_ids:
            CUS_LOGGER.debug(f"[战斗方案编辑器] [加载方案] 填充循环放卡方案的空白波次, 波次0不存在, 花瓶方案, 补充第0波方案.")
            self.loop_use_cards_events.append(
                Event(
                    trigger=TriggerWaveTimer(wave_id=0, time=0),
                    action=ActionLoopUseCards(cards=[], type="loop_use_cards"))
            )
            existing_wave_ids = [0]

        for wave in range(14):

            if wave in existing_wave_ids:
                CUS_LOGGER.debug(f"[战斗方案编辑器] [加载方案] 波次: {wave}, 文件已包含")
                continue

            # 如果没有任何现有波次，则使用默认方案
            if wave not in existing_wave_ids:
                smaller_waves = [w for w in existing_wave_ids if w < wave]
                max_smaller_wave = max(smaller_waves)

                tar_action = copy.deepcopy(
                    next(e for e in self.loop_use_cards_events if e.trigger.wave_id == max_smaller_wave).action
                )

                self.loop_use_cards_events.append(
                    Event(trigger=TriggerWaveTimer(wave_id=wave, time=0), action=tar_action))

                CUS_LOGGER.debug(f"[战斗方案编辑器] [加载方案] 波次: {wave}, 已从波次{max_smaller_wave}完成继承")

        CUS_LOGGER.debug("[战斗方案编辑器] [加载方案] 填充循环放卡方案的空白波次, 正确结束")

        return True

    def fill_blank_card(self):
        """
        填充战斗方案中缺失的卡片
        :return:
        """
        used_card_id_list = [card.card_id for card in self.battle_plan.cards]
        for cid in range(1, 22):
            if cid not in used_card_id_list:
                self.battle_plan.cards.append(Card(card_id=cid, name="新的卡片"))

    """撤回/重做"""

    def append_undo_stack(self):
        # 将当前状态压入栈中
        self.undo_stack.append(copy.deepcopy(self.battle_plan))
        # 清空重做栈
        self.redo_stack.clear()
        # 只保留20次操作
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)

    def undo(self):
        """撤销"""
        if len(self.undo_stack) > 0:
            current_state = copy.deepcopy(self.battle_plan)
            self.redo_stack.append(current_state)
            self.battle_plan = self.undo_stack.pop()
            self.fresh_all_ui()

    def redo(self):
        """重做"""
        if len(self.redo_stack) > 0:
            current_state = copy.deepcopy(self.battle_plan)
            self.undo_stack.append(current_state)
            self.battle_plan = self.redo_stack.pop()

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

    def stage_changed(self, stage_name: str, stage_id: str):
        """
        :param stage_name: 关卡名称
        :param stage_id：XX-X-X
        根据stage_info，使某些格子显示成障碍物或更多内容
        """
        id0, id1, id2 = stage_id.split("-")
        self.stage_info = self.stage_info_all[id0][id1][id2]

        # 高亮棋盘
        self.highlight_chessboard()


class QListWidgetDraggable(QListWidget):
    # 编辑窗口开启
    editRequested = pyqtSignal(object)

    # 跟随移动修改数据表
    moveRequested = pyqtSignal(int, int)

    def __init__(self):
        super(QListWidgetDraggable, self).__init__()

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

        CUS_LOGGER.debug(
            "text:{} from {} to {} memory:{}".format(item.text(), index_from, index_to, self.currentRow()))

        # 执行更改函数
        self.moveRequested.emit(index_from, index_to)

    def mouseReleaseEvent(self, e):
        item = self.itemAt(e.pos())

        if item:
            self.itemClicked.emit(item)
            if e.button() == Qt.MouseButton.RightButton:
                self.editRequested.emit(item)

        # 调用父类的 mouseReleaseEvent 以确保正常的左键行为
        super().mouseReleaseEvent(e)


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


class LoopUseCardsOneCardInfoEditor(QDialog):
    def __init__(self, data, func_update):
        super().__init__()
        self.data = data
        self.func_update = func_update

        # 窗口标题栏
        self.setWindowTitle("编辑常规放卡动作参数")

        # 关键组合：彻底移除系统菜单图标
        self.setWindowFlags(
            Qt.WindowType.CustomizeWindowHint |  # 允许自定义窗口装饰
            Qt.WindowType.WindowCloseButtonHint |  # 仅保留关闭按钮
            Qt.WindowType.WindowStaysOnTopHint  # 窗口置顶
        )

        # UI
        self.WidgetIdInput = None
        self.WidgetNameInput = None
        self.WidgetErgodicInput = None
        self.WidgetQueueInput = None
        self.WidgetKunInput = None
        self.init_ui()

        # 初始化数据
        self.load_data()

        # 绑定变化信号
        self.connect_functions()

    def init_ui(self):
        LayMain = QVBoxLayout()
        self.setLayout(LayMain)

        # ID
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        label = QLabel('卡片顺位(ID)')
        layout.addWidget(label)

        self.WidgetIdInput = QSpinBox()
        self.WidgetIdInput.setFixedWidth(140)
        self.WidgetIdInput.setToolTip("卡在卡组中的第几张")
        self.WidgetIdInput.setRange(1, 21)
        layout.addWidget(self.WidgetIdInput)

        # 名称
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        label = QLabel('名称')
        layout.addWidget(label)

        self.WidgetNameInput = QLineEdit()
        self.WidgetNameInput.setFixedWidth(140)
        self.WidgetNameInput.setToolTip(
            "名称标识是什么卡片\n"
            "手动带卡: 能让用户看懂该带啥就行.\n"
            "自动带卡: 需要遵从命名规范, 请查看右上角教学或相关文档."
        )
        layout.addWidget(self.WidgetNameInput)

        # 分割线
        LayMain.addWidget(create_vertical_line())

        # 遍历
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        tooltips = "队列和遍历不知道是什么可以全true, 具体请参见详细文档"
        label = QLabel('遍历')
        label.setToolTip(tooltips)
        layout.addWidget(label)

        self.WidgetErgodicInput = QComboBox()
        self.WidgetErgodicInput.setFixedWidth(140)
        self.WidgetErgodicInput.addItems(['true', 'false'])
        self.WidgetErgodicInput.setToolTip(tooltips)
        layout.addWidget(self.WidgetErgodicInput)

        # 队列
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        tooltips = "队列和遍历不知道是什么可以全true, 具体请参见详细文档"
        label = QLabel('队列')
        label.setToolTip(tooltips)
        layout.addWidget(label)

        self.WidgetQueueInput = QComboBox()
        self.WidgetQueueInput.setFixedWidth(140)
        self.WidgetQueueInput.addItems(['true', 'false'])
        self.WidgetQueueInput.setToolTip(tooltips)
        layout.addWidget(self.WidgetQueueInput)

        # 幻鸡优先级
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        tooltips = "卡片使用幻幻鸡复制的优先级, 0代表不使用，值越高则使用优先级越高"
        label = QLabel('幻鸡优先级')
        label.setToolTip(tooltips)
        layout.addWidget(label)

        self.WidgetKunInput = QSpinBox()
        self.WidgetKunInput.setFixedWidth(140)
        self.WidgetKunInput.setRange(0, 9)
        self.WidgetKunInput.setToolTip(tooltips)
        layout.addWidget(self.WidgetKunInput)

    def load_data(self):
        self.WidgetIdInput.setValue(self.data["id"])
        self.WidgetNameInput.setText(self.data["name"])
        self.WidgetErgodicInput.setCurrentText(str(self.data['ergodic']).lower())
        self.WidgetQueueInput.setCurrentText(str(self.data['queue']).lower())
        self.WidgetKunInput.setValue(self.data.get('kun', 0))

    def connect_functions(self):
        """绑定信号"""

        # id，名称,遍历，队列控件的更改都连接上更新卡片
        self.WidgetIdInput.valueChanged.connect(self.func_update)
        self.WidgetNameInput.textChanged.connect(self.func_update)
        self.WidgetErgodicInput.currentIndexChanged.connect(self.func_update)
        self.WidgetQueueInput.currentIndexChanged.connect(self.func_update)
        self.WidgetKunInput.valueChanged.connect(self.func_update)


class InsertUseCardInfoEditor(QDialog):
    def __init__(self, data, func_update):
        super().__init__()
        self.data = data
        self.func_update = func_update

        # 窗口标题栏
        self.setWindowTitle("编辑定时放卡动作参数")

        # 关键组合：彻底移除系统菜单图标
        self.setWindowFlags(
            Qt.WindowType.CustomizeWindowHint |  # 允许自定义窗口装饰
            Qt.WindowType.WindowCloseButtonHint |  # 仅保留关闭按钮
            Qt.WindowType.WindowStaysOnTopHint  # 窗口置顶
        )

        # UI
        self.WidgetIdInput2 = None
        self.WidgetNameInput2 = None
        self.WidgetTimeInput = None
        self.WidgetBeforeShovelInput = None
        self.WidgetAfterShovelInput = None
        self.WidgetAfterTimeInput = None
        self.init_ui()

        # 初始化数据
        self.load_data()

        # 绑定变化信号
        self.connect_functions()

    def init_ui(self):
        """单组放卡操作 - 状态编辑器"""

        LayMain = QVBoxLayout()
        self.setLayout(LayMain)

        # 放卡时间
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        tooltips = "识别到对应波次后，会在对应秒数后放置卡片"

        label = QLabel('放卡定时')
        label.setToolTip(tooltips)
        layout.addWidget(label)

        self.WidgetTimeInput = QDoubleSpinBox()
        self.WidgetTimeInput.setFixedWidth(140)
        self.WidgetTimeInput.setToolTip(tooltips)
        self.WidgetTimeInput.setRange(0, 9999)
        layout.addWidget(self.WidgetTimeInput)

        # 分割线
        LayMain.addWidget(create_vertical_line())

        # ID
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        label = QLabel('ID')
        layout.addWidget(label)

        self.WidgetIdInput2 = QSpinBox()
        self.WidgetIdInput2.setFixedWidth(140)
        self.WidgetIdInput2.setToolTip("id代表卡在卡组中的顺序")
        self.WidgetIdInput2.setRange(1, 21)
        layout.addWidget(self.WidgetIdInput2)

        # 名称
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        label = QLabel('名称')
        layout.addWidget(label)
        self.WidgetNameInput2 = QLineEdit()
        self.WidgetNameInput2.setFixedWidth(140)
        self.WidgetNameInput2.setToolTip(
            "名称标识是什么卡片\n"
            "能让用户看懂该带啥就行.\n"
        )
        layout.addWidget(self.WidgetNameInput2)

        # 分割线
        LayMain.addWidget(create_vertical_line())

        # 前铲
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        tooltips = "是否会在放卡的前0.5秒铲除该点以腾出位置放卡"
        label = QLabel('前铲')
        label.setToolTip(tooltips)
        layout.addWidget(label)

        self.WidgetBeforeShovelInput = QComboBox()
        self.WidgetBeforeShovelInput.setFixedWidth(140)
        self.WidgetBeforeShovelInput.addItems(['true', 'false'])
        self.WidgetBeforeShovelInput.setToolTip(tooltips)
        self.WidgetBeforeShovelInput.setCurrentIndex(1)
        layout.addWidget(self.WidgetBeforeShovelInput)

        # 后铲
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        tooltips = "是否会在指定的秒数后铲除该点"

        label = QLabel('后铲')
        label.setToolTip(tooltips)
        layout.addWidget(label)

        self.WidgetAfterShovelInput = QComboBox()
        self.WidgetAfterShovelInput.setFixedWidth(140)
        self.WidgetAfterShovelInput.addItems(['true', 'false'])
        self.WidgetAfterShovelInput.setToolTip(tooltips)
        self.WidgetAfterShovelInput.setCurrentIndex(1)
        layout.addWidget(self.WidgetAfterShovelInput)

        # 放卡时间
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        tooltips = "放置卡片后，几秒后铲除"

        label = QLabel('后铲时间')
        label.setToolTip(tooltips)
        layout.addWidget(label)

        self.WidgetAfterTimeInput = QDoubleSpinBox()
        self.WidgetAfterTimeInput.setFixedWidth(140)
        self.WidgetAfterTimeInput.setToolTip(tooltips)
        self.WidgetAfterTimeInput.setRange(0, 9999)
        layout.addWidget(self.WidgetAfterTimeInput)

    def load_data(self):
        self.WidgetIdInput2.setValue(self.data['card_id'])
        self.WidgetNameInput2.setText(self.data['name'])
        self.WidgetTimeInput.setValue(self.data['time'])
        self.WidgetBeforeShovelInput.setCurrentText(str(self.data['before_shovel']).lower())
        self.WidgetAfterShovelInput.setCurrentText(str(self.data['after_shovel']).lower())
        self.WidgetAfterTimeInput.setValue(self.data['after_shovel_time'])

    def connect_functions(self):
        """绑定信号"""

        # 定时放卡相关变动函数绑定
        self.WidgetIdInput2.valueChanged.connect(self.func_update)
        self.WidgetNameInput2.textChanged.connect(self.func_update)
        self.WidgetTimeInput.valueChanged.connect(self.func_update)
        self.WidgetBeforeShovelInput.currentIndexChanged.connect(self.func_update)
        self.WidgetAfterShovelInput.currentIndexChanged.connect(self.func_update)
        self.WidgetAfterTimeInput.valueChanged.connect(self.func_update)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = QMWEditorOfBattlePlan()
    ex.show()
    sys.exit(app.exec())
