from win32gui import FindWindowEx, FindWindow

"""
窗口结构
Type:DUIWindow Name: channel-name # 360层级
    |- Type: TabContentWnd
        |- Type: CefBrowserWindow
            |- Type: Chrome_WidgetWin_0 # 窗口浏览器层级
                |- Type: WrapperNativeWindowClass
                    |- Type: NativeWindowClass # Flash游戏层级

"""


def faa_get_handle(channel, mode="game"):
    """
    解析频道名称 获取句柄, 仅支持360游戏大厅,
    号1：输入你为游戏命名 例如'锑食‘
    号2：输入你命名的角色名 + 空格 + | + 空格 游戏命名。例如：'深渊之下 | 锑食'
    :param channel: 频道名称
    :param mode: "360" -> "browser" -> "flash"
    :return: handel
    """

    handle = FindWindow("DUIWindow", channel)  # 360窗口 该层级有刷新框
    if mode in ["browser", "flash"]:
        handle = FindWindowEx(handle, None, "TabContentWnd", "")
        handle = FindWindowEx(handle, None, "CefBrowserWindow", "")
        handle = FindWindowEx(handle, None, "Chrome_WidgetWin_0", "")  # 该层级 有 服务器序号输入框
    if mode == "flash":
        handle = FindWindowEx(handle, None, "WrapperNativeWindowClass", "")
        handle = FindWindowEx(handle, None, "NativeWindowClass", "")  # game窗口

    return handle


if __name__ == '__main__':
    print(faa_get_handle(channel="锑食", mode="360"))
    print(faa_get_handle(channel="锑食", mode="browser"))
    print(faa_get_handle(channel="锑食", mode="flash"))  # 刷新游戏后改变
