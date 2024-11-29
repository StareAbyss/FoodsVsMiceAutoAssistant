import json

from function.globals.get_paths import PATHS


def extract_names_and_ids_from_json():
    """
    :return: {str-stage_name: str-stage_id,...}
    """

    # 读取JSON文件
    with open(file=PATHS["config"] + "//stage_info.json", mode="r", encoding="UTF-8") as file:
        stages_info = json.load(file)

    result_dict = {}

    for c_type, sub_types in stages_info.items():

        # if not s_type.isdigit():
        #     continue
        if c_type not in ["NO", "EX", "CS"]:
            continue
        if not isinstance(sub_types, dict):
            continue

        for c_sub_type, stages in sub_types.items():
            if not c_sub_type.isdigit():
                continue
            if not isinstance(stages, dict):
                continue

            for c_stage, stage in stages.items():
                if not c_stage.isdigit():
                    continue
                if not isinstance(stage, dict):
                    continue

                full_code = f"{c_type}-{c_sub_type}-{c_stage}"
                name = stage.get("name")
                if name:
                    result_dict[name] = full_code

    return result_dict
