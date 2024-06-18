import cProfile
import json
import os
import random

from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER

"""
FAA战斗结果分析模块 - 战利品识别与自主学习的异元素融合:有向无环图驱动的高效算法.
基于拓扑排序的异元素战利品识别与自主学习系统, 通过多次迭代自学习战利品出现顺序的规律性,构建有向无环图模型.
利用图论中的拓扑排序算法, 获取最优识别任务序列, 避免重复遍历, 将时间复杂度降低至开双重根号量级.
该系统经过深度优化, 算法效率卓越, 识别准确高效.
致谢: 八重垣天知 
参考文献: "Topological sorting of large networks" (Communications of the ACM, 1962)
"""


def update_ranking(item_list_new):
    """
    根据list中各个物品(str格式)的排序 来保存成一个json文件
    会根据本次输入, 和保存的之前的图比较, 以排序, 最终获得几乎所有物品的物品的结果表
    使用有向无环图, 保留无法区分前后的数据
    :param item_list_new 物品顺序 list 仅一维
    :return: 也就是json的格式
    {
        "ranking": [["物品1"], ["物品2","物品4"], ["物品5"],...] //在ranking中, 0维度代表顺序, 第1维度是无法区分前后的同一级元素
        "ranking_easy": ["物品1", "物品2","物品4", "物品5",...] // 去括号方便直接被调用
    }
    """
    # 读取现 JSON 文件
    json_path = PATHS["logs"] + "\\item_ranking_.json"
    data = ranking_read_data(json_path=json_path)
    # 更新 ranking 有向图
    result = find_total_order(
        item_list_new=item_list_new,
        graph=data.get('graph'),
    )
    data['ranking'] = result[0] if result[0] else data['ranking']
    data['graph'] = result[1]

    # 更新 easy 版
    data['ranking_easy'] = data['ranking']

    # 保存更新后的 JSON 文件
    ranking_save_data(json_path=json_path, data=data)
    return data


def ranking_read_data(json_path):
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "ranking" in data:
                return data
    return {'ranking': [], "ranking_easy": [], 'graph': []}


def ranking_save_data(json_path, data):
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def build_graph(item_list_new, graph):
    """根据输入列表, 构造有向无环图"""
    # 继承老数据
    graph = dict() if not graph else graph  # 图表 用 { x : [a,b,c] , ... } 代表多个有向边 也就是 出度

    # seq 一组数据 例如: ["物品1", "物品2","物品4", "物品5",...]
    for i in range(len(item_list_new)):
        # 例如: "物品1"
        item_1 = item_list_new[i]
        # 首次添加 入度0
        if item_1 not in graph.keys():
            graph[item_1] = []
        # 仅两两一组进行创建边
        if i < len(item_list_new) - 1:
            item_2 = item_list_new[i + 1]
            # 首次添加 入度0
            if item_2 not in graph[item_1]:
                # 图中 item 1 -> item 2
                graph[item_1].append(item_2)
    return graph


def find_total_order(item_list_new, graph):
    """
    构造有向无环图, 并计算新顺序
    """
    # 构造有向无环图
    graph = build_graph(item_list_new=item_list_new, graph=graph)
    # 根据图计算顺序
    result = find_longest_path(graph=graph)
    if result:
        return result, graph
    else:
        # 没有有效的拓扑排序 让那边自己返回旧记录...
        return None, graph


import networkx as nx


def find_longest_path(graph):
    G = nx.DiGraph()

    # 添加边到图中
    for node, neighbors in graph.items():
        for neighbor in neighbors:
            G.add_edge(node, neighbor)

    # 寻找最长路径
    try:
        # nx.dag_longest_path 返回的是节点序列，如果图中存在环，则此函数会抛出错误
        longest_path = nx.dag_longest_path(G)
    except nx.NetworkXError:
        # 如果图不是DAG（有向无环图），则无法找到最长路径
        CUS_LOGGER.error("图中存在环，无法确定最长路径。")
        return None

    return longest_path


