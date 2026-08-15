import copy
import re

from function.core_battle.card_copy_rules import get_creator_god_safe_locations


AUTO_CARD_DEFAULTS = {
    "icecream": True,
    "god": True,
    "ikun": True,
    "timer": False,
}

# 高练度承载卡可以做到 0 费用，优先铺承载能让后续卡片直接落在有效地形上；
# 但萌新使用的承载卡通常需要 25 火苗。若它始终排在产火首卡之前，承载会等火，
# 产火卡又因为排在后面无法先放，最终形成持续缺火的恶性循环。
# 因此该机制必须允许微调方案选择“承载优先”或“战斗方案首卡优先”，并为老玩家保留原默认值。
MAT_CARD_FIRST_DEFAULT = True
AUTO_MAT_CARD_DEFAULTS = {
    "enabled": True,
    "use_first": MAT_CARD_FIRST_DEFAULT,
}


def get_tweak_plan_recording(
        battle_plan_tweak: dict,
) -> tuple[bool, bool, int]:
    """读取微调方案 0.3 的聚合录制配置。"""
    if not isinstance(battle_plan_tweak, dict):
        return False, False, 1
    meta_data = battle_plan_tweak.get("meta_data", {})
    if not isinstance(meta_data, dict):
        return False, False, 1

    settings = meta_data.get("recording", {})
    if not isinstance(settings, dict):
        return False, False, 1
    active = settings.get("active") is True
    timestamp = settings.get("timestamp") is True
    player = settings.get("player", 1)
    if player not in (1, 2):
        player = 1
    return active, timestamp, player


def get_tweak_plan_random_interval(
        battle_plan_tweak: dict,
) -> tuple[bool, list[float] | None]:
    """读取微调方案 0.3 的放卡后随机间隔配置。"""
    if not isinstance(battle_plan_tweak, dict):
        return False, None
    meta_data = battle_plan_tweak.get("meta_data", {})
    if not isinstance(meta_data, dict):
        return False, None

    settings = meta_data.get("cd_after_use_random")
    if not isinstance(settings, dict):
        return False, None
    active = settings.get("active") is True
    interval = settings.get("range")
    if (
            not isinstance(interval, list)
            or len(interval) != 2
            or not all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                for value in interval
            )
    ):
        return False, None
    return active, [float(interval[0]), float(interval[1])]


def get_tweak_plan_auto_mat_card(battle_plan_tweak) -> dict[str, bool]:
    """
    读取微调方案 0.3 的独立自动承载配置。

    承载开关与承载优先级共同放在 ``auto_mat_card`` 中，因为承载依赖关卡地形，
    和冰沙、复制卡等一般辅助卡的职责不同；``enable_auto_card`` 仅负责一般辅助卡。
    """
    settings = AUTO_MAT_CARD_DEFAULTS.copy()
    if not isinstance(battle_plan_tweak, dict):
        return settings

    raw_settings = battle_plan_tweak.get("meta_data", {}).get(
        "auto_mat_card",
        {},
    )
    if not isinstance(raw_settings, dict):
        return settings
    for name in settings:
        value = raw_settings.get(name)
        if isinstance(value, bool):
            settings[name] = value
    return settings


def get_tweak_plan_auto_card_enabled(battle_plan_tweak) -> dict[str, bool]:
    """读取微调方案 0.3 的自动辅助卡片启用状态。"""
    enabled = AUTO_CARD_DEFAULTS.copy()
    if not isinstance(battle_plan_tweak, dict):
        return enabled

    raw_enabled = battle_plan_tweak.get("meta_data", {}).get(
        "enable_auto_card",
        {},
    )
    if not isinstance(raw_enabled, dict):
        return enabled

    for name in enabled:
        value = raw_enabled.get(name)
        if isinstance(value, bool):
            enabled[name] = value
    return enabled


def _base_card_name(card_name: str) -> str:
    """按 FAA 卡片类型解析规则截取卡名中的中文主体。"""
    match = re.match(r"^(.*[\u4e00-\u9fff])", str(card_name))
    return match.group(1) if match else str(card_name)


def _card_name_candidates(card_name: str, card_types: list[dict] | None) -> set[str]:
    """展开一个战斗方案卡名可能解析到的实际卡名。"""
    base_name = _base_card_name(card_name)
    for card_type in card_types or []:
        keys = card_type.get("key", [])
        if base_name in keys:
            return {_base_card_name(name) for name in card_type.get("value", [])}
    return {base_name}


