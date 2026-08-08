import copy


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
