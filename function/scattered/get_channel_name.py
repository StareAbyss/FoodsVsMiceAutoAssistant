SINGLE_PLAYER_MODE = "单人模式"
DUAL_PLAYER_MODE = "双人模式"


def get_player_channels(base_settings: dict) -> dict[int, str]:
    """按当前模式返回生效的玩家编号和窗口名，旧设置默认使用双人模式。"""
    channel_1p, channel_2p = get_channel_name(
        base_settings["game_name"], base_settings["name_1p"], base_settings["name_2p"])
    if base_settings.get("player_mode") == SINGLE_PLAYER_MODE:
        return {1: channel_1p}
    return {1: channel_1p, 2: channel_2p}


def get_channel_name(game_name, name_1p, name_2p):
    """转化出频道名"""
    if name_1p == "":
        channel_1p = game_name
    else:
        channel_1p = name_1p + " | " + game_name

    if name_2p == "":
        channel_2p = game_name
    else:
        channel_2p = name_2p + " | " + game_name
    return channel_1p, channel_2p


def get_reverse_channel_name(title_1p, title_2p=None):
    """转化出标题名"""

    def parse_channel(channel):
        if " | " in channel:
            name, game_name = channel.split(" | ", 1)
        else:
            name = ""
            game_name = channel
        return name, game_name

    name_1p, game_name = parse_channel(title_1p)
    name_2p = None
    if title_2p:
        name_2p, game_name = parse_channel(title_2p)
    return name_1p, name_2p, game_name
