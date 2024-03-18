from ctypes import windll


def get_system_dpi():
    """
    需要注意 该函数必须在ui类中调用才能正常的生效，原因不明
    """
    # 创建一个设备上下文（DC）用于屏幕
    hdc = windll.user32.GetDC(0)
    # 获取屏幕的水平DPI
    my_dpi = windll.gdi32.GetDeviceCaps(hdc, 88)  # 88 is the index for LOGPIXELSX
    windll.user32.ReleaseDC(0, hdc)
    return my_dpi
