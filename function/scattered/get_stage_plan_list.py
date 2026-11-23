import os

from function.common.file_name_sort import sort_file_names_like_windows
from function.globals.get_paths import PATHS


def get_stage_plan_list(with_extension: bool):
    """获取按 Windows 资源管理器规则排序的关卡总表文件名。"""
    folder = PATHS["stage_plan"]
    if not os.path.isdir(folder):
        return []
    my_list = [name for name in os.listdir(folder) if name.lower().endswith(".json")]
    my_list = sort_file_names_like_windows(my_list)
    if with_extension:
        return my_list
    return [name.rsplit(".", 1)[0] for name in my_list]
