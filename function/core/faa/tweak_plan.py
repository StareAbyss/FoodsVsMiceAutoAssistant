import copy

from function.core_battle.card_copy_rules import get_creator_god_safe_locations


AUTO_CARD_DEFAULTS = {
    "icecream": True,
    "god": True,
    "ikun": True,
    "timer": False,
}
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
    """读取微调方案 0.3 的自动承载开关与使用优先级。"""
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


def get_auto_card_target_names(
        stage_mat_card_names: list[str],
        battle_plan_tweak,
) -> tuple[list[str], list[str], list[str]]:
    """
    获取本场战斗允许智能识别和使用的辅助卡片名称。

    Args:
        stage_mat_card_names: 当前关卡允许使用的承载卡名称。
        battle_plan_tweak: 已加载的微调方案字典。

    Returns:
        三个列表依次为承载卡、冰沙和连携卡的识别目标名称。微调方案关闭
        某一功能时，对应列表为空。
    """
    enabled = get_tweak_plan_auto_card_enabled(battle_plan_tweak)
    auto_mat = get_tweak_plan_auto_mat_card(battle_plan_tweak)
    target_mat_list = copy.deepcopy(stage_mat_card_names) if auto_mat["enabled"] else []
    target_smoothie_list = ["冰激凌"] if enabled["icecream"] else []
    target_kun_list = []
    if enabled["ikun"]:
        target_kun_list.append("幻幻鸡")
    if enabled["god"]:
        target_kun_list.append("创造神")
    return target_mat_list, target_smoothie_list, target_kun_list


def get_tweak_plan_auto_timer_enabled(battle_plan_tweak) -> bool:
    """读取微调方案中的美味计时器自动使用开关。"""
    return get_tweak_plan_auto_card_enabled(battle_plan_tweak)["timer"]


def get_tweak_plan_mat_card_first(battle_plan_tweak) -> bool:
    """
    读取是否让自动承载卡先于战斗方案首卡使用。

    ``True`` 适用于零费承载；``False`` 适用于需要火苗的低练度承载，
    可先执行战斗方案首卡以启动产火循环。
    """
    return get_tweak_plan_auto_mat_card(battle_plan_tweak)["use_first"]


def insert_mat_cards_by_priority(
        cards: list[dict],
        mat_cards: list[dict],
        mat_card_first: bool,
) -> list[dict]:
    """按玩家选择把整组自动承载卡插入执行优先级。"""
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
) -> list[str]:
    """获取本场战斗允许自动携带和使用的美味计时器识别目标。"""
    if not get_tweak_plan_auto_timer_enabled(battle_plan_tweak):
        return []
    if get_highest_kun_target(battle_plan) is None:
        return []

    card_names = {
        card.get("name")
        for card in battle_plan.get("cards", [])
        if isinstance(card, dict)
    }
    if card_names.intersection({"美味计时器", "冷却辅助", "冷却拐"}):
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
