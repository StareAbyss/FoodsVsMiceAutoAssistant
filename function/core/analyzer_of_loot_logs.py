import copy
import json
import os
import time

import networkx as nx
from cv2 import imencode

from function.common.same_size_match import one_item_match, match_block_equal_in_images
from function.globals import EXTRA
from function.globals import g_resources
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER

"""
FAA战斗结果分析模块 - 战利品识别与自主学习的异元素融合:有向无环图驱动的高效算法.
基于拓扑排序的异元素战利品识别与自主学习系统, 通过多次迭代自学习战利品出现顺序的规律性,构建有向无环图模型.
使用最长链, 获取最优识别任务序列, 避免重复遍历, 将时间复杂度大幅降低.
该系统经过深度优化, 算法效率卓越, 识别准确高效.
致谢: 八重垣天知 
参考文献: "Topological sorting of large networks" (Communications of the ACM, 1962)
上文由AI生成, 是某人中二病犯病的产物 :D
"""


def match_items_from_image_and_save(img_save_path, image, mode='loots', test_print=False):
    """
    保存图片, 分析图片，获取战利品字典
    [不包含] 判定字典有效性 输出到日志 输出到服务器
    :param img_save_path: 图片保存路径
    :param image: 图片文件  numpy.ndarray
    :param mode: 识别模式
    :param test_print: 是否输出调试信息
    :return: 战利品字典 不要输出None
    """

    # 全局启动 或者 调用启动
    test_print = test_print or EXTRA.EXTRA_LOG_MATCH

    # 统计耗时
    time_start = time.time()

    # 判断mode和method正确:
    if mode not in ["loots", "chests"]:
        raise ValueError("mode参数错误")

    # 保存图片
    imencode('.png', image)[1].tofile(img_save_path)

    block_list = split_image_to_blocks(image=image, mode=mode)

    # 保存最佳匹配道具的识图数据
    best_match_items = []
    # 保留上一次的识别图片名
    last_name = None

    if mode == 'loots':

        # 读取现 JSON Ranking 文件
        json_path = PATHS["logs"] + "\\item_ranking_dag_graph.json"
        ranking_list = ranking_read_data(json_path=json_path)["ranking"]

        # 获取列表的迭代器 从上一个检测的目标开始, 迭代已记录的json顺序中后面的部分
        list_iter = iter(copy.deepcopy(ranking_list))

        # 按照分割规则，遍历分割每一块，然后依次识图
        for block in block_list:

            # loots
            best_match_item, list_iter, _ = match_what_item_is(
                block=block, list_iter=list_iter, last_name=last_name, may_locked=False)

            if best_match_item in ['None-0', 'None-1', 'None-2']:
                # 识别为无 后面的就不用识别了 该block自身也不用统计
                break

            if best_match_item:
                best_match_items.append(best_match_item)

                # 如果不是识别失败,就暂时保存上一次的图片名,下次识图开始时额外识别一次上一次图片
            if best_match_item != "识别失败":
                last_name = best_match_item
            if best_match_item == "识别失败":
                list_iter = iter(copy.deepcopy(ranking_list))  # 重新获取迭代器

    if mode == 'chests':

        # 获取列表迭代器为空, 之后都会以空传递 (即不激活 但需要该参数不断传递)
        list_iter = None

        # 按照分割规则，遍历分割每一块，然后依次识图
        for block in block_list:
            # chests
            best_match_item, list_iter, is_locked = match_what_item_is(
                block=block, list_iter=list_iter, last_name=last_name, may_locked=True)

            if best_match_item in ['None-0', 'None-1', 'None-2']:
                # 识别为无 后面的就不用识别了 该block自身也不用统计
                break

            if is_locked:
                best_match_item_with_locked = f"{best_match_item}-绑定"
            else:
                best_match_item_with_locked = best_match_item

            if best_match_item:
                best_match_items.append(best_match_item_with_locked)

            # 如果不是识别失败,就暂时保存上一次的图片名,下次识图开始时额外识别一次上一次图片
            if best_match_item != "识别失败":
                last_name = best_match_item

    # 把识别结果显示到界面上
    if test_print:
        CUS_LOGGER.info(f"match_items_from_image方法 战利品识别结果：{best_match_items}")

    # 统计耗时
    if mode == 'loots' and test_print:
        CUS_LOGGER.debug(f"一次战利品识别耗时:{time.time() - time_start}s")

    # 返回识别结果
    return best_match_items