def get_battle_plan_card_candidates(
        battle_plan: dict,
        card_types: list[dict] | None,
) -> set[str]:
    """获取战斗方案直接写入或经 card type 展开后可能存在的卡名。"""
    candidates = set()
    if not isinstance(battle_plan, dict):
        return candidates
    for card in battle_plan.get("cards", []):
        if isinstance(card, dict) and isinstance(card.get("name"), str):
            candidates.update(_card_name_candidates(card["name"], card_types))
    return candidates


def get_auto_card_target_names(
        stage_mat_card_names: list[str],
        battle_plan_tweak,
        battle_plan: dict | None = None,
        card_types: list[dict] | None = None,
        exclude_plan_cards: bool = True,
) -> tuple[list[str], list[str], list[str]]:
    """
    获取本场战斗允许智能识别和使用的辅助卡片名称。

    Args:
        stage_mat_card_names: 当前关卡允许使用的承载卡名称。
        battle_plan_tweak: 已加载的微调方案字典。
        battle_plan: 当前战斗方案。
        card_types: 卡片类型配置。
        exclude_plan_cards: 是否根据方案名称排除重复辅助卡。
            手动卡组的方案名称与实际卡片无关，因此战斗开场扫描时必须传入 ``False``。

    Returns:
        三个列表依次为承载卡、冰沙和连携卡的识别目标名称。微调方案关闭某一功能时，对应列表为空。
    """
    enabled = get_tweak_plan_auto_card_enabled(battle_plan_tweak)
    auto_mat = get_tweak_plan_auto_mat_card(battle_plan_tweak)
    existing = (
        get_battle_plan_card_candidates(battle_plan, card_types)
        if exclude_plan_cards
        else set()
    )
    has_kun_target = get_highest_kun_target(battle_plan) is not None

    target_mat_list = []
    if auto_mat["enabled"]:
        target_mat_list = [
            name
            for name in copy.deepcopy(stage_mat_card_names)
            if _base_card_name(name) not in existing
        ]

    smoothie_names = {"冰激凌", "极寒冰沙"}
    target_smoothie_list = []
    if enabled["icecream"] and not smoothie_names.intersection(existing):
        target_smoothie_list = ["冰激凌"]

    target_kun_list = []
    if has_kun_target:
        if enabled["ikun"] and "幻幻鸡" not in existing:
            target_kun_list.append("幻幻鸡")
        if (
                enabled["god"]
                and "创造神" not in existing
                and battle_plan_has_creator_god_target(battle_plan)
        ):
            target_kun_list.append("创造神")
    return target_mat_list, target_smoothie_list, target_kun_list


def get_tweak_plan_auto_timer_enabled(battle_plan_tweak) -> bool:
    """读取微调方案中的美味计时器自动使用开关。"""
    return get_tweak_plan_auto_card_enabled(battle_plan_tweak)["timer"]


def get_tweak_plan_mat_card_first(battle_plan_tweak) -> bool:
    """
    读取是否让自动承载卡先于战斗方案首卡使用。

    ``True`` 适用于 0 费承载：先铺承载不会阻塞后续卡片。
    ``False`` 适用于需要 25 火苗的低练度承载：先让战斗方案首卡（通常是产火卡）启动能量循环，
    避免承载等火的同时把产火卡永久压在队列后方。
    """
    return get_tweak_plan_auto_mat_card(battle_plan_tweak)["use_first"]


def insert_mat_cards_by_priority(
        cards: list[dict],
        mat_cards: list[dict],
        mat_card_first: bool,
) -> list[dict]:
    """
    按玩家选择把自动承载卡插入执行优先级。

    承载优先时整组承载放在队首，适配 0 费承载；关闭时保留战斗方案的首卡在最前，
    整组承载紧随其后，供 25 火承载先通过产火首卡获得启动能量。
    这里整组切片插入还会保留多个承载卡原有顺序，避免逐张 ``insert`` 倒序。
    """
    insert_index = 0 if mat_card_first else min(1, len(cards))
    cards[insert_index:insert_index] = mat_cards
    return cards


def get_highest_kun_target_from_cards(cards: list[dict]) -> dict | None:
    """从已按优先级排列的动作中选择首个最高正数 ``kun`` 目标。"""
    best_card = None
    best_kun = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        kun = card.get("kun", 0)
        locations = card.get("location", [])
        if (
                isinstance(kun, (int, float))
                and not isinstance(kun, bool)
                and kun > best_kun
                and isinstance(locations, list)
                and locations
        ):
            best_card = card
            best_kun = kun
    return best_card


