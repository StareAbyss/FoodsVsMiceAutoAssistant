import copy
import json
import os
import shutil
import sys

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog

from function.core.QMW_1_log import QMainWindowLog
from function.globals import EXTRA, SIGNAL
from function.globals import g_resources
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.scattered.check_battle_plan import fresh_and_check_all_battle_plan
from function.scattered.get_list_battle_plan import get_list_battle_plan
from function.scattered.get_task_sequence_list import get_task_sequence_list
from function.scattered.test_route_connectivity import test_route_connectivity


def ensure_file_exists(file_path, template_suffix="_template") -> None:
    """
    测某文件是否存在 如果不存在且存在_template的模板, 应用模板
    :param file_path: 文件路径
    :param template_suffix: 模板附加名称
    :return:
    """

    # 检查文件是否存在
    if not os.path.exists(file_path):
        # 构建模板文件的路径
        base_name, ext = os.path.splitext(file_path)
        template_file_path = f"{base_name}{template_suffix}{ext}"

        # 检查模板文件是否存在
        if os.path.exists(template_file_path):
            # 如果模板文件存在，则复制模板文件到原始文件路径
            shutil.copy(template_file_path, file_path)
            CUS_LOGGER.warning(f"[资源检查] '{file_path}' 不存在，已从模板 '{template_file_path}' 创建。")
        else:
            CUS_LOGGER.error(f"[资源检查] 无 '{file_path}', 无 '{template_file_path}'. ")
    else:
        CUS_LOGGER.info(f"[资源检查] '{file_path}' 已存在. 直接读取.")


