from pprint import pprint

from function.script.service.calculation_battle_arrange import calculation_cell_all_card
from function.script.service.common import FAA

if __name__ == '__main__':
    def test():
        stage_id = "MT-1-81"
        is_group = False

        faa = FAA()
        faa.get_config_for_battle(
            is_group=is_group,
            battle_plan_index=13,
            stage_id=stage_id)

        quest_card = "None"
        list_ban_card = [
            "糖葫芦炮弹",
            "瓜皮护罩",
            "狮子座精灵",
            "油灯",
            "樱桃反弹布丁",
            "苏打气泡",
            "麦芽糖"]

        list_cell_all, list_shovel = calculation_cell_all_card(
            stage_info=faa.stage_info,
            battle_plan=faa.battle_plan["card"],
            player=faa.player,
            is_group=is_group,
            quest_card=quest_card,
            list_ban_card=list_ban_card)

        pprint(list_cell_all)
        pprint(list_shovel)


    test()
