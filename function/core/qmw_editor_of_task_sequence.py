import json
import os
import sys
import uuid

from PyQt6.QtCore import Qt, QPoint

from function.globals.loadings import loading
from function.scattered.error_dialog_and_log import error_dialog_and_log

loading.update_progress(60, "正在加载FAA任务序列编辑器...")
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QPushButton, QComboBox, QHBoxLayout, QLabel, QLineEdit, \
    QSpinBox, QCheckBox, QWidget, QListWidgetItem, QFileDialog, QMessageBox, QApplication, QListWidget, QSpacerItem, \
    QSizePolicy, QFrame, QAbstractItemView, QInputDialog, QToolButton
from function.widget.SearchableComboBox import SearchableComboBox

from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.scattered.check_battle_plan import fresh_and_check_all_battle_plan, fresh_and_check_all_tweak_plan
from function.scattered.get_list_battle_plan import get_list_battle_plan, get_list_tweak_plan
from function.scattered.check_task_sequence import fresh_and_check_all_task_sequence
from function.scattered.get_task_sequence_list import get_task_sequence_list


def QCVerticalLine():
    """
    创建一个较窄的竖线
    """
    # 创建 QFrame 实例
    vertical_line = QFrame()

    # 设置为垂直线
    vertical_line.setFrameShape(QFrame.Shape.VLine)

    # 设置阴影效果
    vertical_line.setFrameShadow(QFrame.Shadow.Sunken)

    vertical_line.setStyleSheet("QFrame { background-color: gray; margin: 0px; padding: 0px; border: none; }")
    vertical_line.setFixedWidth(1)  # 设置固定的宽度为 1 像素
    return vertical_line


def ui_to_list_get_cus_battle_opt(LineWidget, task_args):
    GlobalPlanActiveCheckBox = LineWidget.findChild(QCheckBox, 'w_global_plan_active')
    task_args['global_plan_active'] = GlobalPlanActiveCheckBox.isChecked()

    DeckComboBox = LineWidget.plan_opt_window.findChild(QComboBox, 'w_deck')
    task_args['deck'] = int(DeckComboBox.currentIndex())

    # 战斗方案
    battle_plan_name_list = get_list_battle_plan(with_extension=False)
    battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

    Plan1pComboBox = LineWidget.plan_opt_window.findChild(SearchableComboBox, 'w_battle_plan_1p')
    text = Plan1pComboBox.currentText()
    if text in battle_plan_name_list:
        index = battle_plan_name_list.index(text)
        uuid = battle_plan_uuid_list[index]
        task_args['battle_plan_1p'] = uuid
    else:
        # 如果找不到对应名称，使用默认值
        task_args['battle_plan_1p'] = "00000000-0000-0000-0000-000000000000"

    Plan2pComboBox = LineWidget.plan_opt_window.findChild(SearchableComboBox, 'w_battle_plan_2p')
    text = Plan2pComboBox.currentText()
    if text in battle_plan_name_list:
        index = battle_plan_name_list.index(text)
        uuid = battle_plan_uuid_list[index]
        task_args['battle_plan_2p'] = uuid
    else:
        # 如果找不到对应名称，使用默认值
        task_args['battle_plan_2p'] = "00000000-0000-0000-0000-000000000001"

    # 微调方案
    tweak_plan_name_list = get_list_tweak_plan(with_extension=False)
    tweak_plan_uuid_list = list(EXTRA.TWEAK_BATTLE_PLAN_UUID_TO_PATH.keys())

    TweakPlanComboBox = LineWidget.plan_opt_window.findChild(SearchableComboBox, 'w_battle_plan_tweak')
    if TweakPlanComboBox and TweakPlanComboBox.count() > 0:  # 确保有选项且控件存在
        text = TweakPlanComboBox.currentText()
        if text in tweak_plan_name_list and tweak_plan_uuid_list:
            index = tweak_plan_name_list.index(text)
            uuid = tweak_plan_uuid_list[index]
            task_args['battle_plan_tweak'] = uuid
        else:
            task_args.pop('battle_plan_tweak', None)  # 无匹配项时清空
    else:
        task_args.pop('battle_plan_tweak', None)  # 控件不存在或无选项时清空

    # 移除多余的微调方案UUID
    if task_args['global_plan_active']:
        task_args.pop('battle_plan_tweak', None)

    return task_args


def ui_to_list_player(LineWidget, task_args):
    PlayerComboBox = LineWidget.findChild(QComboBox, 'w_player')
    text = PlayerComboBox.currentText()
    task_args['player'] = {"1P": [1], "2P": [2], "1+2P": [1, 2]}[text]
    return task_args


def ui_to_list_check_box(LineWidget, task_args, key):
    CheckBox = LineWidget.findChild(QCheckBox, f'w_{key}')
    task_args[key] = CheckBox.isChecked()
    return task_args


class QCListWidgetDraggable(QListWidget):
    """可拖拽的列表 魔改版"""

    def __init__(self, ):
        super(QCListWidgetDraggable, self).__init__()
        # 允许内部拖拽
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.drop_function = None

    def setDropFunction(self, drop_function):
        self.drop_function = drop_function

    def dropEvent(self, e):
        CUS_LOGGER.debug("拖拽事件触发")
        index_from = self.currentRow()
        super(QCListWidgetDraggable, self).dropEvent(e)  # 如果不调用父类的构造方法，拖拽操作将无法正常进行
        index_to = self.currentRow()

        source_Widget = e.source()  # 获取拖入item的父组件
        items = source_Widget.selectedItems()  # 获取所有的拖入item
        item = items[0]  # 不允许多选 所以只有一个

        CUS_LOGGER.debug("text:{} from {} to {} memory:{}".format(item.text(), index_from, index_to, self.currentRow()))

        # 执行更改函数
        self.drop_function()


