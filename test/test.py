
def change_item_list_by_group(group_list, item_list):
    """
    根据给定的分组列表，重新排列物品列表
    具体步骤如下：
    1. 找到项目列表中属于分组列表的项目，并记录它们的位置。
    2. 从项目列表中移除这些项目。
    3. 按照分组列表的顺序将这些项目重新插入到项目列表中，插入位置为第一次找到的分组项目的位置。
    :param group_list: 需要匹配的分组列表
    :param item_list: 需要重新排列的项目列表
    :return: 重新排列后的项目列表
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


item_list_new = [
    "物品A", "物品B",
    "2级四叶草",  # 绑定的四叶草  和 对应的不绑定的香料(也被计数进此处)
    "3级四叶草", "1级四叶草",  # 不绑定的四叶草,  且没有对应绑定物, 被单独在后计数
    "秘制香料", "天然香料",  # 绑定的香料 和 对应的不绑定的香料(也被计数进此处)
    "上等香料",  # 不绑定的香料, 且没有对应绑定物, 被单独在后计数
    "物品C", "物品D"  # 其他正常物品
]
# 强制排序初始list中部分物品
group_1 = ['5级四叶草', '4级四叶草', '3级四叶草', '2级四叶草', '1级四叶草']
group_2 = ['天使香料', '精灵香料', '魔幻香料', '皇室香料', '极品香料', '秘制香料', '上等香料', '天然香料']

item_list_new = change_item_list_by_group(group_list=group_1, item_list=item_list_new)
item_list_new = change_item_list_by_group(group_list=group_2, item_list=item_list_new)
print(item_list_new)
