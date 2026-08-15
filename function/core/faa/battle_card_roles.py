"""战斗卡片的方案身份、物理槽位和功能角色解析。"""

from __future__ import annotations

import copy
from collections.abc import Iterable


ROLE_PLAN = "plan"
ROLE_PRIMARY_MAT = "primary_mat"
ROLE_SECONDARY_MAT = "secondary_mat"
ROLE_QUEST = "quest"
ROLE_TIMER = "timer"
ROLE_SMOOTHIE = "smoothie"
ROLE_CREATOR_GOD = "creator_god"
ROLE_IKUN = "ikun"


def make_card_requirement(
        name: str,
        roles: Iterable[str],
        *,
        plan_id: int | None = None,
        can_failed: bool = False,
        source: str,
) -> dict:
    """
    创建战备阶段使用的卡片需求。

    ``plan_id`` 始终表示战斗方案 JSON 中的 ``card_id``；``slot_id`` 只表示本场战斗中从左到右的真实卡槽。
    额外添加的任务卡、承载和辅助卡没有方案身份，因此 ``plan_id`` 为 ``None``。

    Args:
        name: 交给卡名解析器使用的标识名称。
        roles: 该实体卡承担的功能角色。
        plan_id: 原始战斗方案卡片 ID。
        can_failed: 找不到该卡时是否允许继续战斗。
        source: 兼容现有日志与测试的来源标识。

    Returns:
        尚未展开精准名称、也尚未分配真实卡槽的需求字典。
    """
    return {
        "name": name,
        "can_failed": can_failed,
        "source": source,
        "plan_id": plan_id,
        "slot_id": None,
        "roles": list(dict.fromkeys(roles)),
    }


def add_role(card: dict, role: str) -> None:
    """给实体卡追加角色，并保持角色列表稳定且不重复。"""
    roles = card.setdefault("roles", [])
    if role not in roles:
        roles.append(role)


def has_role(card: dict, role: str) -> bool:
    """判断一张实体卡是否承担指定角色。"""
    return role in card.get("roles", [])


def attach_quest_role(
        cards: list[dict],
        quest_precise_names: list[str],
) -> dict | None:
    """
    把任务角色绑定到已有实体卡，并将其候选收窄到任务卡。

    解析顺序就是自动带卡的物理排列顺序。这样方案中的类型卡、第一承载或已有辅助卡都可以直接承担任务，
    而不会为了第二个角色重复携带同一张卡。

    Args:
        cards: 已完成精准名称展开的自动带卡需求。
        quest_precise_names: 任务卡可以接受的精准名称，按转职优先级排列。

    Returns:
        承担任务的实体卡；没有任何候选重叠时返回 ``None``。
    """
    quest_name_set = set(quest_precise_names)
    for card in cards:
        matched_names = [
            name for name in card.get("names", [])
            if name in quest_name_set
        ]
        if not matched_names:
            continue
        card["names"] = matched_names
        card["can_failed"] = False
        add_role(card, ROLE_QUEST)
        return card
    return None


def retain_cards_by_role(cards: list[dict], max_card_num) -> list[dict]:
    """
    根据角色优先级执行自动带卡限数，同时保持原物理排列。

    保留优先级固定为：第一承载、任务承担者、方案卡 ID 从小到大、其余自动附加卡。
    优先级只决定谁能留下，不决定卡组排列和战斗使用顺序。

    Args:
        cards: 已解析任务角色的自动带卡需求。
        max_card_num: 最大携带数量；``None`` 表示不限卡。

    Returns:
        按原物理排列过滤后的新列表。
    """
    if max_card_num is None:
        return list(cards)
    try:
        limit = max(0, int(max_card_num))
    except (TypeError, ValueError):
        return list(cards)

    indexed_cards = list(enumerate(cards))

    def priority(item: tuple[int, dict]) -> tuple[int, int]:
        index, card = item
        if has_role(card, ROLE_PRIMARY_MAT):
            return 0, index
        if has_role(card, ROLE_QUEST):
            return 1, index
        if has_role(card, ROLE_PLAN):
            plan_id = card.get("plan_id")
            return 2, plan_id if isinstance(plan_id, int) else index
        return 3, index

    retained_indexes = {
        index
        for index, _ in sorted(indexed_cards, key=priority)[:limit]
    }
    return [card for index, card in indexed_cards if index in retained_indexes]


def assign_successful_slot(
        card: dict,
        slot_id: int,
        precise_name: str,
) -> None:
    """记录自动带卡实际成功加入后的物理槽位和精准名称。"""
    card["slot_id"] = slot_id
    card["actual_name"] = precise_name


