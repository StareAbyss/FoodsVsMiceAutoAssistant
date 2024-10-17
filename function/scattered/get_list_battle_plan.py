import os

from function.globals.get_paths import PATHS


def get_list_battle_plan(with_extension):
    """
    :param with_extension: Include extension name
    :return: a list of battle plan
    """

    # 获取战斗计划目录下的所有文件
    my_list = os.listdir(PATHS["battle_plan"] + "\\")

    # 过滤出 .json 文件
    my_list = [file for file in my_list if file.endswith('.json')]

    if with_extension:
        return my_list
    else:
        for i in range(len(my_list)):
            my_list[i] = my_list[i].split(".")[0]
        return my_list
