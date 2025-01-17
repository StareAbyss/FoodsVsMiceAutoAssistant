import copy
import json

from PyQt6 import uic
from PyQt6.QtWidgets import QMainWindow

from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.scattered.check_battle_plan import fresh_and_check_all_battle_plan
from function.scattered.get_list_battle_plan import get_list_battle_plan

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

        self.setWindowTitle('全局方案 & 关卡方案 编辑器')

        # 初始化战斗方案变量
        self.battle_plan_uuid_list = None
        self.battle_plan_name_list = None

        # 初始化战斗方案选择框
        self.init_battle_plan_selector()

        # 获取stage_info
        with open(file=PATHS["config"] + "//stage_info.json", mode="r", encoding="UTF-8") as file:
            self.stage_info = json.load(file)

        # 获取stage_plan文件中的信息
        self.stage_plan_path = PATHS["config"] + "//stage_plan.json"
        try:
            with open(file=self.stage_plan_path, mode="r", encoding="UTF-8") as file:
                self.stage_plan = json.load(file)
        except FileNotFoundError:
            self.stage_plan = {}

        # 如果老版本方案中不包含全局方案, 添加
        if not self.stage_plan.get("global", None):
            self.stage_plan["global"] = {
                "skip": False,
                "deck": 0,
            "senior_setting":False,
                "battle_plan": [
                    "00000000-0000-0000-0000-000000000000",
                    "00000000-0000-0000-0000-000000000001"]
            }

        print(self.stage_plan)

        # 初始化当前选择关卡变量与选择后方法
        self.current_stage = None
        self.stage_selector.on_selected.connect(self.stage_selector_changed)
        self.init_stage_selector()

        # 将 全局方案 状态变更信号连接上变更函数
        self.GlobalDeckBox.currentIndexChanged.connect(self.global_state_changed)
        self.GlobalBattlePlanBox1P.currentIndexChanged.connect(self.global_state_changed)
        self.GlobalBattlePlanBox2P.currentIndexChanged.connect(self.global_state_changed)

        # 将 所有控件 的状态变更信号连接上变更函数
        self.StageSkipCheck.stateChanged.connect(self.stage_state_changed)
        self.StageDeckBox.currentIndexChanged.connect(self.stage_state_changed)
        self.StageBattlePlanBox1P.currentIndexChanged.connect(self.stage_state_changed)
        self.StageBattlePlanBox2P.currentIndexChanged.connect(self.stage_state_changed)
        self.senior_battle_check.stateChanged.connect(self.stage_state_changed)

        # 加载全局方案到ui
        self.init_global_state_ui()

        # 将所有stage input控件设为不可用
        self.set_stage_input_widget_usable(state=False)

    def init_stage_selector(self):
        """
        多层菜单
        初始化关卡选择，从stage_info或更多内容里导入关卡，选择后可以显示障碍物或更多内容
        菜单使用字典，其值只能为字典或列表。键值对中的键恒定为子菜单，而值为选项；列表中元素只能是元组，为关卡名，关卡id
        """
        stage_dict = {}
        for type_id, stage_info_1 in self.stage_info.items():
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

        self.stage_selector.add_menu(data=stage_dict)

    def init_battle_plan_selector(self):
        """
        初始化战斗方案选择框
        """
        fresh_and_check_all_battle_plan()
        self.battle_plan_name_list = get_list_battle_plan(with_extension=False)
        self.battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())
        for index in self.battle_plan_name_list:
            self.GlobalBattlePlanBox1P.addItem(index)
            self.GlobalBattlePlanBox2P.addItem(index)
            self.StageBattlePlanBox1P.addItem(index)
            self.StageBattlePlanBox2P.addItem(index)

    def refresh_battle_plan_selector(self):
        """
        刷新战斗方案选择框，保持指向的战斗方案不变, 并读取最新的战斗方案们.
        """
        fresh_and_check_all_battle_plan()
        self.battle_plan_name_list = get_list_battle_plan(with_extension=False)
        self.battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

        def change_one(widget):
            # 存储当前的索引
            current_index = widget.currentIndex()
            # 暂时屏蔽控件信号
            widget.blockSignals(True)
            # 清空选择框列表
            widget.clear()
            for index in self.battle_plan_name_list:
                widget.addItem(index)
            # 恢复当前索引
            widget.setCurrentIndex(current_index)
            # 恢复控件信号
            widget.blockSignals(False)

        change_one(widget=self.GlobalBattlePlanBox1P)
        change_one(widget=self.GlobalBattlePlanBox1P)
        change_one(widget=self.StageBattlePlanBox1P)
        change_one(widget=self.StageBattlePlanBox2P)

    def stage_selector_changed(self, text, stage):
        """
        关卡选择改变，更新UI
        :param text: 显示在菜单中的文本
        :param stage: 关卡id
        """
        self.current_stage = stage

        # 如果当前关卡没有配置，则拷贝自默认配置
        if stage in self.stage_plan.keys():
            self.label_10.setText("编辑关卡方案")
        else:
            self.label_10.setText("编辑关卡方案 (同步中, 修改全局方案将单向映射至关卡方案)")
            self.stage_plan[stage] = copy.deepcopy(self.stage_plan["global"])

        self.init_stage_state_ui()

        # 解锁 允许交互
        self.set_stage_input_widget_usable(state=True)

    def global_state_changed(self):
        """
        全局关卡方案的状态改变处理器，实时更新并保存
        1. 先修改全局
        """

        if self.current_stage:
            if self.stage_plan["global"] == self.stage_plan[self.current_stage]:
                self.label_10.setText("编辑关卡方案 (同步中, 修改全局方案将单向映射至关卡方案)")
                synchronization = True
            else:
                self.label_10.setText("编辑关卡方案")
                synchronization = False
        else:
            synchronization = False

        sender = self.sender()
        object_name = sender.objectName()

        match object_name:
            case "GlobalDeckBox":
                value = int(sender.currentIndex())
                self.stage_plan["global"]["deck"] = value
                if synchronization:
                    self.stage_plan[self.current_stage]["deck"] = value
                    self.StageDeckBox.setCurrentIndex(value)

            case "GlobalBattlePlanBox1P":
                index = self.GlobalBattlePlanBox1P.currentIndex()
                uuid = self.battle_plan_uuid_list[index]
                self.stage_plan["global"]["battle_plan"][0] = uuid
                if synchronization:
                    self.stage_plan[self.current_stage]["battle_plan"][0] = uuid
                    self.StageBattlePlanBox1P.setCurrentIndex(index)

            case "GlobalBattlePlanBox2P":
                index = self.GlobalBattlePlanBox2P.currentIndex()
                uuid = self.battle_plan_uuid_list[index]
                self.stage_plan["global"]["battle_plan"][1] = uuid
                if synchronization:
                    self.stage_plan[self.current_stage]["battle_plan"][1] = uuid
                    self.StageBattlePlanBox2P.setCurrentIndex(index)

        # 刷新战斗方案选择框
        self.refresh_battle_plan_selector()

        # 实时存储
        self.save_stage_plan()

    def stage_state_changed(self):
        """
        状态改变处理器，实时更新并保存
        """

        sender = self.sender()
        object_name = sender.objectName()
        match object_name:
            case "StageSkipCheck":
                self.stage_plan[self.current_stage]["skip"] = sender.isChecked()
            case "StageDeckBox":
                self.stage_plan[self.current_stage]["deck"] = int(sender.currentIndex())
            case "StageBattlePlanBox1P":
                self.stage_plan[self.current_stage]["battle_plan"][0] = self.battle_plan_uuid_list[
                    self.StageBattlePlanBox1P.currentIndex()]
            case "StageBattlePlanBox2P":
                self.stage_plan[self.current_stage]["battle_plan"][1] = self.battle_plan_uuid_list[
                    self.StageBattlePlanBox2P.currentIndex()]
            case "senior_battle_check":
                    self.stage_plan[self.current_stage]["senior_setting"] = sender.isChecked()

        if self.stage_plan.get(self.current_stage, None):
            if self.stage_plan["global"] == self.stage_plan[self.current_stage]:
                self.label_10.setText("编辑关卡方案 (同步中, 修改全局方案将单向映射至关卡方案)")
            else:
                self.label_10.setText("编辑关卡方案")

        # 刷新战斗方案选择框
        self.refresh_battle_plan_selector()

        # 实时存储
        self.save_stage_plan()

    def init_stage_state_ui(self):
        """
        根据当前所选关卡，初始化ui
        """
        # 屏蔽所有状态改变信号
        self.StageSkipCheck.blockSignals(True)
        self.StageDeckBox.blockSignals(True)
        self.StageBattlePlanBox1P.blockSignals(True)
        self.StageBattlePlanBox2P.blockSignals(True)
        self.senior_battle_check.blockSignals(True)

        # 更新状态

        self.StageSkipCheck.setChecked(self.stage_plan[self.current_stage]["skip"])

        self.StageDeckBox.setCurrentIndex(self.stage_plan[self.current_stage]["deck"])
        try:
            self.senior_battle_check.setChecked(self.stage_plan[self.current_stage]["senior_setting"])
        except KeyError:# 兼容旧版本
            self.senior_battle_check.setChecked(False)
        # 尝试获取当前任务的战斗方案
        try:
            index = self.battle_plan_uuid_list.index(self.stage_plan[self.current_stage]["battle_plan"][0])
        except ValueError:
            index = 0
        self.StageBattlePlanBox1P.setCurrentIndex(index)

        try:
            index = self.battle_plan_uuid_list.index(self.stage_plan[self.current_stage]["battle_plan"][1])
        except ValueError:
            index = 0
        self.StageBattlePlanBox2P.setCurrentIndex(index)

        # 恢复信号
        self.StageSkipCheck.blockSignals(False)
        self.StageDeckBox.blockSignals(False)
        self.StageBattlePlanBox1P.blockSignals(False)
        self.StageBattlePlanBox2P.blockSignals(False)
        self.senior_battle_check.blockSignals(False)

    def init_global_state_ui(self):
        """
        根据当前所选关卡，初始化ui
        """
        # 屏蔽所有状态改变信号
        self.GlobalDeckBox.blockSignals(True)
        self.GlobalBattlePlanBox1P.blockSignals(True)
        self.GlobalBattlePlanBox2P.blockSignals(True)

        self.GlobalDeckBox.setCurrentIndex(self.stage_plan["global"]["deck"])

        try:
            index = self.battle_plan_uuid_list.index(self.stage_plan["global"]["battle_plan"][0])
        except ValueError:
            index = 0
        self.GlobalBattlePlanBox1P.setCurrentIndex(index)

        try:
            index = self.battle_plan_uuid_list.index(self.stage_plan["global"]["battle_plan"][1])
        except ValueError:
            index = 0
        self.GlobalBattlePlanBox2P.setCurrentIndex(index)

        # 恢复信号
        self.GlobalDeckBox.blockSignals(False)
        self.GlobalBattlePlanBox1P.blockSignals(False)
        self.GlobalBattlePlanBox2P.blockSignals(False)

    def save_stage_plan(self):
        """
        保存当前编辑的关卡方案
        """

        stage_plan = copy.deepcopy(self.stage_plan)
        # 收集需要删除的键，跳过键 'global'
        keys_to_remove = [k for k, v in stage_plan.items() if v == stage_plan["global"] and k != "global"]

        # 删除收集到的键
        for k in keys_to_remove:
            stage_plan.pop(k)

        with open(self.stage_plan_path, 'w', encoding='utf-8') as f:
            json.dump(stage_plan, f, ensure_ascii=False, indent=4)

    def set_stage_input_widget_usable(self, state):
        """
        更改输入的状态, 使之可用和不可用
        """
        self.StageSkipCheck.setEnabled(state)
        self.StageDeckBox.setEnabled(state)
        self.StageBattlePlanBox1P.setEnabled(state)
        self.StageBattlePlanBox2P.setEnabled(state)
        self.senior_battle_check.setEnabled(state)
