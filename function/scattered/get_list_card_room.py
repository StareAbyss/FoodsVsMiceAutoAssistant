import os

from function.globals.get_paths import PATHS


def get_list_card_room(with_extension):
    """
    :param with_extension: Include extension name
    :return: a list of battle plan
    """
    my_list = os.listdir(PATHS["picture"]["card"] + "\\房间")
    if with_extension:
        return my_list
    else:
        for i in range(len(my_list)):
            my_list[i] = my_list[i].split(".")[0]
        return my_list


if __name__ == '__main__':
    print(get_list_card_room(with_extension=True))
