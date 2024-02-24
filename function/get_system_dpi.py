from ctypes import windll


def get_system_dpi():
    # 创建一个设备上下文（DC）用于屏幕
    hdc = windll.user32.GetDC(0)
    # 获取屏幕的水平DPI
    my_dpi = windll.gdi32.GetDeviceCaps(hdc, 88)  # 88 is the index for LOGPIXELSX
    windll.user32.ReleaseDC(0, hdc)
    return my_dpi