def get_plan_slot_map(cards: list[dict]) -> dict[int, int]:
    """从已解析卡组生成原始方案 ID 到真实卡槽 ID 的映射。"""
    result = {}
    for card in cards:
        plan_id = card.get("plan_id")
        slot_id = card.get("slot_id")
        if isinstance(plan_id, int) and isinstance(slot_id, int):
            result[plan_id] = slot_id
    return result


def resolve_insert_use_card_events(
        events: list[dict],
        cards: list[dict],
        *,
        resolved_plan_ready: bool,
) -> list[dict]:
    """
    根据最终携带卡组过滤定时放卡事件，并把方案 ID 映射为真实卡槽。

    定时放卡事件中的 ``card_id`` 是稳定的战斗方案身份，不能直接作为物理卡槽使用。
    一张方案卡因限卡、禁卡等原因未被携带时，整个定时事件都要删除，事件附带的前铲和后铲也不能继续执行。

    Args:
        events: 原始战斗方案事件。
        cards: 战备阶段解析出的完整实体卡组。
        resolved_plan_ready: 实体卡组是否已经完成解析；为 ``False`` 时保留旧调用的原始槽位兼容行为。

    Returns:
        只包含有效定时放卡操作的深拷贝事件；每个动作额外包含 ``plan_id`` 和 ``slot_id``。
    """
    timed_events = [
        copy.deepcopy(event)
        for event in events
        if (
            event.get("trigger", {}).get("type") == "wave_timer"
            and event.get("action", {}).get("type") == "insert_use_card"
        )
    ]

    if not resolved_plan_ready:
        for event in timed_events:
            plan_id = event["action"].get("card_id")
            event["action"]["plan_id"] = plan_id
            event["action"]["slot_id"] = plan_id
        return timed_events

    resolved_by_plan_id = {
        card["plan_id"]: card
        for card in cards
        if isinstance(card.get("plan_id"), int)
    }
    plan_slot_map = get_plan_slot_map(cards)
    resolved_events = []
    for event in timed_events:
        plan_id = event["action"].get("card_id")
        resolved_card = resolved_by_plan_id.get(plan_id)
        slot_id = plan_slot_map.get(plan_id)
        if resolved_card is None or slot_id is None:
            continue
        event["action"]["plan_id"] = plan_id
        event["action"]["slot_id"] = slot_id
        event["action"]["name"] = resolved_card.get("name", "")
        resolved_events.append(event)
    return resolved_events


def find_role_card(cards: list[dict], role: str) -> dict | None:
    """返回第一张承担指定角色的实体卡。"""
    return next((card for card in cards if has_role(card, role)), None)


def merge_detected_card(
        cards: list[dict],
        *,
        slot_id: int,
        name: str,
        role: str,
) -> dict:
    """
    将战斗开场识别出的功能角色合并到真实卡槽。

    自动带卡可以在战备阶段就知道槽位；手动带卡的承载和辅助卡则要到战斗开场识图后才能确定。
    两条路径最终都通过槽位合并到同一实体卡，从而避免任务卡和自动辅助卡产生两份放卡动作。

    Args:
        cards: 本场战斗的实体卡解析结果。
        slot_id: 战斗开场识别出的真实卡槽。
        name: 识别出的卡片名称。
        role: 本次识别确认的功能角色。

    Returns:
        合并角色后的实体卡字典。
    """
    card = next(
        (item for item in cards if item.get("slot_id") == slot_id),
        None,
    )
    if card is None:
        card = make_card_requirement(
            name=name,
            roles=[role],
            plan_id=None,
            can_failed=True,
            source="battle_scan",
        )
        card["slot_id"] = slot_id
        card["actual_name"] = name
        cards.append(card)
    else:
        add_role(card, role)
        card.setdefault("actual_name", name)
    return card


def apply_removed_slots(cards: list[dict], removed_slots: list[int] | None) -> None:
    """
    根据战备阶段实际删除的槽位，原地移除并重排卡片的 ``slot_id``。

    禁卡发生在自动带卡或手动限卡之后、进入战斗之前。
    此处只调整物理槽位，不修改稳定的 ``plan_id``，避免后续再次用方案 ID 推算卡槽。
    """
    removed = sorted(set(removed_slots or []))
    if not removed:
        return
    cards[:] = [card for card in cards if card.get("slot_id") not in removed]
    for card in cards:
        slot_id = card.get("slot_id")
        if not isinstance(slot_id, int):
            continue
        card["slot_id"] -= sum(slot < slot_id for slot in removed)


def get_slot_id(card: dict) -> int | None:
    """读取真实卡槽；兼容尚未迁移的旧结构。"""
    slot_id = card.get("slot_id")
    if isinstance(slot_id, int):
        return slot_id
    legacy_card_id = card.get("card_id")
    return legacy_card_id if isinstance(legacy_card_id, int) else None
