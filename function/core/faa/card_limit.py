import re


MIN_CARD_LIMIT = 3


def normalize_max_card_num(max_card_num):
    """把异常的限卡任务修订为至少三张卡，并保留“不限卡”的 ``None``。"""
    if max_card_num is None:
        return None
    if isinstance(max_card_num, bool):
        return None
    try:
        value = int(max_card_num)
    except (TypeError, ValueError):
        return None
    return max(MIN_CARD_LIMIT, value)


def _base_card_name(card_name: str) -> str:
    """去掉转职编号及同类卡后缀，只保留用于承载槽判断的中文主体。"""
    match = re.match(r"^(.*[\u4e00-\u9fff])", str(card_name))
    return match.group(1) if match else str(card_name)


def stage_requires_mat(stage_info: dict | None) -> bool:
    """只有承载候选与承载类型同时为空时，才能认定关卡不需要承载。"""
    if not isinstance(stage_info, dict):
        return False
    return bool(stage_info.get("mat_card") or stage_info.get("mat_card_type"))


def get_required_manual_mat_slot(stage_info: dict | None) -> str | None:
    """
    返回手动卡组需要保留的标准承载槽类型：``wood`` 或 ``malt``。

    ``read_json_to_stage_info`` 已按照“显式 mat_card 优先，否则解析 mat_card_type”生成最终候选列表。
    这里严格沿用候选顺序：先遇到木盘子就保留第一个承载槽，先遇到麦芽糖就保留第二个承载槽；
    其他承载不参与固定槽判断。
    """
    if not isinstance(stage_info, dict):
        return None
    for card_name in stage_info.get("mat_card", []):
        base_name = _base_card_name(card_name)
        if base_name == "木盘子":
            return "wood"
        if base_name == "麦芽糖":
            return "malt"
    return None


def get_retained_plan_card_count(
        plan_card_count: int,
        max_card_num,
        stage_info: dict | None,
        has_quest_card: bool,
) -> int:
    """
    计算限卡后保留多少张战斗方案卡。

    必要承载优先级最高，任务卡次之；剩余名额按方案 ``card_id`` 从小到大分配。
    限卡任务进入执行前已经被规范为至少三张，因此正常任务始终能留下承载、产火和输出的基本结构。
    """
    plan_card_count = max(0, int(plan_card_count))
    if max_card_num is None:
        return plan_card_count

    # 最小三张的任务修订必须在 todo 分配任务时完成。这里是纯计算层，
    # 只消费已经确定的限制值，不能悄悄把上游错误改成另一项战斗规则。
    try:
        card_limit = int(max_card_num)
    except (TypeError, ValueError):
        return plan_card_count

    reserved_count = int(stage_requires_mat(stage_info)) + int(has_quest_card)
    return min(plan_card_count, max(0, card_limit - reserved_count))


def get_manual_card_slots_to_remove(
        plan_card_count: int,
        max_card_num,
        stage_info: dict | None,
        has_quest_card: bool,
) -> list[int]:
    """
    生成手动卡组限卡时需要从 21 到 1 点击移除的原始槽位。

    用户卡组固定布局为“方案卡 + 任务卡预留空位 + 木盘子 + 麦芽糖 + 其他”。
    倒序删除不会让尚未处理的低位槽发生错位；空槽点击本身无害。
    """
    if max_card_num is None:
        return []

    retained_plan_count = get_retained_plan_card_count(
        plan_card_count=plan_card_count,
        max_card_num=max_card_num,
        stage_info=stage_info,
        has_quest_card=has_quest_card,
    )
    kept_slots = set(range(1, retained_plan_count + 1))

    quest_slot = plan_card_count + 1
    if has_quest_card:
        kept_slots.add(quest_slot)

    mat_slot_type = get_required_manual_mat_slot(stage_info)
    if mat_slot_type == "wood":
        kept_slots.add(plan_card_count + 2)
    elif mat_slot_type == "malt":
        kept_slots.add(plan_card_count + 3)

    return [slot_id for slot_id in range(21, 0, -1) if slot_id not in kept_slots]
