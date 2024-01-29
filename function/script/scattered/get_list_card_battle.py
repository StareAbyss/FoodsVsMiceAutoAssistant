import os

from function.get_paths import paths


def get_list_card_battle(with_extension):
    """
    :param with_extension: Include extension name
    :return: a list of battle plan
    """
    my_list = os.listdir(paths["picture"]["card"] + "\\战斗")
    if with_extension:
        return my_list
    else:
        for i in range(len(my_list)):
            my_list[i] = my_list[i].split(".")[0]
        return my_list
