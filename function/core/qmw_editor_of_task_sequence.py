import json
import sys

from PyQt6.QtCore import Qt

from function.globals.loadings import loading

loading.update_progress(60, "正在加载FAA任务序列编辑器...")
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QPushButton, QComboBox, QHBoxLayout, QLabel, QLineEdit, \
    QSpinBox, QCheckBox, QWidget, QListWidgetItem, QFileDialog, QMessageBox, QApplication, QListWidget, QSpacerItem, \
    QSizePolicy, QFrame, QAbstractItemView, QInputDialog
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


class QMWEditorOfTaskSequence(QMainWindow):
    def __init__(self, father=None):
        """
        初始化，完成界面布局，绑定信号与槽，初始化变量
        """
        super().__init__()
        self.father = father
        # 主布局
        self.lay_main = QVBoxLayout()

        # 加载按钮
        self.widget_button_load_json = QPushButton('加载任务序列')
        self.lay_main.addWidget(self.widget_button_load_json)
        self.widget_button_load_json.clicked.connect(self.load_json)

        # 列表
        self.widget_task_sequence_list = QCListWidgetDraggable()
        self.widget_task_sequence_list.setDropFunction(drop_function=self.update_task_id)
        self.lay_main.addWidget(self.widget_task_sequence_list)

        # 添加任务按钮
        self.layout_add_task = QHBoxLayout()
        self.lay_main.addLayout(self.layout_add_task)

        self.widget_button_add_task = QPushButton('添加任务')
        self.layout_add_task.addWidget(self.widget_button_add_task)
        self.widget_button_add_task.clicked.connect(self.add_task_by_button)

        self.widget_combo_box_task = QComboBox()
        self.layout_add_task.addWidget(self.widget_combo_box_task)

        # 保存按钮
        self.widget_button_save_json = QPushButton('保存任务序列')
        self.lay_main.addWidget(self.widget_button_save_json)
        self.widget_button_save_json.clicked.connect(self.save_json)

        # 初始化控件
        self.init_combo_box()

        # 显示布局
        self.centralWidget = QWidget()
        self.centralWidget.setLayout(self.lay_main)
        self.setCentralWidget(self.centralWidget)

        # 读取方案时, 如果出现了uuid找不到方案的情况, 弹窗用变量
        self.could_not_find_battle_plan_uuid = False
        self.could_not_load_json_succeed = False

        # 任务序列元数据
        self.current_task_sequence_meta_data = None

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

    def init_combo_box(self):
        """
        初始化任务选择下拉框
        """
        # 创建任务描述字典
        task_descriptions = {
            '战斗':
                '从进入关卡到完成战斗的完整流程\n'
                '支持几乎所有关卡, 具体请参考右上角的关卡代号一览',
            '刷新游戏':
                '刷新游戏\n'
                '绝大部分情况下**请在开头**执行此项\n'
                '部分依赖此模块复位的功能中包含了该操作',
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
            '领取任务奖励':
                '领取各种任务的奖励.\n'
                '被嵌入在部分其他模块中\n'
                '可自行添加避免漏任务',
            '签到':
                '执行每日签到\n'
                '完整流程:\n'
                '* 温馨礼包(需进阶设置-温馨礼包)\n'
                '* 日氪(需进阶设置-日氪)\n'
                '* VIP签到/每日签到/美食活动/塔罗/法老\n'
                '* 会长发任务/营地领钥匙/月卡礼包',
            '浇水施肥摘果':
                '无需解释',
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
            '任务序列':
                '嵌套执行其他任务序列\n'
                '自动去重, 防止套娃',
            '扫描任务列表':
                '扫描当前可执行的任务列表\n'
                '执念全新功能 - 自动清空普通任务的一部分',
            '自建房战斗':
                '用户自行建房开始战斗\n'
                '请勿和上述的所有其他功能混合使用\n'
                '使用此功能前请勿刷新',
        }

        # 添加项目并设置 tooltip
        for index, task_type in enumerate(task_descriptions.keys()):
            self.widget_combo_box_task.addItem(task_type)
            self.widget_combo_box_task.setItemData(index, task_descriptions[task_type], Qt.ItemDataRole.ToolTipRole)

    def add_task_by_button(self):
        """
        点击按钮, 添加一项任务(行)
        """
        task_type = self.widget_combo_box_task.currentText()

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
                    "dark_crystal": False
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
        task["task_id"] = self.widget_task_sequence_list.count() + 1

        # 生成控件行
        try:
            line_widget = self.add_task_line_widget(task)
            # 在控件中存储原始任务数据，以便后续访问
            line_widget.setProperty('task_data', task)
        except Exception as e:
            print(f"Error in create_task_line: {e}")
            # 标记存在读取失败的情况!
            self.could_not_load_json_succeed = True
            return

        # 创建一个 QListWidgetItem，并将 line_widget 设置为其附加的 widget
        line_item = QListWidgetItem()

        # 设置 QListWidgetItem 的高度
        line_item.setSizeHint(line_widget.sizeHint())

        self.widget_task_sequence_list.addItem(line_item)
        self.widget_task_sequence_list.setItemWidget(line_item, line_widget)

        # 绑定删除按钮的两个函数
        delete_button = line_widget.findChild(QPushButton, 'delete_button')
        delete_button.clicked.connect(lambda: self.remove_task_by_line_item(line_item))
        delete_button.clicked.connect(self.update_task_id)

    def remove_task_by_line_item(self, line_item):
        # 获取索引
        index = self.widget_task_sequence_list.row(line_item)
        # 清除对应索引的行
        self.widget_task_sequence_list.takeItem(index)

    def add_task_line_widget(self, task):
        """
        根据任务生成控件，单独管理列表中每一行的布局
        每一行布局分为三个部分：task_id; task type; task info
        """

        # 本行元素 + 布局
        line_widget = QWidget()
        line_widget.setObjectName('line_widget')
        line_layout = QHBoxLayout(line_widget)

        # 启用状态复选框
        w_enabled = QCheckBox()
        w_enabled.setObjectName('w_enabled')
        w_enabled.setChecked(task.get("enabled", True))  # 默认为启用
        w_enabled.setToolTip("启用/禁用此任务")
        line_layout.addWidget(w_enabled)

        # task_id + type
        layout = QHBoxLayout()
        line_layout.addLayout(layout)

        w_label = QLabel(str(task["task_id"]))
        w_label.setObjectName('label_task_id')
        w_label.setFixedWidth(20)
        layout.addWidget(w_label)

        task_type = task['task_type']
        # 显示别名，如果没有别名则显示任务类型
        display_text = task.get('alias', '') if task.get('alias', '') else task_type
        w_label = QLabel(display_text)
        w_label.setObjectName("label_task_type")
        w_label.setFixedWidth(80)
        # 添加双击编辑别名功能
        w_label.setCursor(Qt.CursorShape.PointingHandCursor)
        tooltip_text = task.get("tooltip", "")
        if not tooltip_text:
            tooltip_text = "双击编辑别名，右键编辑提示信息"
        w_label.setToolTip(tooltip_text)
        w_label.mouseDoubleClickEvent = lambda event, label=w_label, t=task: self.edit_alias(label, t)
        w_label.contextMenuEvent = lambda event, label=w_label, t=task: self.edit_tooltip(event, label, t)
        layout.addWidget(w_label)

        line_layout.addWidget(QCVerticalLine())

        # line_layout.addWidget(QLabel("   "))
        def add_element(line_layout, w_input, w_label=None, end_line=True):

            layout = QHBoxLayout()
            line_layout.addLayout(layout)

            # 添加标签控件(如果有)
            if w_label is not None:
                layout.addWidget(w_label)

            # 添加输入控件
            layout.addWidget(w_input)

            if end_line:
                # line_layout.addWidget(QCVerticalLine())
                line_layout.addWidget(QLabel(" "))

        def battle(line_layout):

            # 所选关卡
            w_label = QLabel('关卡')
            w_input = QLineEdit()
            w_input.setObjectName("w_stage_id")
            w_input.setFixedWidth(70)
            w_input.setText(task["task_args"]["stage_id"])
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            # 战斗次数
            w_label = QLabel('次数')
            w_input = QSpinBox()
            w_input.setObjectName("w_max_times")
            w_input.setFixedWidth(70)
            w_input.setMinimum(1)
            w_input.setMaximum(999)
            w_input.setValue(task["task_args"]["max_times"])
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            # 是否使用钥匙
            w_label = QLabel('钥匙')
            w_input = QCheckBox()
            w_input.setObjectName("w_need_key")
            w_input.setChecked(task["task_args"]["need_key"])
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            # 战斗Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setObjectName("w_player")
            for player in ['1P', '2P', '1P房主', '2P房主']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1P房主', (2, 1): '2P房主'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            # 全局关卡方案
            w_label = QLabel('全局')
            w_gba_input = QCheckBox()
            w_gba_input.setObjectName("w_global_plan_active")
            w_gba_input.setChecked(task["task_args"]["global_plan_active"])
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_gba_input)

            # 战斗卡组 创建控件
            w_label = QLabel('卡组')
            w_d_input = QComboBox()
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_d_input)

            # 战斗方案 1P 创建控件
            w_label = QLabel('1P方案')
            w_1p_input = SearchableComboBox()
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_1p_input)

            # 战斗方案 2P 创建控件
            w_label = QLabel('2P方案')
            w_2p_input = SearchableComboBox()
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_2p_input)

            # 微调方案 创建控件
            w_label = QLabel('微调方案')
            w_tweak_input = SearchableComboBox()
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_tweak_input)

            def toggle_widgets(state, widgets):
                for widget in widgets:
                    widget.setEnabled(state == 0)

            w_gba_input.stateChanged.connect(
                lambda state: toggle_widgets(state, [w_d_input, w_1p_input, w_2p_input, w_tweak_input]))

            # 初始化一次
            toggle_widgets(w_gba_input.checkState().value, [w_d_input, w_1p_input, w_2p_input, w_tweak_input])

            # 战斗卡组 修改数值
            w_d_input.setObjectName("w_deck")
            for index in ['自动', '1', '2', '3', '4', '5', '6']:
                w_d_input.addItem(index)
            w_d_input.setCurrentIndex(task["task_args"]["deck"])

            # 刷新和创建战斗方案的 uuid list 以方便查找对应值
            fresh_and_check_all_battle_plan()
            battle_plan_name_list = get_list_battle_plan(with_extension=False)
            battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

            # 微调方案文件夹路径
            fresh_and_check_all_tweak_plan()
            tweak_plan_name_list = get_list_tweak_plan(with_extension=False)
            tweak_plan_uuid_list = list(EXTRA.TWEAK_BATTLE_PLAN_UUID_TO_PATH.keys())

            # 战斗方案 1P 修改数值
            w_1p_input.setObjectName("w_battle_plan_1p")
            w_1p_input.setMaximumWidth(225)
            for index in battle_plan_name_list:
                w_1p_input.addItem(index)
            try:
                index = battle_plan_uuid_list.index(task["task_args"]["battle_plan_1p"])
            except ValueError:
                self.could_not_find_battle_plan_uuid = True
                index = 0
            w_1p_input.setCurrentIndex(index)

            # 战斗方案 2P 修改数值
            w_2p_input.setObjectName("w_battle_plan_2p")
            w_2p_input.setMaximumWidth(225)
            for index in battle_plan_name_list:
                w_2p_input.addItem(index)
            try:
                index = battle_plan_uuid_list.index(task["task_args"]["battle_plan_2p"])
            except ValueError:
                self.could_not_find_battle_plan_uuid = True
                index = 1
            w_2p_input.setCurrentIndex(index)

            # 微调方案 修改数值
            w_tweak_input.setObjectName("w_battle_plan_tweak")
            w_tweak_input.setMaximumWidth(225)
            for index in tweak_plan_name_list:
                w_tweak_input.addItem(index)
            try:
                index = tweak_plan_uuid_list.index(task["task_args"].get("battle_plan_tweak", ""))
            except ValueError:
                index = -1  # 未找到匹配项
            w_tweak_input.setCurrentIndex(index if index >= 0 else 0)

        def double_card(line_layout):

            # Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setFixedWidth(70)
            w_input.setObjectName("w_player")
            # 设定当前值
            for player in ['1P', '2P', '1+2P']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)

            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            # 战斗次数
            w_label = QLabel('次数')
            w_input = QSpinBox()
            w_input.setObjectName("w_max_times")
            w_input.setFixedWidth(70)
            w_input.setMinimum(1)
            w_input.setMaximum(6)
            # 设定当前值
            w_input.setValue(task["task_args"]["max_times"])

            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

        def fresh_game(line_layout):

            # Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setFixedWidth(70)
            w_input.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

        def clean_items(line_layout):

            # 战斗Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setFixedWidth(70)
            w_input.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

        def receive_quest_rewards(line_layout):

            # 战斗Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setFixedWidth(70)
            w_input.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            def add_quest(c, e):
                w_label = QLabel(c)
                w_input = QCheckBox()
                w_input.setObjectName(f"w_{e}")
                w_input.setChecked(task["task_args"][e])
                add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            add_quest("普通", "normal")
            add_quest("公会", "guild")
            add_quest("情侣", "spouse")
            add_quest("悬赏", "offer_reward")
            add_quest("大赛", "food_competition")
            add_quest("营地", "camp")
            add_quest("富翁", "monopoly")

        def scan_task_menu(line_layout):

            # 战斗Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setFixedWidth(70)
            w_input.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            def add_quest(c, e):
                w_label = QLabel(c)
                w_input = QCheckBox()
                w_input.setObjectName(f"w_{e}")
                w_input.setChecked(task["task_args"][e])
                add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            add_quest("扫描", "scan")
            add_quest("刷关", "battle")

        def sign_in(line_layout):
            # Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setFixedWidth(70)
            w_input.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

        def watering_fertilizing_harvesting(line_layout):
            # Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setFixedWidth(70)
            w_input.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

        def use_consumable(line_layout):
            # Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setFixedWidth(70)
            w_input.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

        def check_for_gaps(line_layout):
            # Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setFixedWidth(70)
            w_input.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

        def cross_server_prestige(line_layout):
            # Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setFixedWidth(70)
            w_input.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

        def tianzhi_card_enhancer(line_layout):
            # Player
            w_label = QLabel('玩家')
            w_input = QComboBox()
            w_input.setFixedWidth(70)
            w_input.setObjectName("w_player")
            for player in ['1P', '2P', '1+2P']:
                w_input.addItem(player)
            player_list_to_str_dict = {(1,): "1P", (2,): '2P', (1, 2): '1+2P', (2, 1): '1+2P'}
            # 查找并设置当前选中的索引
            index = w_input.findText(player_list_to_str_dict[tuple(task["task_args"]["player"])])
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

        def guild_task(line_layout):
            # 跨服
            w_label = QLabel('跨服')
            w_input = QCheckBox()
            w_input.setObjectName("w_cross_server")
            w_input.setChecked(task["task_args"]["cross_server"])
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            # 全局关卡方案
            w_label = QLabel('全局')
            w_gba_input = QCheckBox()
            w_gba_input.setObjectName("w_global_plan_active")
            w_gba_input.setChecked(task["task_args"]["global_plan_active"])
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_gba_input)

            # 战斗卡组 创建控件
            w_label = QLabel('卡组')
            w_d_input = QComboBox()
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_d_input)

            # 战斗方案 1P 创建控件
            w_label = QLabel('1P方案')
            w_1p_input = SearchableComboBox()
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_1p_input)

            # 战斗方案 2P 创建控件
            w_label = QLabel('2P方案')
            w_2p_input = SearchableComboBox()
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_2p_input)

            def toggle_widgets(state, widgets):
                for widget in widgets:
                    widget.setEnabled(state == 0)

            w_gba_input.stateChanged.connect(
                lambda state: toggle_widgets(state, [w_d_input, w_1p_input, w_2p_input]))

            # 初始化一次
            toggle_widgets(w_gba_input.checkState().value, [w_d_input, w_1p_input, w_2p_input])

            # 战斗卡组 修改数值
            w_d_input.setObjectName("w_deck")
            for index in ['自动', '1', '2', '3', '4', '5', '6']:
                w_d_input.addItem(index)
            w_d_input.setCurrentIndex(task["task_args"]["deck"])

            # 刷新和创建战斗方案的 uuid list 以方便查找对应值
            fresh_and_check_all_battle_plan()
            battle_plan_name_list = get_list_battle_plan(with_extension=False)
            battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

            # 战斗方案 1P 修改数值
            w_1p_input.setObjectName("w_battle_plan_1p")
            w_1p_input.setMaximumWidth(225)
            for index in battle_plan_name_list:
                w_1p_input.addItem(index)
            try:
                index = battle_plan_uuid_list.index(task["task_args"]["battle_plan_1p"])
            except ValueError:
                self.could_not_find_battle_plan_uuid = True
                index = 0
            w_1p_input.setCurrentIndex(index)

            # 战斗方案 2P 修改数值
            w_2p_input.setObjectName("w_battle_plan_2p")
            w_2p_input.setMaximumWidth(225)
            for index in battle_plan_name_list:
                w_2p_input.addItem(index)
            try:
                index = battle_plan_uuid_list.index(task["task_args"]["battle_plan_2p"])
            except ValueError:
                self.could_not_find_battle_plan_uuid = True
                index = 1
            w_2p_input.setCurrentIndex(index)

        def couple_task(line_layout):
            # 全局关卡方案
            w_label = QLabel('全局')
            w_gba_input = QCheckBox()
            w_gba_input.setObjectName("w_global_plan_active")
            w_gba_input.setChecked(task["task_args"]["global_plan_active"])
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_gba_input)

            # 战斗卡组 创建控件
            w_label = QLabel('卡组')
            w_d_input = QComboBox()
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_d_input)

            # 战斗方案 1P 创建控件
            w_label = QLabel('1P方案')
            w_1p_input = SearchableComboBox()
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_1p_input)

            # 战斗方案 2P 创建控件
            w_label = QLabel('2P方案')
            w_2p_input = SearchableComboBox()
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_2p_input)

            def toggle_widgets(state, widgets):
                for widget in widgets:
                    widget.setEnabled(state == 0)

            w_gba_input.stateChanged.connect(
                lambda state: toggle_widgets(state, [w_d_input, w_1p_input, w_2p_input]))

            # 初始化一次
            toggle_widgets(w_gba_input.checkState().value, [w_d_input, w_1p_input, w_2p_input])

            # 战斗卡组 修改数值
            w_d_input.setObjectName("w_deck")
            for index in ['自动', '1', '2', '3', '4', '5', '6']:
                w_d_input.addItem(index)
            w_d_input.setCurrentIndex(task["task_args"]["deck"])

            # 刷新和创建战斗方案的 uuid list 以方便查找对应值
            fresh_and_check_all_battle_plan()
            battle_plan_name_list = get_list_battle_plan(with_extension=False)
            battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

            # 战斗方案 1P 修改数值
            w_1p_input.setObjectName("w_battle_plan_1p")
            w_1p_input.setMaximumWidth(225)
            for index in battle_plan_name_list:
                w_1p_input.addItem(index)
            try:
                index = battle_plan_uuid_list.index(task["task_args"]["battle_plan_1p"])
            except ValueError:
                self.could_not_find_battle_plan_uuid = True
                index = 0
            w_1p_input.setCurrentIndex(index)

            # 战斗方案 2P 修改数值
            w_2p_input.setObjectName("w_battle_plan_2p")
            w_2p_input.setMaximumWidth(225)
            for index in battle_plan_name_list:
                w_2p_input.addItem(index)
            try:
                index = battle_plan_uuid_list.index(task["task_args"]["battle_plan_2p"])
            except ValueError:
                self.could_not_find_battle_plan_uuid = True
                index = 1
            w_2p_input.setCurrentIndex(index)

        def task_sequence(line_layout):
            # 添加整数输入框
            w_label = QLabel('起始序列号')

            w_input = QSpinBox()
            w_input.setObjectName("w_sequence_integer")
            w_input.setFixedWidth(70)
            w_input.setMinimum(1)
            w_input.setMaximum(999)
            w_input.setValue(task["task_args"]["sequence_integer"])
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            # 添加任务序列选择下拉框（使用SearchableComboBox）
            w_label = QLabel('任务序列')

            w_input = SearchableComboBox()
            w_input.setObjectName("w_task_sequence_uuid")
            w_input.setFixedWidth(200)

            # 获取任务序列列表
            fresh_and_check_all_task_sequence()
            task_sequence_list = get_task_sequence_list(with_extension=False)
            task_sequence_uuid_to_path_list = list(EXTRA.TASK_SEQUENCE_UUID_TO_PATH.keys())

            # 添加选项到下拉框 注意 由于跳过了和本方案相同的任务序列以避免套娃
            # 所以 下拉栏中的list 和 完整list不再等价 从ui保存为json时务必注意
            for index, sequence_name in enumerate(task_sequence_list):
                if task_sequence_uuid_to_path_list.index(self.current_task_sequence_meta_data['uuid']) == index:
                    continue
                w_input.addItem(sequence_name)

            # 设置当前选中项，根据UUID查找索引
            try:
                current_uuid = task["task_args"]["task_sequence_uuid"]
                current_index = task_sequence_uuid_to_path_list.index(current_uuid)
            except (ValueError, KeyError):
                current_index = 0
            if current_index < w_input.count():
                w_input.setCurrentIndex(current_index)
            else:
                w_input.setCurrentIndex(0)

            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

        match task_type:
            case '战斗':
                battle(line_layout=line_layout)
            case '双暴卡':
                double_card(line_layout=line_layout)
            case '刷新游戏':
                fresh_game(line_layout=line_layout)
            case '清背包':
                clean_items(line_layout=line_layout)
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
                tianzhi_card_enhancer(line_layout=line_layout)
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
        for row in range(self.widget_task_sequence_list.count()):
            item = self.widget_task_sequence_list.item(row)
            widget = self.widget_task_sequence_list.itemWidget(item)

            id_label = widget.findChild(QLabel, 'label_task_id')
            if id_label:
                id_label.setText("")  # 清空 ID 显示

        # 重新分配 ID
        for row in range(self.widget_task_sequence_list.count()):
            # 寻找所有控件
            item = self.widget_task_sequence_list.item(row)
            widget = self.widget_task_sequence_list.itemWidget(item)
            new_id = row + 1

            # ID
            id_label = widget.findChild(QLabel, 'label_task_id')
            id_label.setText(str(new_id))  # 设置新的 ID 显示

    def ui_clear_tasks(self):
        """
        清空所有任务
        """
        # 获取当前的项数
        count = self.widget_task_sequence_list.count()

        # 从后向前遍历并移除每一项
        for i in range(count - 1, -1, -1):
            item = self.widget_task_sequence_list.takeItem(i)
            widget = self.widget_task_sequence_list.itemWidget(item)

            # 删除附加的 widget
            if widget is not None:
                widget.deleteLater()
            del item

    """ .json ↔ list ↔ UI """

    def list_to_ui(self, task_sequence_list):
        """获取json中的数据, 转化为list并写入到ui"""
        # 清空
        self.ui_clear_tasks()

        self.could_not_find_battle_plan_uuid = False
        self.could_not_load_json_succeed = False

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
            # 出现读取失败, 中止
            if self.could_not_load_json_succeed:
                break

        # 出现了读取失败, 意味着格式不符合协议...
        if self.could_not_load_json_succeed:
            QMessageBox.critical(
                self,
                "警告!!!",
                f"该<任务序列>不符合协议! 读取失败! 可能原因如下:\n"
                f"1. 您使用文本编辑器魔改后, 格式不符合协议.\n"
                f"2. 该序列的版本过低, 无法兼容解析.\n"
            )
            return

        # 出现了uuid找不到对应战斗方案的情况 弹窗
        if self.could_not_find_battle_plan_uuid:
            QMessageBox.critical(
                self,
                "警告!!!",
                f"该<任务序列>的部分战斗方案uuid, 无法在您本地的战斗方案中找到对应目标.\n"
                f"已设定为默认值, 请手动添加该<任务序列>需要的战斗方案, 或手动修改")

    def ui_to_list(self):
        """获取UI上的数据, 生成list"""

        def player(w_line, args):
            widget_input = w_line.findChild(QComboBox, 'w_player')
            text = widget_input.currentText()
            args['player'] = {"1P": [1], "2P": [2], "1+2P": [1, 2]}[text]
            return args

        def check_box(w_line, args, key):
            widget = w_line.findChild(QCheckBox, f'w_{key}')
            args[key] = widget.isChecked()
            return args

        data = []

        # 添加元数据
        if self.current_task_sequence_meta_data:
            data.append({
                "meta_data": self.current_task_sequence_meta_data
            })
        elif len(self.widget_task_sequence_list) > 0:
            # 如果没有元数据但需要创建一个新的
            import uuid
            data.append({
                "meta_data": {
                    "uuid": str(uuid.uuid1()),
                    "version": "1.0"
                }
            })

        list_line_widgets = self.widget_task_sequence_list.findChildren(QWidget, 'line_widget')

        for w_line in list_line_widgets:
            data_line = {}

            # 从控件属性中获取原始任务数据
            original_task_data = w_line.property('task_data')

            # 跳过元数据任务
            if original_task_data and 'meta_data' in original_task_data:
                continue

            # 使用原始任务数据中的task_type，而不是从标签文本中获取
            task_type = original_task_data.get('task_type', '') if original_task_data else ''
            data_line['task_type'] = task_type

            label_task_id = w_line.findChild(QLabel, 'label_task_id')
            task_id = label_task_id.text()
            data_line['task_id'] = int(task_id)

            # 获取启用状态
            enabled_widget = w_line.findChild(QCheckBox, 'w_enabled')
            data_line['enabled'] = enabled_widget.isChecked()

            # 获取别名和提示信息
            alias = original_task_data.get('alias', '') if original_task_data else ''
            tooltip = original_task_data.get('tooltip', '') if original_task_data else ''
            data_line['alias'] = alias
            data_line['tooltip'] = tooltip

            data_line["task_args"] = {}
            task_args = data_line["task_args"]

            match task_type:
                case "战斗":
                    widget_input = w_line.findChild(QLineEdit, 'w_stage_id')
                    task_args['stage_id'] = widget_input.text()

                    widget_input = w_line.findChild(QSpinBox, 'w_max_times')
                    task_args['max_times'] = widget_input.value()

                    widget_input = w_line.findChild(QCheckBox, 'w_need_key')
                    task_args['need_key'] = widget_input.isChecked()

                    widget_input = w_line.findChild(QComboBox, 'w_player')
                    text = widget_input.currentText()
                    return_list = {"1P": [1], "2P": [2], "1P房主": [1, 2], "2P房主": [2, 1]}[text]
                    task_args['player'] = return_list

                    widget_input = w_line.findChild(QCheckBox, 'w_global_plan_active')
                    task_args['global_plan_active'] = widget_input.isChecked()

                    widget_input = w_line.findChild(QComboBox, 'w_deck')
                    task_args['deck'] = int(widget_input.currentIndex())

                    # 战斗方案
                    battle_plan_name_list = get_list_battle_plan(with_extension=False)
                    battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

                    # 微调方案
                    tweak_plan_name_list = get_list_tweak_plan(with_extension=False)
                    tweak_plan_uuid_list = list(EXTRA.TWEAK_BATTLE_PLAN_UUID_TO_PATH.keys())

                    widget_input = w_line.findChild(SearchableComboBox, 'w_battle_plan_1p')
                    text = widget_input.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    task_args['battle_plan_1p'] = uuid

                    widget_input = w_line.findChild(SearchableComboBox, 'w_battle_plan_2p')
                    text = widget_input.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    task_args['battle_plan_2p'] = uuid

                    # 微调方案
                    widget_input = w_line.findChild(SearchableComboBox, 'w_battle_plan_tweak')
                    if widget_input.count() > 0:  # 确保有选项
                        text = widget_input.currentText()
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
                case "双暴卡":
                    task_args = player(w_line=w_line, args=task_args)

                    # 最大次数
                    widget = w_line.findChild(QSpinBox, 'w_max_times')
                    task_args['max_times'] = widget.value()

                case "清背包":
                    task_args = player(w_line=w_line, args=task_args)

                case "刷新游戏":
                    task_args = player(w_line=w_line, args=task_args)

                case "领取任务奖励":
                    task_args = player(w_line=w_line, args=task_args)
                    for key in ["normal", "guild", "spouse", "offer_reward", "food_competition", "monopoly", "camp"]:
                        task_args = check_box(w_line=w_line, args=task_args, key=key)

                case "扫描任务列表":
                    task_args = player(w_line=w_line, args=task_args)
                    for key in ["scan", "battle"]:
                        task_args = check_box(w_line=w_line, args=task_args, key=key)

                case "签到":
                    task_args = player(w_line=w_line, args=task_args)

                case "浇水施肥摘果":
                    task_args = player(w_line=w_line, args=task_args)

                case "公会任务":
                    widget_input = w_line.findChild(QCheckBox, 'w_cross_server')
                    task_args['cross_server'] = widget_input.isChecked()

                    widget_input = w_line.findChild(QCheckBox, 'w_global_plan_active')
                    task_args['global_plan_active'] = widget_input.isChecked()

                    widget_input = w_line.findChild(QComboBox, 'w_deck')
                    task_args['deck'] = int(widget_input.currentIndex())

                    # 战斗方案
                    battle_plan_name_list = get_list_battle_plan(with_extension=False)
                    battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

                    widget_input = w_line.findChild(SearchableComboBox, 'w_battle_plan_1p')
                    text = widget_input.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    task_args['battle_plan_1p'] = uuid

                    widget_input = w_line.findChild(SearchableComboBox, 'w_battle_plan_2p')
                    text = widget_input.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    task_args['battle_plan_2p'] = uuid

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
                    widget_input = w_line.findChild(QCheckBox, 'w_global_plan_active')
                    task_args['global_plan_active'] = widget_input.isChecked()

                    widget_input = w_line.findChild(QComboBox, 'w_deck')
                    task_args['deck'] = int(widget_input.currentIndex())

                    # 战斗方案
                    battle_plan_name_list = get_list_battle_plan(with_extension=False)
                    battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

                    widget_input = w_line.findChild(SearchableComboBox, 'w_battle_plan_1p')
                    text = widget_input.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    task_args['battle_plan_1p'] = uuid

                    widget_input = w_line.findChild(SearchableComboBox, 'w_battle_plan_2p')
                    text = widget_input.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    task_args['battle_plan_2p'] = uuid

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
                    task_args = player(w_line=w_line, args=task_args)

                case "查漏补缺":
                    task_args = player(w_line=w_line, args=task_args)

                case "跨服刷威望":
                    task_args = player(w_line=w_line, args=task_args)

                case "天知强卡器":
                    task_args = player(w_line=w_line, args=task_args)

                case "美食大赛":
                    # 美食大赛任务没有参数
                    pass

                case "自建房战斗":
                    widget_input = w_line.findChild(QLineEdit, 'w_stage_id')
                    task_args['stage_id'] = widget_input.text()

                    widget_input = w_line.findChild(QSpinBox, 'w_max_times')
                    task_args['max_times'] = widget_input.value()

                    widget_input = w_line.findChild(QCheckBox, 'w_need_key')
                    task_args['need_key'] = widget_input.isChecked()

                    widget_input = w_line.findChild(QComboBox, 'w_player')
                    text = widget_input.currentText()
                    return_list = {"1P": [1], "2P": [2], "1P房主": [1, 2], "2P房主": [2, 1]}[text]
                    task_args['player'] = return_list

                    widget_input = w_line.findChild(QCheckBox, 'w_global_plan_active')
                    task_args['global_plan_active'] = widget_input.isChecked()

                    widget_input = w_line.findChild(QComboBox, 'w_deck')
                    task_args['deck'] = int(widget_input.currentIndex())

                    # 战斗方案
                    battle_plan_name_list = get_list_battle_plan(with_extension=False)
                    battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

                    # 微调方案
                    tweak_plan_name_list = get_list_tweak_plan(with_extension=False)
                    tweak_plan_uuid_list = list(EXTRA.TWEAK_BATTLE_PLAN_UUID_TO_PATH.keys())

                    widget_input = w_line.findChild(SearchableComboBox, 'w_battle_plan_1p')
                    text = widget_input.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    task_args['battle_plan_1p'] = uuid

                    widget_input = w_line.findChild(SearchableComboBox, 'w_battle_plan_2p')
                    text = widget_input.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    task_args['battle_plan_2p'] = uuid

                    # 微调方案
                    widget_input = w_line.findChild(SearchableComboBox, 'w_battle_plan_tweak')
                    if widget_input.count() > 0:  # 确保有选项
                        text = widget_input.currentText()
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
                    widget_input = w_line.findChild(QSpinBox, 'w_sequence_integer')
                    task_args['sequence_integer'] = widget_input.value()

                    # 获取任务序列下拉框的值（不是uuid 是方案名字）
                    widget_input = w_line.findChild(SearchableComboBox, 'w_task_sequence_uuid')

                    # 获取任务序列列表

                    fresh_and_check_all_task_sequence()
                    task_sequence_list = get_task_sequence_list(with_extension=False)
                    task_sequence_uuid_list = list(EXTRA.TASK_SEQUENCE_UUID_TO_PATH.keys())

                    # 获取当前选中的UUID
                    text = widget_input.currentText()
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

    def load_json(self):
        """
        Load a JSON file and parse it into the task sequence list
        """

        file_name, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="加载<任务序列>.json",
            directory=PATHS["task_sequence"],
            filter="JSON Files (*.json)")

        if file_name:
            try:
                self.father.CurrentPlan_Label_Change.setText(file_name)
            except Exception:
                pass
            try:
                with open(file_name, 'r', encoding='utf-8') as file:
                    self.list_to_ui(json.load(file))
            except Exception as e:
                # 报错弹窗
                QMessageBox.critical(
                    self,
                    "Json格式错误!",
                    f"读取<任务序列>失败! \n"
                    f"这是由于您使用文本编辑器魔改后, 格式不符合Json规范导致\n"
                    f"错误信息: {str(e)}")

    def save_json(self):
        """
        Save the task sequence list as a JSON file.
        """

        try:
            export_list = self.ui_to_list()
            CUS_LOGGER.info(f"[任务序列编辑器] 导出结果:{export_list}", )

        except Exception as e:
            # 获取完整的调用栈信息
            import traceback
            error_traceback = traceback.format_exc()
            # 报错弹窗
            QMessageBox.critical(
                self,
                "错误!",
                f"转化ui内容到list失败\n\n"
                f"完整错误调用栈:\n"
                f"{error_traceback}\n"
                f"请联系开发者!!!")
            print(error_traceback)
            return

        file_name, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="保存任务序列.json",
            directory=PATHS["task_sequence"],
            filter="JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as file:
                    json.dump(export_list, file, ensure_ascii=False, indent=4)
                    QMessageBox.information(
                        self,
                        "成功!",
                        "<任务序列> 已保存成功~")
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "错误!",
                    f"保存<任务序列>失败\n请联系开发者!!!\n错误信息: {str(e)}")

    def edit_alias(self, label, task):
        """编辑任务项别名"""
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
        """编辑任务项提示信息"""
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
    window.show()
    sys.exit(app.exec())
