import requests

data = {
    "timestamp": 1718298801.1952991,
    "stage": "OR-0-1",
    "is_used_key": True,
    "loots": {
        "1级四叶草": 1,
        "秘制香料": 2,
        "上等香料": 1,
        "天然香料": 4,
        "礼盒": 1,
        "白砂糖": 2,
        "小蒸笼": 3,
        "葡萄": 2,
        "牛肉": 5,
        "奶酪": 3,
        "包子": 2,
        "冰块": 1,
        "煮蛋器": 1,
        "生鸡蛋": 1,
        "烤炉": 3,
        "小麦粉": 3
    },
    "chests": {
        "棉花糖-初级技能书": 1,
        "识别失败": 1
    }
}
response = requests.post(url='http://47.108.167.141:5000/faa_server', json=data)