class BattlePlanOptionsWidget(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 置顶并激活窗口
        self.raise_()  # 提升到顶层
        self.activateWindow()  # 激活窗口

        # 设置窗口属性 - 使用 Window 类型，不是 Tool
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowTitleHint)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        # 设置窗口名称
        self.setWindowTitle('独立配置 - 仅适用于本条任务 - 优先于全局设置生效')

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 创建各个选项组件
        self.deck_layout = QHBoxLayout()
        self.deck_label = QLabel('卡组')
        self.deck_input = QComboBox()
        self.deck_input.setObjectName("w_deck")
        self.deck_input.setParent(self, Qt.WindowType.Popup)
        self.deck_input.setFixedWidth(250)
        for index in ['自动', '1', '2', '3', '4', '5', '6']:
            self.deck_input.addItem(index)
        self.deck_layout.addWidget(self.deck_label)
        self.deck_layout.addWidget(self.deck_input)
        main_layout.addLayout(self.deck_layout)

        self.plan_1p_layout = QHBoxLayout()
        self.plan_1p_label = QLabel('1P方案')
        self.plan_1p_input = SearchableComboBox()
        self.plan_1p_input.setObjectName("w_battle_plan_1p")
        self.plan_1p_input.setParent(self, Qt.WindowType.Popup)
        self.plan_1p_input.setFixedWidth(250)
        self.plan_1p_layout.addWidget(self.plan_1p_label)
        self.plan_1p_layout.addWidget(self.plan_1p_input)
        main_layout.addLayout(self.plan_1p_layout)

        self.plan_2p_layout = QHBoxLayout()
        self.plan_2p_label = QLabel('2P方案')
        self.plan_2p_input = SearchableComboBox()
        self.plan_2p_input.setObjectName("w_battle_plan_2p")
        self.plan_2p_input.setParent(self, Qt.WindowType.Popup)
        self.plan_2p_input.setFixedWidth(250)
        self.plan_2p_layout.addWidget(self.plan_2p_label)
        self.plan_2p_layout.addWidget(self.plan_2p_input)
        main_layout.addLayout(self.plan_2p_layout)

        self.tweak_layout = QHBoxLayout()
        self.tweak_label = QLabel('微调方案')
        self.tweak_input = SearchableComboBox()
        self.tweak_input.setObjectName("w_battle_plan_tweak")
        self.tweak_input.setParent(self, Qt.WindowType.Popup)
        self.tweak_input.setFixedWidth(250)
        self.tweak_layout.addWidget(self.tweak_label)
        self.tweak_layout.addWidget(self.tweak_input)
        main_layout.addLayout(self.tweak_layout)

        # 设置主控件
        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        # 将 控件注册 为 窗口主控件
        self.setCentralWidget(main_widget)

    def set_deck_value(self, value):
        self.deck_input.setCurrentIndex(value)

    def get_deck_value(self):
        return self.deck_input.currentIndex()

    def set_1p_plan_items(self, items):
        self.plan_1p_input.clear()
        for item in items:
            self.plan_1p_input.addItem(item)

    def set_1p_plan_value(self, value):
        # 通过uuid查找对应的索引
        for i in range(self.plan_1p_input.count()):
            if self.plan_1p_input.itemText(i) == value:
                self.plan_1p_input.setCurrentIndex(i)
                break

    def get_1p_plan_value(self):
        return self.plan_1p_input.currentText()

    def set_2p_plan_items(self, items):
        self.plan_2p_input.clear()
        for item in items:
            self.plan_2p_input.addItem(item)

    def set_2p_plan_value(self, value):
        # 通过uuid查找对应的索引
        for i in range(self.plan_2p_input.count()):
            if self.plan_2p_input.itemText(i) == value:
                self.plan_2p_input.setCurrentIndex(i)
                break

    def get_2p_plan_value(self):
        return self.plan_2p_input.currentText()

    def set_tweak_plan_items(self, items):
        self.tweak_input.clear()
        for item in items:
            self.tweak_input.addItem(item)

    def set_tweak_plan_value(self, value):
        # 通过uuid查找对应的索引
        for i in range(self.tweak_input.count()):
            if self.tweak_input.itemText(i) == value:
                self.tweak_input.setCurrentIndex(i)
                break

    def get_tweak_plan_value(self):
        return self.tweak_input.currentText()


