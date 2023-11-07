import os

from function.get_paths import get_root_path


def get_battle_plan_list(with_extension):
    """
    :param with_extension: Include extension name
    :return: a list of battle plan
    """
    my_list = os.listdir(get_root_path() + "\\config\\battle_plan\\")
    if with_extension:
        return my_list
    else:
        for i in range(len(my_list)):
            my_list[i] = my_list[i].split(".")[0]
        return my_list
