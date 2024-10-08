from function.common.bg_img_match import match_p_in_w
from function.globals.g_resources import RESOURCE_P


def get_position_card_deck_in_battle(handle, handle_360):
    """识别火苗偏移 True 代表13+张卡 否则 12-张卡，位置为每张卡最左上的一个像素"""
    # 循环查找火苗图标 找到战斗开始
    find = match_p_in_w(
        source_handle=handle,
        source_root_handle=handle_360,
        source_range=[0, 0, 950, 600],
        template=RESOURCE_P["common"]["战斗"]["战斗中_火苗能量.png"])
    if find == [175, 36]:
        # 12-张卡
        my_dict = {
            1: [212, 10],  # X + 53
            2: [265, 10],
            3: [318, 10],
            4: [371, 10],
            5: [424, 10],
            6: [477, 10],
            7: [530, 10],
            8: [583, 10],
            9: [636, 10],
            10: [689, 10],
            11: [742, 10],
            12: [795, 10]}
    else:
        # 13+张卡
        my_dict = {
            1: [191, 10],  # X + 53
            2: [244, 10],
            3: [297, 10],
            4: [350, 10],
            5: [403, 10],
            6: [456, 10],
            7: [509, 10],
            8: [562, 10],
            9: [615, 10],
            10: [668, 10],
            11: [721, 10],
            12: [774, 10],
            13: [827, 10],
            14: [880, 10],
            15: [880, 78],  # Y + 68
            16: [880, 146],
            17: [880, 214],
            18: [880, 282],
            19: [880, 350],
            20: [880, 418],
            21: [880, 486]
        }
    return my_dict


if __name__ == '__main__':
    pass
    # def main():
    #     handle = faa_get_handle(channel="锑食", mode="flash")
    #     print(get_position_card_deck_in_battle(handle=handle))
    #
    #
    # main()
