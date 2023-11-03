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
