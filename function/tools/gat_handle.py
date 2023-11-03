from win32gui import FindWindowEx, FindWindow


def faa_get_handle(channel, mode="game"):
    """
    解析频道名称 获取句柄, 仅支持360游戏大厅,
    号1：输入你为游戏命名 例如'锑食‘
    号2：输入你命名的角色名 + 空格 + | + 空格 游戏命名。例如：'深渊之下 | 锑食'
    :param channel: 频道名称
    :param mode: "browser" -> "game"
    :return: handel
    """

    handle = FindWindow("DUIWindow", channel)  # 360窗口
    if mode == "game":
        handle = FindWindowEx(handle, None, "TabContentWnd", "")
        handle = FindWindowEx(handle, None, "CefBrowserWindow", "")
        handle = FindWindowEx(handle, None, "Chrome_WidgetWin_0", "")  # 4399窗口
        handle = FindWindowEx(handle, None, "WrapperNativeWindowClass", "")
        handle = FindWindowEx(handle, None, "NativeWindowClass", "")  # 游戏窗口

    return handle


if __name__ == '__main__':
    print(faa_get_handle(channel="锑食", mode="browser"))
    print(faa_get_handle(channel="锑食", mode="game"))
