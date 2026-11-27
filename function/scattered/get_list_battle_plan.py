import os

from function.common.file_name_sort import sort_file_names_like_windows
from function.globals.get_paths import PATHS


def get_list_battle_plan(with_extension:bool):
    """
    获取按 Windows 资源管理器规则排序的战斗方案文件名。

    Args:
        with_extension: 是否在返回结果中保留 `.json` 扩展名。

    Returns:
        排序后的战斗方案文件名列表；根据 `with_extension` 保留或移除扩展名。
    """

    # 获取战斗计划目录下的所有文件
    my_list = os.listdir(PATHS["battle_plan"])

    # 过滤出 .json 文件
    my_list = [file for file in my_list if file.endswith('.json')]

    # 按 Windows 资源管理器的自然排序规则排列文件名
    my_list = sort_file_names_like_windows(my_list)

    if with_extension:
        return my_list
    else:
        for i in range(len(my_list)):
            my_list[i] = my_list[i].rsplit('.', 1)[0]
        return my_list


def get_list_tweak_plan(with_extension:bool):
    """
    获取按 Windows 资源管理器规则排序的微调方案文件名。

    Args:
        with_extension: 是否在返回结果中保留 `.json` 扩展名。

    Returns:
        排序后的微调方案文件名列表；根据 `with_extension` 保留或移除扩展名。
    """

    # 获取战斗计划目录下的所有文件
    my_list = os.listdir(PATHS["tweak_battle_plan"])

    # 过滤出 .json 文件
    my_list = [file for file in my_list if file.endswith('.json')]

    # 按 Windows 资源管理器的自然排序规则排列文件名
    my_list = sort_file_names_like_windows(my_list)

    if with_extension:
        return my_list
    else:
        for i in range(len(my_list)):
            my_list[i] = my_list[i].rsplit('.', 1)[0]
        return my_list
