import copy
import json
import os
import time

import networkx as nx
from cv2 import imencode

from function.common.image_processing.same_size_match import one_item_match, match_block_equal_in_images
from function.globals import EXTRA
from function.globals import g_resources
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER

RANKING_BACKUP_JSON_PATH = os.path.join(PATHS["root"], "resource", "template", "item_ranking_dag_graph.json")

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
    保存结算截图并识别其中的战利品或宝箱物品。

    该函数只负责截图保存、图片分块、物品模板匹配和返回识别结果。
    不负责判定掉落数据有效性, 也不负责写入统计日志或上传服务器。

    Args:
        img_save_path: 识别原图保存路径。
        image: 待识别的图片, 格式为 numpy.ndarray。
        mode: 识别模式, 可选值为 "loots" 或 "chests"。
        test_print: 是否输出匹配调试日志。

    Returns:
        list[str]: 按截图顺序排列的物品名称列表。识别失败的块使用 "识别失败" 标记, 不返回 None。

    Raises:
        ValueError: mode 不是 "loots" 或 "chests" 时抛出。
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
        json_path = os.path.join(PATHS["config"], 'item_ranking_dag_graph.json')
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
    """
    按结算界面类型将截图切分为单个物品图标块。

    Args:
        image: 待切分的截图, 格式为 numpy.ndarray。
        mode: 切分模式, "loots" 表示战利品结算截图, "chests" 表示翻宝箱截图。

    Returns:
        list: 切分后的图片块列表, 每个元素都是 numpy.ndarray。
    """
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
    识别单个物品图标块对应的战利品名称。

    识别顺序为: 绑定角标检测 -> 上一次识别结果复用 -> DAG ranking 顺序表遍历 -> 全量模板遍历。
    如果全部匹配失败, 会保存失败图块到 logs/match_failed/loots 供后续补模板。

    Args:
        block: 44x44 的物品图标块, 格式为 numpy.ndarray。
        list_iter: DAG ranking 顺序表迭代器。为 None 时跳过顺序表遍历。
        last_name: 上一次成功识别的物品名, 用于连续相同物品的快速匹配。
        may_locked: 是否检测宝箱物品中可能出现的绑定角标。

    Returns:
        tuple[str, Iterator | None, bool]:
        识别出的物品名称或 "识别失败", 继续向后传递的 ranking 迭代器, 以及是否为绑定物品。
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
        """
        保存或累计无法识别的物品图标块。

        如果图块未在现有失败记录中出现, 使用最小可用 id 保存为新文件。
        如果图块已经出现过, 则把对应文件名中的计数加一。

        Args:
            img_block: 未能识别的物品图标块, 格式为 numpy.ndarray。
        """

        with EXTRA.FILE_LOCK:

            # 注意 需要重载一下内存中的图片
            g_resources.fresh_resource_log_img()

            unmatched_path = os.path.join(PATHS["logs"], 'match_failed', 'loots')

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
                        old_path = os.path.join(unmatched_path, old_name)
                        new_path = os.path.join(unmatched_path, f"unknown_{i_id}_{int(count) + 1}.png")
                        os.rename(old_path, new_path)
                        break

    # 还是找不到, 识图失败 把block保存到 logs / match_failed / 中
    CUS_LOGGER.warning(f'该道具未能识别, 已在 [ logs / match_failed ] 生成文件, 请检查')
    save_unmatched_block(img_block=block)

    return "识别失败", list_iter, False


def update_dag_graph(item_list_new) -> bool:
    """
    根据本次战利品顺序更新 item_ranking_dag_graph.json。

    该函数把一场战斗中识别到的物品顺序转换为有向边, 合并进历史 DAG graph。
    DAG 用于保留物品先后关系, 同时允许无法稳定区分前后的物品不被强行排序。
    四叶草和香料存在隐藏的绑定/不绑定差异, 会导致同类型物品在正常记录中出现顺序错乱,
    因此会先对这些固定分组做强制顺序整理。

    Args:
        item_list_new: 本次识别到的物品顺序列表, 一维 list[str]。

    Returns:
        bool: True 表示合并后仍是 DAG 且已保存; False 表示本次数据会构成环, 需要丢弃。
    """

    CUS_LOGGER.debug("[有向无环图] [更新] 正在进行...")

    # 强制排序初始list中部分物品
    group_1 = ['5级四叶草', '4级四叶草', '3级四叶草', '2级四叶草', '1级四叶草']
    group_2 = ['天使香料', '精灵香料', '魔幻香料', '皇室香料', '极品香料', '秘制香料', '上等香料', '天然香料']

    def change_item_list_by_group(group_list, item_list):
        """
        根据给定分组列表, 修正物品列表中同组物品的相对顺序。

        具体步骤如下:
        1. 找到项目列表中属于分组列表的项目，并记录它们的位置。
        2. 从项目列表中移除这些项目。
        3. 按照分组列表的顺序将这些项目重新插入到项目列表中，插入位置为第一次找到的分组项目的位置。

        Args:
            group_list: 需要强制排序的分组列表。
            item_list: 需要重新排列的物品列表。

        Returns:
            list: 修正同组物品顺序后的物品列表。
        """
        group_item_found_dict = {item: False for item in group_list}
        first_index = None

        # 找到项目列表中属于分组列表的项目，并记录它们的位置
        for index, item_name in enumerate(item_list):
            if item_name in group_list:
                group_item_found_dict[item_name] = True
                if first_index is None:
                    first_index = index

        # 从项目列表中移除这些项目
        new_item_list = []
        for item in item_list:
            if not group_item_found_dict.get(item, False):
                new_item_list.append(item)

        # 按照分组列表的逆序将这些项目重新插入到项目列表中
        for item_name in reversed(group_list):
            if group_item_found_dict[item_name]:
                new_item_list.insert(first_index, item_name)

        return new_item_list

    item_list_new = change_item_list_by_group(group_list=group_1, item_list=item_list_new)
    item_list_new = change_item_list_by_group(group_list=group_2, item_list=item_list_new)

    # 读取现 JSON Ranking 文件
    json_path = os.path.join(PATHS["config"], 'item_ranking_dag_graph.json')
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
    """
    从当前 DAG graph 中计算最长路径并刷新 ranking 列表。

    ranking 列表用于下一轮战利品识别时的优先匹配顺序, 可以减少模板全量遍历次数。
    如果图中存在环, 说明历史数据或本次数据存在冲突, 此时不更新 ranking。

    Returns:
        list[str] | None: 成功时返回新的 ranking 列表; 图中存在环或计算失败时返回 None。
    """
    CUS_LOGGER.debug("[有向无环图] [寻找最长链] 正在进行...")

    # 读取现 JSON Ranking 文件
    json_path = os.path.join(PATHS["config"], 'item_ranking_dag_graph.json')
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


