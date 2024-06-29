import copy
import json
import os
import shutil
import sys
import time

from PyQt5.QtWidgets import QApplication, QMessageBox

from function.core.QMW_0_load_ui_file import QMainWindowLoadUI
from function.globals.extra import EXTRA_GLOBALS
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.scattered.get_customize_todo_list import get_customize_todo_list
from function.scattered.get_list_battle_plan import get_list_battle_plan


class QMainWindowLoadSettings(QMainWindowLoadUI):
    """将读取配置的方法封装在此处"""

    def __init__(self):
        # 继承父类构造方法
        super().__init__()

        # opt路径
        self.opt_path = PATHS["root"] + "\\config\\settings.json"
        # opt模板路径
        self.opt_template_path = PATHS["root"] + "\\config\\settings_template.json"
        # 检测opt是否存在
        self.check_opt_exist()

        # 从json文件中读取opt 并刷新ui
        self.opt = None
        self.json_to_opt()
        self.init_opt_to_ui()

    def check_opt_exist(self):

        settings_file = self.opt_path
        template_file = self.opt_template_path

        # 检查settings.json是否存在
        if not os.path.exists(settings_file):
            # 如果不存在，从模板文件复制
            try:
                shutil.copyfile(template_file, settings_file)
                CUS_LOGGER.warning(f"'{settings_file}' 不存在，已从模板 '{template_file}' 创建。")
            except IOError as e:
                CUS_LOGGER.error(f"无法创建 '{settings_file}' 从 '{template_file}'。错误: {e}")
        else:
            CUS_LOGGER.info(f"'{settings_file}' 已存在。")

    def json_to_opt(self)->None:
        # 自旋锁读写, 防止多线程读写问题
        while EXTRA_GLOBALS.file_is_reading_or_writing:
            time.sleep(0.1)
        EXTRA_GLOBALS.file_is_reading_or_writing = True  # 文件被访问
        with open(file=self.opt_path, mode="r", encoding="UTF-8") as file:
            data = json.load(file)
        EXTRA_GLOBALS.file_is_reading_or_writing = False  # 文件已解锁
        self.opt = data
        return None

    def opt_to_json(self)->None:
        # dict → str 转换True和true
        json_str = json.dumps(self.opt, indent=4)

        # 自旋锁读写, 防止多线程读写问题
        while EXTRA_GLOBALS.file_is_reading_or_writing:
            time.sleep(0.1)
        EXTRA_GLOBALS.file_is_reading_or_writing = True  # 文件被访问
        with open(file=self.opt_path, mode="w", encoding="UTF-8") as file:
            file.write(json_str)
        EXTRA_GLOBALS.file_is_reading_or_writing = False  # 文件已解锁
        return None

    def opt_to_ui_todo_plans(self):
        """
        先从ui上读取目前todo plan index, 然后从opt读取对应的设置到todo plan 配置界面
        :return:
        """
        # 先重新获取ui上的 当前方案选项
        self.opt["current_plan"] = self.CurrentPlan.currentIndex()  # combobox 序号
        # 修改当前方案文本
        self.CurrentPlan_Label_Change.setText(self.CurrentPlan.currentText())

        battle_plan_list = get_list_battle_plan(with_extension=False)
        customize_todo_list = get_customize_todo_list(with_extension=False)

        # 获取前半部分
        my_opt = self.opt["todo_plans"][int(self.opt["current_plan"])]

        # 签到 浇水施肥摘果 勇士本

        self.SignIn_Active.setChecked(my_opt["sign_in"]["active"])
        self.SignIn_Group.setChecked(my_opt["sign_in"]["is_group"])

        self.FedAndWatered_Active.setChecked(my_opt["fed_and_watered"]["active"])
        self.FedAndWatered_Group.setChecked(my_opt["fed_and_watered"]["is_group"])

        self.UseDoubleCard_Active.setChecked(my_opt["use_double_card"]["active"])
        self.UseDoubleCard_Group.setChecked(my_opt["use_double_card"]["is_group"])
        self.UseDoubleCard_MaxTimes.setValue(my_opt["use_double_card"]["max_times"])

        self.Warrior_Active.setChecked(my_opt["warrior"]["active"])
        self.Warrior_Group.setChecked(my_opt["warrior"]["is_group"])
        self.Warrior_MaxTimes.setValue(my_opt["warrior"]["max_times"])
        self.Warrior_Deck.setValue(my_opt["warrior"]["deck"])
        self.Warrior_1P.clear()
        self.Warrior_2P.clear()
        self.Warrior_1P.addItems(battle_plan_list)
        self.Warrior_2P.addItems(battle_plan_list)
        self.Warrior_1P.setCurrentIndex(my_opt["warrior"]["battle_plan_1p"])
        self.Warrior_2P.setCurrentIndex(my_opt["warrior"]["battle_plan_2p"])

        # 常规单本 悬赏任务 跨服任务

        self.NormalBattle_Active.setChecked(my_opt["normal_battle"]["active"])
        self.NormalBattle_Group.setChecked(my_opt["normal_battle"]["is_group"])
        self.NormalBattle_MaxTimes.setValue(my_opt["normal_battle"]["max_times"])
        self.NormalBattle_Stage.setText(my_opt["normal_battle"]["stage"])
        self.NormalBattle_Deck.setValue(my_opt["normal_battle"]["deck"])
        self.NormalBattle_1P.clear()
        self.NormalBattle_2P.clear()
        self.NormalBattle_1P.addItems(battle_plan_list)
        self.NormalBattle_2P.addItems(battle_plan_list)
        self.NormalBattle_1P.setCurrentIndex(my_opt["normal_battle"]["battle_plan_1p"])
        self.NormalBattle_2P.setCurrentIndex(my_opt["normal_battle"]["battle_plan_2p"])

        self.OfferReward_Active.setChecked(my_opt["offer_reward"]["active"])
        self.OfferReward_MaxTimes_1.setValue(my_opt["offer_reward"]["max_times_1"])
        self.OfferReward_MaxTimes_2.setValue(my_opt["offer_reward"]["max_times_2"])
        self.OfferReward_MaxTimes_3.setValue(my_opt["offer_reward"]["max_times_3"])
        self.OfferReward_Deck.setValue(my_opt["offer_reward"]["deck"])
        self.OfferReward_1P.clear()
        self.OfferReward_2P.clear()
        self.OfferReward_1P.addItems(battle_plan_list)
        self.OfferReward_2P.addItems(battle_plan_list)
        self.OfferReward_1P.setCurrentIndex(my_opt["offer_reward"]["battle_plan_1p"])
        self.OfferReward_2P.setCurrentIndex(my_opt["offer_reward"]["battle_plan_2p"])

        self.CrossServer_Active.setChecked(my_opt["cross_server"]["active"])
        self.CrossServer_Group.setChecked(my_opt["cross_server"]["is_group"])
        self.CrossServer_MaxTimes.setValue(my_opt["cross_server"]["max_times"])
        self.CrossServer_Stage.setText(my_opt["cross_server"]["stage"])
        self.CrossServer_Deck.setValue(my_opt["cross_server"]["deck"])
        self.CrossServer_1P.clear()
        self.CrossServer_2P.clear()
        self.CrossServer_1P.addItems(battle_plan_list)
        self.CrossServer_2P.addItems(battle_plan_list)
        self.CrossServer_1P.setCurrentIndex(my_opt["cross_server"]["battle_plan_1p"])
        self.CrossServer_2P.setCurrentIndex(my_opt["cross_server"]["battle_plan_2p"])

        # 公会任务 工会副本 情侣任务 火山遗迹

        self.QuestGuild_Active.setChecked(my_opt["quest_guild"]["active"])
        self.QuestGuild_Stage.setChecked(my_opt["quest_guild"]["stage"])
        self.QuestGuild_Deck.setValue(my_opt["quest_guild"]["deck"])
        self.QuestGuild_1P.clear()
        self.QuestGuild_2P.clear()
        self.QuestGuild_1P.addItems(battle_plan_list)
        self.QuestGuild_2P.addItems(battle_plan_list)
        self.QuestGuild_1P.setCurrentIndex(my_opt["quest_guild"]["battle_plan_1p"])
        self.QuestGuild_2P.setCurrentIndex(my_opt["quest_guild"]["battle_plan_2p"])

        self.GuildDungeon_Active.setChecked(my_opt["guild_dungeon"]["active"])

        self.QuestSpouse_Active.setChecked(my_opt["quest_spouse"]["active"])

        self.Relic_Active.setChecked(my_opt["relic"]["active"])
        self.Relic_Group.setChecked(my_opt["relic"]["is_group"])
        self.Relic_MaxTimes.setValue(my_opt["relic"]["max_times"])
        self.Relic_Stage.setText(my_opt["relic"]["stage"])
        self.Relic_Deck.setValue(my_opt["relic"]["deck"])
        self.Relic_1P.clear()
        self.Relic_2P.clear()
        self.Relic_1P.addItems(battle_plan_list)
        self.Relic_2P.addItems(battle_plan_list)
        self.Relic_1P.setCurrentIndex(my_opt["relic"]["battle_plan_1p"])
        self.Relic_2P.setCurrentIndex(my_opt["relic"]["battle_plan_2p"])

        # 魔塔 萌宠神殿

        self.MagicTowerAlone1_Active.setChecked(my_opt["magic_tower_alone_1"]["active"])
        self.MagicTowerAlone1_MaxTimes.setValue(my_opt["magic_tower_alone_1"]["max_times"])
        self.MagicTowerAlone1_Stage.setValue(my_opt["magic_tower_alone_1"]["stage"])
        self.MagicTowerAlone1_Deck.setValue(my_opt["magic_tower_alone_1"]["deck"])
        self.MagicTowerAlone1_1P.clear()
        self.MagicTowerAlone1_1P.addItems(battle_plan_list)
        self.MagicTowerAlone1_1P.setCurrentIndex(my_opt["magic_tower_alone_1"]["battle_plan_1p"])

        self.MagicTowerAlone2_Active.setChecked(my_opt["magic_tower_alone_2"]["active"])
        self.MagicTowerAlone2_MaxTimes.setValue(my_opt["magic_tower_alone_2"]["max_times"])
        self.MagicTowerAlone2_Stage.setValue(my_opt["magic_tower_alone_2"]["stage"])
        self.MagicTowerAlone2_Deck.setValue(my_opt["magic_tower_alone_2"]["deck"])
        self.MagicTowerAlone2_1P.clear()
        self.MagicTowerAlone2_1P.addItems(battle_plan_list)
        self.MagicTowerAlone2_1P.setCurrentIndex(my_opt["magic_tower_alone_2"]["battle_plan_1p"])

        self.MagicTowerPrison1_Active.setChecked(my_opt["magic_tower_prison_1"]["active"])
        self.MagicTowerPrison1_Stage.setChecked(my_opt["magic_tower_prison_1"]["stage"])
        self.MagicTowerPrison1_Deck.setValue(my_opt["magic_tower_prison_1"]["deck"])
        self.MagicTowerPrison1_1P.clear()
        self.MagicTowerPrison1_1P.addItems(battle_plan_list)
        self.MagicTowerPrison1_1P.setCurrentIndex(my_opt["magic_tower_prison_1"]["battle_plan_1p"])

        self.MagicTowerPrison2_Active.setChecked(my_opt["magic_tower_prison_2"]["active"])
        self.MagicTowerPrison2_Stage.setChecked(my_opt["magic_tower_prison_2"]["stage"])
        self.MagicTowerPrison2_Deck.setValue(my_opt["magic_tower_prison_2"]["deck"])
        self.MagicTowerPrison2_1P.clear()
        self.MagicTowerPrison2_1P.addItems(battle_plan_list)
        self.MagicTowerPrison2_1P.setCurrentIndex(my_opt["magic_tower_prison_2"]["battle_plan_1p"])

        self.MagicTowerDouble_Active.setChecked(my_opt["magic_tower_double"]["active"])
        self.MagicTowerDouble_Stage.setValue(my_opt["magic_tower_double"]["stage"])
        self.MagicTowerDouble_MaxTimes.setValue(my_opt["magic_tower_double"]["max_times"])
        self.MagicTowerDouble_Deck.setValue(my_opt["magic_tower_double"]["deck"])
        self.MagicTowerDouble_1P.clear()
        self.MagicTowerDouble_1P.addItems(battle_plan_list)
        self.MagicTowerDouble_1P.setCurrentIndex(my_opt["magic_tower_double"]["battle_plan_1p"])
        self.MagicTowerDouble_2P.clear()
        self.MagicTowerDouble_2P.addItems(battle_plan_list)
        self.MagicTowerDouble_2P.setCurrentIndex(my_opt["magic_tower_double"]["battle_plan_2p"])

        self.PetTemple1_Active.setChecked(my_opt["pet_temple_1"]["active"])
        self.PetTemple1_Stage.setValue(my_opt["pet_temple_1"]["stage"])
        self.PetTemple1_Deck.setValue(my_opt["pet_temple_1"]["deck"])
        self.PetTemple1_1P.clear()
        self.PetTemple1_1P.addItems(battle_plan_list)
        self.PetTemple1_1P.setCurrentIndex(my_opt["pet_temple_1"]["battle_plan_1p"])

        self.PetTemple2_Active.setChecked(my_opt["pet_temple_2"]["active"])
        self.PetTemple2_Stage.setValue(my_opt["pet_temple_2"]["stage"])
        self.PetTemple2_Deck.setValue(my_opt["pet_temple_2"]["deck"])
        self.PetTemple2_1P.clear()
        self.PetTemple2_1P.addItems(battle_plan_list)
        self.PetTemple2_1P.setCurrentIndex(my_opt["pet_temple_2"]["battle_plan_1p"])

        # 附加功能

        self.ReceiveAwards_Active.setChecked(my_opt["receive_awards"]["active"])
        self.ReceiveAwards_Group.setChecked(my_opt["receive_awards"]["is_group"])

        self.UseItems_Active.setChecked(my_opt["use_items"]["active"])
        self.UseItems_Group.setChecked(my_opt["use_items"]["is_group"])

        self.LoopCrossServer_Active.setChecked(my_opt["loop_cross_server"]["active"])
        self.LoopCrossServer_Group.setChecked(my_opt["loop_cross_server"]["is_group"])

        self.CustomizeBattle_Active.setChecked(my_opt["customize_battle"]["active"])
        self.CustomizeBattle_Group.setCurrentIndex(my_opt["customize_battle"]["is_group"])
        self.CustomizeBattle_MaxTimes.setValue(my_opt["customize_battle"]["max_times"])
        self.CustomizeBattle_Deck.setValue(my_opt["customize_battle"]["deck"])
        self.CustomizeBattle_1P.clear()
        self.CustomizeBattle_2P.clear()
        self.CustomizeBattle_1P.addItems(battle_plan_list)
        self.CustomizeBattle_2P.addItems(battle_plan_list)
        self.CustomizeBattle_1P.setCurrentIndex(my_opt["customize_battle"]["battle_plan_1p"])
        self.CustomizeBattle_2P.setCurrentIndex(my_opt["customize_battle"]["battle_plan_2p"])

        self.Customize_Active.setChecked(my_opt["customize"]["active"])
        self.Customize_Stage.setValue(my_opt["customize"]["stage"])
        self.Customize_1P.clear()
        self.Customize_1P.addItems(customize_todo_list)
        self.Customize_1P.setCurrentIndex(my_opt["customize"]["battle_plan_1p"])

        self.AutoFood_Active.setChecked(my_opt["auto_food"]["active"])
        self.AutoFood_Deck.setValue(my_opt["auto_food"]["deck"])

    def init_opt_to_ui(self):
        # comboBox.setCurrentIndex时 如果超过了已有预设 会显示为空 不会报错
        # comboBox.clear时 会把所有选项设定为默认选项

        todo_plan_name_list = [plan["name"] for plan in self.opt["todo_plans"]]

        def base_settings():
            my_opt = self.opt["base_settings"]
            self.GameName_Input.setText(my_opt["game_name"])
            self.Name1P_Input.setText(my_opt["name_1p"])
            self.Name2P_Input.setText(my_opt["name_2p"])
            self.ZoomRatio_Output.setText(str(self.zoom_rate) + " (自动获取)")
            self.Level1P_Input.setValue(my_opt["level_1p"])
            self.Level2P_Input.setValue(my_opt["level_2p"])

        def timer_settings():
            my_opt = self.opt["timer"]["1"]
            self.Timer1_Active.setChecked(my_opt["active"])
            self.Timer1_H.setValue(my_opt["h"])
            self.Timer1_M.setValue(my_opt["m"])
            self.Timer1_Plan.clear()
            self.Timer1_Plan.addItems(todo_plan_name_list)
            self.Timer1_Plan.setCurrentIndex(my_opt["plan"])

            my_opt = self.opt["timer"]["2"]
            self.Timer2_Active.setChecked(my_opt["active"])
            self.Timer2_H.setValue(my_opt["h"])
            self.Timer2_M.setValue(my_opt["m"])
            self.Timer2_Plan.clear()
            self.Timer2_Plan.addItems(todo_plan_name_list)
            self.Timer2_Plan.setCurrentIndex(my_opt["plan"])

            my_opt = self.opt["timer"]["3"]
            self.Timer3_Active.setChecked(my_opt["active"])
            self.Timer3_H.setValue(my_opt["h"])
            self.Timer3_M.setValue(my_opt["m"])
            self.Timer3_Plan.clear()
            self.Timer3_Plan.addItems(todo_plan_name_list)
            self.Timer3_Plan.setCurrentIndex(my_opt["plan"])

            my_opt = self.opt["timer"]["4"]
            self.Timer4_Active.setChecked(my_opt["active"])
            self.Timer4_H.setValue(my_opt["h"])
            self.Timer4_M.setValue(my_opt["m"])
            self.Timer4_Plan.clear()
            self.Timer4_Plan.addItems(todo_plan_name_list)
            self.Timer4_Plan.setCurrentIndex(my_opt["plan"])

            my_opt = self.opt["timer"]["5"]
            self.Timer5_Active.setChecked(my_opt["active"])
            self.Timer5_H.setValue(my_opt["h"])
            self.Timer5_M.setValue(my_opt["m"])
            self.Timer5_Plan.clear()
            self.Timer5_Plan.addItems(todo_plan_name_list)
            self.Timer5_Plan.setCurrentIndex(my_opt["plan"])

        def advanced_settings():
            my_opt = self.opt["advanced_settings"]
            self.EndExitGame.setChecked(my_opt["end_exit_game"])
            self.AutoUseCard.setChecked(my_opt["auto_use_card"])
            self.AutoPickUp_1P.setChecked(my_opt["auto_pickup_1p"])
            self.AutoPickUp_2P.setChecked(my_opt["auto_pickup_2p"])
            self.AutoDeleteOldImages.setChecked(my_opt["auto_delete_old_images"])

        def get_warm_gift_settings():
            my_opt = self.opt["get_warm_gift"]
            self.GetWarmGift_1P_Active.setChecked(my_opt["1p"]["active"])
            self.GetWarmGift_1P_Link.setText(my_opt["1p"]["link"])
            self.GetWarmGift_2P_Active.setChecked(my_opt["2p"]["active"])
            self.GetWarmGift_2P_Link.setText(my_opt["2p"]["link"])

        def level_2():
            my_opt = self.opt["level_2"]
            self.Level2_1P_Active.setChecked(my_opt["1p"]["active"])
            self.Level2_1P_Password.setText(my_opt["1p"]["password"])
            self.Level2_2P_Active.setChecked(my_opt["2p"]["active"])
            self.Level2_2P_Password.setText(my_opt["2p"]["password"])

        base_settings()
        timer_settings()
        advanced_settings()
        get_warm_gift_settings()
        level_2()
        self.CurrentPlan.clear()
        self.CurrentPlan.addItems(todo_plan_name_list)
        self.CurrentPlan.setCurrentIndex(self.opt["current_plan"])
        self.opt_to_ui_todo_plans()

    def ui_to_opt(self):
        # battle_plan_list
        battle_plan_list = get_list_battle_plan(with_extension=False)
        customize_todo_list = get_customize_todo_list(with_extension=False)

        def my_transformer_b(change_class: object, opt_1, opt_2):
            # 用于配置 带有选单的 战斗方案
            self.opt["todo_plans"][self.opt["current_plan"]][opt_1][opt_2] = change_class.currentIndex()
            change_class.clear()
            change_class.addItems(battle_plan_list)
            change_class.setCurrentIndex(self.opt["todo_plans"][self.opt["current_plan"]][opt_1][opt_2])

        def my_transformer_c(change_class: object, opt_1, opt_2):
            # 用于配置 带有选单的 自定义目标
            self.opt["todo_plans"][self.opt["current_plan"]][opt_1][opt_2] = change_class.currentIndex()
            change_class.clear()
            change_class.addItems(customize_todo_list)
            change_class.setCurrentIndex(self.opt["todo_plans"][self.opt["current_plan"]][opt_1][opt_2])

        def base_settings():
            my_opt = self.opt["base_settings"]
            my_opt["game_name"] = self.GameName_Input.text()
            my_opt["name_1p"] = self.Name1P_Input.text()
            my_opt["name_2p"] = self.Name2P_Input.text()
            self.ZoomRatio_Output.setText(str(self.zoom_rate) + " (自动获取)")
            my_opt["level_1p"] = self.Level1P_Input.value()
            my_opt["level_2p"] = self.Level2P_Input.value()

        def timer_settings():
            my_opt = self.opt["timer"]["1"]
            my_opt["active"] = self.Timer1_Active.isChecked()
            my_opt["h"] = self.Timer1_H.value()
            my_opt["m"] = self.Timer1_M.value()
            my_opt["plan"] = self.Timer1_Plan.currentIndex()

            my_opt = self.opt["timer"]["2"]
            my_opt["active"] = self.Timer2_Active.isChecked()
            my_opt["h"] = self.Timer2_H.value()
            my_opt["m"] = self.Timer2_M.value()
            my_opt["plan"] = self.Timer2_Plan.currentIndex()

            my_opt = self.opt["timer"]["3"]
            my_opt["active"] = self.Timer3_Active.isChecked()
            my_opt["h"] = self.Timer3_H.value()
            my_opt["m"] = self.Timer3_M.value()
            my_opt["plan"] = self.Timer3_Plan.currentIndex()

            my_opt = self.opt["timer"]["4"]
            my_opt["active"] = self.Timer4_Active.isChecked()
            my_opt["h"] = self.Timer4_H.value()
            my_opt["m"] = self.Timer4_M.value()
            my_opt["plan"] = self.Timer4_Plan.currentIndex()

            my_opt = self.opt["timer"]["5"]
            my_opt["active"] = self.Timer5_Active.isChecked()
            my_opt["h"] = self.Timer5_H.value()
            my_opt["m"] = self.Timer5_M.value()
            my_opt["plan"] = self.Timer5_Plan.currentIndex()

        def advanced_settings():
            my_opt = self.opt["advanced_settings"]
            my_opt["end_exit_game"] = self.EndExitGame.isChecked()
            my_opt["auto_use_card"] = self.AutoUseCard.isChecked()
            my_opt["auto_pickup_1p"] = self.AutoPickUp_1P.isChecked()
            my_opt["auto_pickup_2p"] = self.AutoPickUp_2P.isChecked()
            my_opt["auto_delete_old_images"] = self.AutoDeleteOldImages.isChecked()

        def get_warm_gift_settings():
            my_opt = self.opt["get_warm_gift"]
            my_opt["1p"]["active"] = self.GetWarmGift_1P_Active.isChecked()
            my_opt["1p"]["link"] = self.GetWarmGift_1P_Link.text()
            my_opt["2p"]["active"] = self.GetWarmGift_2P_Active.isChecked()
            my_opt["2p"]["link"] = self.GetWarmGift_2P_Link.text()

        def level_2():
            my_opt = self.opt["level_2"]
            my_opt["1p"]["active"] = self.Level2_1P_Active.isChecked()
            my_opt["1p"]["password"] = self.Level2_1P_Password.text()
            my_opt["2p"]["active"] = self.Level2_2P_Active.isChecked()
            my_opt["2p"]["password"] = self.Level2_2P_Password.text()

        def todo_plans():
            # 获取前半部分
            my_opt = self.opt["todo_plans"][self.opt["current_plan"]]

            # 签到 浇水施肥摘果 勇士本

            my_opt["sign_in"]["active"] = self.SignIn_Active.isChecked()
            my_opt["sign_in"]["is_group"] = self.SignIn_Group.isChecked()

            my_opt["fed_and_watered"]["active"] = self.FedAndWatered_Active.isChecked()
            my_opt["fed_and_watered"]["is_group"] = self.FedAndWatered_Group.isChecked()

            my_opt["use_double_card"]["active"] = self.UseDoubleCard_Active.isChecked()
            my_opt["use_double_card"]["is_group"] = self.UseDoubleCard_Group.isChecked()
            my_opt["use_double_card"]["max_times"] = self.UseDoubleCard_MaxTimes.value()

            my_opt["warrior"]["active"] = self.Warrior_Active.isChecked()
            my_opt["warrior"]["is_group"] = self.Warrior_Group.isChecked()
            my_opt["warrior"]["max_times"] = self.Warrior_MaxTimes.value()
            my_opt["warrior"]["deck"] = self.Warrior_Deck.value()
            my_transformer_b(self.Warrior_1P, "warrior", "battle_plan_1p")
            my_transformer_b(self.Warrior_2P, "warrior", "battle_plan_2p")

            # 常规单本 悬赏任务 跨服任务

            my_opt["normal_battle"]["active"] = self.NormalBattle_Active.isChecked()
            my_opt["normal_battle"]["is_group"] = self.NormalBattle_Group.isChecked()
            my_opt["normal_battle"]["max_times"] = self.NormalBattle_MaxTimes.value()
            my_opt["normal_battle"]["stage"] = self.NormalBattle_Stage.text()
            my_opt["normal_battle"]["deck"] = self.NormalBattle_Deck.value()
            my_transformer_b(self.NormalBattle_1P, "normal_battle", "battle_plan_1p")
            my_transformer_b(self.NormalBattle_2P, "normal_battle", "battle_plan_2p")

            my_opt["offer_reward"]["active"] = self.OfferReward_Active.isChecked()
            my_opt["offer_reward"]["deck"] = self.OfferReward_Deck.value()
            my_opt["offer_reward"]["max_times_1"] = self.OfferReward_MaxTimes_1.value()
            my_opt["offer_reward"]["max_times_2"] = self.OfferReward_MaxTimes_2.value()
            my_opt["offer_reward"]["max_times_3"] = self.OfferReward_MaxTimes_3.value()

            my_transformer_b(self.OfferReward_1P, "offer_reward", "battle_plan_1p")
            my_transformer_b(self.OfferReward_2P, "offer_reward", "battle_plan_2p")

            my_opt["cross_server"]["active"] = self.CrossServer_Active.isChecked()
            my_opt["cross_server"]["is_group"] = self.CrossServer_Group.isChecked()
            my_opt["cross_server"]["max_times"] = self.CrossServer_MaxTimes.value()
            my_opt["cross_server"]["stage"] = self.CrossServer_Stage.text()
            my_opt["cross_server"]["deck"] = self.CrossServer_Deck.value()
            my_transformer_b(self.CrossServer_1P, "cross_server", "battle_plan_1p")
            my_transformer_b(self.CrossServer_2P, "cross_server", "battle_plan_2p")

            # 公会任务 工会副本 情侣任务 火山遗迹

            my_opt["quest_guild"]["active"] = self.QuestGuild_Active.isChecked()
            my_opt["quest_guild"]["stage"] = self.QuestGuild_Stage.isChecked()
            my_opt["quest_guild"]["deck"] = self.QuestGuild_Deck.value()
            my_transformer_b(self.QuestGuild_1P, "quest_guild", "battle_plan_1p")
            my_transformer_b(self.QuestGuild_2P, "quest_guild", "battle_plan_2p")

            my_opt["guild_dungeon"]["active"] = self.GuildDungeon_Active.isChecked()

            my_opt["quest_spouse"]["active"] = self.QuestSpouse_Active.isChecked()

            my_opt["relic"]["active"] = self.Relic_Active.isChecked()
            my_opt["relic"]["is_group"] = self.Relic_Group.isChecked()
            my_opt["relic"]["max_times"] = self.Relic_MaxTimes.value()
            my_opt["relic"]["stage"] = self.Relic_Stage.text()
            my_opt["relic"]["deck"] = self.Relic_Deck.value()
            my_transformer_b(self.Relic_1P, "relic", "battle_plan_1p")
            my_transformer_b(self.Relic_2P, "relic", "battle_plan_2p")

            # 魔塔 萌宠神殿

            my_opt["magic_tower_alone_1"]["active"] = self.MagicTowerAlone1_Active.isChecked()
            my_opt["magic_tower_alone_1"]["max_times"] = self.MagicTowerAlone1_MaxTimes.value()
            my_opt["magic_tower_alone_1"]["stage"] = self.MagicTowerAlone1_Stage.value()
            my_opt["magic_tower_alone_1"]["deck"] = self.MagicTowerAlone1_Deck.value()
            my_transformer_b(self.MagicTowerAlone1_1P, "magic_tower_alone_1", "battle_plan_1p")

            my_opt["magic_tower_alone_2"]["active"] = self.MagicTowerAlone2_Active.isChecked()
            my_opt["magic_tower_alone_2"]["max_times"] = self.MagicTowerAlone2_MaxTimes.value()
            my_opt["magic_tower_alone_2"]["stage"] = self.MagicTowerAlone2_Stage.value()
            my_opt["magic_tower_alone_2"]["deck"] = self.MagicTowerAlone2_Deck.value()
            my_transformer_b(self.MagicTowerAlone2_1P, "magic_tower_alone_2", "battle_plan_1p")

            my_opt["magic_tower_prison_1"]["active"] = self.MagicTowerPrison1_Active.isChecked()
            my_opt["magic_tower_prison_1"]["stage"] = self.MagicTowerPrison1_Stage.isChecked()
            my_opt["magic_tower_prison_1"]["deck"] = self.MagicTowerPrison1_Deck.value()
            my_transformer_b(self.MagicTowerPrison1_1P, "magic_tower_prison_1", "battle_plan_1p")

            my_opt["magic_tower_prison_2"]["active"] = self.MagicTowerPrison2_Active.isChecked()
            my_opt["magic_tower_prison_2"]["stage"] = self.MagicTowerPrison2_Stage.isChecked()
            my_opt["magic_tower_prison_2"]["deck"] = self.MagicTowerPrison2_Deck.value()
            my_transformer_b(self.MagicTowerPrison2_1P, "magic_tower_prison_2", "battle_plan_1p")

            my_opt["magic_tower_double"]["active"] = self.MagicTowerDouble_Active.isChecked()
            my_opt["magic_tower_double"]["max_times"] = self.MagicTowerDouble_MaxTimes.value()
            my_opt["magic_tower_double"]["stage"] = self.MagicTowerDouble_Stage.value()
            my_opt["magic_tower_double"]["deck"] = self.MagicTowerDouble_Deck.value()
            my_transformer_b(self.MagicTowerDouble_1P, "magic_tower_double", "battle_plan_1p")
            my_transformer_b(self.MagicTowerDouble_2P, "magic_tower_double", "battle_plan_2p")

            my_opt["pet_temple_1"]["active"] = self.PetTemple1_Active.isChecked()
            my_opt["pet_temple_1"]["stage"] = self.PetTemple1_Stage.value()
            my_opt["pet_temple_1"]["deck"] = self.PetTemple1_Deck.value()
            my_transformer_b(self.PetTemple1_1P, "pet_temple_1", "battle_plan_1p")

            my_opt["pet_temple_2"]["active"] = self.PetTemple2_Active.isChecked()
            my_opt["pet_temple_2"]["stage"] = self.PetTemple2_Stage.value()
            my_opt["pet_temple_2"]["deck"] = self.PetTemple2_Deck.value()
            my_transformer_b(self.PetTemple2_1P, "pet_temple_2", "battle_plan_1p")

            # 附加功能

            my_opt["receive_awards"]["active"] = self.ReceiveAwards_Active.isChecked()
            my_opt["receive_awards"]["is_group"] = self.ReceiveAwards_Group.isChecked()

            my_opt["use_items"]["active"] = self.UseItems_Active.isChecked()
            my_opt["use_items"]["is_group"] = self.UseItems_Group.isChecked()

            my_opt["loop_cross_server"]["active"] = self.LoopCrossServer_Active.isChecked()
            my_opt["loop_cross_server"]["is_group"] = self.LoopCrossServer_Group.isChecked()

            my_opt["customize_battle"]["active"] = self.CustomizeBattle_Active.isChecked()
            my_opt["customize_battle"]["is_group"] = self.CustomizeBattle_Group.currentIndex()  # combobox 序号
            my_opt["customize_battle"]["max_times"] = self.CustomizeBattle_MaxTimes.value()
            my_opt["customize_battle"]["deck"] = self.CustomizeBattle_Deck.value()
            my_transformer_b(self.CustomizeBattle_1P, "customize_battle", "battle_plan_1p")
            my_transformer_b(self.CustomizeBattle_2P, "customize_battle", "battle_plan_2p")

            my_opt["customize"]["active"] = self.Customize_Active.isChecked()
            my_opt["customize"]["stage"] = self.Customize_Stage.value()
            my_transformer_c(self.Customize_1P, "customize", "battle_plan_1p")

            my_opt["auto_food"]["active"] = self.AutoFood_Active.isChecked()
            my_opt["auto_food"]["deck"] = self.AutoFood_Deck.value()

        base_settings()
        timer_settings()
        advanced_settings()
        get_warm_gift_settings()
        level_2()
        self.opt["current_plan"] = self.CurrentPlan.currentIndex()  # combobox 序号
        todo_plans()

    def click_btn_save(self):
        """点击保存配置按钮的函数"""
        self.ui_to_opt()
        self.opt_to_json()

    def delete_current_plan(self):
        """用来删掉当前被选中的 todo plan 但不能删掉默认方案"""
        if self.CurrentPlan.currentIndex() == 0:
            QMessageBox.information(self, "警告", "默认方案不能删除呢...")
            return
        del self.opt["todo_plans"][self.CurrentPlan.currentIndex()]
        # 重载ui
        self.init_opt_to_ui()

    def rename_current_plan(self):
        """用来重命名当前被选中的 todo plan 但不能重命名默认方案"""
        if self.CurrentPlan.currentIndex() == 0:
            QMessageBox.information(self, "警告", "默认方案不能重命名呢...")
            return
        self.opt["todo_plans"][self.CurrentPlan.currentIndex()]["name"] = copy.deepcopy(self.RenamePlan_Input.text())
        # 重载ui
        self.init_opt_to_ui()

    def create_new_plan(self):
        """新建一个 todo plan, 但不能取名为Default"""
        if self.CreatePlan_Input == "Default":
            QMessageBox.information(self, "警告", "不能使用 Default 作为新的 TodoPlan 名呢...")
            return
        # 注意深拷贝
        self.opt["todo_plans"].append(copy.deepcopy(self.opt["todo_plans"][0]))
        self.opt["todo_plans"][-1]["name"] = copy.deepcopy(self.CreatePlan_Input.text())
        # 重载ui
        self.init_opt_to_ui()


if __name__ == "__main__":
    def main():
        # 实例化 PyQt后台管理
        app = QApplication(sys.argv)

        # 实例化 主窗口
        window = QMainWindowLoadSettings()

        # 建立槽连接 注意 多线程中 槽连接必须写在主函数
        # 注册函数：开始/结束按钮
        button = window.Button_Start
        button.clicked.connect(lambda: window.click_btn_start())
        button = window.Button_Save
        button.clicked.connect(lambda: window.click_btn_save())
        button = window.Button_AdvancedSettings
        button.clicked.connect(lambda: window.click_btn_advanced_settings())
        # 主窗口 实现
        window.show()

        # 运行主循环，必须调用此函数才可以开始事件处理
        sys.exit(app.exec_())


    main()