if __name__ == '__main__':
    # Example usage:
    def generate_ordered_sequences(alphabets, num_sequences=1000, sequence_length=15):
        """
        生成指定数量和长度的有序字母序列列表。
        :param alphabets: 样本集, 构成序列的内容 它需要是可排序的 比如字符串 或 数字
        :param num_sequences: 生成序列的数量，默认100。
        :param sequence_length: 序列内数字的数量，默认10。
        :return: 包含有序数字序列的列表。
        """
        all_sequences = []

        for _ in range(num_sequences):
            # 随机选择不重复的
            selected_letters = random.sample(alphabets, sequence_length)
            # 排序选出的字母以确保序列是有序的
            sorted_sequence = sorted(selected_letters)
            all_sequences.append(sorted_sequence)

        return all_sequences


    def test_match():
        alphabets = [str(num) for num in range(100)]  # 获取数字 为str格式

        # 生成示例训练数据
        sequences = generate_ordered_sequences(alphabets=alphabets)

        # # 训练

        for item_list in sequences[:-1]:
            data_json = update_ranking(item_list)
        # 训练结果
        easy_ranking = data_json["ranking_easy"]
        print("训练结果:")
        print(data_json)

        # 如果完全不训练
        # easy_ranking = []

        # 测试目标
        test_line = sequences[-1]

        last_find_bet = None

        match_times_count = 0
        for item in easy_ranking:
            if item in alphabets:
                alphabets.remove(item)

        for test_bet in test_line:

            find_it_flag = False

            # 先试试上一个对不对
            if test_bet == last_find_bet:
                find_it_flag = True
                match_times_count += 1

            if find_it_flag:
                continue

            find_it_flag = False
            for tar_bet in easy_ranking:
                match_times_count += 1
                if tar_bet == test_bet:
                    find_it_flag = True
                    last_find_bet = tar_bet  # 记录上一个找到的
                    break
                else:
                    easy_ranking.remove(tar_bet)

            if find_it_flag:
                continue

            #  全部遍历
            for tar_bet in alphabets:
                match_times_count += 1
                if tar_bet == test_bet:
                    last_find_bet = tar_bet  # 记录上一个找到的
                    break

            # 恢复easy_ranking
            easy_ranking = data_json["ranking_easy"]

        return match_times_count


    def get_average(lst):
        if not lst:
            return None
        total = sum(lst)
        count = len(lst)
        average = total / count
        return average


    def test_match_some_times():

        all_times = 10
        test_one_spend_match_time_list = []
        for i in range(all_times):
            test_one_spend_match_time = test_match()
            test_one_spend_match_time_list.append(test_one_spend_match_time)
        print(f"{all_times}次测试, "
              f"可能出现在序列中的总元素数量:100个, "
              f"训练集样本序列:1000条, "
              f"每条序列(样本和目标)包含元素:15个, "
              f"平均匹配次数: {get_average(test_one_spend_match_time_list)}")

