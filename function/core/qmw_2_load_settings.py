import copy
import json
import os
import shutil
import sys
from function.globals.loadings import loading
loading.update_progress(45,"正在加载配置中...")
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator, QIntValidator
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog, QTableWidgetItem

from function.core.qmw_1_log import QMainWindowLog
from function.globals import EXTRA, SIGNAL
from function.globals import g_resources
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.scattered.check_battle_plan import fresh_and_check_all_battle_plan, fresh_and_check_all_tweak_plan
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

QQ_login_info={}
# 这里用函数来返回，是因为这两个变量会在运行时改变，直接import无法获取这种改变
# 感觉这样写很丑陋，但我也不知道怎么写比较好，总之能跑就行
def get_QQ_login_info():
    """获取qq登录账号和密码"""
    return QQ_login_info



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
        fresh_and_check_all_tweak_plan()

        # 更新完毕后重新刷新对应资源
        g_resources.fresh_resource_cus_img()
        g_resources.fresh_resource_b()
        g_resources.fresh_resource_t()

        # 为部分ui控件添加特性
        self.widget_extra_settings()

        # 绑定
        self.set_connect_for_lock_widget()

        # 从json文件中读取opt 并刷新ui
        self.opt = None
        self.json_to_opt()
        self.opt_to_ui_init()

        # 记录读取时 是否有战斗方案找不到了
        self.cant_find_battle_plan_in_uuid = False

        # 保留默认主题的名字
        self.default_style_name = QApplication.style().name()
        
        global QQ_login_info
        if "QQ_login_info" in self.opt:
            QQ_login_info=self.opt["QQ_login_info"]
        else:
            QQ_login_info = {
                "path":"",
                "use_password":False
            }

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

    # opt -> ui

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
        self.Warrior_Stage.setText(str(my_opt["warrior"]["stage"]))
        self.Warrior_GlobalPlanActive.setChecked(my_opt["warrior"]["global_plan_active"])
        self.Warrior_Deck.setCurrentIndex(my_opt["warrior"]["deck"])
        init_battle_plan(self.Warrior_1P, my_opt["warrior"]["battle_plan_1p"])
        init_battle_plan(self.Warrior_2P, my_opt["warrior"]["battle_plan_2p"])

        # 自定义任务序列
        self.Customize_Active.setChecked(my_opt["customize"]["active"])
        self.Customize_Stage.setValue(my_opt["customize"]["stage"])
        self.Customize_1P.clear()
        self.Customize_1P.addItems(task_sequence_list)
        self.Customize_1P.setCurrentIndex(my_opt["customize"]["battle_plan_1p"])

        # 常规单本 悬赏任务 跨服任务

        self.NormalBattle_Active.setChecked(my_opt["normal_battle"]["active"])
        self.NormalBattle_Group.setChecked(my_opt["normal_battle"]["is_group"])
        self.NormalBattle_MaxTimes.setValue(my_opt["normal_battle"]["max_times"])
        self.NormalBattle_Stage.setText(my_opt["normal_battle"]["stage"])
        self.NormalBattle_GlobalPlanActive.setChecked(my_opt["normal_battle"]["global_plan_active"])
        self.NormalBattle_Deck.setCurrentIndex(my_opt["normal_battle"]["deck"])
        init_battle_plan(self.NormalBattle_1P, my_opt["normal_battle"]["battle_plan_1p"])
        init_battle_plan(self.NormalBattle_2P, my_opt["normal_battle"]["battle_plan_2p"])

        self.OfferReward_Active.setChecked(my_opt["offer_reward"]["active"])
        self.OfferReward_MaxTimes_1.setText(str(my_opt["offer_reward"]["max_times_1"]))
        self.OfferReward_MaxTimes_2.setText(str(my_opt["offer_reward"]["max_times_2"]))
        self.OfferReward_MaxTimes_3.setText(str(my_opt["offer_reward"]["max_times_3"]))
        self.OfferReward_MaxTimes_4.setText(str(my_opt["offer_reward"]["max_times_4"]))
        self.OfferReward_GlobalPlanActive.setChecked(my_opt["offer_reward"]["global_plan_active"])
        self.OfferReward_Deck.setCurrentIndex(my_opt["offer_reward"]["deck"])
        init_battle_plan(self.OfferReward_1P, my_opt["offer_reward"]["battle_plan_1p"])
        init_battle_plan(self.OfferReward_2P, my_opt["offer_reward"]["battle_plan_2p"])

        self.CrossServer_Active.setChecked(my_opt["cross_server"]["active"])
        self.CrossServer_Group.setChecked(my_opt["cross_server"]["is_group"])
        self.CrossServer_MaxTimes.setValue(my_opt["cross_server"]["max_times"])
        self.CrossServer_Stage.setText(my_opt["cross_server"]["stage"])
        self.CrossServer_GlobalPlanActive.setChecked(my_opt["cross_server"]["global_plan_active"])
        self.CrossServer_Deck.setCurrentIndex(my_opt["cross_server"]["deck"])
        init_battle_plan(self.CrossServer_1P, my_opt["cross_server"]["battle_plan_1p"])
        init_battle_plan(self.CrossServer_2P, my_opt["cross_server"]["battle_plan_2p"])

        # 公会任务 公会副本 情侣任务 火山遗迹

        self.QuestGuild_Active.setChecked(my_opt["quest_guild"]["active"])
        self.QuestGuild_Stage.setChecked(my_opt["quest_guild"]["stage"])
        self.QuestGuild_GlobalPlanActive.setChecked(my_opt["quest_guild"]["global_plan_active"])
        self.QuestGuild_Deck.setCurrentIndex(my_opt["quest_guild"]["deck"])
        init_battle_plan(self.QuestGuild_1P, my_opt["quest_guild"]["battle_plan_1p"])
        init_battle_plan(self.QuestGuild_2P, my_opt["quest_guild"]["battle_plan_2p"])

        self.GuildDungeon_Active.setChecked(my_opt["guild_dungeon"]["active"])

        self.QuestSpouse_Active.setChecked(my_opt["quest_spouse"]["active"])

        self.Relic_Active.setChecked(my_opt["relic"]["active"])
        self.Relic_Group.setChecked(my_opt["relic"]["is_group"])
        self.Relic_MaxTimes.setValue(my_opt["relic"]["max_times"])
        self.Relic_Stage.setText(my_opt["relic"]["stage"])
        self.Relic_GlobalPlanActive.setChecked(my_opt["relic"]["global_plan_active"])
        self.Relic_Deck.setCurrentIndex(my_opt["relic"]["deck"])
        init_battle_plan(self.Relic_1P, my_opt["relic"]["battle_plan_1p"])
        init_battle_plan(self.Relic_2P, my_opt["relic"]["battle_plan_2p"])

        # 魔塔 萌宠神殿

        self.MagicTowerAlone1_Active.setChecked(my_opt["magic_tower_alone_1"]["active"])
        self.MagicTowerAlone1_MaxTimes.setValue(my_opt["magic_tower_alone_1"]["max_times"])
        self.MagicTowerAlone1_Stage.setValue(my_opt["magic_tower_alone_1"]["stage"])
        self.MagicTowerAlone1_GlobalPlanActive.setChecked(my_opt["magic_tower_alone_1"]["global_plan_active"])
        self.MagicTowerAlone1_Deck.setCurrentIndex(my_opt["magic_tower_alone_1"]["deck"])
        init_battle_plan(self.MagicTowerAlone1_1P, my_opt["magic_tower_alone_1"]["battle_plan_1p"])

        self.MagicTowerAlone2_Active.setChecked(my_opt["magic_tower_alone_2"]["active"])
        self.MagicTowerAlone2_MaxTimes.setValue(my_opt["magic_tower_alone_2"]["max_times"])
        self.MagicTowerAlone2_Stage.setValue(my_opt["magic_tower_alone_2"]["stage"])
        self.MagicTowerAlone2_GlobalPlanActive.setChecked(my_opt["magic_tower_alone_2"]["global_plan_active"])
        self.MagicTowerAlone2_Deck.setCurrentIndex(my_opt["magic_tower_alone_2"]["deck"])
        init_battle_plan(self.MagicTowerAlone2_1P, my_opt["magic_tower_alone_2"]["battle_plan_1p"])

        self.MagicTowerPrison1_Active.setChecked(my_opt["magic_tower_prison_1"]["active"])
        self.MagicTowerPrison1_Stage.setChecked(my_opt["magic_tower_prison_1"]["stage"])
        self.MagicTowerPrison1_GlobalPlanActive.setChecked(my_opt["magic_tower_prison_1"]["global_plan_active"])
        self.MagicTowerPrison1_Deck.setCurrentIndex(my_opt["magic_tower_prison_1"]["deck"])
        init_battle_plan(self.MagicTowerPrison1_1P, my_opt["magic_tower_prison_1"]["battle_plan_1p"])

        self.MagicTowerPrison2_Active.setChecked(my_opt["magic_tower_prison_2"]["active"])
        self.MagicTowerPrison2_Stage.setChecked(my_opt["magic_tower_prison_2"]["stage"])
        self.MagicTowerPrison2_GlobalPlanActive.setChecked(my_opt["magic_tower_prison_2"]["global_plan_active"])
        self.MagicTowerPrison2_Deck.setCurrentIndex(my_opt["magic_tower_prison_2"]["deck"])
        init_battle_plan(self.MagicTowerPrison2_1P, my_opt["magic_tower_prison_2"]["battle_plan_1p"])

        self.PetTemple1_Active.setChecked(my_opt["pet_temple_1"]["active"])
        self.PetTemple1_Stage.setValue(my_opt["pet_temple_1"]["stage"])
        self.PetTemple1_GlobalPlanActive.setChecked(my_opt["pet_temple_1"]["global_plan_active"])
        self.PetTemple1_Deck.setCurrentIndex(my_opt["pet_temple_1"]["deck"])
        init_battle_plan(self.PetTemple1_1P, my_opt["pet_temple_1"]["battle_plan_1p"])

        self.PetTemple2_Active.setChecked(my_opt["pet_temple_2"]["active"])
        self.PetTemple2_Stage.setValue(my_opt["pet_temple_2"]["stage"])
        self.PetTemple2_GlobalPlanActive.setChecked(my_opt["pet_temple_2"]["global_plan_active"])
        self.PetTemple2_Deck.setCurrentIndex(my_opt["pet_temple_2"]["deck"])
        init_battle_plan(self.PetTemple2_1P, my_opt["pet_temple_2"]["battle_plan_1p"])

        self.MagicTowerDouble_Active.setChecked(my_opt["magic_tower_double"]["active"])
        self.MagicTowerDouble_Stage.setValue(my_opt["magic_tower_double"]["stage"])
        self.MagicTowerDouble_MaxTimes.setValue(my_opt["magic_tower_double"]["max_times"])
        self.MagicTowerDouble_GlobalPlanActive.setChecked(my_opt["magic_tower_double"]["global_plan_active"])
        self.MagicTowerDouble_Deck.setCurrentIndex(my_opt["magic_tower_double"]["deck"])
        init_battle_plan(self.MagicTowerDouble_1P, my_opt["magic_tower_double"]["battle_plan_1p"])
        init_battle_plan(self.MagicTowerDouble_2P, my_opt["magic_tower_double"]["battle_plan_2p"])

        # 附加功能

        self.ReceiveAwards_Active.setChecked(my_opt["receive_awards"]["active"])
        self.ReceiveAwards_Group.setChecked(my_opt["receive_awards"]["is_group"])

        self.UseItems_Active.setChecked(my_opt["use_items"]["active"])
        self.UseItems_Group.setChecked(my_opt["use_items"]["is_group"])

        self.CheckingEndBox.setChecked(my_opt["checking"]["active"])
        self.CheckingEndBox_Group.setChecked(my_opt["checking"]["is_group"])

        self.LoopCrossServer_Active.setChecked(my_opt["loop_cross_server"]["active"])
        self.LoopCrossServer_Group.setChecked(my_opt["loop_cross_server"]["is_group"])

        self.LoopCrossExperience_Active.setChecked(my_opt["loop_cross_experience"]["active"])
        self.LoopCrossExperience_Group.setChecked(my_opt["loop_cross_experience"]["is_group"])

        self.AutoFood_Active.setChecked(my_opt["auto_food"]["active"])

        # 自建房对战
        self.CustomizeBattle_Active.setChecked(my_opt["customize_battle"]["active"])
        self.CustomizeBattle_Group.setCurrentIndex(my_opt["customize_battle"]["is_group"])
        self.CustomizeBattle_MaxTimes.setValue(my_opt["customize_battle"]["max_times"])
        self.CustomizeBattle_Stage.setText(my_opt["customize_battle"]["stage"])
        self.CustomizeBattle_GlobalPlanActive.setChecked(my_opt["customize_battle"]["global_plan_active"])
        self.CustomizeBattle_Deck.setCurrentIndex(my_opt["customize_battle"]["deck"])
        init_battle_plan(self.CustomizeBattle_1P, my_opt["customize_battle"]["battle_plan_1p"])
        init_battle_plan(self.CustomizeBattle_2P, my_opt["customize_battle"]["battle_plan_2p"])

        # 启动天知强卡器
        self.StartTCE_Active.setChecked(my_opt["tce"]["active"])
        self.TCE_Group.setCurrentText(my_opt["tce"]["player"])

        # 一个提示弹窗
        self.cant_find_battle_plan_in_uuid_show_dialog()

    def opt_to_ui_init(self) -> None:
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

            """ 进阶功能 - 高级设置"""
            self.TopUpMoney_1P.setChecked(my_opt["top_up_money_1p"])
            self.TopUpMoney_2P.setChecked(my_opt["top_up_money_2p"])
            self.EndExitGame.setChecked(my_opt["end_exit_game"])

            """ 进阶功能 - 普通战斗设定"""

            # 半自动拾取
            self.AutoPickUp_1P.setChecked(my_opt["auto_pickup_1p"])
            self.AutoPickUp_2P.setChecked(my_opt["auto_pickup_2p"])

            # 翻牌次数
            self.CusFlopTimesActive.setChecked(my_opt["cus_flop_times_active"])
            self.CusFlopTimesValueInput.setValue(my_opt["cus_flop_times_value"])
            EXTRA.FLOP_TIMES = my_opt["cus_flop_times_value"] if my_opt["cus_flop_times_active"] else 2

            # 点击频率
            self.CusCPSActive.setChecked(my_opt["cus_cps_active"])
            self.CusCPSValueInput.setValue(my_opt["cus_cps_value"])
            EXTRA.CLICK_PER_SECOND = my_opt["cus_cps_value"] if my_opt["cus_cps_active"] else 120

            # 最低FPS
            self.CusLowestFPSActive.setChecked(my_opt["cus_lowest_fps_active"])
            self.CusLowestFPSValueInput.setValue(my_opt["cus_lowest_fps_value"])
            EXTRA.LOWEST_FPS = my_opt["cus_lowest_fps_value"] if my_opt["cus_lowest_fps_active"] else 10

            # 自定放满禁用时间 毫秒转为秒
            self.CusFullBanTimeActive.setChecked(my_opt["cus_full_ban_active"])
            self.CusFullBanTimeValueInput.setValue(my_opt["cus_full_ban_value"])
            EXTRA.FULL_BAN_TIME = my_opt["cus_full_ban_value"] / 1000 if my_opt["cus_full_ban_active"] else 5

            # 自动带卡
            self.CusAutoCarryCardActive.setChecked(my_opt["cus_auto_carry_card_active"])
            self.CusAutoCarryCardValueInput.setCurrentIndex(my_opt["cus_auto_carry_card_value"] - 1)

            # 单局最大战斗时间
            self.MaxBattleTimeActive.setChecked(my_opt["max_battle_time_active"])
            self.MaxBattleTimeValueInput.setValue(my_opt["max_battle_time_value"])
            EXTRA.MAX_BATTLE_TIME = my_opt["max_battle_time_value"] if my_opt["max_battle_time_active"] else 0

            # 是否启动用卡
            self.AutoUseCard.setChecked(my_opt["auto_use_card"])

            """其他"""

            # 公会管理
            self.GuildManager_Active.setCurrentIndex(my_opt["guild_manager_active"])

            # link 加载的时候不做校验
            self.MisuLogistics_Link.setText(my_opt["misu_logistics_link"])

        def accelerate_settings() -> None:
            """
            加速功能设定
            """

            my_opt = self.opt["accelerate"]

            self.AccelerateActive.setChecked(my_opt["active"])
            self.AccelerateValue.setValue(my_opt["value"])
            self.AccelerateStartUpActive.setChecked(my_opt["start_up_active"])
            self.AccelerateSettlementActive.setChecked(my_opt["settlement_active"])
            self.AccelerateCustomizeActive.setChecked(my_opt["customize_active"])
            self.AccelerateCustomizeValue.setValue(my_opt["customize_value"])

            def set_accelerate_value(active, value, customize_active=False, customize_value=0):
                if active:
                    return customize_value if customize_active else value
                return 0

            if my_opt["active"]:
                EXTRA.ACCELERATE_START_UP_VALUE = set_accelerate_value(
                    active=my_opt["start_up_active"],
                    value=my_opt["value"],
                    customize_active=my_opt["customize_active"],
                    customize_value=my_opt["customize_value"]
                )
                EXTRA.ACCELERATE_SETTLEMENT_VALUE = set_accelerate_value(
                    active=my_opt["settlement_active"],
                    value=my_opt["value"]
                )
            else:
                EXTRA.ACCELERATE_START_UP_VALUE = 0
                EXTRA.ACCELERATE_SETTLEMENT_VALUE = 0

        def senior_settings() -> None:
            my_opt = self.opt["senior_settings"]
            self.BattleSeniorActive.setChecked(my_opt["auto_senior_settings"])
            self.BattleSeniorGPUActive.setChecked(my_opt["gpu_settings"])
            self.BattleSeniorIntervalValueInput.setValue(my_opt["interval"])
            self.BattleSeniorGPUActive.setEnabled(my_opt["auto_senior_settings"])
            self.BattleSeniorLogFull.setEnabled(my_opt["auto_senior_settings"])
            self.BattleSeniorLogPart.setEnabled(my_opt["auto_senior_settings"])
            if my_opt["senior_log_state"]:
                self.BattleSeniorLogFull.setChecked(True)
            else:
                self.BattleSeniorLogPart.setChecked(True)

        def log_settings() -> None:
            my_opt = self.opt["log_settings"]
            self.senior_log_clean.setValue(my_opt["log_senior_settings"])
            self.other_log_clean.setValue(my_opt["log_other_settings"])

        def login_settings() -> None:
            my_opt = self.opt["login_settings"]
            self.login_first.setValue(my_opt["first_num"])
            self.login_second.setValue(my_opt["second_num"])
            self.open360.setChecked(my_opt["login_open_settings"])
            self.close360.setChecked(my_opt["login_close_settings"])
            self.LoginSettings360PathInput.setText(my_opt["login_path"])

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

        def tce_settings() -> None:
            my_opt = self.opt["tce"]
            self.TCEEnhanceCard_Active.setChecked(my_opt["enhance_card_active"])
            self.TCEDecomposeGem_Active.setChecked(my_opt["decompose_gem_active"])
            self.TCE_path_input.setText(my_opt["tce_path"])

        def QQ_login_info_ui() ->None:
            """从配置中读取登录信息到ui中"""
            if "QQ_login_info" not in self.opt:
                self.opt["QQ_login_info"]={
                    "use_password":False,
                    "path":""
                }
            my_opt=self.opt["QQ_login_info"]
            self.checkbox_use_password.setChecked(my_opt["use_password"])
            self.path_edit.setText(my_opt["path"])
            if os.path.isfile(my_opt["path"]+"/QQ_account.json"):
                with open(my_opt["path"]+"/QQ_account.json","r") as json_file:
                    QQ_account=json.load(json_file)
                username1=QQ_account['1p']['username']
                username2=QQ_account['2p']['username']
                self.username_edit_1.setText(username1)
                self.username_edit_2.setText(username2)
            
        def sleep_opt_to_ui() ->None:
            """""从配置中读取额外睡眠时间到ui中"""""
            if "extra_sleep" not in self.opt:
                self.opt["extra_sleep"]={
                    "need_sleep":False,
                    "sleep_time":5
                }
            my_opt=self.opt["extra_sleep"]
            self.checkbox_need_sleep.setChecked(my_opt["need_sleep"])
            self.sleep_time_edit.setText(str(my_opt["sleep_time"]))



            
        def extension_opt_to_ui() -> None:
            """""从配置中读取插件信息到ui中"""""
            if "extension" not in self.opt:
                self.opt["extension"]={
                    "scripts":[]
                }
            
            my_opt=self.opt["extension"]
            
            # 清空现有表格
            self.tableWidget_extension.setRowCount(0)
            
            # 检查数据有效性
            if not my_opt or not isinstance(my_opt, dict):
                #print("错误：无效的输入数据")
                return
            
            # 遍历字典填充表格
            for script in my_opt.get("scripts", []):
                row = self.tableWidget_extension.rowCount()
                self.tableWidget_extension.insertRow(row)
                
                # 第一列：脚本名（默认空）
                path = script.get("name", "").strip()
                self.tableWidget_extension.setItem(row, 0, QTableWidgetItem(path))
                
                # 第二列：脚本路径（必填）
                path = script.get("path", "").strip()
                self.tableWidget_extension.setItem(row, 1, QTableWidgetItem(path))
                
                # 第三列：重复次数（默认1）
                repeat = str(script.get("repeat", 1))
                self.tableWidget_extension.setItem(row, 2, QTableWidgetItem(repeat))
                
                # 第四列：角色代号（默认3，表示1p和2p都要执行）
                player = str(script.get("player", 3))
                self.tableWidget_extension.setItem(row, 3, QTableWidgetItem(player))
            
            # 自动添加一个空行（用于继续输入）
            last_row = self.tableWidget_extension.rowCount()
            self.tableWidget_extension.insertRow(last_row)
            self.tableWidget_extension.setItem(last_row, 2, QTableWidgetItem("1"))  # 默认重复次数
            self.tableWidget_extension.setItem(last_row, 3, QTableWidgetItem("3"))  # 默认角色代号

        
        base_settings()
        timer_settings()
        advanced_settings()
        senior_settings()
        get_warm_gift_settings()
        log_settings()
        login_settings()
        level_2()
        skin_set()
        accelerate_settings()
        tce_settings()
        QQ_login_info_ui()
        sleep_opt_to_ui()
        extension_opt_to_ui()

        self.CurrentPlan.clear()
        self.CurrentPlan.addItems(todo_plan_name_list)
        self.CurrentPlan.setCurrentIndex(self.opt["current_plan"])
        self.opt_to_ui_todo_plans()

    # ui -> opt

    def ui_to_opt_todo_plans(self) -> None:

        self.cant_find_battle_plan_in_uuid = False

        # battle_plan_list
        battle_plan_name_list_new = get_list_battle_plan(with_extension=False)
        task_sequence_list = get_task_sequence_list(with_extension=False)

        # 检测uuid是否存在于 可能新加入的 battle plan 没有则添加 并将其读入到内存资源中
        fresh_and_check_all_battle_plan()
        fresh_and_check_all_tweak_plan()
        g_resources.fresh_resource_b()
        g_resources.fresh_resource_t()

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
        my_opt["warrior"]["stage"] = int(self.Warrior_Stage.text())
        my_opt["warrior"]["global_plan_active"] = self.Warrior_GlobalPlanActive.isChecked()
        my_opt["warrior"]["deck"] = self.Warrior_Deck.currentIndex()
        my_transformer_b(self.Warrior_1P, "warrior", "battle_plan_1p")
        my_transformer_b(self.Warrior_2P, "warrior", "battle_plan_2p")

        # 自定义任务序列
        my_opt["customize"]["active"] = self.Customize_Active.isChecked()
        my_opt["customize"]["stage"] = self.Customize_Stage.value()
        my_transformer_c(self.Customize_1P, "customize", "battle_plan_1p")

        # 常规单本 悬赏任务 跨服任务

        my_opt["normal_battle"]["active"] = self.NormalBattle_Active.isChecked()
        my_opt["normal_battle"]["is_group"] = self.NormalBattle_Group.isChecked()
        my_opt["normal_battle"]["max_times"] = self.NormalBattle_MaxTimes.value()
        my_opt["normal_battle"]["stage"] = self.NormalBattle_Stage.text()
        my_opt["normal_battle"]["global_plan_active"] = self.NormalBattle_GlobalPlanActive.isChecked()
        my_opt["normal_battle"]["deck"] = self.NormalBattle_Deck.currentIndex()
        my_transformer_b(self.NormalBattle_1P, "normal_battle", "battle_plan_1p")
        my_transformer_b(self.NormalBattle_2P, "normal_battle", "battle_plan_2p")

        my_opt["offer_reward"]["active"] = self.OfferReward_Active.isChecked()
        my_opt["offer_reward"]["deck"] = self.OfferReward_Deck.currentIndex()
        my_opt["offer_reward"]["max_times_1"] = int(self.OfferReward_MaxTimes_1.text())
        my_opt["offer_reward"]["max_times_2"] = int(self.OfferReward_MaxTimes_2.text())
        my_opt["offer_reward"]["max_times_3"] = int(self.OfferReward_MaxTimes_3.text())
        my_opt["offer_reward"]["max_times_4"] = int(self.OfferReward_MaxTimes_4.text())
        my_opt["offer_reward"]["global_plan_active"] = self.OfferReward_GlobalPlanActive.isChecked()
        my_transformer_b(self.OfferReward_1P, "offer_reward", "battle_plan_1p")
        my_transformer_b(self.OfferReward_2P, "offer_reward", "battle_plan_2p")

        my_opt["cross_server"]["active"] = self.CrossServer_Active.isChecked()
        my_opt["cross_server"]["is_group"] = self.CrossServer_Group.isChecked()
        my_opt["cross_server"]["max_times"] = self.CrossServer_MaxTimes.value()
        my_opt["cross_server"]["stage"] = self.CrossServer_Stage.text()
        my_opt["cross_server"]["global_plan_active"] = self.CrossServer_GlobalPlanActive.isChecked()
        my_opt["cross_server"]["deck"] = self.CrossServer_Deck.currentIndex()
        my_transformer_b(self.CrossServer_1P, "cross_server", "battle_plan_1p")
        my_transformer_b(self.CrossServer_2P, "cross_server", "battle_plan_2p")

        # 公会任务 公会副本 情侣任务 火山遗迹

        my_opt["quest_guild"]["active"] = self.QuestGuild_Active.isChecked()
        my_opt["quest_guild"]["stage"] = self.QuestGuild_Stage.isChecked()
        my_opt["quest_guild"]["global_plan_active"] = self.QuestGuild_GlobalPlanActive.isChecked()
        my_opt["quest_guild"]["deck"] = self.QuestGuild_Deck.currentIndex()
        my_transformer_b(self.QuestGuild_1P, "quest_guild", "battle_plan_1p")
        my_transformer_b(self.QuestGuild_2P, "quest_guild", "battle_plan_2p")

        my_opt["guild_dungeon"]["active"] = self.GuildDungeon_Active.isChecked()

        my_opt["quest_spouse"]["active"] = self.QuestSpouse_Active.isChecked()

        my_opt["relic"]["active"] = self.Relic_Active.isChecked()
        my_opt["relic"]["is_group"] = self.Relic_Group.isChecked()
        my_opt["relic"]["max_times"] = self.Relic_MaxTimes.value()
        my_opt["relic"]["stage"] = self.Relic_Stage.text()
        my_opt["relic"]["global_plan_active"] = self.Relic_GlobalPlanActive.isChecked()
        my_opt["relic"]["deck"] = self.Relic_Deck.currentIndex()
        my_transformer_b(self.Relic_1P, "relic", "battle_plan_1p")
        my_transformer_b(self.Relic_2P, "relic", "battle_plan_2p")

        # 魔塔 萌宠神殿

        my_opt["magic_tower_alone_1"]["active"] = self.MagicTowerAlone1_Active.isChecked()
        my_opt["magic_tower_alone_1"]["max_times"] = self.MagicTowerAlone1_MaxTimes.value()
        my_opt["magic_tower_alone_1"]["stage"] = self.MagicTowerAlone1_Stage.value()
        my_opt["magic_tower_alone_1"]["global_plan_active"] = self.MagicTowerAlone1_GlobalPlanActive.isChecked()
        my_opt["magic_tower_alone_1"]["deck"] = self.MagicTowerAlone1_Deck.currentIndex()
        my_transformer_b(self.MagicTowerAlone1_1P, "magic_tower_alone_1", "battle_plan_1p")

        my_opt["magic_tower_alone_2"]["active"] = self.MagicTowerAlone2_Active.isChecked()
        my_opt["magic_tower_alone_2"]["max_times"] = self.MagicTowerAlone2_MaxTimes.value()
        my_opt["magic_tower_alone_2"]["stage"] = self.MagicTowerAlone2_Stage.value()
        my_opt["magic_tower_alone_2"]["global_plan_active"] = self.MagicTowerAlone2_GlobalPlanActive.isChecked()
        my_opt["magic_tower_alone_2"]["deck"] = self.MagicTowerAlone2_Deck.currentIndex()
        my_transformer_b(self.MagicTowerAlone2_1P, "magic_tower_alone_2", "battle_plan_1p")

        my_opt["magic_tower_prison_1"]["active"] = self.MagicTowerPrison1_Active.isChecked()
        my_opt["magic_tower_prison_1"]["stage"] = self.MagicTowerPrison1_Stage.isChecked()
        my_opt["magic_tower_prison_1"]["global_plan_active"] = self.MagicTowerPrison1_GlobalPlanActive.isChecked()
        my_opt["magic_tower_prison_1"]["deck"] = self.MagicTowerPrison1_Deck.currentIndex()
        my_transformer_b(self.MagicTowerPrison1_1P, "magic_tower_prison_1", "battle_plan_1p")

        my_opt["magic_tower_prison_2"]["active"] = self.MagicTowerPrison2_Active.isChecked()
        my_opt["magic_tower_prison_2"]["stage"] = self.MagicTowerPrison2_Stage.isChecked()
        my_opt["magic_tower_prison_2"]["global_plan_active"] = self.MagicTowerPrison2_GlobalPlanActive.isChecked()
        my_opt["magic_tower_prison_2"]["deck"] = self.MagicTowerPrison2_Deck.currentIndex()
        my_transformer_b(self.MagicTowerPrison2_1P, "magic_tower_prison_2", "battle_plan_1p")

        my_opt["pet_temple_1"]["active"] = self.PetTemple1_Active.isChecked()
        my_opt["pet_temple_1"]["stage"] = self.PetTemple1_Stage.value()
        my_opt["pet_temple_1"]["global_plan_active"] = self.PetTemple1_GlobalPlanActive.isChecked()
        my_opt["pet_temple_1"]["deck"] = self.PetTemple1_Deck.currentIndex()
        my_transformer_b(self.PetTemple1_1P, "pet_temple_1", "battle_plan_1p")

        my_opt["pet_temple_2"]["active"] = self.PetTemple2_Active.isChecked()
        my_opt["pet_temple_2"]["stage"] = self.PetTemple2_Stage.value()
        my_opt["pet_temple_2"]["global_plan_active"] = self.PetTemple2_GlobalPlanActive.isChecked()
        my_opt["pet_temple_2"]["deck"] = self.PetTemple2_Deck.currentIndex()
        my_transformer_b(self.PetTemple2_1P, "pet_temple_2", "battle_plan_1p")

        my_opt["magic_tower_double"]["active"] = self.MagicTowerDouble_Active.isChecked()
        my_opt["magic_tower_double"]["max_times"] = self.MagicTowerDouble_MaxTimes.value()
        my_opt["magic_tower_double"]["stage"] = self.MagicTowerDouble_Stage.value()
        my_opt["magic_tower_double"]["global_plan_active"] = self.MagicTowerDouble_GlobalPlanActive.isChecked()
        my_opt["magic_tower_double"]["deck"] = self.MagicTowerDouble_Deck.currentIndex()
        my_transformer_b(self.MagicTowerDouble_1P, "magic_tower_double", "battle_plan_1p")
        my_transformer_b(self.MagicTowerDouble_2P, "magic_tower_double", "battle_plan_2p")

        # 附加功能

        my_opt["receive_awards"]["active"] = self.ReceiveAwards_Active.isChecked()
        my_opt["receive_awards"]["is_group"] = self.ReceiveAwards_Group.isChecked()

        my_opt["use_items"]["active"] = self.UseItems_Active.isChecked()
        my_opt["use_items"]["is_group"] = self.UseItems_Group.isChecked()

        my_opt["checking"]["active"] = self.CheckingEndBox.isChecked()
        my_opt["checking"]["is_group"] = self.CheckingEndBox_Group.isChecked()

        my_opt["loop_cross_server"]["active"] = self.LoopCrossServer_Active.isChecked()
        my_opt["loop_cross_server"]["is_group"] = self.LoopCrossServer_Group.isChecked()

        my_opt["loop_cross_experience"]["active"] = self.LoopCrossExperience_Active.isChecked()
        my_opt["loop_cross_experience"]["is_group"] = self.LoopCrossExperience_Group.isChecked()

        my_opt["auto_food"]["active"] = self.AutoFood_Active.isChecked()

        # 自建房对战
        my_opt["customize_battle"]["active"] = self.CustomizeBattle_Active.isChecked()
        my_opt["customize_battle"]["is_group"] = self.CustomizeBattle_Group.currentIndex()  # combobox 序号
        my_opt["customize_battle"]["max_times"] = self.CustomizeBattle_MaxTimes.value()
        my_opt["customize_battle"]["stage"] = self.CustomizeBattle_Stage.text()
        my_opt["customize_battle"]["global_plan_active"] = self.CustomizeBattle_GlobalPlanActive.isChecked()
        my_opt["customize_battle"]["deck"] = self.CustomizeBattle_Deck.currentIndex()
        my_transformer_b(self.CustomizeBattle_1P, "customize_battle", "battle_plan_1p")
        my_transformer_b(self.CustomizeBattle_2P, "customize_battle", "battle_plan_2p")

        # 天知强卡器
        my_opt["tce"]["active"] = self.StartTCE_Active.isChecked()
        my_opt["tce"]["player"] = self.TCE_Group.currentText()

    def ui_to_opt(self) -> None:

        def base_settings() -> None:
            my_opt = self.opt["base_settings"]
            my_opt["game_name"] = self.GameName_Input.text()
            my_opt["name_1p"] = self.Name1P_Input.text()
            my_opt["name_2p"] = self.Name2P_Input.text()
            self.ZoomRatio_Output.setText(str(self.zoom_rate) + "(自动)")
            my_opt["level_1p"] = self.Level1P_Input.value()
            my_opt["level_2p"] = self.Level2P_Input.value()

        def check_time_settings() -> None:
            for i in range(1,6):
                # 依次检查文本内容是否为空
                if getattr(self, f"Timer{i}_H").text() == "":
                    h_text = str("0").zfill(2)
                    getattr(self, f"Timer{i}_H").setText(h_text)

                if getattr(self, f"Timer{i}_M").text() == "":
                    m_text = str("0").zfill(2)
                    getattr(self, f"Timer{i}_M").setText(m_text)

        def timer_settings() -> None:
            for i in range(1, 6):
                my_opt = self.opt["timer"][f"{i}"]
                my_opt["active"] = getattr(self, f"Timer{i}_Active").isChecked()
                my_opt["h"] = int(getattr(self, f"Timer{i}_H").text())
                my_opt["m"] = int(getattr(self, f"Timer{i}_M").text())
                my_opt["plan"] = getattr(self, f"Timer{i}_Plan").currentIndex()


        def advanced_settings() -> None:
            my_opt = self.opt["advanced_settings"]

            """进阶设定 - 高级设置"""

            # 日氪
            my_opt["top_up_money_1p"] = self.TopUpMoney_1P.isChecked()
            my_opt["top_up_money_2p"] = self.TopUpMoney_2P.isChecked()

            # 结束后退出
            my_opt["end_exit_game"] = self.EndExitGame.isChecked()

            """进阶设定 - 普通战斗"""

            # 半自动拾取
            my_opt["auto_pickup_1p"] = self.AutoPickUp_1P.isChecked()
            my_opt["auto_pickup_2p"] = self.AutoPickUp_2P.isChecked()

            # 翻牌次数
            my_opt["cus_flop_times_active"] = self.CusFlopTimesActive.isChecked()
            my_opt["cus_flop_times_value"] = self.CusFlopTimesValueInput.value()
            EXTRA.FLOP_TIMES = my_opt["cus_flop_times_value"] if my_opt["cus_flop_times_active"] else 2

            # 点击频率
            my_opt["cus_cps_active"] = self.CusCPSActive.isChecked()
            my_opt["cus_cps_value"] = self.CusCPSValueInput.value()
            EXTRA.CLICK_PER_SECOND = my_opt["cus_cps_value"] if my_opt["cus_cps_active"] else 120

            # 最低FPS
            my_opt["cus_lowest_fps_active"] = self.CusLowestFPSActive.isChecked()
            my_opt["cus_lowest_fps_value"] = self.CusLowestFPSValueInput.value()
            EXTRA.LOWEST_FPS = my_opt["cus_lowest_fps_value"] if my_opt["cus_lowest_fps_active"] else 10

            # 自定放满禁用时间 毫秒转为秒
            my_opt["cus_full_ban_active"] = self.CusFullBanTimeActive.isChecked()
            my_opt["cus_full_ban_value"] = self.CusFullBanTimeValueInput.value()
            EXTRA.FULL_BAN_TIME = my_opt["cus_full_ban_value"] / 1000 if my_opt["cus_full_ban_active"] else 5

            # 自动带卡
            my_opt["cus_auto_carry_card_active"] = self.CusAutoCarryCardActive.isChecked()
            my_opt["cus_auto_carry_card_value"] = self.CusAutoCarryCardValueInput.currentIndex() + 1

            # 单局最大战斗时间
            my_opt["max_battle_time_active"] = self.MaxBattleTimeActive.isChecked()
            my_opt["max_battle_time_value"] = self.MaxBattleTimeValueInput.value()
            EXTRA.MAX_BATTLE_TIME = my_opt["max_battle_time_value"] if my_opt["max_battle_time_active"] else 0

            # 自动放卡
            my_opt["auto_use_card"] = self.AutoUseCard.isChecked()

            """其他"""

            # 公会管理器
            my_opt["guild_manager_active"] = self.GuildManager_Active.currentIndex()

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
            my_opt["auto_senior_settings"] = self.BattleSeniorActive.isChecked()
            my_opt["senior_log_state"] = 1 if self.BattleSeniorLogFull.isChecked() else 0
            my_opt["gpu_settings"] = self.BattleSeniorGPUActive.isChecked()
            my_opt["interval"] = self.BattleSeniorIntervalValueInput.value()

        def accelerate_settings() -> None:
            """
            加速功能设定
            """

            my_opt = self.opt["accelerate"]

            my_opt["active"] = self.AccelerateActive.isChecked()
            my_opt["value"] = self.AccelerateValue.value()
            my_opt["start_up_active"] = self.AccelerateStartUpActive.isChecked()
            my_opt["settlement_active"] = self.AccelerateSettlementActive.isChecked()
            my_opt["customize_active"] = self.AccelerateCustomizeActive.isChecked()
            my_opt["customize_value"] = self.AccelerateCustomizeValue.value()

            def set_accelerate_value(duration, active, value, customize_active=False, customize_value=0):
                if active:
                    speed = customize_value if customize_active else value
                    return duration / (speed / 100)
                return 0

            if my_opt["active"]:
                EXTRA.ACCELERATE_START_UP_VALUE = set_accelerate_value(
                    duration=1,
                    active=my_opt["start_up_active"],
                    value=my_opt["value"],
                    customize_active=my_opt["customize_active"],
                    customize_value=my_opt["customize_value"]
                )
                EXTRA.ACCELERATE_SETTLEMENT_VALUE = set_accelerate_value(
                    duration=12,
                    active=my_opt["settlement_active"],
                    value=my_opt["value"]
                )
            else:
                EXTRA.ACCELERATE_START_UP_VALUE = 0
                EXTRA.ACCELERATE_SETTLEMENT_VALUE = 0

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

        def login_settings() -> None:
            my_opt = self.opt["login_settings"]
            my_opt["login_open_settings"] = self.open360.isChecked()
            my_opt["login_close_settings"] = self.close360.isChecked()
            my_opt["login_path"] = self.LoginSettings360PathInput.text()
            my_opt["first_num"] = self.login_first.value()
            my_opt["second_num"] = self.login_second.value()

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

        def tce_settings() -> None:
            my_opt = self.opt["tce"]
            my_opt["enhance_card_active"] = self.TCEEnhanceCard_Active.isChecked()
            my_opt["decompose_gem_active"] = self.TCEDecomposeGem_Active.isChecked()
            my_opt["tce_path"] = self.TCE_path_input.text()

        def QQ_login_info_opt() -> None:
            """将登录信息从ui中写入到opt"""
            my_opt=self.opt["QQ_login_info"]
            my_opt["use_password"]=self.checkbox_use_password.isChecked()
            my_opt["path"]=self.path_edit.text()
        
        def sleep_ui_to_opt() -> None:
            """将QQ登录时的额外休眠时间从ui写入到opt"""
            my_opt=self.opt["extra_sleep"]
            my_opt["need_sleep"]=self.checkbox_need_sleep.isChecked()
            my_opt["sleep_time"]=int(self.sleep_time_edit.text())
        
        def extension_ui_to_opt() -> None:
            """将脚本表格从ui写入到opt"""
            my_opt=self.opt["extension"] 
            my_opt["scripts"]=[] # 先清空列表
            for row in range(self.tableWidget_extension.rowCount()):
                # 获取单元格数据
                name_item = self.tableWidget_extension.item(row, 0)  # 脚本路径
                
                path_item = self.tableWidget_extension.item(row, 1)  # 脚本路径
                repeat_item = self.tableWidget_extension.item(row, 2)  # 重复次数
                player_item = self.tableWidget_extension.item(row, 3)  # 重复次数
                
                # 跳过空行（第一列为空时忽略）
                if path_item and path_item.text().strip():
                    my_opt["scripts"].append({
                        "name":name_item.text().strip() if (name_item and name_item.text()) else "",
                        "path": path_item.text().strip(),
                        "repeat": int(repeat_item.text()) if (repeat_item and repeat_item.text()) else 1,
                        "player": int(player_item.text()) if (player_item and player_item.text()) else 3
                    })
                    
            
        base_settings()
        accelerate_settings()
        check_time_settings()
        timer_settings()
        advanced_settings()
        senior_settings()
        get_warm_gift_settings()
        log_settings()
        login_settings()
        skin_settings()
        level_2()
        tce_settings()
        QQ_login_info_opt()
        sleep_ui_to_opt()
        extension_ui_to_opt()

        self.opt["current_plan"] = self.CurrentPlan.currentIndex()  # combobox 序号
        self.ui_to_opt_todo_plans()

        # 一个提示弹窗
        self.cant_find_battle_plan_in_uuid_show_dialog()

    # 勾选 全局方案 -> 锁定其他几项设置
    def set_connect_for_lock_widget(self) -> None:
        """
        是否激活一个元素, 如果激活, 再允许编辑对应的下级元素
        完成大量这样的操作
        """

        def toggle_widgets_on_unchecked(state, widgets):
            """
            如果按钮未勾选（state 为 0），则启用其他元素，使其可被更改；
            否则，禁用其他元素，使其不可被更改。
            """
            for widget in widgets:
                widget.setEnabled(state == 0)

        def toggle_widgets_on_checked(state, widgets):
            """
            如果按钮勾选（state 为 1 or 2），则启用其他元素，使其可被更改；
            否则，禁用其他元素，使其不可被更改。
            """
            for widget in widgets:
                widget.setEnabled(state != 0)

        self.Warrior_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.Warrior_Deck, self.Warrior_1P, self.Warrior_2P]))

        self.NormalBattle_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.NormalBattle_Deck, self.NormalBattle_1P, self.NormalBattle_2P]))

        self.OfferReward_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.OfferReward_Deck, self.OfferReward_1P, self.OfferReward_2P]))

        self.CrossServer_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.CrossServer_Deck, self.CrossServer_1P, self.CrossServer_2P]))

        # 公会任务 火山遗迹

        self.QuestGuild_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.QuestGuild_Deck, self.QuestGuild_1P, self.QuestGuild_2P]))

        self.Relic_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.Relic_Deck, self.Relic_1P, self.Relic_2P]))

        # 魔塔 萌宠神殿
        self.MagicTowerAlone1_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.MagicTowerAlone1_Deck, self.MagicTowerAlone1_1P]))

        self.MagicTowerAlone2_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.MagicTowerAlone2_Deck, self.MagicTowerAlone2_1P]))

        self.MagicTowerPrison1_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.MagicTowerPrison1_Deck, self.MagicTowerPrison1_1P]))

        self.MagicTowerPrison2_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.MagicTowerPrison2_Deck, self.MagicTowerPrison2_1P]))

        self.PetTemple1_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.PetTemple1_Deck, self.PetTemple1_1P]))

        self.PetTemple2_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.PetTemple2_Deck, self.PetTemple2_1P]))

        self.MagicTowerDouble_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.MagicTowerDouble_Deck, self.MagicTowerDouble_1P, self.MagicTowerDouble_2P]))

        self.CustomizeBattle_GlobalPlanActive.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.CustomizeBattle_Deck, self.CustomizeBattle_1P, self.CustomizeBattle_2P]))

        # 点击频率
        self.CusFlopTimesActive.stateChanged.connect(
            lambda state: toggle_widgets_on_checked(
                state, [self.CusFlopTimesValueInput])
        )

        # 战斗设定 - 常规
        self.CusCPSActive.stateChanged.connect(
            lambda state: toggle_widgets_on_checked(
                state, [self.CusCPSValueInput])
        )

        self.CusLowestFPSActive.stateChanged.connect(
            lambda state: toggle_widgets_on_checked(
                state, [self.CusLowestFPSValueInput])
        )

        self.CusFullBanTimeActive.stateChanged.connect(
            lambda state: toggle_widgets_on_checked(
                state, [self.CusFullBanTimeValueInput])
        )

        self.CusAutoCarryCardActive.stateChanged.connect(
            lambda state: toggle_widgets_on_checked(
                state, [self.CusAutoCarryCardValueInput])
        )
        self.MaxBattleTimeActive.stateChanged.connect(
            lambda state: toggle_widgets_on_checked(
                state, [self.MaxBattleTimeValueInput])
        )

        # 战斗设定 - 加速
        self.AccelerateActive.stateChanged.connect(
            lambda state: toggle_widgets_on_checked(
                state,
                [
                    self.AccelerateValue,
                    self.AccelerateStartUpActive,
                    self.AccelerateSettlementActive,
                    self.AccelerateCustomizeActive,
                    self.AccelerateCustomizeValue
                ]
            )
        )

        # 战斗设定 - 高级
        self.BattleSeniorActive.stateChanged.connect(
            lambda state: toggle_widgets_on_checked(
                state,
                [
                    self.BattleSeniorLogFull,
                    self.BattleSeniorLogPart,
                    self.BattleSeniorGPUActive,
                    self.SeniorBattleIntervalLabel,
                    self.BattleSeniorIntervalValueInput
                ]
            )
        )

        # 结束流程后, 若选择关闭游戏大厅 自然不用退出到登录页
        self.close360.stateChanged.connect(
            lambda state: toggle_widgets_on_unchecked(
                state, [self.EndExitGame])
        )

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
        self.opt_to_ui_init()

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
            self.opt_to_ui_init()
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
            self.opt_to_ui_init()
            # 默认选中新方案
            self.CurrentPlan.setCurrentIndex(len(self.opt["todo_plans"]) - 1)
        else:
            QMessageBox.information(self, "提示", "方案未创建。")

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
                # 先设置主题 再在此基础上叠加皮肤样式表
                # self.app.setStyle("WindowsVista")
                qssStyle = CommonHelper.readQss(styleFile)
                self.set_theme_common()
                self.MainFrame.setStyleSheet(qssStyle)
                self.set_common_theme()
            else:
                # 还原主题
                # self.app.setStyle(self.default_style_name)
                self.set_theme_common()
                self.set_theme_default()
                self.set_common_theme()

    def widget_extra_settings(self):
        """
        为部分控件在加载时添加额外的属性
        :return:
        """
        # 只允许输入整数 0-9
        intValidator = QIntValidator(0, 9, self)
        self.OfferReward_MaxTimes_1.setValidator(intValidator)
        self.OfferReward_MaxTimes_2.setValidator(intValidator)
        self.OfferReward_MaxTimes_3.setValidator(intValidator)
        self.OfferReward_MaxTimes_4.setValidator(intValidator)

        # 监听文本变化事件 触发修正函数
        def warrior_stage_changed(text):

            if text:

                try:
                    value = int(text)
                    if not 1 <= value <= 23:
                        SIGNAL.DIALOG.emit("出错！(╬◣д◢)", "勇士本关卡值仅为1-23, 请检查输入")
                        # 回退到最后一次有效的状态或者清除无效输入
                        self.Warrior_Stage.setText('')

                except ValueError:
                    SIGNAL.DIALOG.emit("出错！(╬◣д◢)", "此处只可输入数字! 不要输入怪东西!")
                    self.Warrior_Stage.setText('')

        self.Warrior_Stage.textChanged.connect(warrior_stage_changed)


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
