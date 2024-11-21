from PyQt6.QtWidgets import QMainWindow
from PyQt6 import uic
import json

from function.globals import EXTRA
from function.scattered.check_battle_plan import fresh_and_check_all_battle_plan
from function.scattered.get_list_battle_plan import get_list_battle_plan
from function.widget.MultiLevelMenu import MultiLevelMenu
from function.globals.get_paths import PATHS

"""
关卡方案编辑器
"""


class QMWEditorOfStagePlan(QMainWindow):
    """
    关卡方案编辑器，实时保存
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 读取ui
        uic.loadUi(PATHS["root"] + '\\resource\\ui\\StagePlanEditor.ui', self)

        # 初始化战斗方案变量
        self.battle_plan_uuid_list = None
        self.battle_plan_name_list = None

        # 初始化战斗方案选择框
        self.init_battle_plan_selector()

        # 获取stage_info
        with open(file=PATHS["config"] + "//stage_info.json", mode="r", encoding="UTF-8") as file:
            self.stage_info = json.load(file)
        # 获取stage_plan
        self.stage_plan_path = PATHS["config"] + "//stage_plan.json"
        try:
            with open(file=self.stage_plan_path, mode="r", encoding="UTF-8") as file:
                self.stage_plan = json.load(file)
        except FileNotFoundError:
            self.stage_plan = {}

        # 初始化当前选择变量与选择后方法
        self.current_stage = None
        self.stage_selector.on_selected.connect(self.stage_changed)
        self.init_stage_selector()

        # 将所有控件的状态变更信号连接上变更函数
        self.skip_check.stateChanged.connect(self.state_changed)
        self.deck_box_1P.currentIndexChanged.connect(self.state_changed)
        self.deck_box_2P.currentIndexChanged.connect(self.state_changed)
        self.battle_plan_box_1P.currentIndexChanged.connect(self.state_changed)
        self.battle_plan_box_2P.currentIndexChanged.connect(self.state_changed)


    def init_stage_selector(self):
        """
        多层菜单
        初始化关卡选择，从stage_info或更多内容里导入关卡，选择后可以显示障碍物或更多内容
        菜单使用字典，其值只能为字典或列表。键值对中的键恒定为子菜单，而值为选项；列表中元素只能是元组，为关卡名，关卡id
        """
        stage_dict = {}
        # 给定初级菜单
        first_menu = ["主线副本", "番外关卡", "公会副本", "悬赏副本", "跨服副本", "魔塔蛋糕"]

        for stage_upper_type in first_menu:
            # 初始化每个初级菜单项的子菜单字典
            stage_dict[stage_upper_type] = {}

            match stage_upper_type:
                case "主线副本":
                    main_stage = ["美味岛", "火山岛", "火山遗迹", "浮空岛", "海底旋涡", "星际穿越"]
                    for stage_type in main_stage:
                        index = main_stage.index(stage_type) + 1
                        stage_dict[stage_upper_type][stage_type] = []
                        for stage_id, stage_info in self.stage_info["NO"][str(index)].items():
                            stage_dict[stage_upper_type][stage_type].append((stage_info["name"],
                                                                             f"NO-{index}-{stage_id}"))
                case "番外关卡":
                    extra_stage = ["探险营地", "沙漠", "雪山", "雷城", "漫游奇境"]
                    for stage_type in extra_stage:
                        index = extra_stage.index(stage_type) + 1
                        stage_dict[stage_upper_type][stage_type] = []
                        for stage_id, stage_info in self.stage_info["EX"][str(index)].items():
                            stage_dict[stage_upper_type][stage_type].append((stage_info["name"],
                                                                             f"EX-{index}-{stage_id}"))
                case "公会副本":
                    pass

                case "悬赏副本":
                    pass

                case "跨服副本":
                    pass

                case "魔塔蛋糕":
                    pass

        self.stage_selector.add_menu(data=stage_dict)

    def init_battle_plan_selector(self):
        """
        初始化战斗方案选择框
        """
        fresh_and_check_all_battle_plan()
        self.battle_plan_name_list = get_list_battle_plan(with_extension=False)
        self.battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())
        for index in self.battle_plan_name_list:
            self.battle_plan_box_1P.addItem(index)
            self.battle_plan_box_2P.addItem(index)

    def refresh_battle_plan_selector(self):
        """
        刷新战斗方案选择框，确保读取了当前的战斗方案
        """
        fresh_and_check_all_battle_plan()
        self.battle_plan_name_list = get_list_battle_plan(with_extension=False)
        self.battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())
        # 存储当前的索引
        current_index_1P = self.battle_plan_box_1P.currentIndex()
        current_index_2P = self.battle_plan_box_2P.currentIndex()
        # 暂时屏蔽控件信号
        self.battle_plan_box_1P.blockSignals(True)
        self.battle_plan_box_2P.blockSignals(True)
        # 清空选择框列表
        self.battle_plan_box_1P.clear()
        self.battle_plan_box_2P.clear()
        for index in self.battle_plan_name_list:
            self.battle_plan_box_1P.addItem(index)
            self.battle_plan_box_2P.addItem(index)
        # 恢复当前索引
        self.battle_plan_box_1P.setCurrentIndex(current_index_1P)
        self.battle_plan_box_2P.setCurrentIndex(current_index_2P)
        # 恢复控件信号
        self.battle_plan_box_1P.blockSignals(False)
        self.battle_plan_box_2P.blockSignals(False)

    def stage_changed(self, text, data):
        """
        关卡选择改变，更新UI
        :param text: 显示在菜单中的文本
        :param data: 关卡id
        """
        self.current_stage = data
        if data in self.stage_plan.keys():
            self.init_state_ui()
        else:
            self.stage_plan[data] = {
                "skip": False,
                "deck": [1, 1],
                "battle_plan": [0, 1]
            }
            self.init_state_ui()

    def state_changed(self):
        """
        状态改变处理器，实时更新并保存
        """
        sender = self.sender()
        object_name = sender.objectName()
        match object_name:
            case "skip_check":
                self.stage_plan[self.current_stage]["skip"] = sender.isChecked()
            case "deck_box_1P":
                self.stage_plan[self.current_stage]["deck"][0] = int(sender.currentText())
            case "deck_box_2P":
                self.stage_plan[self.current_stage]["deck"][1] = int(sender.currentText())
            case "battle_plan_box_1P":
                self.stage_plan[self.current_stage]["battle_plan"][0] = self.battle_plan_uuid_list[self.battle_plan_box_1P.currentIndex()]
            case "battle_plan_box_2P":
                self.stage_plan[self.current_stage]["battle_plan"][1] = self.battle_plan_uuid_list[self.battle_plan_box_2P.currentIndex()]
        # 刷新战斗方案选择框
        self.refresh_battle_plan_selector()
        # 实时存储
        self.save_stage_plan()



    def init_state_ui(self):
        """
        根据当前所选关卡，初始化ui
        """
        # 屏蔽所有状态改变信号
        self.skip_check.blockSignals(True)
        self.deck_box_1P.blockSignals(True)
        self.deck_box_2P.blockSignals(True)
        self.battle_plan_box_1P.blockSignals(True)
        self.battle_plan_box_2P.blockSignals(True)
        # 更新状态
        self.skip_check.setChecked(self.stage_plan[self.current_stage]["skip"])
        self.deck_box_1P.setCurrentIndex(self.stage_plan[self.current_stage]["deck"][0] - 1)
        self.deck_box_2P.setCurrentIndex(self.stage_plan[self.current_stage]["deck"][1] - 1)
        # 尝试获取当前任务的战斗方案
        try:
            index = self.battle_plan_uuid_list.index(self.stage_plan[self.current_stage]["battle_plan"][0])
        except ValueError:
            index = 0
        self.battle_plan_box_1P.setCurrentIndex(index)
        try:
            index = self.battle_plan_uuid_list.index(self.stage_plan[self.current_stage]["battle_plan"][1])
        except ValueError:
            index = 0
        self.battle_plan_box_2P.setCurrentIndex(index)
        # 恢复信号
        self.skip_check.blockSignals(False)
        self.deck_box_1P.blockSignals(False)
        self.deck_box_2P.blockSignals(False)
        self.battle_plan_box_1P.blockSignals(False)
        self.battle_plan_box_2P.blockSignals(False)

    def save_stage_plan(self):
        """
        保存当前编辑的关卡方案
        """
        with open(self.stage_plan_path, 'w', encoding='utf-8') as f:
            json.dump(self.stage_plan, f, ensure_ascii=False, indent=4)