if __name__ == '__main__':
    def main_1():
        test_match_some_times()


    def biuld_dag_find_longest_path():
        graph = {
            "城堡钥匙": [
                "2级四叶草",
                "3级四叶草"
            ],
            "2级四叶草": [
                "秘制香料",
                "上等香料",
                "煮蛋器投手-初级技能书",
                "番茄色拉投手-高级技能书",
                "巧克力投手-高级技能书",
                "天然香料",
                "煮蛋器投手-高级技能书",
                "极品香料",
                "1级四叶草",
                "国王小笼包-高级技能书"
            ],
            "秘制香料": [
                "上等香料",
                "天然香料",
                "番茄色拉投手配方",
                "三线酒架配方",
                "开水壶炸弹配方",
                "白砂糖",
                "小蒸笼",
                "礼盒"
            ],
            "上等香料": [
                "天然香料",
                "番茄色拉投手配方",
                "三线酒架配方",
                "开水壶炸弹配方",
                "巧克力投手配方",
                "小刀",
                "麻辣串炸弹配方",
                "蛋筒",
                "三向小笼包配方",
                "礼盒",
                "猫猫箱配方",
                "热狗大炮配方",
                "椰奶"
            ],
            "天然香料": [
                "三线酒架配方",
                "番茄色拉投手配方",
                "双层小笼包配方",
                "瓜皮护罩配方",
                "煮蛋器投手配方",
                "红豆腐",
                "油灯配方",
                "巧克力投手配方",
                "猫猫盒配方",
                "关东煮喷锅配方",
                "双层冰冻小笼包配方",
                "棉花糖配方",
                "麻辣串炸弹配方",
                "冰激凌配方",
                "三向冰冻小笼包配方",
                "生菜",
                "三向小笼包配方",
                "白砂糖",
                "葡萄",
                "礼盒"
            ],
            "三线酒架配方": [
                "瓜皮护罩配方",
                "双层小笼包配方",
                "煮蛋器投手配方",
                "番茄",
                "红豆腐",
                "巧克力面包配方",
                "生菜"
            ],
            "瓜皮护罩配方": [
                "煮蛋器投手配方",
                "双层小笼包配方",
                "红豆腐",
                "番茄"
            ],
            "煮蛋器投手配方": [
                "番茄",
                "色拉酱",
                "红豆腐",
                "菠萝",
                "白砂糖",
                "巧克力面包配方"
            ],
            "番茄": [
                "白砂糖",
                "色拉酱",
                "红豆腐",
                "菠萝",
                "小蒸笼",
                "筷子"
            ],
            "白砂糖": [
                "小蒸笼",
                "小刀",
                "酒瓶",
                "葡萄",
                "水壶",
                "生鸡蛋"
            ],
            "小蒸笼": [
                "小刀",
                "西瓜",
                "木块",
                "酒瓶",
                "餐叉",
                "酒架",
                "葡萄",
                "钢管",
                "水壶",
                "牛肉"
            ],
            "小刀": [
                "木块",
                "西瓜",
                "酒架",
                "酒瓶",
                "餐叉",
                "铁丝",
                "扇片",
                "葡萄",
                "巧克力",
                "水壶"
            ],
            "木块": [
                "酒瓶",
                "酒架",
                "贪吃猫",
                "餐叉",
                "包子",
                "袋子",
                "发动机",
                "面饼",
                "火药",
                "煤油"
            ],
            "酒瓶": [
                "餐叉",
                "酒架",
                "包子",
                "煮蛋器",
                "包装袋",
                "贪吃猫"
            ],
            "餐叉": [
                "包子",
                "煮蛋器",
                "贪吃猫",
                "小麦粉",
                "汤勺",
                "火药"
            ],
            "包子": [
                "煮蛋器",
                "贪吃猫",
                "小麦粉",
                "汤勺",
                "冰块",
                "火药",
                "无烟煤",
                "纯净水"
            ],
            "煮蛋器": [
                "汤勺",
                "小麦粉",
                "纯净水",
                "生鸡蛋",
                "烤炉"
            ],
            "汤勺": [
                "小麦粉",
                "纯净水",
                "巧克力",
                "生鸡蛋"
            ],
            "小麦粉": [
                "纯净水"
            ],
            "纯净水": [],
            "番茄色拉投手配方": [
                "三线酒架配方",
                "瓜皮护罩配方",
                "双层小笼包配方",
                "面粉袋配方"
            ],
            "双层小笼包配方": [
                "煮蛋器投手配方",
                "番茄",
                "红豆腐"
            ],
            "色拉酱": [
                "红豆腐",
                "菠萝",
                "白砂糖",
                "奶油",
                "小蒸笼",
                "礼盒",
                "电鳗鱼肉"
            ],
            "红豆腐": [
                "菠萝",
                "白砂糖",
                "小蒸笼",
                "葡萄"
            ],
            "菠萝": [
                "白砂糖",
                "小蒸笼",
                "小刀"
            ],
            "西瓜": [
                "木块",
                "酒架",
                "酒瓶"
            ],
            "酒架": [
                "包子",
                "餐叉",
                "贪吃猫",
                "煮蛋器",
                "汤勺",
                "小麦粉",
                "发动机",
                "包装袋",
                "火药",
                "阀门"
            ],
            "贪吃猫": [
                "煮蛋器",
                "小麦粉",
                "汤勺",
                "无烟煤",
                "纯净水"
            ],
            "煮蛋器投手-初级技能书": [
                "上等香料",
                "极品香料",
                "秘制香料",
                "番茄色拉投手-高级技能书",
                "巧克力投手-高级技能书",
                "天然香料"
            ],
            "3级四叶草": [
                "极品香料",
                "煮蛋器投手-初级技能书",
                "煮蛋器投手-高级技能书",
                "秘制香料",
                "天然香料",
                "巧克力大炮-初级技能书",
                "三向小笼包配方",
                "麻辣串炸弹配方",
                "上等香料",
                "冰煮蛋器投手-初级技能书",
                "机枪冰冻小笼包-初级技能书",
                "2级四叶草",
                "1级四叶草",
                "国王小笼包-高级技能书"
            ],
            "极品香料": [
                "上等香料",
                "秘制香料",
                "天然香料",
                "三向冰冻小笼包配方",
                "礼盒",
                "皇室香料"
            ],
            "煮蛋器投手-高级技能书": [
                "极品香料",
                "秘制香料"
            ],
            "番茄色拉投手-高级技能书": [
                "上等香料",
                "秘制香料"
            ],
            "巧克力投手-高级技能书": [
                "秘制香料"
            ],
            "轰炸宝石": [
                "城堡钥匙",
                "2级四叶草"
            ],
            "城堡徽章A": [
                "上等香料",
                "秘制香料",
                "天然香料",
                "1级四叶草"
            ],
            "葡萄": [
                "酒架",
                "火药",
                "牛肉",
                "生鸡蛋",
                "巧克力",
                "奶酪",
                "酒瓶"
            ],
            "发动机": [
                "汤勺",
                "包装袋",
                "袋子"
            ],
            "巧克力": [
                "小麦粉"
            ],
            "强化水晶": [
                "城堡徽章A",
                "皇室香料",
                "火山徽章B"
            ],
            "火药": [
                "生鸡蛋",
                "冰块",
                "煮蛋器",
                "纯净水",
                "小麦粉",
                "贪吃猫"
            ],
            "生鸡蛋": [
                "巧克力",
                "小麦粉",
                "烤炉",
                "纯净水"
            ],
            "开水壶炸弹配方": [
                "换气扇配方",
                "礼盒",
                "油灯配方",
                "三线酒架配方",
                "生菜"
            ],
            "换气扇配方": [
                "酒瓶"
            ],
            "包装袋": [
                "火药",
                "冰块",
                "生鸡蛋"
            ],
            "冰块": [
                "贪吃猫",
                "鲜鱼",
                "小麦粉",
                "煮蛋器",
                "生鸡蛋"
            ],
            "无烟煤": [
                "纯净水",
                "巧克力"
            ],
            "深渊徽章B": [
                "天然香料"
            ],
            "油灯配方": [
                "小蒸笼",
                "肉丁",
                "汤料",
                "果冻胶",
                "礼盒"
            ],
            "钢管": [
                "包装袋"
            ],
            "巧克力投手配方": [
                "三线酒架配方"
            ],
            "巧克力面包配方": [
                "番茄"
            ],
            "筷子": [
                "小蒸笼",
                "白砂糖"
            ],
            "铁丝": [
                "木块"
            ],
            "袋子": [
                "冰块",
                "包装袋"
            ],
            "鲜鱼": [
                "纯净水"
            ],
            "三通管": [
                "小刀",
                "白砂糖",
                "葡萄",
                "小蒸笼"
            ],
            "助人为乐宝箱": [
                "2级四叶草",
                "秘制香料",
                "礼盒",
                "冰冻小笼包-初级技能书",
                "白砂糖",
                "上等香料",
                "鱼刺配方",
                "葡萄",
                "白银徽章"
            ],
            "礼盒": [
                "白砂糖",
                "电鳗鱼肉",
                "小蒸笼",
                "葡萄",
                "假牙",
                "冰包子"
            ],
            "牛肉": [
                "奶酪",
                "火药",
                "木块",
                "包子",
                "冰块"
            ],
            "奶酪": [
                "包子",
                "火药",
                "冰块"
            ],
            "烤炉": [
                "小麦粉"
            ],
            "神殿徽章A": [
                "天然香料"
            ],
            "猫猫盒配方": [
                "面粉袋配方",
                "白砂糖"
            ],
            "面粉袋配方": [
                "小蒸笼",
                "木块",
                "老鼠夹子配方"
            ],
            "面饼": [
                "包子"
            ],
            "港口徽章B": [
                "1级四叶草"
            ],
            "1级四叶草": [
                "秘制香料",
                "天然香料",
                "上等香料",
                "极品香料",
                "三线酒架-初级技能书"
            ],
            "关东煮喷锅配方": [
                "樱桃反弹布丁配方"
            ],
            "樱桃反弹布丁配方": [
                "双层冰冻小笼包配方"
            ],
            "双层冰冻小笼包配方": [
                "肉丁",
                "开水壶炸弹配方",
                "三向小笼包配方"
            ],
            "肉丁": [
                "果冻胶"
            ],
            "果冻胶": [
                "礼盒",
                "色拉酱",
                "三通管",
                "生鸡蛋",
                "假牙",
                "白砂糖",
                "小刀",
                "樱桃"
            ],
            "电鳗鱼肉": [
                "白砂糖",
                "冰包子"
            ],
            "水壶": [
                "牛肉",
                "砂纸",
                "葡萄",
                "扇片",
                "木块"
            ],
            "棉花糖配方": [
                "鱼丸",
                "蛋筒"
            ],
            "鱼丸": [
                "果冻胶",
                "三通管"
            ],
            "奶油": [
                "冰包子",
                "礼盒"
            ],
            "冰包子": [
                "白砂糖",
                "三通管",
                "菠萝"
            ],
            "砂纸": [
                "木块",
                "啤酒"
            ],
            "火山徽章B": [
                "上等香料",
                "秘制香料"
            ],
            "麻辣串炸弹配方": [
                "三向小笼包配方",
                "蛋筒",
                "生菜",
                "三向冰冻小笼包配方",
                "棉花糖配方"
            ],
            "三向小笼包配方": [
                "棉花糖配方",
                "蛋筒",
                "生菜",
                "鱼丸",
                "开水壶炸弹配方"
            ],
            "蛋筒": [
                "樱桃",
                "果冻胶",
                "鱼丸",
                "三通管"
            ],
            "樱桃": [
                "三通管",
                "奶油",
                "色拉酱"
            ],
            "扇片": [
                "砂纸"
            ],
            "啤酒": [
                "阀门",
                "木块"
            ],
            "阀门": [
                "汤勺"
            ],
            "冰激凌配方": [
                "麻辣串炸弹配方"
            ],
            "火山钥匙": [
                "巧克力大炮-初级技能书",
                "3级四叶草",
                "秘制香料",
                "冰煮蛋器投手-初级技能书",
                "极品香料"
            ],
            "巧克力大炮-初级技能书": [
                "上等香料",
                "冰煮蛋器投手-初级技能书",
                "皇室香料",
                "秘制香料",
                "蛋筒"
            ],
            "三向冰冻小笼包配方": [
                "生菜",
                "三向小笼包配方",
                "蛋筒",
                "热狗大炮配方"
            ],
            "生菜": [
                "蛋筒",
                "鱼丸",
                "假牙",
                "色拉酱"
            ],
            "冰煮蛋器投手-初级技能书": [
                "天然香料",
                "上等香料",
                "极品香料"
            ],
            "假牙": [
                "三通管",
                "白砂糖",
                "葡萄"
            ],
            "皇室香料": [
                "天然香料",
                "三向冰冻小笼包配方"
            ],
            "机枪冰冻小笼包-初级技能书": [
                "皇室香料",
                "极品香料",
                "天然香料"
            ],
            "热狗大炮配方": [
                "三向小笼包配方",
                "猫猫箱配方"
            ],
            "4级四叶草": [
                "3级四叶草",
                "2级四叶草"
            ],
            "冰冻小笼包-初级技能书": [
                "猫猫盒配方"
            ],
            "鱼刺配方": [
                "礼盒"
            ],
            "遗迹古券": [
                "皇室香料",
                "金食神宝箱菜谱碎片"
            ],
            "威望币": [
                "皇室香料",
                "极品香料",
                "强化水晶"
            ],
            "幸运金币": [
                "花园钥匙"
            ],
            "花园钥匙": [
                "2级四叶草",
                "3级四叶草"
            ],
            "国王小笼包-高级技能书": [
                "生煎锅-高级技能书"
            ],
            "生煎锅-高级技能书": [
                "麻辣香锅-高级技能书"
            ],
            "麻辣香锅-高级技能书": [
                "肥牛火锅-高级技能书"
            ],
            "肥牛火锅-高级技能书": [
                "极品香料",
                "秘制香料"
            ],
            "猫猫箱配方": [
                "开水壶炸弹配方"
            ],
            "煤油": [
                "酒瓶"
            ],
            "港口徽章A": [
                "秘制香料"
            ],
            "汤料": [
                "果冻胶"
            ],
            "北极贝徽章B": [
                "上等香料",
                "2级四叶草"
            ],
            "椰奶": [
                "三通管"
            ],
            "白银徽章": [
                "赤铜徽章"
            ],
            "赤铜徽章": [
                "1级四叶草",
                "2级四叶草"
            ],
            "三线酒架-初级技能书": [
                "小笼包-初级技能书"
            ],
            "小笼包-初级技能书": [
                "极品香料"
            ],
            "老鼠夹子配方": [
                "小蒸笼"
            ],
            "金食神宝箱菜谱碎片": [
                "皇室香料"
            ]
        }

        print(find_total_order(item_list_new=[],graph=graph))

    cProfile.run("biuld_dag_find_longest_path()")