def get_kun_cards_for_wave(
        detected_kun_cards: list[dict] | None,
        cards: list[dict],
) -> list[dict]:
    """
    仅在当前波次存在正数 ``kun`` 目标时返回已识别的复制卡。

    每波都从战前识别结果重新生成列表，不能沿用上一波被清空的运行时列表；
    否则第一波没有复制目标时，会让后续拥有目标的波次也永久失去复制卡。
    """
    if get_highest_kun_target_from_cards(cards) is None:
        return []
    return copy.deepcopy(detected_kun_cards or [])


def get_highest_kun_target(
        battle_plan: dict,
        wave: int | None = None,
) -> dict | None:
    """返回指定波次中首个最高正数 ``kun`` 目标。"""
    if not isinstance(battle_plan, dict):
        return None

    eligible_cards = []
    for event in battle_plan.get("events", []):
        if not isinstance(event, dict):
            continue
        trigger = event.get("trigger", {})
        action = event.get("action", {})
        if (
                trigger.get("type") != "wave_timer"
                or action.get("type") != "loop_use_cards"
                or (wave is not None and trigger.get("wave_id") != int(wave))
        ):
            continue
        eligible_cards.extend(action.get("cards", []))
    return get_highest_kun_target_from_cards(eligible_cards)


def get_auto_timer_target_names(
        battle_plan_tweak: dict,
        battle_plan: dict,
        card_types: list[dict] | None = None,
        exclude_plan_cards: bool = True,
) -> list[str]:
    """
    获取本场战斗允许自动携带和使用的美味计时器识别目标。

    计时器必须有正数 ``kun`` 目标才能确定唯一落点；
    战斗方案直接写入计时器或通过“冷却辅助/冷却拐”类型可能解析到计时器时，不再重复加入。

    Args:
        battle_plan_tweak: 当前微调方案。
        battle_plan: 当前战斗方案，用于检查正数 ``kun`` 目标。
        card_types: 卡片类型配置。
        exclude_plan_cards: 是否根据方案名称排除计时器。
            手动卡组名称与方案无关，因此战斗开场扫描时必须传入 ``False``。

    Returns:
        需要识别时返回 ``["美味计时器"]``，否则返回空列表。
    """
    if not get_tweak_plan_auto_timer_enabled(battle_plan_tweak):
        return []
    if get_highest_kun_target(battle_plan) is None:
        return []

    existing = (
        get_battle_plan_card_candidates(battle_plan, card_types)
        if exclude_plan_cards
        else set()
    )
    # 传入 card_types 时，冷却辅助类会展开为实际计时器；
    # 未传入时仍需直接识别历史方案使用的两个类型名，保持独立调用这个函数也安全。
    if existing.intersection({"美味计时器", "冷却辅助", "冷却拐"}):
        return []
    return ["美味计时器"]


def offset_timer_location(location: str) -> str:
    """把二转计时器的 3×1 生效范围限制在 9×7 棋盘内。"""
    try:
        column_text, row_text = location.split("-", maxsplit=1)
        column = int(column_text)
        row = int(row_text)
    except (AttributeError, TypeError, ValueError):
        return location
    if not 1 <= row <= 7:
        return location
    column = min(8, max(2, column))
    return f"{column}-{row}"


def build_auto_timer_card(timer_info: dict | None, cards: list[dict]) -> dict | None:
    """按最高正数 ``kun`` 目标的首格生成美味计时器动作。"""
    target = get_highest_kun_target_from_cards(cards)
    if not timer_info or target is None:
        return None
    target_location = target["location"][0]
    if timer_info.get("second_job", False):
        target_location = offset_timer_location(target_location)
    return {
        "name": timer_info["name"],
        "card_id": timer_info["card_id"],
        "location": [target_location],
        "ergodic": False,
        "queue": False,
        "kun": 0,
    }


def battle_plan_has_creator_god_target(battle_plan: dict) -> bool:
    """判断任一正数 ``kun`` 目标是否拥有完整 3×3 安全中心。"""
    if not isinstance(battle_plan, dict):
        return False
    for event in battle_plan.get("events", []):
        if not isinstance(event, dict):
            continue
        action = event.get("action", {})
        if action.get("type") != "loop_use_cards":
            continue
        for card in action.get("cards", []):
            if not isinstance(card, dict):
                continue
            kun = card.get("kun", 0)
            if (
                    isinstance(kun, (int, float))
                    and not isinstance(kun, bool)
                    and kun > 0
                    and get_creator_god_safe_locations(card.get("location", []))
            ):
                return True
    return False