def split_image_to_blocks(image, mode):
    # 单个图片的列表
    block_list = []
    # 按模式分割图片
    if mode == 'loots':
        # 战利品模式 把每张图片分割成35 * 35像素的块，间隔的x与y都是49
        rows = 5
        column = 10
        for i in range(rows):
            for j in range(column):
                # 切分为 49x49 block = img[i * 49:(i + 1) * 49, j * 49:(j + 1) * 49, :]
                # 切分为 44x44 block = block[1:-4, 1:-4, :]
                block_list.append(image[i * 49 + 1: (i + 1) * 49 - 4, j * 49 + 1: (j + 1) * 49 - 4, :])
    if mode == 'chests':
        # 开宝箱模式 先切分为 44x44
        for i in range(0, image.shape[1], 44):
            block_list.append(image[:, i:i + 44, :])
    return block_list


def match_what_item_is(block, list_iter=None, last_name=None, may_locked=True):
    """
    :param block: 44x44的 numpy.array 图片
    :param list_iter: 迭代器
    :param last_name: 上次名称
    :param may_locked: 是否检测潜在的绑定物品
    :return: str: 优秀匹配结果物品名称 or "识别失败" , 迭代器, 是否是绑定的
    """

    item_is_bind = False
    if may_locked:
        item_is_bind, _ = one_item_match(img_block=block, img_tar=None, mode="match_is_bind")

    if item_is_bind:
        # 全部遍历, 绑定物品只有开箱子会有 一般不会出现两个重复的识别结果 顺序表也不是为绑定物品准备

        for item_name, item_img in g_resources.RESOURCE_P["item"]["战利品"].items():
            item_name = item_name.replace(".png", "")
            # 对比 block 和 target_image 识图成功 返回识别的道具名称(不含扩展名)
            is_it, _ = one_item_match(img_block=block, img_tar=item_img, mode="match_template_with_mask_locked")
            if is_it:
                return item_name, list_iter, True

    """未识别到绑定角标"""

    # 如果上次识图成功, 则再试一次, 看看是不是同一张图
    if last_name is not None:
        item_img = g_resources.RESOURCE_P["item"]["战利品"][last_name + ".png"]

        # 对比 block 和 target_image 识图成功 返回识别的道具名称(不含扩展名)
        is_it, _ = one_item_match(img_block=block, img_tar=item_img, mode="match_template_with_mask_tradable")
        if is_it:
            return last_name, list_iter, False

    # 先按照顺序表遍历, 极大减少耗时(如果有顺序表)
    if list_iter:
        for item_name in list_iter:
            item_img = g_resources.RESOURCE_P["item"]["战利品"][item_name + ".png"]

            # 对比 block 和 target_image 识图成功 返回识别的道具名称(不含扩展名)
            is_it, _ = one_item_match(img_block=block, img_tar=item_img, mode="match_template_with_mask_tradable")
            if is_it:
                return item_name, list_iter, False

    # 如果在json中按顺序查找没有找到, 全部遍历
    for item_name, item_img in g_resources.RESOURCE_P["item"]["战利品"].items():
        item_name = item_name.replace(".png", "")

        # 对比 block 和 target_image 识图成功 返回识别的道具名称(不含扩展名)
        is_it, _ = one_item_match(img_block=block, img_tar=item_img, mode="match_template_with_mask_tradable")
        if is_it:
            return item_name, list_iter, False

    """识别失败"""

    def save_unmatched_block(img_block):

        with EXTRA.FILE_LOCK:

            # 注意 需要重载一下内存中的图片
            g_resources.fresh_resource_log_img()

            unmatched_path = PATHS["logs"] + "\\match_failed\\loots"

            if not match_block_equal_in_images(
                    block_array=img_block,
                    images=g_resources.RESOURCE_LOG_IMG["loots"]):

                # 获得最小的未使用的i_id
                used_i_ids = set()
                for name, _ in g_resources.RESOURCE_LOG_IMG["loots"].items():
                    i_id_used = int(name.split('.')[0].split("_")[1])
                    used_i_ids.add(i_id_used)
                i_id = 0
                while i_id in used_i_ids:
                    i_id += 1

                # 保存图片
                save_path = os.path.join(unmatched_path, f"unknown_{i_id}_1.png")
                imencode('.png', img_block)[1].tofile(save_path)

            else:

                # 重命名为数量+1 注意此tar_name 包含后缀名
                for old_name, tar_image in g_resources.RESOURCE_LOG_IMG["loots"].items():
                    is_it, _ = one_item_match(img_block, tar_image, mode="equal")
                    if is_it:
                        _, i_id, count = old_name.split('.')[0].split("_")
                        old_path = f'{unmatched_path}\\{old_name}'
                        new_path = f"{unmatched_path}\\unknown_{i_id}_{int(count) + 1}.png"
                        os.rename(old_path, new_path)
                        break

    # 还是找不到, 识图失败 把block保存到 logs / match_failed / 中
    CUS_LOGGER.warning(f'该道具未能识别, 已在 [ logs / match_failed ] 生成文件, 请检查')
    save_unmatched_block(img_block=block)

    return "识别失败", list_iter, False


