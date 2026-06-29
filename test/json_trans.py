import json


def add_name_field(data):
    """
    为每一层增加一个 name 字段，格式为 "name": "魔塔蛋糕第X层"
    :param data: JSON 数据
    :return: 增加了 name 字段的 JSON 数据
    """
    for key, layer in data.items():
        layer['name'] = f"萌宠神殿第{key}层"
    return data


def main():
    # 读取 JSON 文件
    file_path = 'aaa.json'
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # 增加 name 字段
    updated_data = add_name_field(data)
    print(updated_data)
    # 写回 JSON 文件
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(updated_data, file, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
