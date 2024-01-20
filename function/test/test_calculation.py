from pprint import pprint

from function.script.service.common import FAA

if __name__ == '__main__':
    def test():
        faa = FAA()

        faa.set_config_for_battle(
            stage_id="MT-1-81",
            quest_card="None",
            ban_card_list=[
                "糖葫芦炮弹",
                "瓜皮护罩",
                "狮子座精灵",
                "油灯",
                "樱桃反弹布丁",
                "苏打气泡",
                "麦芽糖"]
        )

        mat_card_position = faa.get_mat_card_position()
        list_cell_all, list_shovel = faa.calculation_cell_all_card(
            mat_card_position=mat_card_position)

        pprint(list_cell_all)
        pprint(list_shovel)


    test()
