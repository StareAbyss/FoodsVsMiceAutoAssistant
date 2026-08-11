import copy

from function.core_battle.card_copy_rules import get_creator_god_safe_locations


AUTO_TIMER_DEFAULT = False


def get_tweak_plan_ban_state(battle_plan_tweak) -> dict[str, bool]:
    """
    获取微调方案中各类自动辅助卡片功能的禁用状态。

    `mat`、`icecream`、`god` 和 `ikun` 为 True 时，同时停止该类卡片的
    自动携带与智能使用。`coffee` 暂时保留原有的直接禁用携带行为。

    Args:
        battle_plan_tweak: 已加载的微调方案字典；缺失或格式异常时使用默认值。

    Returns:
        包含 mat、icecream、god、ikun、coffee 五个布尔字段的完整字典。
    """
    default_state = {
        "mat": False,
        "icecream": False,
        "god": False,
        "ikun": False,
        "coffee": False,
    }
    if not isinstance(battle_plan_tweak, dict):
        return default_state

    ban_state = battle_plan_tweak.get("meta_data", {}).get("ban_state", {})
    if not isinstance(ban_state, dict):
        return default_state

    for name in default_state:
        default_state[name] = ban_state.get(name, False) is True
    return default_state


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
        三个列表依次为承载卡、冰沙和连携卡的识别目标名称。微调方案
        禁用某一功能时，对应列表为空。
    """
    ban_state = get_tweak_plan_ban_state(battle_plan_tweak)
    target_mat_list = [] if ban_state["mat"] else copy.deepcopy(stage_mat_card_names)
    target_smoothie_list = [] if ban_state["icecream"] else ["冰激凌"]
    target_kun_list = []
    if not ban_state["ikun"]:
        target_kun_list.append("幻幻鸡")
    if not ban_state["god"]:
        target_kun_list.append("创造神")
    return target_mat_list, target_smoothie_list, target_kun_list


def get_tweak_plan_auto_timer_enabled(battle_plan_tweak) -> bool:
    """读取微调方案中的美味计时器自动使用开关。"""
    if not isinstance(battle_plan_tweak, dict):
        return AUTO_TIMER_DEFAULT
    enable_auto_card = battle_plan_tweak.get("meta_data", {}).get(
        "enable_auto_card",
        {},
    )
    if not isinstance(enable_auto_card, dict):
        return AUTO_TIMER_DEFAULT
    value = enable_auto_card.get("timer")
    return value if isinstance(value, bool) else AUTO_TIMER_DEFAULT


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
