import json
import sys

from PyQt5.QtWidgets import QApplication

from function.script.scattered.get_battle_plan_list import get_battle_plan_list
from function.script.ui.ui_0_load_ui_file import MyMainWindow0


class MyMainWindow1(MyMainWindow0):
    """将读取配置的方法封装在此处"""

    def __init__(self):
        # 继承父类构造方法
        super().__init__()

        # opt路径
        self.opt_path = self.path_root + "\\config\\opt_main.json"

        # 从json文件中读取opt 并刷新ui
        self.opt = self.json_to_opt()
        self.opt_to_ui()

    def json_to_opt(self):
        with open(self.opt_path) as json_file:
            opt = json.load(json_file)
        return opt

    def opt_to_json(self):
        # dict → str 转换True和true
        json_str = json.dumps(self.opt, indent=4)
        # 写入
        with open(self.opt_path, 'w') as json_file:
            json_file.write(json_str)
        return None

    def opt_to_ui(self):
        # comboBox.setCurrentIndex时 如果超过了已有预设 会显示为空 不会报错
        # comboBox.clear时 会把所有选项设定为默认选项
        battle_plan_list = get_battle_plan_list(with_extension=False)

        self.GameName_Input.setText(self.opt["GameName"])
        self.Name1P_Input.setText(self.opt["Name1P"])
        self.Name2P_Input.setText(self.opt["Name2P"])
        self.ZoomRatio_Input.setCurrentIndex(self.opt["ZoomRatio"])

        self.Level1P_Input.setValue(self.opt["Level1P"])
        self.Level2P_Input.setValue(self.opt["Level2P"])
        self.AutoUseCard.setChecked(self.opt["AutoUseCard"])

        self.GuildTask_Active.setChecked(self.opt["GuildTask"]["Active"])
        self.GuildTask_Skip.setChecked(self.opt["GuildTask"]["Skip"])
        self.GuildTask_Deck.setValue(self.opt["GuildTask"]["Deck"])
        self.GuildTask_1P.addItems(battle_plan_list)
        self.GuildTask_2P.addItems(battle_plan_list)
        self.GuildTask_1P.setCurrentIndex(self.opt["GuildTask"]["BattlePlan1P"])
        self.GuildTask_2P.setCurrentIndex(self.opt["GuildTask"]["BattlePlan2P"])

        self.SpouseTask_Active.setChecked(self.opt["SpouseTask"]["Active"])
        self.SpouseTask_Deck.setValue(self.opt["SpouseTask"]["Deck"])
        self.SpouseTask_1P.addItems(battle_plan_list)
        self.SpouseTask_2P.addItems(battle_plan_list)
        self.SpouseTask_1P.setCurrentIndex(self.opt["SpouseTask"]["BattlePlan1P"])
        self.SpouseTask_2P.setCurrentIndex(self.opt["SpouseTask"]["BattlePlan2P"])

        self.OfferReward_Active.setChecked(self.opt["OfferReward"]["Active"])
        self.OfferReward_Deck.setValue(self.opt["OfferReward"]["Deck"])
        self.OfferReward_1P.addItems(battle_plan_list)
        self.OfferReward_2P.addItems(battle_plan_list)
        self.OfferReward_1P.setCurrentIndex(self.opt["OfferReward"]["BattlePlan1P"])
        self.OfferReward_2P.setCurrentIndex(self.opt["OfferReward"]["BattlePlan2P"])

        self.MagicTowerDouble_Active.setChecked(self.opt["MagicTowerDouble"]["Active"])
        self.MagicTowerDouble_MaxTimes.setValue(self.opt["MagicTowerDouble"]["MaxTimes"])
        self.MagicTowerDouble_Stage.setValue(self.opt["MagicTowerDouble"]["Stage"])
        self.MagicTowerDouble_Deck.setValue(self.opt["MagicTowerDouble"]["Deck"])
        self.MagicTowerDouble_1P.addItems(battle_plan_list)
        self.MagicTowerDouble_2P.addItems(battle_plan_list)
        self.MagicTowerDouble_1P.setCurrentIndex(self.opt["MagicTowerDouble"]["BattlePlan1P"])
        self.MagicTowerDouble_2P.setCurrentIndex(self.opt["MagicTowerDouble"]["BattlePlan2P"])

        self.MagicTowerAlone_Active.setChecked(self.opt["MagicTowerAlone"]["Active"])
        self.MagicTowerAlone_MaxTimes.setValue(self.opt["MagicTowerAlone"]["MaxTimes"])
        self.MagicTowerAlone_Stage.setValue(self.opt["MagicTowerAlone"]["Stage"])
        self.MagicTowerAlone_Deck.setValue(self.opt["MagicTowerAlone"]["Deck"])
        self.MagicTowerAlone_1P.addItems(battle_plan_list)
        self.MagicTowerAlone_1P.setCurrentIndex(self.opt["MagicTowerAlone"]["BattlePlan1P"])

        self.MagicTowerPrison_Active.setChecked(self.opt["MagicTowerPrison"]["Active"])
        self.MagicTowerPrison_Extra.setChecked(self.opt["MagicTowerPrison"]["Extra"])
        self.MagicTowerPrison_Deck.setValue(self.opt["MagicTowerPrison"]["Deck"])
        self.MagicTowerPrison_1P.addItems(battle_plan_list)
        self.MagicTowerPrison_1P.setCurrentIndex(self.opt["MagicTowerPrison"]["BattlePlan1P"])

        self.Warrior_Active.setChecked(self.opt["Warrior"]["Active"])
        self.Warrior_Group.setChecked(self.opt["Warrior"]["IsGroup"])
        self.Warrior_MaxTimes.setValue(self.opt["Warrior"]["MaxTimes"])
        self.Warrior_Deck.setValue(self.opt["Warrior"]["Deck"])
        self.Warrior_1P.addItems(battle_plan_list)
        self.Warrior_2P.addItems(battle_plan_list)
        self.Warrior_1P.setCurrentIndex(self.opt["Warrior"]["BattlePlan1P"])
        self.Warrior_2P.setCurrentIndex(self.opt["Warrior"]["BattlePlan2P"])

        self.CrossServer_Active.setChecked(self.opt["CrossServer"]["Active"])
        self.CrossServer_Group.setChecked(self.opt["CrossServer"]["IsGroup"])
        self.CrossServer_MaxTimes.setValue(self.opt["CrossServer"]["MaxTimes"])
        self.CrossServer_Stage.setText(self.opt["CrossServer"]["Stage"])
        self.CrossServer_Deck.setValue(self.opt["CrossServer"]["Deck"])
        self.CrossServer_1P.addItems(battle_plan_list)
        self.CrossServer_2P.addItems(battle_plan_list)
        self.CrossServer_1P.setCurrentIndex(self.opt["CrossServer"]["BattlePlan1P"])
        self.CrossServer_2P.setCurrentIndex(self.opt["CrossServer"]["BattlePlan2P"])

        self.Relic_Active.setChecked(self.opt["Relic"]["Active"])
        self.Relic_Group.setChecked(self.opt["Relic"]["IsGroup"])
        self.Relic_MaxTimes.setValue(self.opt["Relic"]["MaxTimes"])
        self.Relic_Stage.setText(self.opt["Relic"]["Stage"])
        self.Relic_Deck.setValue(self.opt["Relic"]["Deck"])
        self.Relic_1P.addItems(battle_plan_list)
        self.Relic_2P.addItems(battle_plan_list)
        self.Relic_1P.setCurrentIndex(self.opt["Relic"]["BattlePlan1P"])
        self.Relic_2P.setCurrentIndex(self.opt["Relic"]["BattlePlan2P"])

        self.NormalBattle_Active.setChecked(self.opt["NormalBattle"]["Active"])
        self.NormalBattle_Group.setChecked(self.opt["NormalBattle"]["IsGroup"])
        self.NormalBattle_MaxTimes.setValue(self.opt["NormalBattle"]["MaxTimes"])
        self.NormalBattle_Stage.setText(self.opt["NormalBattle"]["Stage"])
        self.NormalBattle_Deck.setValue(self.opt["NormalBattle"]["Deck"])
        self.NormalBattle_1P.addItems(battle_plan_list)
        self.NormalBattle_2P.addItems(battle_plan_list)
        self.NormalBattle_1P.setCurrentIndex(self.opt["NormalBattle"]["BattlePlan1P"])
        self.NormalBattle_2P.setCurrentIndex(self.opt["NormalBattle"]["BattlePlan2P"])

        self.Customize_Active.setChecked(self.opt["Customize"]["Active"])

    def ui_to_opt(self):
        # battle_plan_list
        battle_plan_list = get_battle_plan_list(with_extension=False)

        def my_transformer(change_class: object, opt_1, opt_2):
            self.opt[opt_1][opt_2] = change_class.currentIndex()
            change_class.clear()
            change_class.addItems(battle_plan_list)
            change_class.setCurrentIndex(self.opt[opt_1][opt_2])

        self.opt["GameName"] = self.GameName_Input.text()
        self.opt["Name1P"] = self.Name1P_Input.text()
        self.opt["Name2P"] = self.Name2P_Input.text()
        self.opt["ZoomRatio"] = self.ZoomRatio_Input.currentIndex()  # combobox 序号

        self.opt["Level1P"] = self.Level1P_Input.value()
        self.opt["Level2P"] = self.Level2P_Input.value()
        self.opt["AutoUseCard"] = self.AutoUseCard.isChecked()

        self.opt["GuildTask"]["Active"] = self.GuildTask_Active.isChecked()
        self.opt["GuildTask"]["Skip"] = self.GuildTask_Skip.isChecked()
        self.opt["GuildTask"]["Deck"] = self.GuildTask_Deck.value()
        my_transformer(self.GuildTask_1P, "GuildTask", "BattlePlan1P")
        my_transformer(self.GuildTask_2P, "GuildTask", "BattlePlan2P")

        self.opt["SpouseTask"]["Active"] = self.SpouseTask_Active.isChecked()
        self.opt["SpouseTask"]["Deck"] = self.SpouseTask_Deck.value()
        my_transformer(self.SpouseTask_1P, "SpouseTask", "BattlePlan1P")
        my_transformer(self.SpouseTask_2P, "SpouseTask", "BattlePlan2P")

        self.opt["OfferReward"]["Active"] = self.OfferReward_Active.isChecked()
        self.opt["OfferReward"]["Deck"] = self.OfferReward_Deck.value()
        my_transformer(self.OfferReward_1P, "OfferReward", "BattlePlan1P")
        my_transformer(self.OfferReward_2P, "OfferReward", "BattlePlan2P")

        self.opt["MagicTowerDouble"]["Active"] = self.MagicTowerDouble_Active.isChecked()
        self.opt["MagicTowerDouble"]["MaxTimes"] = self.MagicTowerDouble_MaxTimes.value()
        self.opt["MagicTowerDouble"]["Stage"] = self.MagicTowerDouble_Stage.value()
        self.opt["MagicTowerDouble"]["Deck"] = self.MagicTowerDouble_Deck.value()
        my_transformer(self.MagicTowerDouble_1P, "MagicTowerDouble", "BattlePlan1P")
        my_transformer(self.MagicTowerDouble_2P, "MagicTowerDouble", "BattlePlan2P")

        self.opt["MagicTowerAlone"]["Active"] = self.MagicTowerAlone_Active.isChecked()
        self.opt["MagicTowerAlone"]["MaxTimes"] = self.MagicTowerAlone_MaxTimes.value()
        self.opt["MagicTowerAlone"]["Stage"] = self.MagicTowerAlone_Stage.value()
        self.opt["MagicTowerAlone"]["Deck"] = self.MagicTowerAlone_Deck.value()
        my_transformer(self.MagicTowerAlone_1P, "MagicTowerAlone", "BattlePlan1P")
        self.opt["MagicTowerAlone"]["BattlePlan2P"] = None

        self.opt["MagicTowerPrison"]["Active"] = self.MagicTowerPrison_Active.isChecked()
        self.opt["MagicTowerPrison"]["Extra"] = self.MagicTowerPrison_Extra.isChecked()
        self.opt["MagicTowerPrison"]["Deck"] = self.MagicTowerPrison_Deck.value()
        my_transformer(self.MagicTowerPrison_1P, "MagicTowerPrison", "BattlePlan1P")
        self.opt["MagicTowerPrison"]["BattlePlan2P"] = None

        self.opt["Warrior"]["Active"] = self.Warrior_Active.isChecked()
        self.opt["Warrior"]["IsGroup"] = self.Warrior_Group.isChecked()
        self.opt["Warrior"]["MaxTimes"] = self.Warrior_MaxTimes.value()
        self.opt["Warrior"]["Deck"] = self.Warrior_Deck.value()
        my_transformer(self.Warrior_1P, "Warrior", "BattlePlan1P")
        my_transformer(self.Warrior_2P, "Warrior", "BattlePlan2P")

        self.opt["CrossServer"]["Active"] = self.CrossServer_Active.isChecked()
        self.opt["CrossServer"]["IsGroup"] = self.CrossServer_Group.isChecked()
        self.opt["CrossServer"]["MaxTimes"] = self.CrossServer_MaxTimes.value()
        self.opt["CrossServer"]["Stage"] = self.CrossServer_Stage.text()
        self.opt["CrossServer"]["Deck"] = self.CrossServer_Deck.value()
        my_transformer(self.CrossServer_1P, "CrossServer", "BattlePlan1P")
        my_transformer(self.CrossServer_2P, "CrossServer", "BattlePlan2P")

        self.opt["Relic"]["Active"] = self.Relic_Active.isChecked()
        self.opt["Relic"]["IsGroup"] = self.Relic_Group.isChecked()
        self.opt["Relic"]["MaxTimes"] = self.Relic_MaxTimes.value()
        self.opt["Relic"]["Stage"] = self.Relic_Stage.text()
        self.opt["Relic"]["Deck"] = self.Relic_Deck.value()
        my_transformer(self.Relic_1P, "Relic", "BattlePlan1P")
        my_transformer(self.Relic_2P, "Relic", "BattlePlan2P")

        self.opt["NormalBattle"]["Active"] = self.NormalBattle_Active.isChecked()
        self.opt["NormalBattle"]["IsGroup"] = self.NormalBattle_Group.isChecked()
        self.opt["NormalBattle"]["MaxTimes"] = self.NormalBattle_MaxTimes.value()
        self.opt["NormalBattle"]["Stage"] = self.NormalBattle_Stage.text()
        self.opt["NormalBattle"]["Deck"] = self.NormalBattle_Deck.value()
        my_transformer(self.NormalBattle_1P, "NormalBattle", "BattlePlan1P")
        my_transformer(self.NormalBattle_2P, "NormalBattle", "BattlePlan2P")

        self.opt["Customize"]["Active"] = self.Customize_Active.isChecked()

    def click_btn_save(self):
        """点击保存配置按钮的函数"""
        self.ui_to_opt()
        self.opt_to_json()

    # def click_btn_start(self):
    #     """
    #     开始/结束按钮 需要注册的函数
    #     Args:
    #         button: 被注册的按钮对象
    #     """
    #
    #     # 先刷新数据
    #     self.refresh_process_parameter(p_id)
    #
    #     if not self.dic_p["flag_activation"][p_id]:
    #         # 创建 储存 启动进程
    #         print([p_id, self.dic_p["dic_process_opt"][p_id]])
    #         self.dic_p["process"][p_id] = multiprocessing.Process(
    #             target=self.battle_all_round,
    #             args=(p_id, self.dic_p["dic_process_opt"][p_id])
    #         )
    #         print(self.dic_p["process"][p_id])
    #         self.dic_p["process"][p_id].start()
    #         # 设置按钮文本
    #         button.sender().setText("终止\nEnd")
    #         # 设置flag
    #         self.dic_p["flag_activation"][p_id] = True
    #     else:
    #         # 中止进程
    #         # if self.dic_p["process"][p_id].is_alive():  # 判断进程是否还在运作中
    #         #     self.dic_p["process"][p_id].terminate()  # 中断进程
    #         #     self.dic_p["process"][p_id].join()  # 清理僵尸进程
    #         # 设置按钮文本
    #         button.sender().setText("开始\nLink Start")
    #         # 设置进程状态文本
    #         self.findChild(QLabel, "E_{}_7_2".format(p_id * 2 + 1)).setText("已中断进程")
    #         # 设置flag
    #         self.dic_p["flag_activation"][p_id] = False


if __name__ == "__main__":
    def main():
        # 实例化 PyQt后台管理
        app = QApplication(sys.argv)

        # 实例化 主窗口
        window = MyMainWindow1()

        # 建立槽连接 注意 多线程中 槽连接必须写在主函数
        # 注册函数：开始/结束按钮
        button = window.Button_Start
        button.clicked.connect(lambda: window.click_btn_start())
        button = window.Button_Save
        button.clicked.connect(lambda: window.click_btn_save())
        # 主窗口 实现
        window.show()

        # 运行主循环，必须调用此函数才可以开始事件处理
        sys.exit(app.exec_())


    main()
