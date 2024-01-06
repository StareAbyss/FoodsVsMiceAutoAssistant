from pprint import pprint

from function.script.service.common import FAA
from function.script.service.round_of_battle_calculation_arrange import calculation_cell_all_card

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
        list_ban_card = []
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
