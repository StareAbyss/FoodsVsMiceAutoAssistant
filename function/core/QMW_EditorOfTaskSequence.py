import json
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QPushButton, QComboBox, QHBoxLayout, QLabel, QLineEdit, \
    QSpinBox, QCheckBox, QWidget, QListWidgetItem, QFileDialog, QMessageBox, QApplication, QListWidget, QSpacerItem, \
    QSizePolicy, QFrame, QAbstractItemView

from function.globals import g_extra
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.scattered.check_uuid_in_battle_plan import fresh_and_check_battle_plan_uuid
from function.scattered.get_list_battle_plan import get_list_battle_plan


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
    def __init__(self):
        """
        初始化，完成界面布局，绑定信号与槽，初始化变量
        """
        super().__init__()
        # 大小
        self.setMaximumSize(1280, 5000)
        self.setMinimumSize(1280, 600)

        # 序列 主要元素
        self.TaskSequenceList = QCListWidgetDraggable()
        self.TaskSequenceList.setDropFunction(drop_function=self.update_task_id)

        # 布局
        self.LayMain = QVBoxLayout()

        # 加载按钮
        self.ButtonLoadJson = QPushButton('加载任务序列')
        self.LayMain.addWidget(self.ButtonLoadJson)
        self.ButtonLoadJson.clicked.connect(self.load_json)

        # 列表
        self.LayMain.addWidget(self.TaskSequenceList)

        # 添加任务按钮
        self.ButtonAddTask = QPushButton('添加任务')
        self.ComboBoxTask = QComboBox()
        self.AddTaskLayout = QHBoxLayout()
        self.AddTaskLayout.addWidget(self.ButtonAddTask)
        self.AddTaskLayout.addWidget(self.ComboBoxTask)
        self.LayMain.addLayout(self.AddTaskLayout)
        self.ButtonAddTask.clicked.connect(self.add_task_by_button)

        # 保存按钮
        self.ButtonSaveJson = QPushButton('保存任务序列')
        self.LayMain.addWidget(self.ButtonSaveJson)
        self.ButtonSaveJson.clicked.connect(self.save_json)

        # 初始化控件
        self.init_combo_box()

        # 显示布局
        self.centralWidget = QWidget()
        self.centralWidget.setLayout(self.LayMain)
        self.setCentralWidget(self.centralWidget)

        # 读取方案时, 如果出现了uuid找不到方案的情况, 弹窗用变量
        self.could_not_find_battle_plan_uuid = False
        self.could_not_load_json_succeed = False

        # 外观
        self.UICss()

    def UICss(self):
        """
        设置界面样式
        """
        # 设置窗口标题
        self.setWindowTitle('事项序列编辑器')
        # 设置窗口图标
        self.setWindowIcon(QIcon(PATHS["logo"] + "\\圆角-FetTuo-192x.png"))

    def set_my_font(self, my_font):
        """用于继承字体, 而不需要多次读取"""
        self.setFont(my_font)

    def init_combo_box(self):
        """
        初始化任务选择下拉框
        """
        self.ComboBoxTask.addItem('战斗')
        self.ComboBoxTask.addItem('刷新游戏')
        self.ComboBoxTask.addItem('双暴卡')
        self.ComboBoxTask.addItem('清背包')
        self.ComboBoxTask.addItem('领取任务奖励')

        # 待实现
        # self.ComboBoxTask.addItem('使用绑定消耗品')
        # self.ComboBoxTask.addItem('签到')
        # self.ComboBoxTask.addItem('浇水施肥摘果')
        # self.ComboBoxTask.addItem('扫描公会贡献')
        # self.ComboBoxTask.addItem('公会任务')
        # self.ComboBoxTask.addItem('情侣任务')

    def add_task_by_button(self):
        """
        点击按钮, 添加一项任务(行)
        """
        task_type = self.ComboBoxTask.currentText()

        # 默认值
        task = {
            "task_type": task_type,
            "task_id": 0,
            "task_args": dict()
        }
        match task_type:
            case '战斗':
                task["task_args"] = {
                    "stage_id": "NO-1-7",
                    "deck": 1,
                    "max_times": 1,
                    "battle_plan_1p": "00000000-0000-0000-0000-000000000000",
                    "battle_plan_2p": "00000000-0000-0000-0000-000000000001",
                    "need_key": True,
                    "player": [2, 1],
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
            case '扫描公会贡献':
                task["task_args"] = {
                    "player": 1,  # or 2
                }
            case '使用绑定消耗品':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }
            case '浇水施肥摘果':
                task["task_args"] = {
                    "player": [1, 2],  # or [1] [2]
                }

        self.add_task(task=task)

    def add_task(self, task):
        """
        添加任务
        :param task:
        :return:
        """

        # 重新生成id
        task["task_id"] = self.TaskSequenceList.count() + 1

        # 生成控件行
        try:
            line_widget = self.add_task_line_widget(task)
        except Exception as e:
            print(f"Error in create_task_line: {e}")
            # 标记存在读取失败的情况!
            self.could_not_load_json_succeed = True
            return

        # 创建一个 QListWidgetItem，并将 line_widget 设置为其附加的 widget
        item = QListWidgetItem()

        # 设置 QListWidgetItem 的高度
        item.setSizeHint(line_widget.sizeHint())

        self.TaskSequenceList.addItem(item)
        self.TaskSequenceList.setItemWidget(item, line_widget)

    def add_task_line_widget(self, task):
        """
        根据任务生成控件，单独管理列表中每一行的布局
        每一行布局分为三个部分：task_id; task type; task info
        """

        # 本行元素 + 布局
        line_widget = QWidget()
        line_widget.setObjectName('line_widget')
        line_layout = QHBoxLayout(line_widget)

        # task_id + type
        layout = QHBoxLayout()
        line_layout.addLayout(layout)

        w_label = QLabel(str(task["task_id"]))
        w_label.setObjectName('label_task_id')
        w_label.setFixedWidth(20)
        layout.addWidget(w_label)

        task_type = task['task_type']
        w_label = QLabel(task_type)
        w_label.setObjectName("label_task_type")
        w_label.setFixedWidth(80)
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
                line_layout.addWidget(QLabel("   "))

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
            w_input.setMaximum(99)
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

            # 战斗卡组
            w_label = QLabel('卡组')
            w_input = QComboBox()
            w_input.setObjectName("w_deck")
            for index in ['1', '2', '3', '4', '5', '6']:
                w_input.addItem(index)
            index = w_input.findText(str(task["task_args"]["deck"]))
            if index >= 0:
                w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            # 刷新和创建战斗方案的 uuid list 以方便查找对应值
            fresh_and_check_battle_plan_uuid()
            battle_plan_name_list = get_list_battle_plan(with_extension=False)
            battle_plan_uuid_list = g_extra.GLOBAL_EXTRA.battle_plan_uuid_list

            # 战斗方案 1P
            w_label = QLabel('1P方案')
            w_input = QComboBox()
            w_input.setObjectName("w_battle_plan_1p")
            w_input.setMaximumWidth(225)
            for index in battle_plan_name_list:
                w_input.addItem(index)
            # 设定当前值
            try:
                index = battle_plan_uuid_list.index(task["task_args"]["battle_plan_1p"])
            except ValueError:
                self.could_not_find_battle_plan_uuid = True
                index = 0
            w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

            # 战斗方案 2P
            w_label = QLabel('2P方案')
            w_input = QComboBox()
            w_input.setObjectName("w_battle_plan_2p")
            w_input.setMaximumWidth(225)
            for index in battle_plan_name_list:
                w_input.addItem(index)
            # 设定当前值
            try:
                index = battle_plan_uuid_list.index(task["task_args"]["battle_plan_2p"])
            except ValueError:
                self.could_not_find_battle_plan_uuid = True
                index = 1
            w_input.setCurrentIndex(index)
            add_element(line_layout=line_layout, w_label=w_label, w_input=w_input)

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

        # 创建一个水平弹簧
        spacer = QSpacerItem(0, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        line_layout.addItem(spacer)

        # 添加完成后，在布局的最后添加一个删除按钮
        delete_button = QPushButton('删除')
        delete_button.setMaximumWidth(50)

        # 绑定两个函数
        delete_button.clicked.connect(lambda: self.delete_task(task["task_id"]))
        delete_button.clicked.connect(lambda: self.update_task_id())
        line_layout.addWidget(QCVerticalLine())
        line_layout.addWidget(delete_button)

        return line_widget

    def update_task_id(self):
        """
        增删后 更新任务id
        """
        # 清空所有任务的 ID
        for row in range(self.TaskSequenceList.count()):
            item = self.TaskSequenceList.item(row)
            widget = self.TaskSequenceList.itemWidget(item)

            id_label = widget.findChild(QLabel, 'label_task_id')
            if id_label:
                id_label.setText("")  # 清空 ID 显示

        # 重新分配 ID
        for row in range(self.TaskSequenceList.count()):
            # UI 部分
            item = self.TaskSequenceList.item(row)
            widget = self.TaskSequenceList.itemWidget(item)
            id_label = widget.findChild(QLabel, 'label_task_id')
            if id_label:
                id_label.setText(str(row + 1))  # 设置新的 ID 显示

    def delete_task(self, item_id):
        """删除指定 ID 的任务"""
        try:
            # 从 self.TaskSequenceList 中删除对应的项
            item = self.TaskSequenceList.item(item_id - 1)
            widget = self.TaskSequenceList.itemWidget(item)

            # 清除附加的 widget
            self.TaskSequenceList.removeItemWidget(item)

            # 移除 QListWidgetItem
            self.TaskSequenceList.takeItem(item_id - 1)

            # 删除 widget 和 QListWidgetItem
            if widget is not None:
                widget.deleteLater()
            del item
        except Exception as e:
            print(f"Error: {e} ")

    def clear_tasks(self):
        """
        清空所有任务
        """
        # 获取当前的项数
        count = self.TaskSequenceList.count()

        # 从后向前遍历并移除每一项
        for i in range(count - 1, -1, -1):
            item = self.TaskSequenceList.takeItem(i)
            widget = self.TaskSequenceList.itemWidget(item)

            # 删除附加的 widget
            if widget is not None:
                widget.deleteLater()
            del item

    """ .json ↔ list ↔ UI """

    def list_to_ui(self, task_sequence_list):
        """获取json中的数据, 转化为list并写入到ui"""
        # 清空
        self.clear_tasks()

        self.could_not_find_battle_plan_uuid = False
        self.could_not_load_json_succeed = False

        # 读取
        for task in task_sequence_list:
            self.add_task(task)
            # 出现读取失败, 中止
            if self.could_not_load_json_succeed:
                break

        # 出现了读取失败, 意味着格式不符合协议...
        if self.could_not_load_json_succeed:
            QMessageBox.critical(
                self,
                "警告!!!",
                f"该<事项序列>不符合协议! 读取失败! 可能原因如下:\n"
                f"1. 您使用文本编辑器魔改后, 格式不符合协议.\n"
                f"2. 该序列的版本过低, 无法兼容解析.\n"
            )
            return

        # 出现了uuid找不到对应战斗方案的情况 弹窗
        if self.could_not_find_battle_plan_uuid:
            QMessageBox.critical(
                self,
                "警告!!!",
                f"该<事项序列>的部分战斗方案uuid, 无法在您本地的战斗方案中找到对应目标.\n"
                f"已设定为默认值, 请手动添加该<事项序列>需要的战斗方案, 或手动修改")

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

        list_line_widgets = self.TaskSequenceList.findChildren(QWidget, 'line_widget')

        for w_line in list_line_widgets:
            data_line = {}

            label_task_type = w_line.findChild(QLabel, 'label_task_type')
            task_type = label_task_type.text()
            data_line['task_type'] = task_type

            label_task_id = w_line.findChild(QLabel, 'label_task_id')
            task_id = label_task_id.text()
            data_line['task_id'] = int(task_id)

            data_line["task_args"] = {}
            args = data_line["task_args"]

            match task_type:
                case "战斗":
                    widget_input = w_line.findChild(QLineEdit, 'w_stage_id')
                    args['stage_id'] = widget_input.text()

                    widget_input = w_line.findChild(QSpinBox, 'w_max_times')
                    args['max_times'] = widget_input.value()

                    widget_input = w_line.findChild(QCheckBox, 'w_need_key')
                    args['need_key'] = widget_input.isChecked()

                    widget_input = w_line.findChild(QComboBox, 'w_player')
                    text = widget_input.currentText()
                    return_list = {"1P": [1], "2P": [2], "1P房主": [1, 2], "2P房主": [2, 1]}[text]
                    args['player'] = return_list

                    widget_input = w_line.findChild(QComboBox, 'w_deck')
                    args['deck'] = int(widget_input.currentText())

                    # 战斗方案
                    battle_plan_name_list = get_list_battle_plan(with_extension=False)
                    battle_plan_uuid_list = g_extra.GLOBAL_EXTRA.battle_plan_uuid_list

                    widget_input = w_line.findChild(QComboBox, 'w_battle_plan_1p')
                    text = widget_input.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    args['battle_plan_1p'] = uuid

                    widget_input = w_line.findChild(QComboBox, 'w_battle_plan_2p')
                    text = widget_input.currentText()
                    index = battle_plan_name_list.index(text)
                    uuid = battle_plan_uuid_list[index]
                    args['battle_plan_2p'] = uuid

                    # 固定值 请不要用于 魔塔 / 萌宠神殿 这两类特殊关卡！
                    args["quest_card"] = "None"
                    args["ban_card_list"] = []
                    args["dict_exit"] = {
                        "other_time_player_a": [],
                        "other_time_player_b": [],
                        "last_time_player_a": ["竞技岛"],
                        "last_time_player_b": ["竞技岛"]
                    }

                case "双暴卡":
                    args = player(w_line=w_line, args=args)

                    # 最大次数
                    widget = w_line.findChild(QSpinBox, 'w_max_times')
                    args['max_times'] = widget.value()

                case "清背包":
                    args = player(w_line=w_line, args=args)

                case "刷新游戏":
                    args = player(w_line=w_line, args=args)

                case "领取任务奖励":
                    args = player(w_line=w_line, args=args)
                    for key in ["normal", "guild", "spouse", "offer_reward", "food_competition", "monopoly", "camp"]:
                        args = check_box(w_line=w_line, args=args, key=key)

            data_line["task_args"] = args

            data.append(data_line)

        # 根据id排序 输出
        data = sorted(data, key=lambda x: x['task_id'])
        return data

    def load_json(self):
        """
        Load a JSON file and parse it into the task sequence list
        """

        file_name, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="加载<事项序列>.json",
            directory=PATHS["task_sequence"],
            filter="JSON Files (*.json)")

        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as file:
                    self.list_to_ui(json.load(file))
            except Exception as e:
                # 报错弹窗
                QMessageBox.critical(
                    self,
                    "Json格式错误!",
                    f"读取<事项序列>失败! \n"
                    f"这是由于您使用文本编辑器魔改后,格式不符合Json规范导致\n"
                    f"错误信息: {str(e)}")

    def save_json(self):
        """
        Save the task sequence list as a JSON file.
        """

        try:
            export_list = self.ui_to_list()
            print("导出结果:", export_list)
        except Exception as e:
            # 报错弹窗
            QMessageBox.critical(
                self,
                "错误!",
                f"转化ui内容到list失败\n请联系开发者!!!\n错误信息: {str(e)}")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="保存事项序列.json",
            directory=PATHS["task_sequence"],
            filter="JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as file:
                    json.dump(export_list, file, ensure_ascii=False, indent=4)
                    QMessageBox.information(
                        self,
                        "成功!",
                        "<事项序列> 已保存成功~")
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "错误!",
                    f"保存<事项序列>失败\n请联系开发者!!!\n错误信息: {str(e)}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = QMWEditorOfTaskSequence()
    window.show()
    sys.exit(app.exec())