def update_dag_graph(item_list_new) -> bool:
    """
    根据list中各个物品(str格式)的排序 来保存成一个json文件
    会根据本次输入, 和保存的之前的图比较, 以排序, 最终获得几乎所有物品的物品的结果表
    使用有向无环图, 保留无法区分前后的数据
    :param item_list_new 物品顺序 list 仅一维
    :return: 是否成功更新, 也是判断数据输入是否有效
    """

    CUS_LOGGER.debug("[有向无环图] [更新] 正在进行...")

    # 读取现 JSON Ranking 文件
    json_path = PATHS["logs"] + "\\item_ranking_dag_graph.json"
    data = ranking_read_data(json_path=json_path)

    """根据输入列表, 构造有向无环图"""
    # 继承老数据 图表 用 { x : [a,b,c] , ... } 代表多个有向边 也就是 出度
    graph = data.get('graph') if data.get('graph') else dict()

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

    # 使用 is_directed_acyclic_graph 函数判断 G 是否为 DAG
    if nx.is_directed_acyclic_graph(nx.DiGraph(graph)):
        data['graph'] = graph
        # 保存更新后的 JSON 文件
        ranking_save_data(json_path=json_path, data=data)
        return True
    else:
        return False


def find_longest_path_from_dag():
    CUS_LOGGER.debug("[有向无环图] [寻找最长链] 正在进行...")

    # 读取现 JSON Ranking 文件
    json_path = PATHS["logs"] + "\\item_ranking_dag_graph.json"
    data = ranking_read_data(json_path=json_path)

    G = nx.DiGraph()

    # 添加边到图中
    for node, neighbors in data.get('graph').items():
        for neighbor in neighbors:
            G.add_edge(node, neighbor)

    # 寻找最长路径
    try:
        # nx.dag_longest_path 返回的是节点序列，如果图中存在环，则此函数会抛出错误
        data["ranking"] = nx.dag_longest_path(G)
        CUS_LOGGER.debug("[有向无环图] [寻找最长链] 成功")
        # 保存更新后的 JSON 文件
        ranking_save_data(json_path=json_path, data=data)
        return data["ranking"]

    except nx.NetworkXError:
        # 如果图不是DAG（有向无环图），则无法找到最长路径
        CUS_LOGGER.error("[有向无环图] [寻找最长链] 图中存在环，无法确定最长路径。")
        return None


def ranking_read_data(json_path):
    if os.path.exists(json_path):

        with EXTRA.FILE_LOCK:
            with open(file=json_path, mode="r", encoding="UTF-8") as file:
                data = json.load(file)

        if "ranking" in data:
            return data
        else:
            return {'ranking': [], 'graph': {}}


def ranking_save_data(json_path, data):
    # 自旋锁读写, 防止多线程读写问题
    with EXTRA.FILE_LOCK:
        with open(file=json_path, mode='w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