class QMainWindowLoadSettings(QMainWindowLog):
    """将读取配置的方法封装在此处"""

    def __init__(self):
        # 继承父类构造方法
        super().__init__()

        # opt路径
        self.opt_path = PATHS["root"] + "\\config\\settings.json"

        # 检测某文件是否存在 如果不存在且存在_template的模板, 应用模板
        ensure_file_exists_tar_list = [
            PATHS["root"] + "\\config\\cus_images\\用户自截\\空间服登录界面_1P.png",
            PATHS["root"] + "\\config\\cus_images\\用户自截\\空间服登录界面_2P.png",
            PATHS["root"] + "\\config\\cus_images\\用户自截\\跨服远征_1p.png",
            self.opt_path]
        for file_path in ensure_file_exists_tar_list:
            ensure_file_exists(file_path=file_path)

        # 检测&修复 settings文件和模板的格式是否对应.
        self.correct_settings_file()

        # 检测uuid是否存在于battle plan 没有则添加 并将其读入到内存资源中
        fresh_and_check_all_battle_plan()

        # 更新完毕后重新刷新对应资源
        g_resources.fresh_resource_cus_img()
        g_resources.fresh_resource_b()

        # 从json文件中读取opt 并刷新ui
        self.opt = None
        self.json_to_opt()
        self.init_opt_to_ui()

        # 记录读取时 是否有战斗方案找不到了
        self.cant_find_battle_plan_in_uuid = False

    def correct_settings_file(self, template_suffix="_template") -> None:
        """
        检查settings.json 是否和 template.json
        各级的字段名和数据类型是否一致, 如果不一致, 应用模板
        :param template_suffix: 模板附加名称
        :return: None
        """

        # 构建模板文件的路径
        file_path = self.opt_path
        base_name, ext = os.path.splitext(file_path)
        template_file_path = f"{base_name}{template_suffix}{ext}"

        # 如果值为list 使用template中第一个值作为模板对照进行merge
        def merge_settings_with_template(settings, template):
            def merge(dict1, dict2):
                for key, value in dict2.items():
                    if key not in dict1:
                        dict1[key] = copy.deepcopy(value)
                    else:
                        if isinstance(value, dict):
                            if isinstance(dict1[key], dict):
                                merge(dict1[key], value)
                            else:
                                dict1[key] = copy.deepcopy(value)
                        elif isinstance(value, list):
                            if isinstance(dict1[key], list):
                                if len(dict1[key]) > 0 and isinstance(dict1[key][0], dict):
                                    sample_dict = value[0]
                                    for i, item in enumerate(dict1[key]):
                                        if isinstance(item, dict):
                                            merge(item, sample_dict)
                                        else:
                                            dict1[key] = copy.deepcopy(value)
                                            break
                            else:
                                dict1[key] = copy.deepcopy(value)
                        else:
                            if not isinstance(dict1[key], type(value)):
                                dict1[key] = copy.deepcopy(value)

            settings_copy = copy.deepcopy(settings)
            merge(settings_copy, template)
            return settings_copy

        CUS_LOGGER.info(f"[订正FAA基础配置文件] 订正开始.")

        # 自旋锁读写, 防止多线程读写问题
        with EXTRA.FILE_LOCK:

            with open(file=file_path, mode="r", encoding="UTF-8") as file:
                data_settings = json.load(file)
            with open(file=template_file_path, mode="r", encoding="UTF-8") as file:
                data_template = json.load(file)

            data_settings = merge_settings_with_template(settings=data_settings, template=data_template)
            with open(file=self.opt_path, mode="w", encoding="UTF-8") as file:
                json.dump(obj=data_settings, fp=file, ensure_ascii=False, indent=4)

        CUS_LOGGER.info(f"[订正FAA基础配置文件] 订正完成.")

        return None

    """opt和json的交互"""

    def json_to_opt(self) -> None:
        # 自旋锁读写, 防止多线程读写问题
        with EXTRA.FILE_LOCK:
            with open(file=self.opt_path, mode="r", encoding="UTF-8") as file:
                data = json.load(file)

        self.opt = data
        return None

    def opt_to_json(self) -> None:
        # dict → str 转换True和true
        json_str = json.dumps(self.opt, indent=4)

        with EXTRA.FILE_LOCK:
            with open(file=self.opt_path, mode="w", encoding="UTF-8") as file:
                file.write(json_str)

        return None

    """ui和opt的交互"""

    def cant_find_battle_plan_in_uuid_show_dialog(self) -> None:
        # 一个提示弹窗
        if self.cant_find_battle_plan_in_uuid:
            QMessageBox.information(
                self,
                "警告",
                "您删除了被配置使用的战斗方案.\n对应的战斗方案已恢复为默认方案! 请点击保存配置!",
                QMessageBox.StandardButton.Ok
            )

    def opt_to_ui_todo_plans(self) -> None:
        """
        先从ui上读取目前todo plan index, 然后从opt读取对应的设置到todo plan 配置界面
        :return:
        """
        battle_plan_name_list = get_list_battle_plan(with_extension=False)
        battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())
        task_sequence_list = get_task_sequence_list(with_extension=False)
        self.cant_find_battle_plan_in_uuid = False

        def init_battle_plan(tar_widget, opt):
            # 初始化每一项和对应的内部数据 uuid
            tar_widget.clear()
            for index in range(len(battle_plan_name_list)):
                tar_widget.addItem(
                    battle_plan_name_list[index],
                    {"uuid": battle_plan_uuid_list[index]})
            # 根据uuid 设定当前选中项
            try:
                index = battle_plan_uuid_list.index(opt)
            except ValueError:
                index = battle_plan_uuid_list.index("00000000-0000-0000-0000-000000000000")
                self.cant_find_battle_plan_in_uuid = True
            tar_widget.setCurrentIndex(index)

        # 先重新获取ui上的 当前方案选项
        self.opt["current_plan"] = self.CurrentPlan.currentIndex()  # combobox 序号
        # 修改当前方案文本
        self.CurrentPlan_Label_Change.setText(self.CurrentPlan.currentText())

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
        self.Warrior_Deck.setCurrentIndex(my_opt["warrior"]["deck"] - 1)
        init_battle_plan(self.Warrior_1P, my_opt["warrior"]["battle_plan_1p"])
        init_battle_plan(self.Warrior_2P, my_opt["warrior"]["battle_plan_2p"])

        # 常规单本 悬赏任务 跨服任务

        self.NormalBattle_Active.setChecked(my_opt["normal_battle"]["active"])
        self.NormalBattle_Group.setChecked(my_opt["normal_battle"]["is_group"])
        self.NormalBattle_MaxTimes.setValue(my_opt["normal_battle"]["max_times"])
        self.NormalBattle_Stage.setText(my_opt["normal_battle"]["stage"])
        self.NormalBattle_Deck.setCurrentIndex(my_opt["normal_battle"]["deck"] - 1)
        init_battle_plan(self.NormalBattle_1P, my_opt["normal_battle"]["battle_plan_1p"])
        init_battle_plan(self.NormalBattle_2P, my_opt["normal_battle"]["battle_plan_2p"])

        self.OfferReward_Active.setChecked(my_opt["offer_reward"]["active"])
        self.OfferReward_MaxTimes_1.setText(str(my_opt["offer_reward"]["max_times_1"]))
        self.OfferReward_MaxTimes_2.setText(str(my_opt["offer_reward"]["max_times_2"]))
        self.OfferReward_MaxTimes_3.setText(str(my_opt["offer_reward"]["max_times_3"]))
        self.OfferReward_Deck.setCurrentIndex(my_opt["offer_reward"]["deck"] - 1)
        init_battle_plan(self.OfferReward_1P, my_opt["offer_reward"]["battle_plan_1p"])
        init_battle_plan(self.OfferReward_2P, my_opt["offer_reward"]["battle_plan_2p"])

        self.CrossServer_Active.setChecked(my_opt["cross_server"]["active"])
        self.CrossServer_Group.setChecked(my_opt["cross_server"]["is_group"])
        self.CrossServer_MaxTimes.setValue(my_opt["cross_server"]["max_times"])
        self.CrossServer_Stage.setText(my_opt["cross_server"]["stage"])
        self.CrossServer_Deck.setCurrentIndex(my_opt["cross_server"]["deck"] - 1)
        init_battle_plan(self.CrossServer_1P, my_opt["cross_server"]["battle_plan_1p"])
        init_battle_plan(self.CrossServer_2P, my_opt["cross_server"]["battle_plan_2p"])

        # 公会任务 工会副本 情侣任务 火山遗迹

        self.QuestGuild_Active.setChecked(my_opt["quest_guild"]["active"])
        self.QuestGuild_Stage.setChecked(my_opt["quest_guild"]["stage"])
        self.QuestGuild_Deck.setCurrentIndex(my_opt["quest_guild"]["deck"] - 1)
        init_battle_plan(self.QuestGuild_1P, my_opt["quest_guild"]["battle_plan_1p"])
        init_battle_plan(self.QuestGuild_2P, my_opt["quest_guild"]["battle_plan_2p"])

        self.GuildDungeon_Active.setChecked(my_opt["guild_dungeon"]["active"])

        self.QuestSpouse_Active.setChecked(my_opt["quest_spouse"]["active"])

        self.Relic_Active.setChecked(my_opt["relic"]["active"])
        self.Relic_Group.setChecked(my_opt["relic"]["is_group"])
        self.Relic_MaxTimes.setValue(my_opt["relic"]["max_times"])
        self.Relic_Stage.setText(my_opt["relic"]["stage"])
        self.Relic_Deck.setCurrentIndex(my_opt["relic"]["deck"] - 1)
        init_battle_plan(self.Relic_1P, my_opt["relic"]["battle_plan_1p"])
        init_battle_plan(self.Relic_2P, my_opt["relic"]["battle_plan_2p"])

        # 魔塔 萌宠神殿

        self.MagicTowerAlone1_Active.setChecked(my_opt["magic_tower_alone_1"]["active"])
        self.MagicTowerAlone1_MaxTimes.setValue(my_opt["magic_tower_alone_1"]["max_times"])
        self.MagicTowerAlone1_Stage.setValue(my_opt["magic_tower_alone_1"]["stage"])
        self.MagicTowerAlone1_Deck.setCurrentIndex(my_opt["magic_tower_alone_1"]["deck"] - 1)
        init_battle_plan(self.MagicTowerAlone1_1P, my_opt["magic_tower_alone_1"]["battle_plan_1p"])

        self.MagicTowerAlone2_Active.setChecked(my_opt["magic_tower_alone_2"]["active"])
        self.MagicTowerAlone2_MaxTimes.setValue(my_opt["magic_tower_alone_2"]["max_times"])
        self.MagicTowerAlone2_Stage.setValue(my_opt["magic_tower_alone_2"]["stage"])
        self.MagicTowerAlone2_Deck.setCurrentIndex(my_opt["magic_tower_alone_2"]["deck"] - 1)
        init_battle_plan(self.MagicTowerAlone2_1P, my_opt["magic_tower_alone_2"]["battle_plan_1p"])

        self.MagicTowerPrison1_Active.setChecked(my_opt["magic_tower_prison_1"]["active"])
        self.MagicTowerPrison1_Stage.setChecked(my_opt["magic_tower_prison_1"]["stage"])
        self.MagicTowerPrison1_Deck.setCurrentIndex(my_opt["magic_tower_prison_1"]["deck"] - 1)
        init_battle_plan(self.MagicTowerPrison1_1P, my_opt["magic_tower_prison_1"]["battle_plan_1p"])

        self.MagicTowerPrison2_Active.setChecked(my_opt["magic_tower_prison_2"]["active"])
        self.MagicTowerPrison2_Stage.setChecked(my_opt["magic_tower_prison_2"]["stage"])
        self.MagicTowerPrison2_Deck.setCurrentIndex(my_opt["magic_tower_prison_2"]["deck"] - 1)
        init_battle_plan(self.MagicTowerPrison2_1P, my_opt["magic_tower_prison_2"]["battle_plan_1p"])

        self.MagicTowerDouble_Active.setChecked(my_opt["magic_tower_double"]["active"])
        self.MagicTowerDouble_Stage.setValue(my_opt["magic_tower_double"]["stage"])
        self.MagicTowerDouble_MaxTimes.setValue(my_opt["magic_tower_double"]["max_times"])
        self.MagicTowerDouble_Deck.setCurrentIndex(my_opt["magic_tower_double"]["deck"] - 1)
        init_battle_plan(self.MagicTowerDouble_1P, my_opt["magic_tower_double"]["battle_plan_1p"])
        init_battle_plan(self.MagicTowerDouble_2P, my_opt["magic_tower_double"]["battle_plan_2p"])

        self.PetTemple1_Active.setChecked(my_opt["pet_temple_1"]["active"])
        self.PetTemple1_Stage.setValue(my_opt["pet_temple_1"]["stage"])
        self.PetTemple1_Deck.setCurrentIndex(my_opt["pet_temple_1"]["deck"] - 1)
        init_battle_plan(self.PetTemple1_1P, my_opt["pet_temple_1"]["battle_plan_1p"])

        self.PetTemple2_Active.setChecked(my_opt["pet_temple_2"]["active"])
        self.PetTemple2_Stage.setValue(my_opt["pet_temple_2"]["stage"])
        self.PetTemple2_Deck.setCurrentIndex(my_opt["pet_temple_2"]["deck"] - 1)
        init_battle_plan(self.PetTemple2_1P, my_opt["pet_temple_2"]["battle_plan_1p"])

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
        self.CustomizeBattle_Deck.setCurrentIndex(my_opt["customize_battle"]["deck"] - 1)
        init_battle_plan(self.CustomizeBattle_1P, my_opt["customize_battle"]["battle_plan_1p"])
        init_battle_plan(self.CustomizeBattle_2P, my_opt["customize_battle"]["battle_plan_2p"])

        # 自定义作战序列
        self.Customize_Active.setChecked(my_opt["customize"]["active"])
        self.Customize_Stage.setValue(my_opt["customize"]["stage"])
        self.Customize_1P.clear()
        self.Customize_1P.addItems(task_sequence_list)
        self.Customize_1P.setCurrentIndex(my_opt["customize"]["battle_plan_1p"])

        self.AutoFood_Active.setChecked(my_opt["auto_food"]["active"])
        self.AutoFood_Deck.setCurrentIndex(my_opt["auto_food"]["deck"] - 1)

        # 一个提示弹窗
        self.cant_find_battle_plan_in_uuid_show_dialog()

    def init_opt_to_ui(self) -> None:
        # comboBox.setCurrentIndex时 如果超过了已有预设 会显示为空 不会报错
        # comboBox.clear时 会把所有选项设定为默认选项

        todo_plan_name_list = [plan["name"] for plan in self.opt["todo_plans"]]

        def base_settings() -> None:
            my_opt = self.opt["base_settings"]
            self.GameName_Input.setText(my_opt["game_name"])
            self.Name1P_Input.setText(my_opt["name_1p"])
            self.Name2P_Input.setText(my_opt["name_2p"])
            self.ZoomRatio_Output.setText(str(self.zoom_rate) + "(自动)")
            self.Level1P_Input.setValue(my_opt["level_1p"])
            self.Level2P_Input.setValue(my_opt["level_2p"])

        def timer_settings() -> None:
            h_validator = QRegularExpressionValidator(QRegularExpression(r"^(?:[01][0-9]|2[0-3])$"))
            m_validator = QRegularExpressionValidator(QRegularExpression(r"^[0-5]?[0-9]$"))

            for timer_index in range(1, 6):
                my_opt = self.opt["timer"][f"{timer_index}"]
                getattr(self, f"Timer{timer_index}_Active").setChecked(my_opt["active"])

                # 格式化小时和分钟
                h_text = str(my_opt["h"]).zfill(2)
                m_text = str(my_opt["m"]).zfill(2)

                getattr(self, f"Timer{timer_index}_H").setText(h_text)
                getattr(self, f"Timer{timer_index}_M").setText(m_text)

                getattr(self, f"Timer{timer_index}_Plan").clear()
                getattr(self, f"Timer{timer_index}_Plan").addItems(todo_plan_name_list)
                getattr(self, f"Timer{timer_index}_Plan").setCurrentIndex(my_opt["plan"])

                getattr(self, f"Timer{timer_index}_H").setValidator(h_validator)
                getattr(self, f"Timer{timer_index}_M").setValidator(m_validator)

        def advanced_settings() -> None:
            my_opt = self.opt["advanced_settings"]
            # 高级配置页
            self.AutoPickUp_1P.setChecked(my_opt["auto_pickup_1p"])
            self.AutoPickUp_2P.setChecked(my_opt["auto_pickup_2p"])
            self.TopUpMoney_1P.setChecked(my_opt["top_up_money_1p"])
            self.TopUpMoney_2P.setChecked(my_opt["top_up_money_2p"])
            self.EndExitGame.setChecked(my_opt["end_exit_game"])
            self.AutoUseCard.setChecked(my_opt["auto_use_card"])

            # 其他放在此分类的配置
            self.GuildManager_Active.setCurrentIndex(my_opt["guild_manager_active"])

            # 点击频率
            self.CusCPS_Active.setChecked(my_opt["cus_cps_active"])
            self.CusCPS_Value.setValue(my_opt["cus_cps_value"])
            EXTRA.CLICK_PER_SECOND = my_opt["cus_cps_value"] if my_opt["cus_cps_active"] else 120

            # 最低FPS
            self.CusLowestFPS_Active.setChecked(my_opt["cus_lowest_fps_active"])
            self.CusLowestFPS_Value.setValue(my_opt["cus_lowest_fps_value"])
            EXTRA.LOWEST_FPS = my_opt["cus_lowest_fps_value"] if my_opt["cus_lowest_fps_active"] else 10

            # link 加载的时候不做校验
            self.MisuLogistics_Link.setText(my_opt["misu_logistics_link"])

        def senior_settings() -> None:
            my_opt = self.opt["senior_settings"]
            self.Battle_senior_checkedbox.setChecked(my_opt["auto_senior_settings"])
            self.Battle_senior_gpu.setChecked(my_opt["gpu_settings"])
            self.Advance_battle_interval_Value.setValue(my_opt["interval"])
            self.Battle_senior_checkedbox.stateChanged.connect(self.on_checkbox_state_changed)
            self.all_senior_log.setEnabled(my_opt["auto_senior_settings"])
            self.Battle_senior_gpu.setEnabled(my_opt["auto_senior_settings"])
            self.indeed_need.setEnabled(my_opt["auto_senior_settings"])
            if my_opt["senior_log_state"]:
                self.all_senior_log.setChecked(True)
            else:
                self.indeed_need.setChecked(True)

        def log_settings() -> None:
            my_opt = self.opt["log_settings"]
            self.senior_log_clean.setValue(my_opt["log_senior_settings"])
            self.other_log_clean.setValue(my_opt["log_other_settings"])

        def get_warm_gift_settings() -> None:
            my_opt = self.opt["get_warm_gift"]
            self.GetWarmGift_1P_Active.setChecked(my_opt["1p"]["active"])
            self.GetWarmGift_1P_Link.setText(my_opt["1p"]["link"])
            self.GetWarmGift_2P_Active.setChecked(my_opt["2p"]["active"])
            self.GetWarmGift_2P_Link.setText(my_opt["2p"]["link"])

        def level_2() -> None:
            my_opt = self.opt["level_2"]
            self.Level2_1P_Active.setChecked(my_opt["1p"]["active"])
            self.Level2_1P_Password.setText(my_opt["1p"]["password"])
            self.Level2_2P_Active.setChecked(my_opt["2p"]["active"])
            self.Level2_2P_Password.setText(my_opt["2p"]["password"])

        def skin_set() -> None:
            my_opt = self.opt["skin_type"]
            skin_dict = {
                1: self.skin1,
                2: self.skin2,
                3: self.skin3,
                4: self.skin4,
                5: self.skin5,
                6: self.skin6,
                7: self.skin7,
                8: self.skin8,
                9: self.skin9,
                10: self.skin10,
                11: self.skin11
            }

            # 使用 get 方法设置皮肤
            skin = skin_dict.get(my_opt)
            if skin:
                skin.setChecked(True)
            styleFile = self.getstylefile(my_opt)
            if styleFile is not None:
                qssStyle = CommonHelper.readQss(styleFile)
                self.set_theme_common()
                self.MainFrame.setStyleSheet(qssStyle)
                self.set_common_theme()


            else:
                self.set_theme_common()
                self.set_theme_default()
                self.set_common_theme()

            # 设置信号和槽
            self.skin1.toggled.connect(self.on_skin_state_changed)
            self.skin2.toggled.connect(self.on_skin_state_changed)
            self.skin3.toggled.connect(self.on_skin_state_changed)
            self.skin4.toggled.connect(self.on_skin_state_changed)
            self.skin5.toggled.connect(self.on_skin_state_changed)
            self.skin6.toggled.connect(self.on_skin_state_changed)
            self.skin7.toggled.connect(self.on_skin_state_changed)
            self.skin8.toggled.connect(self.on_skin_state_changed)
            self.skin9.toggled.connect(self.on_skin_state_changed)
            self.skin10.toggled.connect(self.on_skin_state_changed)
            self.skin11.toggled.connect(self.on_skin_state_changed)

        base_settings()
        timer_settings()
        advanced_settings()
        senior_settings()
        get_warm_gift_settings()
        log_settings()
        level_2()
        skin_set()

        self.CurrentPlan.clear()
        self.CurrentPlan.addItems(todo_plan_name_list)
        self.CurrentPlan.setCurrentIndex(self.opt["current_plan"])
        self.opt_to_ui_todo_plans()

    def ui_to_opt(self) -> None:

        self.cant_find_battle_plan_in_uuid = False

        # battle_plan_list
        battle_plan_name_list_new = get_list_battle_plan(with_extension=False)
        task_sequence_list = get_task_sequence_list(with_extension=False)

        # 检测uuid是否存在于 可能新加入的 battle plan 没有则添加 并将其读入到内存资源中
        fresh_and_check_all_battle_plan()
        g_resources.fresh_resource_b()

        # 新的uuid list
        battle_plan_uuid_list_new = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

        def my_transformer_b(tar_widget: object, opt_1, opt_2) -> None:
            """用于配置 带有选单的 战斗方案"""

            # 根据更新前的数据, 获取index对应的正确uuid 并写入到opt
            ui_uuid = tar_widget.itemData(tar_widget.currentIndex())['uuid']
            self.opt["todo_plans"][self.opt["current_plan"]][opt_1][opt_2] = ui_uuid

            # 根据新的数据, 重新生成每一个列表的元素 根据uuid重新定向一次index
            tar_widget.clear()
            for index in range(len(battle_plan_name_list_new)):
                tar_widget.addItem(
                    battle_plan_name_list_new[index],
                    {"uuid": battle_plan_uuid_list_new[index]})

            # 根据uuid 设定当前选中项
            try:
                index = battle_plan_uuid_list_new.index(ui_uuid)
            except ValueError:
                index = battle_plan_uuid_list_new.index("00000000-0000-0000-0000-000000000000")
                self.cant_find_battle_plan_in_uuid = True
            tar_widget.setCurrentIndex(index)

        def my_transformer_c(change_class: object, opt_1, opt_2) -> None:
            """用于配置 带有选单的 自定义作战序列"""

            self.opt["todo_plans"][self.opt["current_plan"]][opt_1][opt_2] = change_class.currentIndex()
            change_class.clear()
            change_class.addItems(task_sequence_list)
            change_class.setCurrentIndex(self.opt["todo_plans"][self.opt["current_plan"]][opt_1][opt_2])

        def base_settings() -> None:
            my_opt = self.opt["base_settings"]
            my_opt["game_name"] = self.GameName_Input.text()
            my_opt["name_1p"] = self.Name1P_Input.text()
            my_opt["name_2p"] = self.Name2P_Input.text()
            self.ZoomRatio_Output.setText(str(self.zoom_rate) + "(自动)")
            my_opt["level_1p"] = self.Level1P_Input.value()
            my_opt["level_2p"] = self.Level2P_Input.value()

        def timer_settings() -> None:
            for i in range(1, 6):
                my_opt = self.opt["timer"][f"{i}"]
                my_opt["active"] = getattr(self, f"Timer{i}_Active").isChecked()
                my_opt["h"] = int(getattr(self, f"Timer{i}_H").text())
                my_opt["m"] = int(getattr(self, f"Timer{i}_M").text())
                my_opt["plan"] = getattr(self, f"Timer{i}_Plan").currentIndex()

        def advanced_settings() -> None:
            my_opt = self.opt["advanced_settings"]
            # 高级配置页
            my_opt["auto_pickup_1p"] = self.AutoPickUp_1P.isChecked()
            my_opt["auto_pickup_2p"] = self.AutoPickUp_2P.isChecked()
            my_opt["top_up_money_1p"] = self.TopUpMoney_1P.isChecked()
            my_opt["top_up_money_2p"] = self.TopUpMoney_2P.isChecked()
            my_opt["end_exit_game"] = self.EndExitGame.isChecked()
            my_opt["auto_use_card"] = self.AutoUseCard.isChecked()

            # 其他放在此分类的配置
            my_opt["guild_manager_active"] = self.GuildManager_Active.currentIndex()

            # 点击频率
            my_opt["cus_cps_active"] = self.CusCPS_Active.isChecked()
            my_opt["cus_cps_value"] = self.CusCPS_Value.value()
            EXTRA.CLICK_PER_SECOND = my_opt["cus_cps_value"] if my_opt["cus_cps_active"] else 120

            # 最低FPS
            my_opt["cus_lowest_fps_active"] = self.CusLowestFPS_Active.isChecked()
            my_opt["cus_lowest_fps_value"] = self.CusLowestFPS_Value.value()
            EXTRA.LOWEST_FPS = my_opt["cus_lowest_fps_value"] if my_opt["cus_lowest_fps_active"] else 10

            # link 需要额外的检查
            url = self.MisuLogistics_Link.text()
            result_bool, _ = test_route_connectivity(url=url)

            if url != "":
                if result_bool:
                    my_opt["misu_logistics_link"] = url
                    SIGNAL.PRINT_TO_UI.emit(
                        text=f"FAA X 米苏物流 连通性测试 使用非默认url:{url} 成功!", color_level=3)
                else:
                    SIGNAL.PRINT_TO_UI.emit(
                        text=f"FAA X 米苏物流 连通性测试 使用非默认url:{url} 失败! 将修正为默认url重试", color_level=1)
                    url = ""
                    my_opt["misu_logistics_link"] = url
                    self.MisuLogistics_Link.setText(url)
                    result_bool, _ = test_route_connectivity(url=url)

            if url == "":
                if result_bool:
                    my_opt["misu_logistics_link"] = url
                    SIGNAL.PRINT_TO_UI.emit(
                        text=f"FAA X 米苏物流 连通性测试 使用默认url 成功!", color_level=3)
                else:
                    SIGNAL.PRINT_TO_UI.emit(
                        text=f"FAA X 米苏物流 连通性测试 使用默认url 失败!", color_level=1)
                    SIGNAL.PRINT_TO_UI.emit(
                        text=f"内置url可能已过期, 推荐更新url, 以防请求等待超时, 降低战斗效率!!!", color_level=1)

        def senior_settings() -> None:
            my_opt = self.opt["senior_settings"]
            my_opt["auto_senior_settings"] = self.Battle_senior_checkedbox.isChecked()
            my_opt["senior_log_state"] = 1 if self.all_senior_log.isChecked() else 0
            my_opt["gpu_settings"] = self.Battle_senior_gpu.isChecked()
            my_opt["interval"] = self.Advance_battle_interval_Value.value()

        def skin_settings() -> None:
            # 定义一个字典，将复选框对象映射到对应的值
            skin_dict = {
                self.skin1: 1,
                self.skin2: 2,
                self.skin3: 3,
                self.skin4: 4,
                self.skin5: 5,
                self.skin6: 6,
                self.skin7: 7,
                self.skin8: 8,
                self.skin9: 9,
                self.skin10: 10,
                self.skin11: 11
            }

            # 遍历字典，找到第一个被选中的复选框
            for skin, option in skin_dict.items():
                if skin.isChecked():
                    self.opt["skin_type"] = option
                    break

        def log_settings() -> None:
            my_opt = self.opt["log_settings"]
            my_opt["log_senior_settings"] = self.senior_log_clean.value()
            my_opt["log_other_settings"] = self.other_log_clean.value()

        def get_warm_gift_settings() -> None:
            my_opt = self.opt["get_warm_gift"]
            my_opt["1p"]["active"] = self.GetWarmGift_1P_Active.isChecked()
            my_opt["1p"]["link"] = self.GetWarmGift_1P_Link.text()
            my_opt["2p"]["active"] = self.GetWarmGift_2P_Active.isChecked()
            my_opt["2p"]["link"] = self.GetWarmGift_2P_Link.text()

        def level_2() -> None:
            my_opt = self.opt["level_2"]
            my_opt["1p"]["active"] = self.Level2_1P_Active.isChecked()
            my_opt["1p"]["password"] = self.Level2_1P_Password.text()
            my_opt["2p"]["active"] = self.Level2_2P_Active.isChecked()
            my_opt["2p"]["password"] = self.Level2_2P_Password.text()

        def todo_plans() -> None:
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
            my_opt["warrior"]["deck"] = self.Warrior_Deck.currentIndex() + 1
            my_transformer_b(self.Warrior_1P, "warrior", "battle_plan_1p")
            my_transformer_b(self.Warrior_2P, "warrior", "battle_plan_2p")

            # 常规单本 悬赏任务 跨服任务

            my_opt["normal_battle"]["active"] = self.NormalBattle_Active.isChecked()
            my_opt["normal_battle"]["is_group"] = self.NormalBattle_Group.isChecked()
            my_opt["normal_battle"]["max_times"] = self.NormalBattle_MaxTimes.value()
            my_opt["normal_battle"]["stage"] = self.NormalBattle_Stage.text()
            my_opt["normal_battle"]["deck"] = self.NormalBattle_Deck.currentIndex() + 1
            my_transformer_b(self.NormalBattle_1P, "normal_battle", "battle_plan_1p")
            my_transformer_b(self.NormalBattle_2P, "normal_battle", "battle_plan_2p")

            my_opt["offer_reward"]["active"] = self.OfferReward_Active.isChecked()
            my_opt["offer_reward"]["deck"] = self.OfferReward_Deck.currentIndex() + 1
            my_opt["offer_reward"]["max_times_1"] = int(self.OfferReward_MaxTimes_1.text())
            my_opt["offer_reward"]["max_times_2"] = int(self.OfferReward_MaxTimes_2.text())
            my_opt["offer_reward"]["max_times_3"] = int(self.OfferReward_MaxTimes_3.text())

            my_transformer_b(self.OfferReward_1P, "offer_reward", "battle_plan_1p")
            my_transformer_b(self.OfferReward_2P, "offer_reward", "battle_plan_2p")

            my_opt["cross_server"]["active"] = self.CrossServer_Active.isChecked()
            my_opt["cross_server"]["is_group"] = self.CrossServer_Group.isChecked()
            my_opt["cross_server"]["max_times"] = self.CrossServer_MaxTimes.value()
            my_opt["cross_server"]["stage"] = self.CrossServer_Stage.text()
            my_opt["cross_server"]["deck"] = self.CrossServer_Deck.currentIndex() + 1
            my_transformer_b(self.CrossServer_1P, "cross_server", "battle_plan_1p")
            my_transformer_b(self.CrossServer_2P, "cross_server", "battle_plan_2p")

            # 公会任务 工会副本 情侣任务 火山遗迹

            my_opt["quest_guild"]["active"] = self.QuestGuild_Active.isChecked()
            my_opt["quest_guild"]["stage"] = self.QuestGuild_Stage.isChecked()
            my_opt["quest_guild"]["deck"] = self.QuestGuild_Deck.currentIndex() + 1
            my_transformer_b(self.QuestGuild_1P, "quest_guild", "battle_plan_1p")
            my_transformer_b(self.QuestGuild_2P, "quest_guild", "battle_plan_2p")

            my_opt["guild_dungeon"]["active"] = self.GuildDungeon_Active.isChecked()

            my_opt["quest_spouse"]["active"] = self.QuestSpouse_Active.isChecked()

            my_opt["relic"]["active"] = self.Relic_Active.isChecked()
            my_opt["relic"]["is_group"] = self.Relic_Group.isChecked()
            my_opt["relic"]["max_times"] = self.Relic_MaxTimes.value()
            my_opt["relic"]["stage"] = self.Relic_Stage.text()
            my_opt["relic"]["deck"] = self.Relic_Deck.currentIndex() + 1
            my_transformer_b(self.Relic_1P, "relic", "battle_plan_1p")
            my_transformer_b(self.Relic_2P, "relic", "battle_plan_2p")

            # 魔塔 萌宠神殿

            my_opt["magic_tower_alone_1"]["active"] = self.MagicTowerAlone1_Active.isChecked()
            my_opt["magic_tower_alone_1"]["max_times"] = self.MagicTowerAlone1_MaxTimes.value()
            my_opt["magic_tower_alone_1"]["stage"] = self.MagicTowerAlone1_Stage.value()
            my_opt["magic_tower_alone_1"]["deck"] = self.MagicTowerAlone1_Deck.currentIndex() + 1
            my_transformer_b(self.MagicTowerAlone1_1P, "magic_tower_alone_1", "battle_plan_1p")

            my_opt["magic_tower_alone_2"]["active"] = self.MagicTowerAlone2_Active.isChecked()
            my_opt["magic_tower_alone_2"]["max_times"] = self.MagicTowerAlone2_MaxTimes.value()
            my_opt["magic_tower_alone_2"]["stage"] = self.MagicTowerAlone2_Stage.value()
            my_opt["magic_tower_alone_2"]["deck"] = self.MagicTowerAlone2_Deck.currentIndex() + 1
            my_transformer_b(self.MagicTowerAlone2_1P, "magic_tower_alone_2", "battle_plan_1p")

            my_opt["magic_tower_prison_1"]["active"] = self.MagicTowerPrison1_Active.isChecked()
            my_opt["magic_tower_prison_1"]["stage"] = self.MagicTowerPrison1_Stage.isChecked()
            my_opt["magic_tower_prison_1"]["deck"] = self.MagicTowerPrison1_Deck.currentIndex() + 1
            my_transformer_b(self.MagicTowerPrison1_1P, "magic_tower_prison_1", "battle_plan_1p")

            my_opt["magic_tower_prison_2"]["active"] = self.MagicTowerPrison2_Active.isChecked()
            my_opt["magic_tower_prison_2"]["stage"] = self.MagicTowerPrison2_Stage.isChecked()
            my_opt["magic_tower_prison_2"]["deck"] = self.MagicTowerPrison2_Deck.currentIndex() + 1
            my_transformer_b(self.MagicTowerPrison2_1P, "magic_tower_prison_2", "battle_plan_1p")

            my_opt["magic_tower_double"]["active"] = self.MagicTowerDouble_Active.isChecked()
            my_opt["magic_tower_double"]["max_times"] = self.MagicTowerDouble_MaxTimes.value()
            my_opt["magic_tower_double"]["stage"] = self.MagicTowerDouble_Stage.value()
            my_opt["magic_tower_double"]["deck"] = self.MagicTowerDouble_Deck.currentIndex() + 1
            my_transformer_b(self.MagicTowerDouble_1P, "magic_tower_double", "battle_plan_1p")
            my_transformer_b(self.MagicTowerDouble_2P, "magic_tower_double", "battle_plan_2p")

            my_opt["pet_temple_1"]["active"] = self.PetTemple1_Active.isChecked()
            my_opt["pet_temple_1"]["stage"] = self.PetTemple1_Stage.value()
            my_opt["pet_temple_1"]["deck"] = self.PetTemple1_Deck.currentIndex() + 1
            my_transformer_b(self.PetTemple1_1P, "pet_temple_1", "battle_plan_1p")

            my_opt["pet_temple_2"]["active"] = self.PetTemple2_Active.isChecked()
            my_opt["pet_temple_2"]["stage"] = self.PetTemple2_Stage.value()
            my_opt["pet_temple_2"]["deck"] = self.PetTemple2_Deck.currentIndex() + 1
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
            my_opt["customize_battle"]["deck"] = self.CustomizeBattle_Deck.currentIndex() + 1
            my_transformer_b(self.CustomizeBattle_1P, "customize_battle", "battle_plan_1p")
            my_transformer_b(self.CustomizeBattle_2P, "customize_battle", "battle_plan_2p")

            # 自定义作战
            my_opt["customize"]["active"] = self.Customize_Active.isChecked()
            my_opt["customize"]["stage"] = self.Customize_Stage.value()
            my_transformer_c(self.Customize_1P, "customize", "battle_plan_1p")

            my_opt["auto_food"]["active"] = self.AutoFood_Active.isChecked()
            my_opt["auto_food"]["deck"] = self.AutoFood_Deck.currentIndex() + 1

        base_settings()
        timer_settings()
        advanced_settings()
        senior_settings()
        get_warm_gift_settings()
        log_settings()
        skin_settings()
        level_2()

        self.opt["current_plan"] = self.CurrentPlan.currentIndex()  # combobox 序号
        todo_plans()

        # 一个提示弹窗
        self.cant_find_battle_plan_in_uuid_show_dialog()

    """按钮动作"""

    def click_btn_save(self) -> None:
        """点击保存配置按钮的函数"""
        SIGNAL.PRINT_TO_UI.emit(text="", time=False)
        self.ui_to_opt()
        self.opt_to_json()
        SIGNAL.PRINT_TO_UI.emit(text=f"方案:[{self.CurrentPlan.currentText()}] 已保存!", color_level=3)

    def delete_current_plan(self) -> None:
        """用来删掉当前被选中的 todo plan 但不能删掉默认方案"""
        if self.CurrentPlan.currentIndex() == 0:
            QMessageBox.information(self, "警告", "默认方案不能删除呢...")
            return
        del self.opt["todo_plans"][self.CurrentPlan.currentIndex()]
        # 重载ui
        self.init_opt_to_ui()

    def rename_current_plan(self) -> None:
        """用来重命名当前被选中的 todo plan 但不能重命名默认方案"""
        if self.CurrentPlan.currentIndex() == 0:
            QMessageBox.information(self, "警告", "默认方案不能重命名呢...")
            return

        # 弹出对话框获取新名称
        new_name, ok = QInputDialog.getText(self, "重命名方案", "请输入新的方案名称:")

        if ok and new_name:
            self.opt["todo_plans"][self.CurrentPlan.currentIndex()]["name"] = copy.deepcopy(new_name)
            current_index = self.CurrentPlan.currentIndex()
            # 重载ui
            self.init_opt_to_ui()
            # 默认选中重命名后方案
            self.CurrentPlan.setCurrentIndex(current_index)
        else:
            QMessageBox.information(self, "提示", "方案名称未改变。")

    def create_new_plan(self) -> None:
        """新建一个 todo plan, 但不能取名为Default"""
        # 弹出对话框获取新方案名称
        new_name, ok = QInputDialog.getText(self, "新建方案", "请输入新的方案名称:")

        if ok and new_name:
            if new_name == "Default":
                QMessageBox.information(self, "警告", "不能使用 Default 作为新的 TodoPlan 名呢...")
                return

            # 注意深拷贝
            self.opt["todo_plans"].append(copy.deepcopy(self.opt["todo_plans"][self.CurrentPlan.currentIndex()]))
            self.opt["todo_plans"][-1]["name"] = copy.deepcopy(new_name)
            # 重载ui
            self.init_opt_to_ui()
            # 默认选中新方案
            self.CurrentPlan.setCurrentIndex(len(self.opt["todo_plans"]) - 1)
        else:
            QMessageBox.information(self, "提示", "方案未创建。")

    def on_checkbox_state_changed(self, state):
        if state == 2:  # Qt.Checked
            self.all_senior_log.setEnabled(True)
            self.indeed_need.setEnabled(True)
            self.Battle_senior_gpu.setEnabled(True)
        else:
            self.all_senior_log.setEnabled(False)
            self.indeed_need.setEnabled(False)
            self.Battle_senior_gpu.setEnabled(False)

    """其他"""

    def getstylefile(self, num):
        skin_path_dict = {
            1: None,
            2: PATHS["theme"] + "\\feiyang\\blacksoft.css",
            3: PATHS["theme"] + "\\feiyang\\flatgray.css",
            4: PATHS["theme"] + "\\feiyang\\lightblue.css",
            5: PATHS["theme"] + "\\GTRONICK\\ElegantDark.qss",
            6: PATHS["theme"] + "\\GTRONICK\\MaterialDark.qss",
            7: PATHS["theme"] + "\\GTRONICK\\NeonButtons.qss",
            8: PATHS["theme"] + "\\GTRONICK\\Aqua.qss",
            9: PATHS["theme"] + "\\GTRONICK\\ManjaroMix.qss",
            10: PATHS["theme"] + "\\GTRONICK\\MacOS.qss",
            11: PATHS["theme"] + "\\GTRONICK\\Ubuntu.qss"
        }

        # 使用 get 方法设置皮肤
        path = skin_path_dict.get(num)
        return path

    def on_skin_state_changed(self, checked):
        # 获取发送信号的复选框对象
        sender = self.sender()

        # 定义一个字典，将复选框对象映射到对应的值
        skin_dict = {
            self.skin1: 1,
            self.skin2: 2,
            self.skin3: 3,
            self.skin4: 4,
            self.skin5: 5,
            self.skin6: 6,
            self.skin7: 7,
            self.skin8: 8,
            self.skin9: 9,
            self.skin10: 10,
            self.skin11: 11
        }
        if checked:
            current_option = skin_dict[sender]
            styleFile = self.getstylefile(current_option)
            if styleFile is not None:
                qssStyle = CommonHelper.readQss(styleFile)
                self.set_theme_common()
                self.MainFrame.setStyleSheet(qssStyle)
                self.set_common_theme()


            else:
                self.set_theme_common()
                self.set_theme_default()
                self.set_common_theme()


class CommonHelper:  # 主题加载类
    def __init__(self):
        pass

    @staticmethod
    def readQss(style):
        with open(style, 'r') as f:
            return f.read()


if __name__ == "__main__":
    def main() -> None:
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
        sys.exit(app.exec())


    main()
