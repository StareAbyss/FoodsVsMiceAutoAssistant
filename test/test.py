import json

# 示例数据
members_data = [
    {
        "id": 123,
        "data": {
            "2024-09-08": 5948,
            "2024-09-09": 4564
        }
    }
]

# 保存路径
output_path = "members_data.json"

# 保存数据到 JSON 文件
with open(output_path, 'w', encoding='utf-8') as json_file:
    json.dump(members_data, json_file, ensure_ascii=False, indent=4)

print(f"数据已保存到 {output_path}")