def _empty_ranking_data():
    """
    创建 DAG graph 排序文件的空数据结构。

    Returns:
        dict: 包含 ranking 和 graph 两个顶层字段的空结构。
    """
    return {'ranking': [], 'graph': {}}


def _read_ranking_backup_data(source_path, reason):
    """
    在主排序文件不可用时读取 resource/template 中的备份数据。

    该兜底用于避免 config/item_ranking_dag_graph.json 缺失、为空或损坏时中断战斗结算。
    只有备份文件也不可用或结构异常时, 才返回空排序结构。

    Args:
        source_path: 原本尝试读取的主排序文件路径。
        reason: 触发备份读取的原因, 用于日志定位。

    Returns:
        dict: 备份排序数据; 备份不可用时返回空排序结构。
    """
    if not os.path.exists(RANKING_BACKUP_JSON_PATH):
        CUS_LOGGER.warning(
            f"[有向无环图] 排序数据备份文件不存在: {RANKING_BACKUP_JSON_PATH}; "
            f"来源文件: {source_path}; 原因: {reason}. 将使用空排序数据继续运行.")
        return _empty_ranking_data()

    try:
        with open(file=RANKING_BACKUP_JSON_PATH, mode="r", encoding="UTF-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError) as e:
        CUS_LOGGER.warning(
            f"[有向无环图] 读取排序数据备份失败: {RANKING_BACKUP_JSON_PATH}; "
            f"来源文件: {source_path}; 原因: {reason}; 错误: {e}. 将使用空排序数据继续运行.")
        return _empty_ranking_data()

    if isinstance(data, dict) and "ranking" in data:
        CUS_LOGGER.warning(
            f"[有向无环图] 使用排序数据备份: {RANKING_BACKUP_JSON_PATH}; "
            f"来源文件: {source_path}; 原因: {reason}.")
        return data

    CUS_LOGGER.warning(
        f"[有向无环图] 排序数据备份结构异常: {RANKING_BACKUP_JSON_PATH}; "
        f"来源文件: {source_path}; 原因: {reason}. 将使用空排序数据继续运行.")
    return _empty_ranking_data()


def ranking_read_data(json_path):
    """
    读取 DAG graph 排序数据。

    优先读取 config 中的可写排序文件。主文件不存在、为空、损坏、读取失败或结构异常时,
    自动回退到 resource/template/item_ranking_dag_graph.json。

    Args:
        json_path: config 中的可写排序文件路径。

    Returns:
        dict: 排序数据, 至少包含 ranking 和 graph 字段。主文件和备份都不可用时返回空结构。
    """
    if os.path.exists(json_path):

        with EXTRA.FILE_LOCK:
            try:
                with open(file=json_path, mode="r", encoding="UTF-8") as file:
                    data = json.load(file)
            except json.JSONDecodeError as e:
                CUS_LOGGER.warning(
                    f"[有向无环图] 读取排序数据失败, JSON文件为空或损坏: {json_path}; "
                    f"错误: {e}. 将尝试使用备份排序数据.")
                return _read_ranking_backup_data(source_path=json_path, reason="JSON文件为空或损坏")
            except OSError as e:
                CUS_LOGGER.warning(
                    f"[有向无环图] 读取排序数据失败: {json_path}; "
                    f"错误: {e}. 将尝试使用备份排序数据.")
                return _read_ranking_backup_data(source_path=json_path, reason="读取失败")

        if isinstance(data, dict) and "ranking" in data:
            return data
        else:
            return _read_ranking_backup_data(source_path=json_path, reason="主文件结构异常")

    return _read_ranking_backup_data(source_path=json_path, reason="主文件不存在")


def ranking_save_data(json_path, data):
    """
    原子化保存 DAG graph 排序数据。

    写入时先生成带进程号和时间戳的临时文件, flush/fsync 成功后再使用 os.replace 替换主文件。
    这样可以避免程序崩溃、断电或多开进程竞争时把主 JSON 留在空文件或半截文件状态。

    Args:
        json_path: config 中的可写排序文件路径。
        data: 需要保存的 DAG graph 排序数据。

    Raises:
        Exception: 临时文件写入、落盘或替换失败时抛出, 并尝试清理临时文件。
    """
    # 自旋锁读写, 防止多线程读写问题
    with EXTRA.FILE_LOCK:
        temp_path = f"{json_path}.{os.getpid()}.{time.time_ns()}.tmp"
        try:
            with open(file=temp_path, mode='w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, json_path)
        except Exception as e:
            CUS_LOGGER.error(f"[有向无环图] 保存排序数据失败: {json_path}; 错误: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise
