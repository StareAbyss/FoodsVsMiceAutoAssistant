import copy
import json
from pprint import pprint

from function.globals.get_paths import PATHS


def merge_settings_with_template(settings, template):
    def merge(dict1, dict2):
        for key, value in dict2.items():
            if key not in dict1:
                dict1[key] = copy.deepcopy(value)
            else:
                if isinstance(value, dict):
                    if isinstance(dict1[key], dict):
                        merge(dict1[key], value)
                    else:
                        dict1[key] = copy.deepcopy(value)
                elif isinstance(value, list):
                    if isinstance(dict1[key], list):
                        if len(dict1[key]) > 0 and isinstance(dict1[key][0], dict):
                            sample_dict = value[0]
                            for i, item in enumerate(dict1[key]):
                                if isinstance(item, dict):
                                    merge(item, sample_dict)
                                else:
                                    dict1[key] = copy.deepcopy(value)
                                    break
                    else:
                        dict1[key] = copy.deepcopy(value)
                else:
                    if not isinstance(dict1[key], type(value)):
                        dict1[key] = copy.deepcopy(value)

    settings_copy = copy.deepcopy(settings)
    merge(settings_copy, template)
    return settings_copy


# opt路径
opt_path = PATHS["root"] + "\\config\\settings.json"
# opt模板路径
opt_template_path = PATHS["root"] + "\\config\\settings_template.json"

with open(file=opt_path, mode="r", encoding="UTF-8") as file:
    data_settings = json.load(file)
with open(file=opt_template_path, mode="r", encoding="UTF-8") as file:
    data_template = json.load(file)

pprint(merge_settings_with_template(settings=data_settings, template=data_template))
