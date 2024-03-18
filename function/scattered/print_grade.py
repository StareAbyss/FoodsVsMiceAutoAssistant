def print_g(text, player, garde=1):
    """
    分级print函数
    :param text: 正文
    :param player: player id
    :param garde: 级别, 1-[Info]默认 2-[Warning] 3或其他-[Error]
    :return: None
    """
    if garde == 1:
        garde_text = "Info"
    elif garde == 2:
        garde_text = "Warning"
    else:
        garde_text = "Error"

    print("[{}] [{}P] {}".format(garde_text,player,text))
