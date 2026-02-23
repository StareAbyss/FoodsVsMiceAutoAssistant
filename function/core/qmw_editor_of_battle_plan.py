import copy
import json
import os
import sys
import uuid

from function.globals.loadings import loading

loading.update_progress(50, "正在加载FAA关卡编辑器...")
from typing import List, Union

from PyQt6.QtCore import pyqtSignal, Qt, QPoint
from PyQt6.QtGui import QKeySequence, QIcon, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGridLayout, QPushButton, QWidget, QFileDialog, QVBoxLayout, QLabel, QComboBox,
    QLineEdit, QHBoxLayout, QTextEdit, QListWidget, QMessageBox, QSpinBox, QListWidgetItem, QFrame, QAbstractItemView,
    QSpacerItem, QSizePolicy, QDoubleSpinBox, QDialog, QDialogButtonBox)

from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.scattered.class_battle_plan_v3d0 import json_to_obj, TriggerWaveTimer, \
    ActionLoopUseCards, ActionInsertUseCard, ActionShovel, ActionUseGem, ActionEscape, ActionBanCard, Event, BattlePlan, \
    obj_to_json, Card, MetaData, \
    CardLoopConfig, ActionRandomSingleCard, ActionRandomMultiCard
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

        # 提示信息编辑框
        self.TextEditTips = None

        # 选择关卡和打开教学
        self.WidgetStageSelector = None

        # 编辑模式
        self.ButtonCardsEdit: Union[QPushButton, None] = None
        self.ButtonLoopActionEdit: Union[QPushButton, None] = None
        self.ButtonTimerActionEdit: Union[QPushButton, None] = None
        self.LabelEditorMode: Union[QPushButton, None] = None

        # 波次编辑
        self.LabelWaveCopyTip: Union[QLabel, None] = None
        self.BtnWaveCopy: Union[QPushButton, None] = None
        self.BtnWavePaste: Union[QPushButton, None] = None
        self.BtnWaveApplyToAfter: Union[QPushButton, None] = None
        self.BtnWaveApplyToAll: Union[QPushButton, None] = None

        # 方案加载保存另存为
        self.LabelCurrentBattlePlanFileName = None
        self.LabelCurrentBattlePlanUUID = None
        self.BtnLoadJson: Union[QPushButton, None] = None
        self.BtnSave: Union[QPushButton, None] = None
        self.BtnSaveAs: Union[QPushButton, None] = None

        # 编辑模式列表 0
        self.LayCardEditor = None
        self.BtnAddCard: Union[QPushButton, None] = None
        self.BtnDeleteCard: Union[QPushButton, None] = None
        self.ListCards: Union[QListWidgetDraggable, None] = None

        # 编辑模式列表 1
        self.LayLoopActionEditor = None
        self.BtnPlayer: Union[QPushButton, None] = None
        self.BtnAddLoopAction: Union[QPushButton, None] = None
        self.BtnDeleteLoopAction: Union[QPushButton, None] = None
        self.ListLoopAction: Union[QListWidgetDraggable, None] = None

        # 编辑模式列表 2
        self.LayTimerActionEditor = None
        self.BtnAddTimerAction: Union[QPushButton, None] = None
        self.BtnDeleteTimerAction: Union[QPushButton, None] = None
        self.ListTimerActions: Union[QListWidgetDraggable, None] = None

        # 编辑模式列表 3
        self.LaySpecialActionEditor = None
        self.ListSpecialActions: Union[QListWidgetDraggable, None] = None

        # 点击列表元素弹出的 元素信息编辑框
        self.EditorOfActionInfo = None

        # 棋盘
        self.chessboard_buttons = None
        self.chessboard_frames = None

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
                    WidgetCourseButton.clicked.connect(func_open_tip)  # type: ignore
                    self.LayLeft.addWidget(WidgetCourseButton)

                    # 分割线
                    self.LayLeft.addWidget(create_vertical_line())

                    # 点击切换放卡编辑模式
                    self.ButtonCardsEdit = QPushButton('卡组编辑')
                    self.LayLeft.addWidget(self.ButtonCardsEdit)

                    self.ButtonLoopActionEdit = QPushButton('循环放卡编辑')
                    self.LayLeft.addWidget(self.ButtonLoopActionEdit)

                    self.ButtonTimerActionEdit = QPushButton('定时放卡编辑')
                    self.LayLeft.addWidget(self.ButtonTimerActionEdit)

                    # 当前模式
                    self.LabelEditorMode = QLabel('当前模式 - 循环放卡编辑')
                    self.LabelEditorMode.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                    self.LayLeft.addWidget(self.LabelEditorMode)

                def init_ui_lay_wave_editor():
                    """波次编辑器"""

                    self.LayWaveEditor = QVBoxLayout()
                    self.LayLeft.addLayout(self.LayWaveEditor)

                    title_label = QLabel('波次编辑器')
                    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                    self.LayWaveEditor.addWidget(title_label)

                    for v_index in range(3):
                        lay_line = QHBoxLayout()
                        for h_index in range(5):
                            i = v_index * 5 + h_index
                            if i != 14:
                                button = QPushButton(f"{i}")
                                button.setObjectName(f"changeWaveButton_{i}")
                                button.clicked.connect(  # type: ignore
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

                    # 添加剪切板文本提示
                    self.LabelWaveCopyTip = QLabel('尚未复制任何波次信息')
                    self.LabelWaveCopyTip.setAlignment(Qt.AlignmentFlag.AlignCenter)

                    # 添加复制按钮
                    self.BtnWaveCopy = QPushButton('复制')
                    self.BtnWaveCopy.clicked.connect(self.wave_plan_copy)  # type: ignore
                    self.BtnWaveCopy.setToolTip(f"复制当前选中波次方案, 保存到剪切板")

                    # 添加粘贴按钮 锁定 不可使用
                    self.BtnWavePaste = QPushButton('粘贴')
                    self.BtnWavePaste.clicked.connect(self.wave_plan_paste)  # type: ignore
                    self.BtnWavePaste.setEnabled(False)
                    self.BtnWavePaste.setToolTip(f"将剪切板中的方案, 粘贴到当前选中波次")

                    # 向后应用
                    self.BtnWaveApplyToAfter = QPushButton('向后应用')
                    self.BtnWaveApplyToAfter.clicked.connect(self.wave_plan_apply_to_after)  # type: ignore
                    self.BtnWaveApplyToAfter.setToolTip(f"复制当前选中波次方案, 粘贴到当前选中波次之后的所有波次")

                    # 应用到全部
                    self.BtnWaveApplyToAll = QPushButton('应用到全部')
                    self.BtnWaveApplyToAll.clicked.connect(self.wave_plan_apply_to_all)  # type: ignore
                    self.BtnWaveApplyToAll.setToolTip("复制当前选中波次方案, 粘贴到全部波次")

                    # 创建水平布局，来容纳按钮
                    self.LayLeft.addWidget(self.LabelWaveCopyTip)

                    LayWaveAction = QHBoxLayout()
                    LayWaveAction.addWidget(self.BtnWaveCopy)
                    LayWaveAction.addWidget(self.BtnWavePaste)
                    self.LayLeft.addLayout(LayWaveAction)

                    LayWaveAction = QHBoxLayout()
                    LayWaveAction.addWidget(self.BtnWaveApplyToAfter)
                    LayWaveAction.addWidget(self.BtnWaveApplyToAll)
                    self.LayLeft.addLayout(LayWaveAction)

                def init_ui_lay_save_and_load():
                    """加载和保存按钮"""

                    title_label = QLabel('方案加载与保存')
                    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐

                    self.LabelCurrentBattlePlanFileName = QLabel("当前方案: 无")
                    self.LabelCurrentBattlePlanFileName.setMaximumWidth(250)

                    self.LabelCurrentBattlePlanUUID = QLabel("当前方案UUID: 无")

                    self.BtnLoadJson = QPushButton('加载')

                    self.BtnSave = QPushButton('保存')
                    self.BtnSave.setEnabled(False)

                    self.BtnSaveAs = QPushButton('另存为')

                    # 创建水平布局，来容纳保存和另存为按钮
                    LaySaveBottom = QHBoxLayout()
                    LaySaveBottom.addWidget(self.BtnLoadJson)
                    LaySaveBottom.addWidget(self.BtnSave)
                    LaySaveBottom.addWidget(self.BtnSaveAs)

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

            def init_ui_lay_deck_editor():
                """卡组编辑器"""
                self.LayCardEditor = QVBoxLayout()
                self.LayoutMainBottom.addLayout(self.LayCardEditor)

                title_label = QLabel('卡组编辑 - 拖拽修改ID，右键编辑名称')
                title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.LayCardEditor.addWidget(title_label)

                # 添加卡片按钮
                self.BtnAddCard = QPushButton('添加新卡片')
                self.LayCardEditor.addWidget(self.BtnAddCard)

                # 删除卡片按钮
                self.BtnDeleteCard = QPushButton('删除选中卡片')
                self.LayCardEditor.addWidget(self.BtnDeleteCard)

                # 卡组列表控件
                self.ListCards = QListWidgetDraggable()
                self.ListCards.setMaximumWidth(260)
                self.ListCards.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                self.LayCardEditor.addWidget(self.ListCards)

                # ID变更记录
                self.card_id_changes_memory = {}  # 记录ID变更 {old_id: new_id}

            def init_ui_lay_normal_actions():
                """常规操作列表"""

                # 竖向布局
                self.LayLoopActionEditor = QVBoxLayout()
                self.LayoutMainBottom.addLayout(self.LayLoopActionEditor)

                # title_label = QLabel('普通放卡编辑')
                # title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                # self.LayNormalActionList.addWidget(title_label)

                title_label = QLabel('左键-选中放卡   右键-编辑参数')
                title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                self.LayLoopActionEditor.addWidget(title_label)

                self.BtnPlayer = QPushButton('玩家位置')
                self.LayLoopActionEditor.addWidget(self.BtnPlayer)

                self.BtnAddLoopAction = QPushButton('新增一组放卡操作')
                self.LayLoopActionEditor.addWidget(self.BtnAddLoopAction)

                self.BtnDeleteLoopAction = QPushButton('删除选中放卡操作')
                self.LayLoopActionEditor.addWidget(self.BtnDeleteLoopAction)

                # 列表控件
                self.ListLoopAction = QListWidgetDraggable()
                self.ListLoopAction.setMaximumWidth(260)  # 经过验证的完美数字
                self.LayLoopActionEditor.addWidget(self.ListLoopAction)

            def init_ui_lay_timeline_actions():
                """定时操作列表"""

                # 竖向布局
                self.LayTimerActionEditor = QVBoxLayout()
                self.LayoutMainBottom.addLayout(self.LayTimerActionEditor)

                # title_label = QLabel('定时操作')
                # title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                # self.LayTimelineActionList.addWidget(title_label)

                title_label = QLabel('左键-选中放卡   右键-编辑参数')
                title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置文本居中对齐
                self.LayTimerActionEditor.addWidget(title_label)

                self.BtnAddTimerAction = QPushButton('新增定时放卡操作')
                self.LayTimerActionEditor.addWidget(self.BtnAddTimerAction)

                self.BtnDeleteTimerAction = QPushButton('删除定时放卡操作')
                self.LayTimerActionEditor.addWidget(self.BtnDeleteTimerAction)

                # 列表控件
                self.ListTimerActions = QListWidgetDraggable()
                self.ListTimerActions.setMaximumWidth(260)  # 经过验证的完美数字
                self.LayTimerActionEditor.addWidget(self.ListTimerActions)

            def init_ui_lay_special_actions():
                """特殊操作列表"""
                self.LaySpecialActionEditor = QVBoxLayout()
                self.LayoutMainBottom.addLayout(self.LaySpecialActionEditor)

                title_label = QLabel('左键-选中操作   右键-编辑参数')
                title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.LaySpecialActionEditor.addWidget(title_label)

                self.ButtonAddSpecialAction = QPushButton('新增特殊操作')
                self.LaySpecialActionEditor.addWidget(self.ButtonAddSpecialAction)

                self.ButtonDeleteSpecialAction = QPushButton('删除选中特殊操作')
                self.LaySpecialActionEditor.addWidget(self.ButtonDeleteSpecialAction)

                self.ListSpecialActions = QListWidgetDraggable()
                self.ListSpecialActions.setMaximumWidth(260)
                self.LaySpecialActionEditor.addWidget(self.ListSpecialActions)

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

                        btn.clicked.connect(lambda checked, x=i, y=j: self.left_click_card_pos(y, x))  # type: ignore
                        btn.rightClicked.connect(lambda x=i, y=j: self.right_click_card_pos(y, x))  # type: ignore
                        self.chessboard_layout.addWidget(btn, i, j, alignment=Qt.AlignmentFlag.AlignCenter)
                        btn.setToolTip(f"当前位置: {j + 1}-{i + 1}")
                        row_buttons.append(btn)

                        btn.setFixedSize(80, 80)

                    self.chessboard_buttons.append(row_buttons)
                    self.chessboard_frames.append(row_frames)

            init_ui_lay_left()
            init_ui_lay_deck_editor()
            init_ui_lay_normal_actions()
            init_ui_lay_timeline_actions()
            init_ui_lay_special_actions()
            init_ui_lay_chessboard()

            # 隐藏定时操作列表
            hide_layout(self.LayCardEditor)
            hide_layout(self.LayTimerActionEditor)
            hide_layout(self.LaySpecialActionEditor)

        init_ui_lay_tip()
        init_ui_layout_bottom()

        # 设置主控件
        self.central_widget = QWidget()
        self.central_widget.setLayout(self.LayMain)
        self.setCentralWidget(self.central_widget)

        def connect_signal_and_slot():
            """信号和槽函数链接"""

            # 读取json
            self.BtnLoadJson.clicked.connect(self.open_battle_plan)  # type: ignore

            # 保存json
            self.BtnSaveAs.clicked.connect(self.save_json)  # type: ignore
            self.BtnSave.clicked.connect(self.save_json)  # type: ignore

            # 关卡选择
            self.WidgetStageSelector.on_selected.connect(self.stage_changed)

            # 卡组编辑相关连接
            self.ListCards.moveRequested.connect(self.event_list_be_moved_mode_0)  # type: ignore
            self.ListCards.itemClicked.connect(self.be_edited_action_change_mode_0)  # type: ignore
            self.ListCards.editRequested.connect(self.show_edit_window)  # type: ignore
            self.BtnAddCard.clicked.connect(self.add_new_card)  # type: ignore
            self.BtnDeleteCard.clicked.connect(self.delete_selected_card)  # type: ignore

            # 循环放卡编辑 相关连接
            # 拖拽 -> 移动顺序
            # 左键 -> 删除目标 / 位置编辑 / 高亮
            # 右键 -> 信息编辑
            self.ListLoopAction.moveRequested.connect(self.event_list_be_moved_mode_1)  # type: ignore
            self.ListLoopAction.itemClicked.connect(self.be_edited_action_change_mode_1)  # type: ignore
            self.ListLoopAction.editRequested.connect(self.show_edit_window)  # type: ignore
            self.BtnAddLoopAction.clicked.connect(self.add_loop_use_cards_one_card)  # type: ignore
            self.BtnDeleteLoopAction.clicked.connect(self.delete_loop_use_cards_one_card)  # type: ignore

            # 定时放卡编辑 相关连接
            self.ListTimerActions.moveRequested.connect(self.event_list_be_moved_mode_2)  # type: ignore
            self.ListTimerActions.itemClicked.connect(self.be_edited_action_change_mode_2)  # type: ignore
            self.ListTimerActions.editRequested.connect(self.show_edit_window)  # type: ignore
            self.BtnAddTimerAction.clicked.connect(self.add_insert_use_card)  # type: ignore
            self.BtnDeleteTimerAction.clicked.connect(self.delete_insert_use_card)  # type: ignore
            self.BtnPlayer.clicked.connect(self.click_player_button)  # type: ignore

            # 特殊操作编辑 相关连接
            self.ListSpecialActions.itemClicked.connect(self.be_edited_special_change)  # type: ignore
            self.ListSpecialActions.editRequested.connect(self.show_edit_window)  # type: ignore
            self.ButtonAddSpecialAction.clicked.connect(self.add_use_special_action)  # type: ignore
            self.ButtonDeleteSpecialAction.clicked.connect(self.delete_use_special_action)  # type: ignore

            # 切换编辑模式按钮绑定
            self.ButtonCardsEdit.clicked.connect(lambda: self.change_edit_mode(0))  # type: ignore
            self.ButtonLoopActionEdit.clicked.connect(lambda: self.change_edit_mode(1))  # type: ignore
            self.ButtonTimerActionEdit.clicked.connect(lambda: self.change_edit_mode(2))  # type: ignore

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

        # 模式
        # 0 - 卡组编辑
        # 1 - 常规遍历队列式放卡
        # 2 - 定时放卡
        # 3 - 特殊操作

        self.editing_mode = 1

        # 当前编辑内容
        self.be_edited_player = False
        self.be_edited_wave_id = 0
        self.be_edited_index_mod_0 = None
        self.be_edited_index_mod_1 = None
        self.be_edited_index_mod_2 = None
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
        self.insert_use_special_events: List[Event] = []
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
        self.undo_shortcut.activated.connect(self.undo)  # type: ignore
        self.redo_shortcut.activated.connect(self.redo)  # type: ignore

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

    def change_edit_mode(self, mode):
        """
        切换编辑模式
        :param mode: 目标模式编号(1-4)
        """

        self.editing_mode = mode

        # 管理布局可见性
        hide_layout(self.LayCardEditor)
        hide_layout(self.LayLoopActionEditor)
        hide_layout(self.LayTimerActionEditor)
        hide_layout(self.LaySpecialActionEditor)

        def set_all_wave_editor_btn_enabled(tar_type: bool):
            self.BtnWaveCopy.setEnabled(tar_type)
            self.BtnWavePaste.setEnabled(False)  # 默认是不可用的！ 需要复制
            self.BtnWaveApplyToAfter.setEnabled(tar_type)
            self.BtnWaveApplyToAll.setEnabled(tar_type)

        # 根据当前模式显示对应布局和更新按钮状态
        if self.editing_mode == 0:
            self.LabelEditorMode.setText("当前模式 - 卡组编辑")
            show_layout(self.LayCardEditor)
            set_all_wave_editor_btn_enabled(tar_type=False)

        elif self.editing_mode == 1:
            self.LabelEditorMode.setText("当前模式 - 循环放卡编辑")
            show_layout(self.LayLoopActionEditor)
            set_all_wave_editor_btn_enabled(tar_type=True)

        elif self.editing_mode == 2:
            self.LabelEditorMode.setText("当前模式 - 定时放卡编辑")
            show_layout(self.LayTimerActionEditor)
            set_all_wave_editor_btn_enabled(tar_type=False)

        elif self.editing_mode == 3:
            self.LabelEditorMode.setText("当前模式 - 特殊操作编辑")
            show_layout(self.LaySpecialActionEditor)
            set_all_wave_editor_btn_enabled(tar_type=False)

        # 刷新所有UI状态
        self.fresh_all_ui()

    def change_wave(self, wave: int):

        self.be_edited_wave_id = wave

        # 去除选中
        self.be_edited_player = False
        self.BtnPlayer.setText("玩家位置")
        self.be_edited_index_mod_1 = None
        self.be_edited_index_mod_2 = None

        # 关闭放卡动作编辑框
        self.close_edit_window()

        # 重载UI
        self.fresh_all_ui()

    def wave_plan_copy(self):
        """复制"""

        # 仅在模式1中允许复制
        if self.editing_mode != 1:
            # 警告
            QMessageBox.warning(self, "警告", "该操作仅在 循环放卡编辑模式 可用")
            return

        self.be_copied_loop_use_cards_event_wave_id = copy.deepcopy(self.be_edited_wave_id)

        # 复制后 允许其粘贴
        self.BtnWavePaste.setEnabled(True)

        # 更新剪切板
        self.LabelWaveCopyTip.setText(f"已复制{self.be_edited_wave_id}波方案")

        CUS_LOGGER.debug(
            f"[战斗方案编辑器] 已复制循环放卡事件, 波次编号: {self.be_copied_loop_use_cards_event_wave_id}")

    def wave_plan_paste(self):

        # 仅在模式1中允许复制
        if self.editing_mode != 1:
            # 警告
            QMessageBox.warning(self, "警告", "该操作仅在 循环放卡编辑模式 可用")
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

    def wave_plan_apply_to_after(self):
        """应用到后续"""

        # 仅在模式1中允许复制
        if self.editing_mode != 1:
            # 警告
            QMessageBox.warning(self, "警告", "该操作仅在 循环放卡编辑模式 可用")
            return

        to_action = next(e.action for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
        for e in self.loop_use_cards_events:
            if e.trigger.wave_id <= self.be_edited_wave_id:
                continue
            e.action = copy.deepcopy(to_action)

        # 仅需变色波次按钮颜色
        self.refresh_wave_button_color()

        CUS_LOGGER.debug(f"[战斗方案编辑器] 波次:{self.be_edited_wave_id}方案已应用到后续波次")

    def wave_plan_apply_to_all(self):
        """应用到全部"""

        # 仅在模式1中允许复制
        if self.editing_mode != 1:
            # 警告
            QMessageBox.warning(self, "警告", "该操作仅在 循环放卡编辑模式 可用")
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
        self.load_data_to_ui_list_mode_0()
        self.load_data_to_ui_list_mode_1()
        self.load_data_to_ui_list_mode_2()
        self.load_data_to_ui_list_mode_3()

        # 重绘 UI棋盘网格
        self.refresh_chessboard()

        # 刷新波次按钮颜色
        self.refresh_wave_button_color()

        # 刷新棋盘高亮
        self.highlight_chessboard()

    """卡组 编辑操作"""

    def load_data_to_ui_list_mode_0(self):
        """从内部数据表载入卡组数据到UI列表"""

        if self.editing_mode != 0:
            return

        self.ListCards.clear()

        # 根据中文和西文分别记录最高宽度
        name_max_width_c = 0
        name_max_width_e = 0
        for card in self.battle_plan.cards:
            width_c, width_e = calculate_text_width(card.name)
            name_max_width_c = max(name_max_width_c, width_c)
            name_max_width_e = max(name_max_width_e, width_e)

        if not self.battle_plan.cards:
            return

        # 找到最长的id长度
        max_id_length = max(len(str(card.card_id)) for card in self.battle_plan.cards)

        for card in self.battle_plan.cards:
            # 根据中文和西文 分别根据距离相应的最大宽度的差值填充中西文空格
            width_c, width_e = calculate_text_width(card.name)
            padded_name = str(card.name)
            padded_name += "\u2002" * (name_max_width_e - width_e)  # 半宽空格
            padded_name += '\u3000' * (name_max_width_c - width_c)  # 表意空格(方块字空格)

            padded_id = str(card.card_id).ljust(max_id_length)

            text = "ID:{}  名称:{}".format(padded_id, padded_name)

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, card.card_id)  # 存储card_id
            self.ListCards.addItem(item)

    def be_edited_action_change_mode_0(self, item):
        """被任意键单击后, 被选中的卡片改变了"""

        # list的index 是 QModelIndex 此处还需要获取到行号
        self.be_edited_index_mod_0 = self.ListCards.indexFromItem(item).row()

    def event_list_be_moved_mode_0(self, index_from, index_to):

        if self.editing_mode != 0:
            return

        # 将当前状态压入栈中
        self.append_undo_stack()

        tar_card = self.battle_plan.cards.pop(index_from)
        self.battle_plan.cards.insert(index_to, tar_card)

        # 更新所有卡片的ID使其连续排列
        for i, card in enumerate(self.battle_plan.cards):
            old_card_id = card.card_id
            card.card_id = i + 1
            if old_card_id != card.card_id:
                self.card_id_changes_memory[old_card_id] = card.card_id

        CUS_LOGGER.debug(f"进行操作: 卡片列表元素移动 ID:{index_from + 1} -> ID:{index_to + 1}")
        CUS_LOGGER.debug(f"卡片 数据已更新: {self.battle_plan.cards}")

        # 更新循环和定时放卡中的引用
        self.update_card_references()

        self.load_data_to_ui_list_mode_0()

    def update_card_references(self):

        CUS_LOGGER.debug(f"卡片数据已更新, 即将更新操作中的卡片ID引用, 操作表: {self.card_id_changes_memory}")

        if not self.card_id_changes_memory:
            return

        # 更新循环放卡中的引用
        for event in self.loop_use_cards_events:
            for card_config in event.action.cards:
                if card_config.card_id in self.card_id_changes_memory:
                    old_id = card_config.card_id
                    new_id = self.card_id_changes_memory[old_id]
                    card_config.card_id = new_id
                    # CUS_LOGGER.debug(f"循环放卡操作 更新引用: {old_id} -> {new_id}")

        # 更新定时放卡中的引用
        for event in self.insert_use_card_events:
            if hasattr(event.action, 'card_id') and event.action.card_id in self.card_id_changes_memory:
                old_id = event.action.card_id
                new_id = self.card_id_changes_memory[old_id]
                event.action.card_id = new_id
                # CUS_LOGGER.debug(f"定时放卡操作 更新引用: {old_id} -> {new_id}")

        # 清空变更记录
        self.card_id_changes_memory.clear()

    """循环放卡 编辑操作"""

    def click_player_button(self):

        # 用 -1 代表正在编辑玩家位置
        self.be_edited_player = True
        self.BtnPlayer.setText(">> 玩家位置 <<")
        self.be_edited_index_mod_1 = None

        self.highlight_chessboard()

    def load_data_to_ui_list_mode_1(self):
        """从 [内部数据表] 载入数据到 [ui的放卡动作列表]"""

        if self.editing_mode != 1:
            return

        self.ListLoopAction.clear()

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
            self.ListLoopAction.addItem(item)

    def be_edited_action_change_mode_1(self, item):
        """被任意键单击后, 被选中的卡片改变了"""

        # 不再编辑玩家位置
        self.be_edited_player = False
        self.BtnPlayer.setText("玩家位置")

        # list的index 是 QModelIndex 此处还需要获取到行号
        self.be_edited_index_mod_1 = self.ListLoopAction.indexFromItem(item).row()

        # 高亮棋盘
        self.highlight_chessboard()

        # print(f"编辑 - 位置 - 普通动作编辑 目标改变: {self.be_edited_loop_use_cards_one_card_index}")

    def event_list_be_moved_mode_1(self, index_from, index_to):
        """在list的drop事件中调用, 用于更新内部数据表"""

        if self.editing_mode != 1:
            return

        # 将当前状态压入栈中
        self.append_undo_stack()

        current_event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
        cards = current_event.action.cards

        tar_card = cards.pop(index_from)
        cards.insert(index_to, tar_card)

        CUS_LOGGER.debug(f"进行操作: 循环放卡操作列表元素移动 ID:{index_from} -> ID:{index_to}")
        CUS_LOGGER.debug("当前波次 循环放卡 数据已更新: {}".format(cards))

        self.load_data_to_ui_list_mode_1()

        # 刷新波次上色
        self.refresh_wave_button_color()

    """定时放卡 编辑操作"""

    def load_data_to_ui_list_mode_2(self):
        """从 [内部数据表] 载入数据到 [ui的放卡动作列表]"""
        if self.editing_mode != 2:
            return

        self.ListTimerActions.clear()

        events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]

        # 根据中文和西文分别记录最高宽度
        name_max_width_c = 0
        name_max_width_e = 0

        # 仅处理普通放卡事件
        for event in events:
            if isinstance(event.action, ActionInsertUseCard):
                try:
                    card_name = next(c.name for c in self.battle_plan.cards
                                     if c.card_id == event.action.card_id)
                    width_c, width_e = calculate_text_width(card_name)
                    name_max_width_c = max(name_max_width_c, width_c)
                    name_max_width_e = max(name_max_width_e, width_e)
                except StopIteration:
                    continue

        for event in events:
            # 根据操作类型生成摘要
            if isinstance(event.action, ActionShovel):
                text = f"{event.trigger.time}s 铲子操作 {event.action.location}"
            elif isinstance(event.action, ActionInsertUseCard):
                try:
                    card_name = next(c.name for c in self.battle_plan.cards
                                     if c.card_id == event.action.card_id)
                    width_c, width_e = calculate_text_width(card_name)
                    padded_name = str(card_name)
                    padded_name += "\u2002" * (name_max_width_e - width_e)
                    padded_name += '\u3000' * (name_max_width_c - width_c)

                    padded_id = str(event.action.card_id).ljust(2)

                    text = "{}s {}  ID:{} 先铲{} 放后{}s 后铲{}".format(
                        event.trigger.time,
                        padded_name,
                        padded_id,
                        "√" if event.action.before_shovel else "X",
                        event.action.after_shovel_time,
                        "√" if event.action.after_shovel else "X"
                    )
                except StopIteration:
                    continue
            else:
                continue

            item = QListWidgetItem(text)
            self.ListTimerActions.addItem(item)

    def be_edited_action_change_mode_2(self, item):
        """被单击后, 被选中的卡片改变了"""

        # list的index 是 QModelIndex 此处还需要获取到行号
        self.be_edited_index_mod_2 = self.ListTimerActions.indexFromItem(item).row()

        # 高亮棋盘
        self.highlight_chessboard()

        # print(f"编辑 - 位置 - 定时动作编辑 目标改变: {self.be_edited_insert_use_card_index}")

    def event_list_be_moved_mode_2(self, index_from, index_to):
        """在list的drop事件中调用, 用于更新内部数据表"""

        if self.editing_mode != 2:
            return

        # 将当前状态压入栈中
        self.append_undo_stack()

        indices = [i for i, e in enumerate(self.insert_use_card_events)
                   if e.trigger.wave_id == self.be_edited_wave_id]

        if 0 <= index_from < len(indices) and 0 <= index_to < len(indices):
            global_from = indices[index_from]
            global_to = indices[index_to]

            # 在原始列表中移动事件
            event = self.insert_use_card_events.pop(global_from)
            self.insert_use_card_events.insert(global_to, event)

        # CUS_LOGGER.debug(tar_event)
        CUS_LOGGER.debug("当前波次 插入放卡 数据已更新: {}".format(self.insert_use_card_events))

        self.load_data_to_ui_list_mode_2()

        # 刷新波次上色
        self.refresh_wave_button_color()

    """特殊放卡 编辑操作"""

    def load_data_to_ui_list_mode_3(self):
        """宝石操作列表数据加载"""
        self.ListSpecialActions.clear()
        events = [e for e in self.insert_use_special_events
                  if e.trigger.wave_id == self.be_edited_wave_id]

        for event in events:
            item_text = ""
            if isinstance(event.action, ActionUseGem):
                item_text = f"波次{event.trigger.wave_id} {event.trigger.time}s 宝石{event.action.gem_id}"
            elif isinstance(event.action, ActionEscape):
                item_text = f"波次{event.trigger.wave_id} {event.trigger.time}s 逃跑操作"
            elif isinstance(event.action, ActionBanCard):
                item_text = f"波次{event.trigger.wave_id} {event.trigger.time}s 禁用卡片{event.action.card_id}"
            elif isinstance(event.action, ActionRandomSingleCard):
                item_text = f"波次{event.trigger.wave_id} {event.trigger.time}s 单卡随机{event.action.card_index}"
            elif isinstance(event.action, ActionRandomMultiCard):
                indices_str = ",".join(map(str, event.action.card_indices))
                item_text = f"波次{event.trigger.wave_id} {event.trigger.time}s 多卡随机[{indices_str}]"
            self.ListSpecialActions.addItem(QListWidgetItem(item_text))

    def be_edited_special_change(self, item):
        """被单击后, 被选中的宝石操作改变了"""
        self.be_edited_index_mod_3 = self.ListSpecialActions.indexFromItem(item).row()
        # print(f"编辑 - 宝石操作 目标改变: {self.be_edited_special_action_index}")

    """右键list中元素弹出额外窗口, 属性编辑, 统一编辑"""

    def close_edit_window(self):
        if hasattr(self, "edit_window"):
            self.edit_window.close()

    def show_edit_window(self, list_item):

        self.close_edit_window()

        # 创建新窗口 个路径模式不同

        if self.editing_mode == 0:

            card = self.battle_plan.cards[self.be_edited_index_mod_0]
            data = {
                "name": card.name
            }
            self.EditorOfActionInfo = InfoEditorOfCards(
                data=data,
                func_update=self.update_info_mode_0
            )

        elif self.editing_mode == 1:

            # print("即将显示 常规动作编辑窗口 索引 - ", self.be_edited_loop_use_cards_one_card_index)

            event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
            a_card = event.action.cards[self.be_edited_index_mod_1]
            data = {
                "cards": self.battle_plan.cards,
                "id": a_card.card_id,
                "ergodic": a_card.ergodic,
                "queue": a_card.queue,
                "kun": a_card.kun
            }
            self.EditorOfActionInfo = InfoEditorOfLoopUseCardsOneCard(
                data=data,
                func_update=self.update_info_mode_1
            )

        elif self.editing_mode == 2:

            # print("即将显示 定时动作编辑窗口 索引 - ", self.be_edited_insert_use_card_index)
            events = [e for e in self.insert_use_card_events

                      if e.trigger.wave_id == self.be_edited_wave_id]
            event = events[self.be_edited_index_mod_2]

            # 根据操作类型创建不同的编辑器实例
            if event.action.type == "shovel":
                data = {
                    "time": event.trigger.time,
                    "type": "shovel",
                    "location": event.action.location
                }
                self.EditorOfActionInfo = ShovelActionEditor(
                    data=data,
                    func_update=self.update_shovel_action_info,
                    editor_parent=self,
                    event_index=self.be_edited_index_mod_2
                )

            else:
                data = {
                    "time": event.trigger.time,
                    "type": event.action.type,
                    "location": event.action.location,
                    "cards": self.battle_plan.cards,
                    "card_id": event.action.card_id,
                    "before_shovel": event.action.before_shovel,
                    "after_shovel": event.action.after_shovel,
                    "after_shovel_time": event.action.after_shovel_time
                }
                self.EditorOfActionInfo = InfoEditorOfInsertUseCard(
                    data=data,
                    func_update=self.update_info_mode_2,
                    editor_parent=self,
                    event_index=self.be_edited_index_mod_2
                )

        elif self.editing_mode == 3:

            events = [e for e in self.insert_use_special_events if e.trigger.wave_id == self.be_edited_wave_id]
            event = events[self.be_edited_index_mod_3]

            if isinstance(event.action, ActionEscape):
                data = {"time": event.trigger.time}
                self.EditorOfActionInfo = EscapeActionEditor(data=data, func_update=self.update_escape_action_info)
            elif isinstance(event.action, ActionBanCard):
                data = {
                    "start_time": event.action.start_time,
                    "end_time": event.action.end_time,
                    "card_id": event.action.card_id
                }
                self.EditorOfActionInfo = BanCardActionEditor(data=data, func_update=self.update_ban_card_info)
            elif isinstance(event.action, ActionRandomSingleCard):
                data = {
                    "time": event.trigger.time,
                    "card_index": event.action.card_index
                }
                self.EditorOfActionInfo = RandomSingleCardActionEditor(
                    data=data,
                    func_update=self.update_random_single_card_info)
            elif isinstance(event.action, ActionRandomMultiCard):
                data = {
                    "time": event.trigger.time,
                    "card_indices": event.action.card_indices
                }
                self.EditorOfActionInfo = RandomMultiCardActionEditor(
                    data=data,
                    func_update=self.update_random_multi_card_info)
            else:
                data = {"gem_id": event.action.gem_id, "time": event.trigger.time}
                self.EditorOfActionInfo = GemInfoEditor(data=data, func_update=self.update_info_mode_3)

        # 计算显示位置
        global_pos = self.ListLoopAction.viewport().mapToGlobal(
            self.ListLoopAction.visualItemRect(list_item).topRight()
        )
        self.EditorOfActionInfo.move(global_pos + QPoint(20, 0))

        # 完成显示
        # self.card_action_editor.show()

        # 事件循环!~
        self.EditorOfActionInfo.exec()
        self.fresh_all_ui()

    def update_random_single_card_info(self):
        """
        更新单卡随机操作的UI与数据
        """
        try:
            events = [e for e in self.insert_use_special_events
                      if e.trigger.wave_id == self.be_edited_wave_id]
            event = events[self.be_edited_index_mod_3]

            if isinstance(event.action, ActionRandomSingleCard):
                new_data = self.EditorOfActionInfo.get_data()
                if event.action.card_index != new_data["card_index"]:
                    event.action.card_index = new_data["card_index"]
                    self.fresh_all_ui()

        except Exception as e:
            QMessageBox.warning(self, "输入错误", f"请输入有效的参数: {str(e)}")
            self.EditorOfActionInfo.card_index.setFocus()

    def update_random_multi_card_info(self):
        """
        更新多卡随机操作的UI与数据
        """
        try:
            events = [e for e in self.insert_use_special_events
                      if e.trigger.wave_id == self.be_edited_wave_id]
            event = events[self.be_edited_index_mod_3]

            if isinstance(event.action, ActionRandomMultiCard):
                new_data = self.EditorOfActionInfo.get_data()
                if event.action.card_indices != new_data["card_indices"]:
                    event.action.card_indices = new_data["card_indices"]
                    self.fresh_all_ui()

        except Exception as e:
            QMessageBox.warning(self, "输入错误", f"请输入有效的参数: {str(e)}")
            self.EditorOfActionInfo.card_indices_edit.setFocus()

    def update_shovel_action_info(self):
        """更新铲子操作事件的UI与数据"""
        try:
            events = [e for e in self.insert_use_card_events
                      if e.trigger.wave_id == self.be_edited_wave_id]
            event = events[self.be_edited_index_mod_2]

            # 获取当前UI数据
            new_data = self.EditorOfActionInfo.get_data()

            # 替换整个action对象保证数据同步
            event.action = ActionShovel(
                time=new_data["time"],
                location=new_data["location"]
            )

            # 同步更新触发器时间
            event.trigger.time = new_data["time"]

            # 强制触发所有UI更新
            self.fresh_all_ui()

        except Exception as e:
            QMessageBox.warning(self, "输入错误", f"请输入有效的参数: {str(e)}")
            self.EditorOfActionInfo.WidgetTimeInput.setFocus()

    def update_escape_action_info(self):
        try:
            events = [e for e in self.insert_use_special_events if e.trigger.wave_id == self.be_edited_wave_id]
            event = events[self.be_edited_index_mod_3]
            new_data = self.EditorOfActionInfo.get_data()

            event.action = ActionEscape(time=new_data["time"])
            event.trigger.time = new_data["time"]
            self.fresh_all_ui()
        except Exception as ve:
            QMessageBox.warning(self, "输入错误", f"请输入有效的参数: {str(ve)}")

    def update_ban_card_info(self):
        try:
            events = [e for e in self.insert_use_special_events if e.trigger.wave_id == self.be_edited_wave_id]
            event = events[self.be_edited_index_mod_3]
            new_data = self.EditorOfActionInfo.get_data()

            event.action = ActionBanCard(
                start_time=new_data["start_time"],
                end_time=new_data["end_time"],
                card_id=new_data["card_id"])
            event.trigger.time = new_data["start_time"]  # 使用开始时间作为触发时间
            self.fresh_all_ui()
        except Exception as ve:
            QMessageBox.warning(self, "输入错误", f"请输入有效的参数: {str(ve)}")

    """添加卡片或操作 - 根据操作修改内部数据表 再刷新UI"""

    def add_new_card(self):
        """添加新卡片"""
        # 将当前状态压入栈中
        self.append_undo_stack()

        # 找到下一个可用的ID
        used_ids = [card.card_id for card in self.battle_plan.cards]
        new_id = 1
        while new_id in used_ids and new_id <= 21:
            new_id += 1

        if new_id > 21:
            QMessageBox.warning(self, "警告", "卡组已达到最大容量(21张)")
            return

        # 创建新卡片
        new_card = Card(card_id=new_id, name="新的卡片")
        self.battle_plan.cards.append(new_card)

        # 更新所有卡片的ID使其连续排列
        for i, card in enumerate(self.battle_plan.cards):
            old_card_id = card.card_id
            card.card_id = i + 1
            if old_card_id != card.card_id:
                self.card_id_changes_memory[old_card_id] = card.card_id

        # 更新循环和定时放卡中的引用
        self.update_card_references()

        self.load_data_to_ui_list_mode_0()
        self.fresh_all_ui()

    def add_loop_use_cards_one_card(self):

        # 目前已经使用过的 卡片
        event = next(event for event in self.loop_use_cards_events if event.trigger.wave_id == self.be_edited_wave_id)
        cards = event.action.cards
        used_card_ids = [card.card_id for card in cards]

        # 所有可用的卡片
        can_use_card_ids = [card.card_id for card in self.battle_plan.cards]

        if not can_use_card_ids:
            QMessageBox.warning(self, "错误", "请先添加卡片, 再为其添加动作")
            return

        for i in can_use_card_ids:
            if i not in used_card_ids:
                id_ = i
                break
        else:
            id_ = 1

            response = QMessageBox.question(
                self,
                "注意！",
                "若您完全理解'动作列表'和卡'卡片列表'的区别, 理解同一张卡片可以有多个动作, 请继续操作",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if response == QMessageBox.StandardButton.No:
                return

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

        # 所有可用的卡片
        can_use_card_ids = [card.card_id for card in self.battle_plan.cards]

        if not can_use_card_ids:
            QMessageBox.warning(self, "错误", "请先添加卡片, 再为其添加动作")
            return

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

    def add_use_special_action(self):
        """
        新增特殊操作
        """
        if self.be_edited_wave_id is None:
            QMessageBox.information(self, "错误！", "请先选择波次")
            return

        dialog = SpecialActionTypeDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            action_type = dialog.get_selected_type()

            # 创建基础触发器
            trigger = TriggerWaveTimer(wave_id=self.be_edited_wave_id, time=0)

            # 根据操作类型创建对应的动作
            if action_type == "escape":
                action = ActionEscape(time=0)
            elif action_type == "disable_card":
                action = ActionBanCard(start_time=0, end_time=0, card_id=1)
            elif action_type == "gem":
                action = ActionUseGem(gem_id=1)
            elif action_type == "random_single_card":
                action = ActionRandomSingleCard(card_index=1)
            elif action_type == "random_multi_card":
                action = ActionRandomMultiCard(card_indices=[1, 2])
            else:
                QMessageBox.warning(self, "错误", "未知的操作类型")
                return

            # 创建事件并添加到列表
            event = Event(trigger=trigger, action=action)
            self.insert_use_special_events.append(event)

            # 刷新UI
            self.fresh_all_ui()

    """删除卡片或操作 - 根据操作修改内部数据表 再刷新UI"""

    def delete_selected_card(self):
        """删除选中的卡片"""

        if self.be_edited_index_mod_0 is None:
            QMessageBox.information(self, "操作错误！", "请先选择一个对象(卡片)!")
            return False

        tar_card = copy.deepcopy(self.battle_plan.cards[self.be_edited_index_mod_0])

        reply = QMessageBox.question(
            self, '确认删除',
            f'确定要删除卡片 {tar_card.name}(ID: {tar_card.card_id}) 吗？\n 使用该卡片的所有动作将全部被删除！',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if not reply == QMessageBox.StandardButton.Yes:
            return

        # 将当前状态压入栈中
        self.append_undo_stack()

        del self.battle_plan.cards[self.be_edited_index_mod_0]
        CUS_LOGGER.debug(f"[战斗方案编辑器] [删除卡片] 删除了卡片: {tar_card.name} (ID: {tar_card.card_id})")

        # 更新所有卡片的ID使其连续排列
        for i, card in enumerate(self.battle_plan.cards):
            old_card_id = card.card_id
            card.card_id = i + 1
            if old_card_id != card.card_id:
                self.card_id_changes_memory[old_card_id] = card.card_id

        # 去除使用了该卡片的所有动作
        removed_count = 0
        for e in self.loop_use_cards_events:
            original_count = len(e.action.cards)
            e.action.cards = [c for c in e.action.cards if c.card_id != tar_card.card_id]
            removed_count += original_count - len(e.action.cards)
        CUS_LOGGER.debug(f"[战斗方案编辑器] [删除卡片] 从循环放卡中删除了{removed_count}个使用该卡片的动作")

        # 删除定时放卡中使用该卡片的动作
        original_count = len(self.insert_use_card_events)
        self.insert_use_card_events = [e for e in self.insert_use_card_events if e.action.card_id != tar_card.card_id]
        removed_count = original_count - len(self.insert_use_card_events)
        CUS_LOGGER.debug(f"[战斗方案编辑器] [删除卡片] 从定时放卡中删除了{removed_count}个使用该卡片的动作")

        # 更新循环和定时放卡中的引用
        self.update_card_references()

        self.load_data_to_ui_list_mode_0()
        self.fresh_all_ui()

    def delete_loop_use_cards_one_card(self):
        """
        选中一组放卡操作后, 点击按钮, 删除它
        :return: None
        """

        if self.be_edited_index_mod_1 is None:
            QMessageBox.information(self, "操作错误！", "请先选择一个对象(卡片)!")
            return False

        # 将当前状态压入栈中
        self.append_undo_stack()

        event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
        cards = event.action.cards
        del cards[self.be_edited_index_mod_1]

        # 清空选中的卡片
        self.be_edited_index_mod_1 = None

        self.fresh_all_ui()

    def delete_insert_use_card(self):
        """
        选中一组定时放卡操作后, 点击按钮, 删除它
        :return: None
        """

        if self.be_edited_index_mod_2 is None:
            QMessageBox.information(self, "操作错误！", "请先选择一个对象(定时放卡)!")
            return False

        # 将当前状态压入栈中
        self.append_undo_stack()

        events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]
        event = events[self.be_edited_index_mod_2]
        self.insert_use_card_events.remove(event)

        # 清空选中的卡片
        self.be_edited_index_mod_2 = None

        self.fresh_all_ui()

    def delete_use_special_action(self):
        """
        删除选中的宝石操作
        """
        if self.be_edited_index_mod_3 is None:
            QMessageBox.information(self, "错误！", "请先选择宝石操作")
            return

        # 获取当前波次的所有宝石事件
        current_events = [e for e in self.insert_use_special_events if e.trigger.wave_id == self.be_edited_wave_id]

        if not current_events:
            return

        # 确保索引有效
        if self.be_edited_index_mod_3 >= len(current_events):
            CUS_LOGGER.warning(f"[战斗方案编辑器] 宝石操作索引越界: {self.be_edited_index_mod_3}")
            return

        # 获取要删除的事件
        event_to_delete = current_events[self.be_edited_index_mod_3]

        # 从原始列表中删除
        self.insert_use_special_events.remove(event_to_delete)

        # 清空选中状态
        self.be_edited_index_mod_3 = None

        # 刷新UI
        self.fresh_all_ui()

    """更新卡片或操作 - 根据操作修改内部数据表 再刷新UI"""

    def update_info_mode_0(self):
        """
        在UI上编辑更新一组放卡操作的状态后
        将该操作同步到内部数据表
        并刷新到左侧列表和棋盘等位置
        :return: None
        """
        print("即将更新 卡片列表 - 被选中卡片 的数据, 索引: ", self.be_edited_index_mod_0)

        # 将当前状态压入栈中
        self.append_undo_stack()

        o_card = self.battle_plan.cards[self.be_edited_index_mod_0]

        ui_value = self.EditorOfActionInfo.WidgetNameInput.text()
        if o_card.name != ui_value:
            o_card.name = ui_value
            self.fresh_all_ui()
            return

    def update_info_mode_1(self):
        """
        在UI上编辑更新一组放卡操作的状态后
        将该操作同步到内部数据表
        并刷新到左侧列表和棋盘等位置
        :return: None
        """

        print("即将更新 当前波次 - 循环放卡 - 被选中卡片 的数据, 索引: ", self.be_edited_index_mod_1)

        # 将当前状态压入栈中
        self.append_undo_stack()

        cards = next(e.action.cards for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
        a_card = cards[self.be_edited_index_mod_1]

        ui_value = int(self.EditorOfActionInfo.WidgetIdInput.currentData())
        if a_card.card_id != ui_value:
            a_card.card_id = ui_value
            self.fresh_all_ui()
            return

        ui_value = bool(self.EditorOfActionInfo.WidgetErgodicInput.currentText() == 'true')
        if a_card.ergodic != ui_value:
            a_card.ergodic = ui_value
            self.fresh_all_ui()
            return

        ui_value = bool(self.EditorOfActionInfo.WidgetQueueInput.currentText() == 'true')
        if a_card.queue != ui_value:
            a_card.queue = ui_value
            self.fresh_all_ui()
            return

        ui_value = self.EditorOfActionInfo.WidgetKunInput.value()
        if a_card.kun != ui_value:
            a_card.kun = ui_value
            self.fresh_all_ui()
            return

    def update_info_mode_2(self):
        """
        在UI上编辑更新一组定时放卡操作的状态后
        将该操作同步到内部数据表
        并刷新到左侧列表和棋盘等位置
        :return: None
        """
        print("即将更新 当前波次的 定时用卡中 被选中卡片的数据, 索引: ", self.be_edited_index_mod_2)

        # 将当前状态压入栈中
        self.append_undo_stack()

        events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]
        event = events[self.be_edited_index_mod_2]

        # 获取当前UI数据
        ui_data = self.EditorOfActionInfo.get_data()
        print("UI数据: ", ui_data)
        # 创建新的操作对象
        if ui_data["type"] == "shovel":
            # 创建新的铲子操作对象
            new_action = ActionShovel(
                time=ui_data["time"],
                location=event.action.location
            )
        else:
            # 创建新的普通放卡对象
            new_action = ActionInsertUseCard(
                card_id=ui_data.get("card_id", 1),
                location=event.action.location,
                before_shovel=ui_data.get("before_shovel", False),
                after_shovel=ui_data.get("after_shovel", False),
                after_shovel_time=ui_data.get("after_shovel_time", 0)
            )

        # 替换事件中的action对象
        event.action = new_action

        # 更新触发器时间
        event.trigger.time = ui_data["time"]

        self.fresh_all_ui()

    def update_info_mode_3(self):
        """更新宝石操作事件的UI与数据"""
        try:
            events = [e for e in self.insert_use_special_events if e.trigger.wave_id == self.be_edited_wave_id]
            event = events[self.be_edited_index_mod_3]

            # 获取当前UI数据
            ui_gem_id = self.EditorOfActionInfo.WidgetGemIdInput.currentText()
            if not ui_gem_id.strip():
                raise ValueError("宝石ID不能为空")

            # 创建新的操作对象
            if isinstance(event.action, ActionEscape):
                new_data = self.EditorOfActionInfo.get_data()
                new_action = ActionEscape(time=new_data["time"])
                event.trigger.time = new_data["time"]
            elif isinstance(event.action, ActionBanCard):
                new_data = self.EditorOfActionInfo.get_data()
                new_action = ActionBanCard(
                    start_time=new_data["start_time"],
                    end_time=new_data["end_time"],
                    card_id=new_data["card_id"])
                event.trigger.time = new_data["start_time"]
            else:  # ActionUseGem
                # 显式定义new_data
                new_data = {
                    "gem_id": int(ui_gem_id),
                    "time": self.EditorOfActionInfo.WidgetTimeInput.value()
                }
                new_action = ActionUseGem(gem_id=new_data["gem_id"])
                event.trigger.time = new_data["time"]

            # 替换事件中的action对象
            event.action = new_action

            self.fresh_all_ui()

        except ValueError as ve:
            QMessageBox.warning(self, "输入错误", f"请输入有效的宝石ID: {str(ve)}")
            self.EditorOfActionInfo.WidgetGemIdInput.setFocus()

    """棋盘操作 - 根据操作修改内部数据表 再刷新UI"""

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

            elif self.be_edited_index_mod_1 is not None:

                # 将当前状态压入栈中
                self.append_undo_stack()

                # 当前index为卡片
                event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
                target = event.action.cards[self.be_edited_index_mod_1]
                # 如果这个位置已经有了这张卡片，那么移除它；否则添加它
                if location_key in target.location:
                    target.location.remove(location_key)
                else:
                    target.location.append(location_key)

        # 定时放卡模式
        if self.editing_mode == 2 and self.be_edited_index_mod_2 is not None:
            # 将当前状态压入栈中
            self.append_undo_stack()

            events = [e for e in self.insert_use_card_events if e.trigger.wave_id == self.be_edited_wave_id]
            event = events[self.be_edited_index_mod_2]
            # 根据操作类型处理位置选择
            if isinstance(event.action, ActionInsertUseCard):
                event.action.location = "" if event.action.location == location_key else location_key
            elif isinstance(event.action, ActionShovel):
                event.action.location = location_key

        self.refresh_chessboard()
        self.refresh_wave_button_color()
        self.highlight_chessboard()
        self.fresh_all_ui()

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

                        # 只显示当前选中格子的操作
                        if event.action.location == this_location:
                            # 统一处理所有操作类型
                            if isinstance(event.action, ActionInsertUseCard):
                                try:
                                    card_name = next(
                                        c.name for c in self.battle_plan.cards
                                        if c.card_id == event.action.card_id
                                    )
                                    text_block.append(f"{card_name} {event.trigger.time}s")
                                except StopIteration:
                                    continue
                            elif isinstance(event.action, ActionShovel):
                                text_block.append(f"铲子 {event.trigger.time}s")

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
                if self.be_edited_index_mod_1 is not None:
                    event = next(e for e in self.loop_use_cards_events if e.trigger.wave_id == self.be_edited_wave_id)
                    a_card = event.action.cards[self.be_edited_index_mod_1]
                    current_card_locations = a_card.location

            for location in current_card_locations:
                x, y = map(int, location.split('-'))
                selected_cells.add((x, y))
                # 如果是选中的卡片 蓝色
                self.chessboard_frames[y - 1][x - 1].setStyleSheet("background-color: rgba(30, 144, 255, 150);")

        if self.editing_mode == 2:
            if self.be_edited_index_mod_2 is not None:
                events = [e for e in self.insert_use_card_events
                          if e.trigger.wave_id == self.be_edited_wave_id]

                if 0 <= self.be_edited_index_mod_2 < len(events):
                    event = events[self.be_edited_index_mod_2]

                    # 统一处理所有操作类型
                    if isinstance(event.action, ActionInsertUseCard) or isinstance(event.action, ActionShovel):
                        location = event.action.location
                        if location:
                            x, y = map(int, location.split('-'))
                            selected_cells.add((x, y))
                            self.chessboard_frames[y - 1][x - 1].setStyleSheet(
                                "background-color: rgba(30, 144, 255, 150);")

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
            self.insert_use_card_events.sort(key=lambda x: (x.trigger.wave_id, x.trigger.time))
            self.battle_plan.events.extend(copy.deepcopy(event) for event in self.loop_use_cards_events)
            self.battle_plan.events.extend(copy.deepcopy(event) for event in self.insert_use_card_events)
            self.battle_plan.events.extend(copy.deepcopy(event) for event in self.insert_use_special_events)

        view_to_obj_battle_plan()

        is_save_as = self.sender() == self.BtnSaveAs

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
            if not new_file_path:
                # 用户直接退出另存为界面
                return
        else:
            if not self.file_path:
                # 保存, 提示用户还未选择任何战斗方案
                QMessageBox.information(self, "禁止虚空保存！", "请先选择一个战斗方案!")
                return
            # 保存
            new_file_path = self.file_path

        if not os.path.exists(new_file_path):
            # 如果是另存为到新文件，则创建新的UUID
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
                QMessageBox.information(self, "成功!", "<战斗方案> 已保存成功~")

        # 打开新建 or 覆盖掉的文件 确保内部数据一致性
        self.load_json(file_path=new_file_path)

        self.init_battle_plan()

        self.BtnSave.setEnabled(True)

    """打开战斗方案"""

    def open_battle_plan(self):

        file_name = self.open_json()

        if file_name:
            result = self.load_json(file_path=file_name)
            if result:
                self.init_battle_plan()
                self.BtnSave.setEnabled(True)
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

        self.LabelCurrentBattlePlanFileName.setText(f"当前方案: {current_plan_name}")
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
                isinstance(event.action, (ActionInsertUseCard, ActionShovel)))
        ]

        # 类型3 特殊操作
        self.insert_use_special_events: List[Event] = [
            event for event in self.battle_plan.events
            if (isinstance(event.trigger, TriggerWaveTimer) and
                isinstance(event.action, (ActionUseGem, ActionEscape, ActionBanCard,
                                          ActionRandomSingleCard, ActionRandomMultiCard)))
        ]

        # 填充构造所有波次的 变阵操作 保存的时候再去掉重复项
        self.fill_blank_wave()

        # 填充构造所有卡牌 保存时去掉没有被使用的项
        self.fill_blank_card()

        # 初始化当前选中
        self.editing_mode = 1
        self.change_edit_mode(1)
        self.be_edited_wave_id = 0
        self.be_edited_index_mod_1 = None
        self.be_edited_index_mod_2 = None
        self.be_copied_loop_use_cards_event_wave_id = None
        self.be_edited_player = False
        self.BtnPlayer.setText("玩家位置")
        self.LabelWaveCopyTip.setText('尚未复制任何波次信息')

        # 初始化卡组编辑相关属性
        self.card_id_changes_memory = {}  # ID变更记录

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
            CUS_LOGGER.debug(
                f"[战斗方案编辑器] [加载方案] 填充循环放卡方案的空白波次, 波次0不存在, 花瓶方案, 补充第0波方案.")
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
        为空的战斗方案补充一个卡
        :return:
        """
        # 如果卡组为空，则添加一张默认卡片
        if not self.battle_plan.cards:
            self.battle_plan.cards.append(Card(card_id=1, name="新的卡片"))

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

        CUS_LOGGER.debug(f"拖拽事件信息 text:{item.text()} from {index_from} to {index_to} memory:{self.currentRow()}")

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


class InfoEditorOfCards(QDialog):

    def __init__(self, data, func_update):
        super().__init__()
        self.data = data
        self.func_update = func_update

        # 窗口标题栏
        self.setWindowTitle("编辑卡片属性")

        # 彻底移除系统菜单图标
        self.setWindowFlags(
            Qt.WindowType.CustomizeWindowHint |  # 允许自定义窗口装饰
            Qt.WindowType.WindowCloseButtonHint |  # 仅保留关闭按钮
            Qt.WindowType.WindowStaysOnTopHint  # 窗口置顶
        )

        # UI
        self.WidgetNameInput = None
        self.init_ui()

        # 初始化数据
        self.load_data()

        # 绑定变化信号
        self.connect_functions()

    def init_ui(self):
        LayMain = QVBoxLayout()
        self.setLayout(LayMain)

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

    def load_data(self):
        self.WidgetNameInput.setText(str(self.data["name"]))

    def connect_functions(self):
        """绑定信号"""

        self.WidgetNameInput.textChanged.connect(self.func_update)


class InfoEditorOfLoopUseCardsOneCard(QDialog):
    def __init__(self, data, func_update):
        super().__init__()
        self.data = data
        self.func_update = func_update

        # 窗口标题栏
        self.setWindowTitle("编辑循环放卡动作参数")

        # 彻底移除系统菜单图标
        self.setWindowFlags(
            Qt.WindowType.CustomizeWindowHint |  # 允许自定义窗口装饰
            Qt.WindowType.WindowCloseButtonHint |  # 仅保留关闭按钮
            Qt.WindowType.WindowStaysOnTopHint  # 窗口置顶
        )

        # UI
        self.WidgetIdInput = None
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

        tooltips = "选择要使用的卡片"
        label = QLabel('使用卡片')
        label.setToolTip(tooltips)
        layout.addWidget(label)

        self.WidgetIdInput = QComboBox()
        self.WidgetIdInput.setFixedWidth(140)
        self.WidgetIdInput.setToolTip(tooltips)
        layout.addWidget(self.WidgetIdInput)

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

        # 填充列表并选择对应数据
        self.WidgetIdInput.clear()
        for card in self.data["cards"]:
            self.WidgetIdInput.addItem(f"ID:{card.card_id} - {card.name}", card.card_id)
        index = self.WidgetIdInput.findData(self.data["id"])
        if index >= 0:
            self.WidgetIdInput.setCurrentIndex(index)

        self.WidgetErgodicInput.setCurrentText(str(self.data['ergodic']).lower())
        self.WidgetQueueInput.setCurrentText(str(self.data['queue']).lower())
        self.WidgetKunInput.setValue(self.data.get('kun', 0))

    def connect_functions(self):
        """绑定信号"""

        # id，名称,遍历，队列控件的更改都连接上更新卡片
        self.WidgetIdInput.currentIndexChanged.connect(self.func_update)
        self.WidgetErgodicInput.currentIndexChanged.connect(self.func_update)
        self.WidgetQueueInput.currentIndexChanged.connect(self.func_update)
        self.WidgetKunInput.valueChanged.connect(self.func_update)


class InfoEditorOfInsertUseCard(QDialog):
    def __init__(self, data, func_update, editor_parent, event_index):
        super().__init__()

        self.data = data.copy() if data else {}  # 数据隔离
        self.func_update = func_update
        self.editor_parent = editor_parent
        self.event_index = event_index

        # 初始化必要字段
        self._ensure_required_fields()

        # UI
        self.WidgetIdInput2 = None
        self.WidgetBeforeShovelInput = None
        self.WidgetTimeInput = None
        self.WidgetTypeSelect = None
        self.WidgetAfterTimeInput = None
        self.WidgetAfterShovelInput = None
        self.normal_params = None

        # UI组件初始化
        self.init_ui()
        self.load_data()
        self.connect_functions()

        # 设置窗口属性
        self.setWindowTitle("编辑定时操作参数")
        self.setWindowFlags(
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

    def _ensure_required_fields(self):
        """确保基础字段存在"""
        if 'type' not in self.data:
            self.data['type'] = 'insert_use_card'
        if 'time' not in self.data:
            self.data['time'] = 0.0
        if 'location' not in self.data:
            self.data['location'] = ''

    def init_ui(self):
        """初始化定时操作参数编辑界面"""
        LayMain = QVBoxLayout()
        self.setLayout(LayMain)

        # 操作类型选择
        type_layout = QHBoxLayout()
        type_label = QLabel('操作类型')
        self.WidgetTypeSelect = QComboBox()
        self.WidgetTypeSelect.addItems(['定时放卡', '定时铲子'])
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.WidgetTypeSelect)
        LayMain.addLayout(type_layout)

        # 时间参数
        time_layout = QHBoxLayout()
        time_label = QLabel('执行时间')
        self.WidgetTimeInput = QDoubleSpinBox()
        self.WidgetTimeInput.setFixedWidth(140)
        self.WidgetTimeInput.setToolTip("识别到对应波次后，会在对应秒数后执行操作")
        self.WidgetTimeInput.setRange(0, 9999)
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.WidgetTimeInput)
        LayMain.addLayout(time_layout)

        # 普通放卡参数组
        self.normal_params = QWidget()
        normal_layout = QVBoxLayout()
        self.normal_params.setLayout(normal_layout)

        # ID
        layout = QHBoxLayout()
        LayMain.addLayout(layout)

        tooltips = "选择要使用的卡片"
        label = QLabel('使用卡片')
        label.setToolTip(tooltips)
        layout.addWidget(label)

        self.WidgetIdInput2 = QComboBox()
        self.WidgetIdInput2.setFixedWidth(140)
        self.WidgetIdInput2.setToolTip(tooltips)
        layout.addWidget(self.WidgetIdInput2)
        normal_layout.addLayout(layout)

        # 分割线
        normal_layout.addWidget(create_vertical_line())

        # 前铲参数
        before_shovel_layout = QHBoxLayout()
        before_shovel_label = QLabel('前铲')
        before_shovel_label.setToolTip("是否会在操作前0.5秒铲除该点以腾出位置")
        self.WidgetBeforeShovelInput = QComboBox()
        self.WidgetBeforeShovelInput.setFixedWidth(140)
        self.WidgetBeforeShovelInput.addItems(['true', 'false'])
        self.WidgetBeforeShovelInput.setToolTip("是否会在操作前0.5秒铲除该点以腾出位置")
        self.WidgetBeforeShovelInput.setCurrentIndex(1)
        before_shovel_layout.addWidget(before_shovel_label)
        before_shovel_layout.addWidget(self.WidgetBeforeShovelInput)
        normal_layout.addLayout(before_shovel_layout)

        # 后铲参数
        after_shovel_layout = QHBoxLayout()
        after_shovel_label = QLabel('后铲')
        after_shovel_label.setToolTip("是否会在指定的秒数后执行清理操作")
        self.WidgetAfterShovelInput = QComboBox()
        self.WidgetAfterShovelInput.setFixedWidth(140)
        self.WidgetAfterShovelInput.addItems(['true', 'false'])
        self.WidgetAfterShovelInput.setToolTip("是否会在指定的秒数后执行清理操作")
        self.WidgetAfterShovelInput.setCurrentIndex(1)
        after_shovel_layout.addWidget(after_shovel_label)
        after_shovel_layout.addWidget(self.WidgetAfterShovelInput)
        normal_layout.addLayout(after_shovel_layout)

        # 后铲时间参数
        after_time_layout = QHBoxLayout()
        after_time_label = QLabel('清理延迟')
        after_time_label.setToolTip("操作完成后，几秒后执行清理")
        self.WidgetAfterTimeInput = QDoubleSpinBox()
        self.WidgetAfterTimeInput.setFixedWidth(140)
        self.WidgetAfterTimeInput.setToolTip("操作完成后，几秒后执行清理")
        self.WidgetAfterTimeInput.setRange(0, 9999)
        after_time_layout.addWidget(after_time_label)
        after_time_layout.addWidget(self.WidgetAfterTimeInput)
        normal_layout.addLayout(after_time_layout)

        LayMain.addWidget(self.normal_params)

    def connect_functions(self):
        """绑定信号"""

        self.WidgetTypeSelect.currentIndexChanged.connect(self.func_update)  # type: ignore
        self.WidgetTimeInput.valueChanged.connect(self.func_update)  # type: ignore
        self.WidgetIdInput2.currentIndexChanged.connect(self.func_update)  # type: ignore
        self.WidgetBeforeShovelInput.currentIndexChanged.connect(self.func_update)  # type: ignore
        self.WidgetAfterShovelInput.currentIndexChanged.connect(self.func_update)  # type: ignore
        self.WidgetAfterTimeInput.valueChanged.connect(self.func_update)  # type: ignore

    def on_type_changed(self):
        """处理操作类型切换"""
        is_shovel = self.WidgetTypeSelect.currentIndex() == 1

        # 更新数据模型
        self.data['type'] = 'shovel' if is_shovel else 'insert_use_card'

        # 清理非必要字段
        if is_shovel:
            for key in ['card_id', 'name', 'before_shovel', 'after_shovel', 'after_shovel_time']:
                self.data.pop(key, None)
        else:
            if 'card_id' not in self.data:
                self.data['card_id'] = 1
            if 'name' not in self.data:
                self.data['name'] = ''
            if 'before_shovel' not in self.data:
                self.data['before_shovel'] = False
            if 'after_shovel' not in self.data:
                self.data['after_shovel'] = False
            if 'after_shovel_time' not in self.data:
                self.data['after_shovel_time'] = 0.0

        # 强制重新加载数据到UI
        self.load_data()

        # 强制触发外部更新
        self.func_update()
        self.editor_parent.fresh_all_ui()

    def load_data(self):
        """加载数据到UI"""
        # 基础字段
        self.WidgetTimeInput.setValue(self.data.get('time', 0))

        # 类型选择器
        self.WidgetTypeSelect.setCurrentIndex(
            1 if self.data.get('type') == 'shovel' else 0)

        # 普通放卡字段
        if self.data.get('type') != 'shovel':

            # 填充列表并选择对应数据
            self.WidgetIdInput2.clear()
            for card in self.data["cards"]:
                self.WidgetIdInput2.addItem(f"ID:{card.card_id} - {card.name}", card.card_id)
            index = self.WidgetIdInput2.findData(self.data["id"])
            if index >= 0:
                self.WidgetIdInput2.setCurrentIndex(index)

            self.WidgetBeforeShovelInput.setCurrentText(
                str(self.data.get('before_shovel', False)).lower())

            self.WidgetAfterShovelInput.setCurrentText(
                str(self.data.get('after_shovel', False)).lower())

            self.WidgetAfterTimeInput.setValue(
                self.data.get('after_shovel_time', 0))

        # 更新UI可见性
        self.normal_params.setVisible(self.data.get('type') != 'shovel')

    def get_data(self):
        """获取当前UI数据"""
        data = {
            "time": self.WidgetTimeInput.value(),
            "type": "shovel" if self.WidgetTypeSelect.currentIndex() == 1 else "insert_use_card",
            "location": self.data.get("location", "")
        }

        # 普通放卡特有字段
        if data["type"] != "shovel":
            data.update({
                "card_id": self.WidgetIdInput2.currentData(),
                "before_shovel": self.WidgetBeforeShovelInput.currentText() == "true",
                "after_shovel": self.WidgetAfterShovelInput.currentText() == "true",
                "after_shovel_time": self.WidgetAfterTimeInput.value()
            })

        return data


class ShovelActionEditor(QDialog):
    def __init__(self, data, func_update, editor_parent, event_index):
        super().__init__()

        self.data = data.copy() if data else {}
        self.func_update = func_update
        self.editor_parent = editor_parent
        self.event_index = event_index

        # 确保必要字段
        if 'time' not in self.data:
            self.data['time'] = 0.0
        if 'location' not in self.data:
            self.data['location'] = ''

        # UI
        self.WidgetTimeInput = None
        self.init_ui()
        self.load_data()
        self.WidgetTimeInput.valueChanged.connect(self.func_update)  # type: ignore

        # 窗口设置
        self.setWindowTitle("编辑定时铲子参数")
        self.setWindowFlags(
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

    def init_ui(self):
        """初始化铲子操作参数编辑界面"""
        LayMain = QVBoxLayout()
        self.setLayout(LayMain)

        # 时间参数
        time_layout = QHBoxLayout()
        time_label = QLabel('执行时间')
        self.WidgetTimeInput = QDoubleSpinBox()
        self.WidgetTimeInput.setFixedWidth(140)
        self.WidgetTimeInput.setToolTip("识别到对应波次后，会在对应秒数后执行操作")
        self.WidgetTimeInput.setRange(0, 9999)
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.WidgetTimeInput)
        LayMain.addLayout(time_layout)

    def load_data(self):
        """加载数据到UI"""
        self.WidgetTimeInput.setValue(self.data.get('time', 0))

    def get_data(self):
        """获取当前UI数据"""
        return {
            "time": self.WidgetTimeInput.value(),
            "type": "shovel",
            "location": self.data.get("location", "")
        }


class GemInfoEditor(QDialog):
    def __init__(self, data, func_update):
        super().__init__()
        self.data = data
        self.func_update = func_update

        # 初始化时确保有默认值
        if "gem_id" not in self.data or not str(self.data["gem_id"]).strip():
            self.data["gem_id"] = 1  # 设置默认值
        if "time" not in self.data:
            self.data["time"] = 0.0

        # UI组件初始化
        self.WidgetTimeInput = QDoubleSpinBox()
        self.WidgetGemIdInput = QComboBox()

        # 填充宝石ID选项
        for i in range(1, 4):  # 假设宝石ID范围是1-3
            self.WidgetGemIdInput.addItem(str(i))

        self.setWindowTitle("编辑宝石操作参数")
        self.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint)
        self.init_ui()
        self.load_data()
        self.connect_functions()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)  # 设置窗口边距
        layout.setSpacing(15)  # 控件间垂直间距

        # 时间输入行
        time_layout = QHBoxLayout()
        time_layout.setSpacing(10)  # 行内控件间距
        time_label = QLabel("触发时间(s):")
        time_label.setFixedWidth(80)  # 固定标签宽度
        self.WidgetTimeInput.setFixedWidth(140)
        self.WidgetTimeInput.setToolTip("识别到对应波次后，会在该时间放置宝石")
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.WidgetTimeInput, 1)
        layout.addLayout(time_layout)

        # 宝石ID选择行
        gem_layout = QHBoxLayout()
        gem_layout.setSpacing(10)
        gem_label = QLabel("宝石ID:")
        gem_label.setFixedWidth(80)
        self.WidgetGemIdInput.setFixedWidth(140)
        self.WidgetGemIdInput.setToolTip("选择宝石在卡组中的编号（1-3）")
        gem_layout.addWidget(gem_label)
        gem_layout.addWidget(self.WidgetGemIdInput, 1)
        layout.addLayout(gem_layout)

    def load_data(self):
        # 确保加载时使用有效数据
        self.WidgetTimeInput.setValue(float(self.data.get("time", 0)))
        gem_id = self.data.get("gem_id", 1)
        index = self.WidgetGemIdInput.findText(str(gem_id))
        if index >= 0:
            self.WidgetGemIdInput.setCurrentIndex(index)
        else:
            self.WidgetGemIdInput.setCurrentIndex(0)  # 默认选第一个

    def connect_functions(self):
        self.WidgetTimeInput.valueChanged.connect(self.func_update)  # type: ignore
        self.WidgetGemIdInput.currentIndexChanged.connect(self.func_update)  # type: ignore


class SpecialActionTypeDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("选择特殊操作类型")
        layout = QVBoxLayout(self)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["逃跑操作", "禁用卡片", "宝石操作", "单卡随机", "多卡随机"])

        layout.addWidget(self.type_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)  # type: ignore
        buttons.rejected.connect(self.reject)  # type: ignore
        layout.addWidget(buttons)

    def get_selected_type(self):
        return {
            "逃跑操作": "escape",
            "禁用卡片": "disable_card",
            "宝石操作": "gem",
            "单卡随机": "random_single_card",
            "多卡随机": "random_multi_card"
        }[self.type_combo.currentText()]


class RandomSingleCardActionEditor(QDialog):
    def __init__(self, data, func_update):
        super().__init__()
        self.data = data.copy() if data else {"time": 0.0, "card_index": 1}
        self.func_update = func_update

        self.card_index = QSpinBox()
        self.card_index.setValue(self.data.get("card_index", 1))
        self.card_index.valueChanged.connect(self.on_value_changed)  # type: ignore

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("输入单卡索引"))
        layout.addWidget(self.card_index)

        self.setLayout(layout)
        self.setWindowTitle("编辑单卡随机")
        self.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint)

    def on_value_changed(self):
        self.data["card_index"] = self.card_index.value()
        if self.func_update:
            self.func_update()

    def get_data(self):
        return {
            "card_index": self.card_index.value(),
            "type": "random_single_card",
            "time": self.data.get("time", 0)
        }


class RandomMultiCardActionEditor(QDialog):
    def __init__(self, data, func_update):
        super().__init__()
        self.data = data.copy() if data else {"time": 0.0, "card_indices": [1, 2]}
        self.func_update = func_update

        self.card_indices_edit = QLineEdit()
        self.card_indices_edit.setText(",".join(map(str, self.data.get("card_indices", [1, 2]))))
        self.card_indices_edit.setPlaceholderText("输入多个索引，用逗号分隔")
        self.card_indices_edit.textEdited.connect(self.on_text_edited)  # type: ignore

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("选择多卡索引(用逗号分隔)"))
        layout.addWidget(self.card_indices_edit)

        self.setLayout(layout)
        self.setWindowTitle("编辑多卡随机")
        self.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint)

    def on_text_edited(self):
        card_indices_text = self.card_indices_edit.text()
        try:
            card_indices = [int(id.strip()) for _ in card_indices_text.split(",")] if card_indices_text else []
            self.data["card_indices"] = card_indices
            if self.func_update:
                self.func_update()
        except ValueError:
            pass  # 忽略无效输入

    def get_data(self):
        card_indices_text = self.card_indices_edit.text()
        card_indices = [int(id.strip()) for _ in card_indices_text.split(",")] if card_indices_text else []
        return {
            "card_indices": card_indices,
            "type": "random_multi_card",
            "time": self.data.get("time", 0)
        }


class EscapeActionEditor(QDialog):
    def __init__(self, data, func_update):
        super().__init__()
        self.data = data.copy() if data else {"time": 0.0}
        self.func_update = func_update

        self.WidgetTimeInput = QDoubleSpinBox()
        self.WidgetTimeInput.setRange(0, 9999)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        self.WidgetTimeInput.setFixedWidth(140)
        layout.addWidget(QLabel("触发时间(秒)"))
        layout.addWidget(self.WidgetTimeInput)

        self.setLayout(layout)
        self.setWindowTitle("编辑逃跑操作")
        self.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint)

        self.load_data()
        self.WidgetTimeInput.valueChanged.connect(self.func_update)  # type: ignore

    def load_data(self):
        self.WidgetTimeInput.setValue(self.data.get("time", 0))

    def get_data(self):
        return {"time": self.WidgetTimeInput.value(), "type": "escape"}


class BanCardActionEditor(QDialog):
    def __init__(self, data, func_update):
        super().__init__()
        self.data = data.copy() if data else {"start_time": 0.0, "end_time": 0.0, "card_id": 1}
        self.func_update = func_update

        self.start_time = QDoubleSpinBox()
        self.start_time.setRange(0, 9999)
        self.end_time = QDoubleSpinBox()
        self.end_time.setRange(0, 9999)
        self.card_id = QSpinBox()
        self.card_id.setRange(0, 21)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        layout.addWidget(QLabel("开始时间(秒)"))
        layout.addWidget(self.start_time)
        layout.addWidget(QLabel("结束时间(秒)"))
        layout.addWidget(self.end_time)
        layout.addWidget(QLabel("禁用的卡片ID(0-21)"))
        layout.addWidget(self.card_id)

        self.setLayout(layout)
        self.setWindowTitle("编辑禁用卡片")
        self.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint)

        self.load_data()
        self.start_time.valueChanged.connect(self.func_update)  # type: ignore
        self.end_time.valueChanged.connect(self.func_update)  # type: ignore
        self.card_id.valueChanged.connect(self.func_update)  # type: ignore

    def load_data(self):
        self.start_time.setValue(self.data.get("start_time", 0))
        self.end_time.setValue(self.data.get("end_time", 0))
        self.card_id.setValue(self.data.get("card_id", 1))

    def get_data(self):
        return {
            "start_time": self.start_time.value(),
            "end_time": self.end_time.value(),
            "card_id": self.card_id.value(),
            "type": "disable_card"
        }


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = QMWEditorOfBattlePlan(func_open_tip=lambda x: None)
    # 设定字体
    ex.set_my_font(EXTRA.Q_FONT)
    ex.show()
    sys.exit(app.exec())