class QMWEditorOfTaskSequence(QMainWindow):
    def __init__(self, father=None):
        """
        初始化，完成界面布局，绑定信号与槽，初始化变量
        """
        super().__init__()
        self.father = father
        # 主布局
        self.lay_main = QVBoxLayout()

        # 列表
        self.WidgetTaskSequenceList = QCListWidgetDraggable()
        self.WidgetTaskSequenceList.setDropFunction(drop_function=self.update_task_id)
        self.lay_main.addWidget(self.WidgetTaskSequenceList)

        # 加载按钮
        self.father.TaskSequenceButtonLoadJson.clicked.connect(self.open_task_sequence)
        # 添加任务按钮
        self.father.TaskSequenceButtonAddTask.clicked.connect(self.add_task_by_button)
        # 初始化添加任务列表
        self.init_task_sequence_add_combo_box()
        # 保存和另存为按钮
        self.father.TaskSequenceButtonSaveJson.setEnabled(False)
        self.father.TaskSequenceButtonSaveJson.clicked.connect(self.save_json)
        self.father.TaskSequenceButtonSaveAsJson.clicked.connect(self.save_json)

        # 显示布局
        self.centralWidget = QWidget()
        self.centralWidget.setLayout(self.lay_main)
        self.setCentralWidget(self.centralWidget)

        # 读取方案时, 如果出现了uuid找不到方案的情况, 弹窗用变量
        self.could_not_find_battle_plan_uuid_list = []

        # 任务序列元数据
        self.current_task_sequence_meta_data = None
        self.file_path = None

        # 外观
        self.UICss()

    def UICss(self):
        """
        设置界面样式
        """
        # 设置窗口标题
        self.setWindowTitle('任务序列编辑器')

        # 设置窗口图标
        self.setWindowIcon(QIcon(PATHS["logo"] + "\\圆角-FetDeathWing-450x.png"))

        # 大小
        # 移除固定大小限制，让布局管理器可以控制大小
        # self.setMaximumSize(1500, 5000)
        # self.setMinimumSize(1500, 600)

    def set_my_font(self, my_font):
        """用于继承字体, 而不需要多次读取"""
        self.setFont(my_font)

    def init_task_sequence_add_combo_box(self):

        """
        初始化任务选择下拉框
        """
        # 创建任务描述字典
        task_descriptions = {
            '刷新游戏':
                '刷新游戏\n'
                '绝大部分情况下**请在开头**执行此项\n'
                '部分依赖此模块复位的功能中包含了该操作',
            '战斗':
                '从进入关卡到完成战斗的完整流程\n'
                '支持几乎所有关卡, 具体请参考右上角的关卡代号一览',
            '公会任务':
                '扫描并完成公会任务\n'
                '完整流程:\n'
                '* 清背包(需进阶设置-二级密码)\n'
                '* 领取公会任务奖励\n'
                '* 扫描任务并战斗\n'
                '* 清背包(需进阶设置-二级密码)\n'
                '* 领取公会任务奖励\n'
                '* 领取普通任务奖励(公会点)',
            '情侣任务':
                '扫描并完成情侣任务\n'
                '完整流程:\n'
                '* 领取情侣任务奖励\n'
                '* 扫描任务并战斗\n'
                '* 领取情侣任务奖励\n'
                '* 领取普通任务奖励(公会点)',
            '双暴卡':
                '使用双暴卡',
            '清背包':
                '删除背包中的垃圾\n'
                '需进阶设置-二级密码处进行设定\n'
                '被嵌入在部分其他模块中\n'
                '完整流程:\n'
                '* 输入二级密码\n'
                '* 清理背包\n'
                '* 刷新游戏',
            '兑换暗晶':
                '进行暗晶兑换\n'
                '需进阶设置完成二级密码设定\n'
                '完整流程:\n'
                '* 输入二级密码\n'
                '* 兑换暗晶\n'
                '* 刷新游戏',
            '签到':
                '执行每日签到\n'
                '完整流程:\n'
                '* 温馨礼包(需进阶设置-温馨礼包)\n'
                '* 日氪(需进阶设置-日氪)\n'
                '* VIP签到/每日签到/美食活动/塔罗/法老\n'
                '* 会长发任务/营地领钥匙/月卡礼包',
            '领取任务奖励':
                '领取各种任务的奖励.\n'
                '被嵌入在部分其他模块中\n'
                '可自行添加避免漏任务',
            '浇水施肥摘果':
                '无需解释',
            '使用消耗品':
                '使用背包中的消耗品',
            '查漏补缺':
                '检查并补充缺少的物品或任务',
            '跨服刷威望':
                '跨服务器刷取威望值\n'
                '无限执行直到被其他定时任务中止/手动停止',
            '天知强卡器':
                '联动激活天知强卡器\n'
                '无限执行直到被其他定时任务中止/手动停止/天知强卡器自爆',
            '美食大赛':
                'FAA第三代全自动美食大赛模块\n'
                '会自动触发美食大赛进度领取',
            '扫描任务列表':
                '扫描当前可执行的任务列表\n'
                '执念全新功能 - 自动清空普通任务的一部分',
            '任务序列':
                '嵌套执行其他任务序列\n'
                '自动去重, 防止套娃',
            '自建房战斗':
                '用户自行建房开始战斗\n'
                '请勿和上述的所有其他功能混合使用\n'
                '使用此功能前请勿刷新',
        }

        # 添加项目并设置 tooltip
        for index, task_type in enumerate(task_descriptions.keys()):
            self.father.TaskSequenceComboBoxAddTask.addItem(task_type)
            self.father.TaskSequenceComboBoxAddTask.setItemData(
                index, task_descriptions[task_type], Qt.ItemDataRole.ToolTipRole)

    def add_task_by_button(self):
        """
        点击按钮, 添加一项任务(行)
        """
        task_type = self.father.TaskSequenceComboBoxAddTask.currentText()

        # 默认值
        task = {
            "task_type": task_type,
            "task_id": 0,
            "enabled": True,
            "alias": "",  # 添加别名字段
            "tooltip": "",  # 添加提示字段
            "task_args": dict()
        }
        match task_type:
            case '战斗':
                task["task_args"] = {
                    "stage_id": "NO-1-7",
                    "max_times": 1,
                    "need_key": True,
                    "player": [2, 1],
                    "global_plan_active": False,
                    "deck": 0,
                    "battle_plan_1p": "00000000-0000-0000-0000-000000000000",
                    "battle_plan_2p": "00000000-0000-0000-0000-000000000001",
                }
            case '双暴卡':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                    "max_times": 1,
                }
            case '刷新游戏':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }
            case '清背包':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }
            case '兑换暗晶':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }
            case '领取任务奖励':
                task["task_args"] = {
                    "player": [1, 2],
                    "normal": False,
                    "guild": False,
                    "spouse": False,
                    "offer_reward": False,
                    "food_competition": False,
                    "monopoly": False,
                    "camp": False
                }
            case '扫描任务列表':
                task["task_args"] = {
                    "player": [1, 2],
                    "scan": False,
                    "battle": False
                }
            case '扫描公会贡献':
                task["task_args"] = {
                    "player": 1,  # or 2
                }
            case '使用绑定消耗品':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }
            case '签到':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }
            case '浇水施肥摘果':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }
            case '公会任务':
                task["task_args"] = {
                    "cross_server": False,
                    "global_plan_active": False,
                    "deck": 0,
                    "battle_plan_1p": "00000000-0000-0000-0000-000000000000",
                    "battle_plan_2p": "00000000-0000-0000-0000-000000000001",
                }
            case '情侣任务':
                task["task_args"] = {
                    "global_plan_active": False,
                    "deck": 0,
                    "battle_plan_1p": "00000000-0000-0000-0000-000000000000",
                    "battle_plan_2p": "00000000-0000-0000-0000-000000000001",
                }
            case '使用消耗品':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }
            case '查漏补缺':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }
            case '跨服刷威望':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }
            case '天知强卡器':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }
            case '美食大赛':
                task["task_args"] = {
                }
            case '自建房战斗':
                task["task_args"] = {
                    "stage_id": "NO-1-7",
                    "max_times": 1,
                    "need_key": True,
                    "player": [2, 1],
                    "global_plan_active": False,
                    "deck": 0,
                    "battle_plan_1p": "00000000-0000-0000-0000-000000000000",
                    "battle_plan_2p": "00000000-0000-0000-0000-000000000001",
                }
            case '任务序列':
                # 初始化时创建UUID列表
                fresh_and_check_all_task_sequence()
                task_sequence_uuid_list = list(EXTRA.TASK_SEQUENCE_UUID_TO_PATH.keys())
                if self.current_task_sequence_meta_data:
                    if self.current_task_sequence_meta_data.get("uuid", None):
                        task_sequence_uuid_list.remove(self.current_task_sequence_meta_data["uuid"])
                default_task_sequence_uuid = task_sequence_uuid_list[0]

                task["task_args"] = {
                    "sequence_integer": 1,
                    "task_sequence_uuid": default_task_sequence_uuid,
                }

        self.add_task(task=task)

    def add_task(self, task):
        """
        添加任务
        :param task:
        :return:
        """

        # 重新生成id
        task["task_id"] = self.WidgetTaskSequenceList.count() + 1

        # 生成控件行
        line_widget = self.create_task_line_widget(task)
        # 在控件中存储原始任务数据，以便后续访问
        line_widget.setProperty('task_data', task)

        # 创建一个 QListWidgetItem，并将 line_widget 设置为其附加的 widget
        line_item = QListWidgetItem()

        # 设置 QListWidgetItem 的高度
        line_item.setSizeHint(line_widget.sizeHint())

        self.WidgetTaskSequenceList.addItem(line_item)
        self.WidgetTaskSequenceList.setItemWidget(line_item, line_widget)

        # 绑定删除按钮的两个函数
        delete_button = line_widget.findChild(QPushButton, 'delete_button')
        delete_button.clicked.connect(lambda: self.remove_task_by_line_item(line_item))
        delete_button.clicked.connect(self.update_task_id)

    def remove_task_by_line_item(self, line_item):
        # 获取索引
        index = self.WidgetTaskSequenceList.row(line_item)
        # 清除对应索引的行
        self.WidgetTaskSequenceList.takeItem(index)

    def create_task_line_widget(self, task):
        """
        根据任务生成控件，单独管理列表中每一行的布局
        每一行布局分为三个部分：task_id; task type; task info
        """

        # 本行元素 + 布局
        line_widget = QWidget()
        line_widget.setObjectName('line_widget')
        line_layout = QHBoxLayout(line_widget)

        # 启用状态复选框
        EnabledCheckBox = QCheckBox()
        EnabledCheckBox.setObjectName('w_enabled')
        EnabledCheckBox.setChecked(task.get("enabled", True))  # 默认为启用
        EnabledCheckBox.setToolTip("启用/禁用此任务")
        line_layout.addWidget(EnabledCheckBox)

        # task_id + type
        layout = QHBoxLayout()
        line_layout.addLayout(layout)

        IdLabel = QLabel(str(task["task_id"]))
        IdLabel.setObjectName('label_task_id')
        IdLabel.setFixedWidth(20)
        layout.addWidget(IdLabel)

        task_type = task['task_type']

        # 显示别名，如果没有别名则显示任务类型
        display_text = task.get('alias', '') if task.get('alias', '') else task_type
        TypeLabel = QLabel(display_text)
        TypeLabel.setObjectName("label_task_type")
        TypeLabel.setFixedWidth(80)

        # 添加双击编辑别名功能
        TypeLabel.setCursor(Qt.CursorShape.PointingHandCursor)
        tooltip_text = task.get("tooltip", "")
        if not tooltip_text:
            tooltip_text = "双击编辑别名，右键编辑提示信息"
        TypeLabel.setToolTip(tooltip_text)
        TypeLabel.mouseDoubleClickEvent = lambda event, label=TypeLabel, t=task: self.edit_alias(label, t)
        TypeLabel.contextMenuEvent = lambda event, label=TypeLabel, t=task: self.edit_tooltip(event, label, t)
        layout.addWidget(TypeLabel)

        line_layout.addWidget(QCVerticalLine())

        def addElement(line_layout, input_widget, label_widget=None, end_line=True):

            layout = QHBoxLayout()
            line_layout.addLayout(layout)

            # 添加标签控件(如果有)
            if label_widget is not None:
                layout.addWidget(label_widget)

            # 添加输入控件
            layout.addWidget(input_widget)

            if end_line:
                # line_layout.addWidget(QCVerticalLine())
                line_layout.addWidget(QLabel(" "))

        def add_custom_plan_widget(line_layout):

            # 全局关卡方案
            GlobalPlanActiveCheckBox = QCheckBox()
            GlobalPlanActiveCheckBox.setObjectName("w_global_plan_active")
            GlobalPlanActiveCheckBox.setChecked(task["task_args"]["global_plan_active"])
            addElement(
                line_layout=line_layout,
                label_widget=QLabel('应用全局&关卡方案'),
                input_widget=GlobalPlanActiveCheckBox)

            # 创建齿轮按钮
            line_layout.addWidget(QLabel('独立方案'))
            GearButton = QToolButton()
            GearButton.setObjectName("gear_button")
            GearButton.setText("⚙")
            GearButton.setFixedSize(20, 20)
            line_layout.addWidget(GearButton)

            # 创建子窗口
            options_widget = BattlePlanOptionsWidget()
            line_widget.plan_opt_window = options_widget

            # 设置战斗方案数据
            fresh_and_check_all_battle_plan()
            battle_plan_name_list = get_list_battle_plan(with_extension=False)
            battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())
            options_widget.set_1p_plan_items(battle_plan_name_list)
            options_widget.set_2p_plan_items(battle_plan_name_list)

            # 设置微调方案数据
            fresh_and_check_all_tweak_plan()
            tweak_plan_name_list = get_list_tweak_plan(with_extension=False)
            tweak_plan_uuid_list = list(EXTRA.TWEAK_BATTLE_PLAN_UUID_TO_PATH.keys())
            options_widget.set_tweak_plan_items(tweak_plan_name_list)

            # 设置当前值
            try:
                index_1p = battle_plan_uuid_list.index(task["task_args"]["battle_plan_1p"])
                name_1p = battle_plan_name_list[index_1p]
            except ValueError:
                self.could_not_find_battle_plan_uuid_list.append(task["task_args"]["battle_plan_1p"])
                name_1p = battle_plan_name_list[0] if battle_plan_name_list else ""
            options_widget.set_1p_plan_value(name_1p)

            try:
                index_2p = battle_plan_uuid_list.index(task["task_args"]["battle_plan_2p"])
                name_2p = battle_plan_name_list[index_2p]
            except ValueError:
                self.could_not_find_battle_plan_uuid_list.append(task["task_args"]["battle_plan_2p"])
                name_2p = battle_plan_name_list[1] if len(battle_plan_name_list) > 1 else ""
            options_widget.set_2p_plan_value(name_2p)

            try:
                index_tweak = tweak_plan_uuid_list.index(task["task_args"].get("battle_plan_tweak", ""))
                name_tweak = tweak_plan_name_list[index_tweak]
            except (ValueError, IndexError):
                name_tweak = tweak_plan_name_list[0] if tweak_plan_name_list else ""
            options_widget.set_tweak_plan_value(name_tweak)

            options_widget.set_deck_value(task["task_args"]["deck"])

            # 定义切换子窗口的函数
            def toggle_options_widget():
                # 检查全局方案是否激活，如果激活则不允许打开子窗口
                if GlobalPlanActiveCheckBox.isChecked():
                    return  # 全局方案激活时不打开子窗口

                if options_widget.isVisible():
                    options_widget.hide()
                else:
                    # 计算子窗口位置，向右偏移20像素
                    pos = GearButton.mapToGlobal(QPoint(20, GearButton.height()))
                    options_widget.show()
                    options_widget.move(pos.x(), pos.y() - options_widget.height())

            # 当全局方案状态改变时，同步更新按钮状态
            def on_global_plan_changed(state):
                # 如果全局方案被激活，隐藏子窗口
                if state == Qt.CheckState.Checked.value:
                    if options_widget.isVisible():
                        options_widget.hide()
                    GearButton.setText("X")
                else:
                    GearButton.setText("⚙")

            GearButton.clicked.connect(toggle_options_widget)
            GlobalPlanActiveCheckBox.stateChanged.connect(on_global_plan_changed)

        def battle(line_layout):
            # 所选关卡
            StageIdLineEdit = QLineEdit()
            StageIdLineEdit.setObjectName("w_stage_id")
            StageIdLineEdit.setFixedWidth(70)
            StageIdLineEdit.setText(task["task_args"]["stage_id"])
            addElement(line_layout=line_layout, label_widget=QLabel('关卡'), input_widget=StageIdLineEdit)

            # 战斗次数
            MaxTimesSpinBox = QSpinBox()
            MaxTimesSpinBox.setObjectName("w_max_times")
            MaxTimesSpinBox.setFixedWidth(70)
            MaxTimesSpinBox.setMinimum(1)
            MaxTimesSpinBox.setMaximum(999)
            MaxTimesSpinBox.setValue(task["task_args"]["max_times"])
            addElement(line_layout=line_layout, label_widget=QLabel('次数'), input_widget=MaxTimesSpinBox)

            # 战斗Player
            PlayerComboBox = QComboBox()
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1P房主', '2P房主']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1P房主', (2, 1): '2P房主'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=QLabel('玩家'), input_widget=PlayerComboBox)

            # 是否使用钥匙
            NeedKeyCheckBox = QCheckBox()
            NeedKeyCheckBox.setObjectName("w_need_key")
            NeedKeyCheckBox.setChecked(task["task_args"]["need_key"])
            addElement(line_layout=line_layout, label_widget=QLabel('钥匙'), input_widget=NeedKeyCheckBox)

            add_custom_plan_widget(line_layout=line_layout)

        def double_card(line_layout):

            # Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            # 设定当前值
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)

            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

            # 战斗次数
            TimesLabel = QLabel('次数')
            MaxTimesSpinBox = QSpinBox()
            MaxTimesSpinBox.setObjectName("w_max_times")
            MaxTimesSpinBox.setFixedWidth(70)
            MaxTimesSpinBox.setMinimum(1)
            MaxTimesSpinBox.setMaximum(6)
            # 设定当前值
            MaxTimesSpinBox.setValue(task["task_args"]["max_times"])

            addElement(line_layout=line_layout, label_widget=TimesLabel, input_widget=MaxTimesSpinBox)

        def fresh_game(line_layout):

            # Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

        def clean_items(line_layout):

            # 战斗Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

        def exchange_dark_crystal(line_layout):

            # 战斗Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

        def receive_quest_rewards(line_layout):

            # 战斗Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

            def add_quest(c, e):
                QuestLabel = QLabel(c)
                QuestCheckBox = QCheckBox()
                QuestCheckBox.setObjectName(f"w_{e}")
                QuestCheckBox.setChecked(task["task_args"][e])
                addElement(line_layout=line_layout, label_widget=QuestLabel, input_widget=QuestCheckBox)

            add_quest("普通", "normal")
            add_quest("公会", "guild")
            add_quest("情侣", "spouse")
            add_quest("悬赏", "offer_reward")
            add_quest("大赛", "food_competition")
            add_quest("营地", "camp")
            add_quest("富翁", "monopoly")

        def scan_task_menu(line_layout):

            # 战斗Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

            def add_quest(c, e):
                ScanLabel = QLabel(c)
                ScanCheckBox = QCheckBox()
                ScanCheckBox.setObjectName(f"w_{e}")
                ScanCheckBox.setChecked(task["task_args"][e])
                addElement(line_layout=line_layout, label_widget=ScanLabel, input_widget=ScanCheckBox)

            add_quest("扫描", "scan")
            add_quest("刷关", "battle")

        def sign_in(line_layout):
            # Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

        def watering_fertilizing_harvesting(line_layout):
            # Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

        def use_consumable(line_layout):
            # Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

        def check_for_gaps(line_layout):
            # Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

        def cross_server_prestige(line_layout):
            # Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

        def card_enhancer(line_layout):
            # Player
            PlayerLabel = QLabel('玩家')
            PlayerComboBox = QComboBox()
            PlayerComboBox.setFixedWidth(70)
            PlayerComboBox.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                PlayerComboBox.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = PlayerComboBox.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                PlayerComboBox.setCurrentIndex(index)
            addElement(line_layout=line_layout, label_widget=PlayerLabel, input_widget=PlayerComboBox)

        def guild_task(line_layout):
            add_custom_plan_widget(line_layout=line_layout)

            # 跨服
            CrossServerLabel = QLabel('尝试跨服公会任务')
            CrossServerCheckBox = QCheckBox()
            CrossServerCheckBox.setObjectName("w_cross_server")
            CrossServerCheckBox.setChecked(task["task_args"]["cross_server"])
            addElement(line_layout=line_layout, label_widget=CrossServerLabel, input_widget=CrossServerCheckBox)

        def couple_task(line_layout):
            add_custom_plan_widget(line_layout=line_layout)

        def task_sequence(line_layout):
            # 添加整数输入框
            SequenceIntegerLabel = QLabel('起始序列号')

            SequenceIntegerSpinBox = QSpinBox()
            SequenceIntegerSpinBox.setObjectName("w_sequence_integer")
            SequenceIntegerSpinBox.setFixedWidth(70)
            SequenceIntegerSpinBox.setMinimum(1)
            SequenceIntegerSpinBox.setMaximum(999)
            SequenceIntegerSpinBox.setValue(task["task_args"]["sequence_integer"])
            addElement(line_layout=line_layout, label_widget=SequenceIntegerLabel, input_widget=SequenceIntegerSpinBox)

            # 添加任务序列选择下拉框（使用SearchableComboBox）
            TaskSequenceLabel = QLabel('任务序列')

            TaskSequenceComboBox = SearchableComboBox()
            TaskSequenceComboBox.setObjectName("w_task_sequence_uuid")
            TaskSequenceComboBox.setFixedWidth(200)

            # 获取任务序列列表
            fresh_and_check_all_task_sequence()
            task_sequence_name_list = get_task_sequence_list(with_extension=False)
            task_sequence_uuid_list = list(EXTRA.TASK_SEQUENCE_UUID_TO_PATH.keys())
            task_sequence_uuid_to_name_dict = dict(zip(task_sequence_uuid_list, task_sequence_name_list))

            # 添加选项到下拉框 注意 由于跳过了和本方案相同的任务序列以避免套娃
            # 所以 下拉栏中的list 和 完整list不再等价 从ui保存为json时务必注意
            for f_uuid, f_name in task_sequence_uuid_to_name_dict.items():
                if self.current_task_sequence_meta_data:
                    if self.current_task_sequence_meta_data.get("uuid", None) == f_uuid:
                        continue
                TaskSequenceComboBox.addItem(f_name)

            # 设置当前选中项，根据UUID查找索引
            try:
                TaskSequenceComboBox.setCurrentText(
                    task_sequence_uuid_to_name_dict[task["task_args"]["task_sequence_uuid"]])
            except Exception as e:
                TaskSequenceComboBox.setCurrentIndex(0)

            addElement(line_layout=line_layout, label_widget=TaskSequenceLabel, input_widget=TaskSequenceComboBox)

        match task_type:
            case '战斗':
                battle(line_layout=line_layout)
            case '双暴卡':
                double_card(line_layout=line_layout)
            case '刷新游戏':
                fresh_game(line_layout=line_layout)
            case '清背包':
                clean_items(line_layout=line_layout)
            case '兑换暗晶':
                exchange_dark_crystal(line_layout=line_layout)
            case '领取任务奖励':
                receive_quest_rewards(line_layout=line_layout)
            case '扫描任务列表':
                scan_task_menu(line_layout=line_layout)
            case '签到':
                sign_in(line_layout=line_layout)
            case '浇水施肥摘果':
                watering_fertilizing_harvesting(line_layout=line_layout)
            case '公会任务':
                guild_task(line_layout=line_layout)
            case '情侣任务':
                couple_task(line_layout=line_layout)
            case '使用消耗品':
                use_consumable(line_layout=line_layout)
            case '查漏补缺':
                check_for_gaps(line_layout=line_layout)
            case '跨服刷威望':
                cross_server_prestige(line_layout=line_layout)
            case '天知强卡器':
                card_enhancer(line_layout=line_layout)
            case '美食大赛':
                # 美食大赛任务没有参数，所以不需要添加任何控件
                pass
            case '自建房战斗':
                battle(line_layout=line_layout)
            case '任务序列':
                task_sequence(line_layout=line_layout)

        # 创建一个水平弹簧
        spacer = QSpacerItem(0, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        line_layout.addItem(spacer)

        # 添加完成后，在布局的最后添加一个删除按钮
        delete_button = QPushButton('删除')
        delete_button.setMaximumWidth(50)
        delete_button.setObjectName("delete_button")
        line_layout.addWidget(delete_button)

        line_layout.addWidget(QCVerticalLine())

        return line_widget

    def update_task_id(self):
        """
        增删后 更新任务id
        """
        # 清空所有任务的 ID
        for row in range(self.WidgetTaskSequenceList.count()):
            item = self.WidgetTaskSequenceList.item(row)
            widget = self.WidgetTaskSequenceList.itemWidget(item)

            id_label = widget.findChild(QLabel, 'label_task_id')
            if id_label:
                id_label.setText("")  # 清空 ID 显示

        # 重新分配 ID
        for row in range(self.WidgetTaskSequenceList.count()):
            # 寻找所有控件
            item = self.WidgetTaskSequenceList.item(row)
            widget = self.WidgetTaskSequenceList.itemWidget(item)
            new_id = row + 1

            # ID
            id_label = widget.findChild(QLabel, 'label_task_id')
            id_label.setText(str(new_id))  # 设置新的 ID 显示

    def ui_clear_tasks(self):
        """
        清空所有任务
        """
        # 获取当前的项数
        count = self.WidgetTaskSequenceList.count()

        # 从后向前遍历并移除每一项
        for i in range(count - 1, -1, -1):
            item = self.WidgetTaskSequenceList.takeItem(i)
            widget = self.WidgetTaskSequenceList.itemWidget(item)

            # 删除附加的 widget
            if widget is not None:
                widget.deleteLater()
            del item

    """ .json ↔ list ↔ UI """

    def json_dict_to_ui(self, task_sequence_list):
        """获取json中的数据, 转化为list并写入到ui"""
        # 清空
        self.ui_clear_tasks()

        self.could_not_find_battle_plan_uuid_list = []

        # 保存元数据到实例变量
        if len(task_sequence_list) > 0 and "meta_data" in task_sequence_list[0]:
            self.current_task_sequence_meta_data = task_sequence_list[0]["meta_data"]
            start_index = 1
        else:
            self.current_task_sequence_meta_data = None
            start_index = 0

        # 读取
        for i in range(start_index, len(task_sequence_list)):
            task = task_sequence_list[i]
            # 兼容旧版本任务序列，添加默认的alias和tooltip字段
            if "alias" not in task:
                task["alias"] = ""
            if "tooltip" not in task:
                task["tooltip"] = ""
            # 确保任务有task_id
            if "task_id" not in task:
                task["task_id"] = i
            # 添加一个任务到ui上
            self.add_task(task)

        # 出现了uuid找不到对应战斗方案的情况 弹窗
        if self.could_not_find_battle_plan_uuid_list:
            QMessageBox.critical(
                self,
                "警告!!!",
                f"该<任务序列>中使用的部分战斗方案, 无法根据UUID在您本地的战斗方案中找到对应目标.\n"
                f"已设定为默认值, 请手动添加该<任务序列>需要的战斗方案, 或手动修改\n"
                f"问题UUID: {self.could_not_find_battle_plan_uuid_list}"
            )

    def ui_to_json_dict(self):
        """获取UI上的数据, 生成json"""

        data = []

        # 添加元数据
        if self.current_task_sequence_meta_data:
            data.append({
                "meta_data": self.current_task_sequence_meta_data
            })
        elif len(self.WidgetTaskSequenceList) > 0:
            # 如果没有元数据但需要创建一个新的
            import uuid
            data.append({
                "meta_data": {
                    "uuid": str(uuid.uuid1()),
                    "version": "1.0"
                }
            })

        list_line_widgets = self.WidgetTaskSequenceList.findChildren(QWidget, 'line_widget')

        for LineWidget in list_line_widgets:
            data_line = {}

            # 从控件属性中获取原始任务数据
            original_task_data = LineWidget.property('task_data')

            # 跳过元数据任务
            if original_task_data and 'meta_data' in original_task_data:
                continue

            # 使用原始任务数据中的task_type，而不是从标签文本中获取
            task_type = original_task_data.get('task_type', '') if original_task_data else ''
            data_line['task_type'] = task_type

            label_task_id = LineWidget.findChild(QLabel, 'label_task_id')
            task_id = label_task_id.text()
            data_line['task_id'] = int(task_id)

            # 获取启用状态
            enabled_widget = LineWidget.findChild(QCheckBox, 'w_enabled')
            data_line['enabled'] = enabled_widget.isChecked()

            # 获取别名和提示信息
            alias = original_task_data.get('alias', '') if original_task_data else ''
            tooltip = original_task_data.get('tooltip', '') if original_task_data else ''
            data_line['alias'] = alias
            data_line['tooltip'] = tooltip

            data_line["task_args"] = {}
            task_args = data_line["task_args"]

            match task_type:
                case '战斗':
                    StageIdLineEdit = LineWidget.findChild(QLineEdit, 'w_stage_id')
                    task_args['stage_id'] = StageIdLineEdit.text()

                    MaxTimesSpinBox = LineWidget.findChild(QSpinBox, 'w_max_times')
                    task_args['max_times'] = MaxTimesSpinBox.value()

                    NeedKeyCheckBox = LineWidget.findChild(QCheckBox, 'w_need_key')
                    task_args['need_key'] = NeedKeyCheckBox.isChecked()

                    PlayerComboBox = LineWidget.findChild(QComboBox, 'w_player')
                    text = PlayerComboBox.currentText()
                    return_list = {"1P": [1], "2P": [2], "1P房主": [1, 2], "2P房主": [2, 1]}[text]
                    task_args['player'] = return_list

                    task_args = ui_to_list_get_cus_battle_opt(LineWidget=LineWidget, task_args=task_args)

                    # 固定值 请不要用于 魔塔 / 萌宠神殿 这两类特殊关卡！
                    task_args["quest_card"] = "None"
                    task_args["ban_card_list"] = []
                    task_args["dict_exit"] = {
                        "other_time_player_a": [],
                        "other_time_player_b": [],
                        "last_time_player_a": ["竞技岛"],
                        "last_time_player_b": ["竞技岛"]
                    }

                case "双暴卡":
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)

                    # 最大次数
                    MaxTimesSpinBox = LineWidget.findChild(QSpinBox, 'w_max_times')
                    task_args['max_times'] = MaxTimesSpinBox.value()

                case "清背包":
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)

                case '兑换暗晶':
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)

                case "刷新游戏":
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)

                case "领取任务奖励":
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)
                    for key in ["normal", "guild", "spouse", "offer_reward", "food_competition", "monopoly", "camp"]:
                        task_args = ui_to_list_check_box(LineWidget=LineWidget, task_args=task_args, key=key)

                case "扫描任务列表":
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)
                    for key in ["scan", "battle"]:
                        task_args = ui_to_list_check_box(LineWidget=LineWidget, task_args=task_args, key=key)

                case "签到":
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)

                case "浇水施肥摘果":
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)

                case "公会任务":
                    CrossServerCheckBox = LineWidget.findChild(QCheckBox, 'w_cross_server')
                    task_args['cross_server'] = CrossServerCheckBox.isChecked()

                    task_args = ui_to_list_get_cus_battle_opt(LineWidget=LineWidget, task_args=task_args)

                    # 固定值
                    task_args["quest_card"] = "None"
                    task_args["ban_card_list"] = []
                    task_args["dict_exit"] = {
                        "other_time_player_a": [],
                        "other_time_player_b": [],
                        "last_time_player_a": ["竞技岛"],
                        "last_time_player_b": ["竞技岛"]
                    }

                case "情侣任务":
                    task_args = ui_to_list_get_cus_battle_opt(LineWidget=LineWidget, task_args=task_args)

                    # 固定值
                    task_args["quest_card"] = "None"
                    task_args["ban_card_list"] = []
                    task_args["dict_exit"] = {
                        "other_time_player_a": [],
                        "other_time_player_b": [],
                        "last_time_player_a": ["竞技岛"],
                        "last_time_player_b": ["竞技岛"]
                    }

                case "使用消耗品":
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)

                case "查漏补缺":
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)

                case "跨服刷威望":
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)

                case "天知强卡器":
                    task_args = ui_to_list_player(LineWidget=LineWidget, task_args=task_args)

                case "美食大赛":
                    # 美食大赛任务没有参数
                    pass

                case "自建房战斗":
                    StageIdLineEdit = LineWidget.findChild(QLineEdit, 'w_stage_id')
                    task_args['stage_id'] = StageIdLineEdit.text()

                    MaxTimesSpinBox = LineWidget.findChild(QSpinBox, 'w_max_times')
                    task_args['max_times'] = MaxTimesSpinBox.value()

                    NeedKeyCheckBox = LineWidget.findChild(QCheckBox, 'w_need_key')
                    task_args['need_key'] = NeedKeyCheckBox.isChecked()

                    PlayerComboBox = LineWidget.findChild(QComboBox, 'w_player')
                    text = PlayerComboBox.currentText()
                    return_list = {"1P": [1], "2P": [2], "1P房主": [1, 2], "2P房主": [2, 1]}[text]
                    task_args['player'] = return_list

                    GlobalPlanActiveCheckBox = LineWidget.findChild(QCheckBox, 'w_global_plan_active')
                    task_args['global_plan_active'] = GlobalPlanActiveCheckBox.isChecked()

                    DeckComboBox = LineWidget.findChild(QComboBox, 'w_deck')
                    task_args['deck'] = int(DeckComboBox.currentIndex())

                    # 战斗方案
                    battle_plan_name_list = get_list_battle_plan(with_extension=False)
                    battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

                    # 微调方案
                    tweak_plan_name_list = get_list_tweak_plan(with_extension=False)
                    tweak_plan_uuid_list = list(EXTRA.TWEAK_BATTLE_PLAN_UUID_TO_PATH.keys())

                    Plan1pComboBox = LineWidget.findChild(SearchableComboBox, 'w_battle_plan_1p')
                    text = Plan1pComboBox.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    task_args['battle_plan_1p'] = uuid

                    Plan2pComboBox = LineWidget.findChild(SearchableComboBox, 'w_battle_plan_2p')
                    text = Plan2pComboBox.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    task_args['battle_plan_2p'] = uuid

                    # 微调方案
                    TweakPlanComboBox = LineWidget.findChild(SearchableComboBox, 'w_battle_plan_tweak')
                    if TweakPlanComboBox.count() > 0:  # 确保有选项
                        text = TweakPlanComboBox.currentText()
                        if text in tweak_plan_name_list:
                            index = tweak_plan_name_list.index(text)
                            uuid = tweak_plan_uuid_list[index]
                            task_args['battle_plan_tweak'] = uuid
                        else:
                            task_args.pop('battle_plan_tweak', None)  # 无匹配项时清空
                    if task_args['global_plan_active']:
                        # 移除微调方案UUID
                        task_args.pop('battle_plan_tweak', None)

                    # 固定值 请不要用于 魔塔 / 萌宠神殿 这两类特殊关卡！
                    task_args["quest_card"] = "None"
                    task_args["ban_card_list"] = []
                    task_args["dict_exit"] = {
                        "other_time_player_a": [],
                        "other_time_player_b": [],
                        "last_time_player_a": ["竞技岛"],
                        "last_time_player_b": ["竞技岛"]
                    }

                case "任务序列":
                    # 获取整数输入框的值
                    SequenceIntegerSpinBox = LineWidget.findChild(QSpinBox, 'w_sequence_integer')
                    task_args['sequence_integer'] = SequenceIntegerSpinBox.value()

                    # 获取任务序列下拉框的值（不是uuid 是方案名字）
                    TaskSequenceComboBox = LineWidget.findChild(SearchableComboBox, 'w_task_sequence_uuid')

                    # 获取任务序列列表

                    fresh_and_check_all_task_sequence()
                    task_sequence_list = get_task_sequence_list(with_extension=False)
                    task_sequence_uuid_list = list(EXTRA.TASK_SEQUENCE_UUID_TO_PATH.keys())

                    # 获取当前选中的UUID
                    text = TaskSequenceComboBox.currentText()
                    try:
                        index = task_sequence_list.index(text)
                        uuid = task_sequence_uuid_list[index]

                    except (ValueError, IndexError):
                        # 如果找不到匹配项，保留原有的UUID
                        uuid = original_task_data.get(
                            'task_args', {}).get(
                            'task_sequence_uuid', "00000000-0000-0000-0000-000000000000")

                    task_args['task_sequence_uuid'] = uuid

            data_line["task_args"] = task_args

            data.append(data_line)

        # 根据id排序 输出
        # 只对有task_id的项进行排序，排除元数据项
        data_with_id = [item for item in data if 'task_id' in item]
        data_without_id = [item for item in data if 'task_id' not in item]
        data_with_id = sorted(data_with_id, key=lambda x: x['task_id'])
        # 合并结果，元数据项放在前面
        data = data_without_id + data_with_id
        return data

    def open_task_sequence(self):

        file_name = self.open_json()

        if file_name:
            result = self.load_json(file_path=file_name)
            if result:
                self.father.TaskSequenceButtonSaveJson.setEnabled(True)

    def open_json(self):
        """打开窗口 打开json文件"""

        file_name, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="打开 JSON 文件",
            directory=PATHS["task_sequence"],
            filter="JSON Files (*.json)")

        return file_name

    def load_json(self, file_path):
        """
         读取对应的json文件, 几乎总是要接着 init_battle_plan()
         """
        try:
            with EXTRA.FILE_LOCK:
                with open(file=file_path, mode='r', encoding='utf-8') as file:
                    json_dict = json.load(file)
        except Exception as e:
            message = (
                f"读取<任务序列>失败! \n"
                f"这是由于您使用文本编辑器魔改后, 格式不符合Json规范导致"
            )
            error_dialog_and_log(e=e, message=message, parent=self, title="Json格式错误")
            return False

        try:
            self.json_dict_to_ui(json_dict)
        except Exception as e:
            message = (
                "该<任务序列>不符合协议! 读取失败! 可能原因如下:\n"
                f"1. 您使用文本编辑器魔改后, 格式不符合协议.\n"
                f"2. 该序列的版本过低, 无法兼容解析."
            )
            error_dialog_and_log(e=e, message=message, parent=self, title="Json不符合战斗序列协议")
            return False

        # 储存当前方案路径
        self.file_path = file_path

        # 更新界面上显示的文件名
        current_plan_name = os.path.basename(self.file_path).replace(".json", "")
        CUS_LOGGER.debug(f"[任务序列编辑器] [加载方案] 开始读取:{current_plan_name}")
        self.father.TaskSequenceLabelCurrentEditName.setText(f"{current_plan_name}")

        # 更新界面上显示的UUID
        if json_dict and "meta_data" in json_dict[0]:
            current_uuid = json_dict[0]["meta_data"].get("uuid", "???")
            self.father.TaskSequenceLabelCurrentEditUUID.setText(f"{current_uuid}")

        return True

    def save_json(self):
        """
        保存方法，拥有保存和另存为两种功能，还能创建uuid
        """

        try:
            export_list = self.ui_to_json_dict()
        except Exception as e:
            message = "读请联系开发者!!!"
            error_dialog_and_log(e=e, message=message, parent=self, title="转化<任务序列>ui内容到list失败")
            return

        export_str = f"[任务序列编辑器] 导出结果:\n"
        for data_line in export_list:
            export_str += f"{data_line}\n"
        CUS_LOGGER.info(export_str)

        is_save_as = self.sender() == self.father.TaskSequenceButtonSaveAsJson
        if is_save_as:
            # 保存为
            new_file_path, _ = QFileDialog.getSaveFileName(
                parent=self,
                caption="保存任务序列.json",
                directory=PATHS["task_sequence"],
                filter="JSON Files (*.json)"
            )
        else:
            # 保存
            if hasattr(self, 'file_path') and self.file_path:
                new_file_path = self.file_path
            else:
                # 保存, 提示用户还未选择任何任务序列
                QMessageBox.information(self, "禁止虚空保存！", "请先选择一个任务序列!")
                return

        try:
            # 如果是另存为到新文件，则创建新的UUID
            if not os.path.exists(new_file_path):
                # 为新文件创建UUID
                if export_list and "meta_data" in export_list[0]:
                    export_list[0]["meta_data"]["uuid"] = str(uuid.uuid1())
            else:
                # 如果是覆盖现有文件，则尝试保留原有的UUID
                with EXTRA.FILE_LOCK:
                    with open(file=new_file_path, mode='r', encoding='utf-8') as file:
                        existing_data = json.load(file)
            # 确保该方案拥有UUID
            if existing_data and len(existing_data) > 0 and "meta_data" in existing_data[0]:
                existing_uuid = existing_data[0]["meta_data"].get("uuid", None)
                if existing_uuid:
                    # 使用现有的UUID
                    if export_list and "meta_data" in export_list[0]:
                        export_list[0]["meta_data"]["uuid"] = existing_uuid
                    # 更新当前元数据中的UUID
                    self.current_task_sequence_meta_data["uuid"] = existing_uuid

            with open(new_file_path, 'w', encoding='utf-8') as file:
                json.dump(export_list, file, ensure_ascii=False, indent=4)
                QMessageBox.information(self, "成功!", "<任务序列> 已保存成功~")

            # 更新当前文件路径和显示信息
            self.file_path = new_file_path
            if export_list and "meta_data" in export_list[0]:
                current_uuid = export_list[0]["meta_data"].get("uuid", "未知")
                self.father.TaskSequenceLabelCurrentEditUUID.setText(f"{current_uuid}")
            self.father.TaskSequenceButtonSaveJson.setEnabled(True)

            # 重新加载文件以确保内部数据一致性
            self.load_json(new_file_path)

        except Exception as e:
            message = "读请联系开发者!!!"
            error_dialog_and_log(e=e, message=message, parent=self, title="保存<任务序列>失败")

    def edit_alias(self, label, task):
        """
        编辑任务项别名
        """

        current_alias = task.get('alias', '')
        new_alias, ok = QInputDialog.getText(self, "编辑别名", "请输入别名:", text=current_alias)
        if ok:
            task['alias'] = new_alias
            # 更新显示文本，有别名显示别名，否则显示任务类型
            task_type = task['task_type']
            display_text = new_alias if new_alias else task_type
            label.setText(display_text)

            # 同时更新父控件的属性，确保保存时能获取到最新的数据
            parent_widget = label.parentWidget()
            if parent_widget:
                parent_widget.setProperty('task_data', task)

    def edit_tooltip(self, event, label, task):
        """
        编辑任务项提示信息
        """

        current_tooltip = task.get('tooltip', '')
        new_tooltip, ok = QInputDialog.getText(self, "编辑提示", "请输入提示信息:", text=current_tooltip)
        if ok:
            task['tooltip'] = new_tooltip
            label.setToolTip(new_tooltip if new_tooltip else "双击编辑别名，右键编辑提示信息")

            # 同时更新父控件的属性，确保保存时能获取到最新的数据
            parent_widget = label.parentWidget()
            if parent_widget:
                parent_widget.setProperty('task_data', task)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = QMWEditorOfTaskSequence()
    window.resize(900, 750)
    window.show()
    sys.exit(app.exec())
