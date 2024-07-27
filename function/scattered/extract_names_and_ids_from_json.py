import json

from function.globals.get_paths import PATHS


def extract_names_and_ids_from_json():
    # 读取JSON文件
    with open(file=PATHS["config"] + "//stage_info.json", mode="r", encoding="UTF-8") as file:
        stages_info = json.load(file)

    def extract_names_and_ids(json_data, prefix=""):
        result_dict = {}
        for key, value in json_data.items():
            if isinstance(value, dict):
                # 检查key是否为数字且prefix以"NO", "EX", 或"CS"开头
                if key.isdigit() and (prefix.startswith("NO") or prefix.startswith("EX") or prefix.startswith("CS")):
                    new_prefix = f"{prefix}-{key}" if prefix else str(key)
                    result_dict.update(extract_names_and_ids(value, new_prefix))
            elif key == "name":
                result_dict[value] = prefix
        return result_dict

    # 初始化结果字典
    final_result = {}

    # 假设你的JSON数据的顶级键包含"NO", "EX", 和"CS"
    for top_key in ['NO', 'EX', 'CS']:
        if top_key in stages_info:
            final_result.update(extract_names_and_ids(stages_info[top_key], top_key))

    return final_result
