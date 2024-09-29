import win32gui
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel


class DragLabel(QLabel):
    # 定义一个自定义信号，信号传递一个字符串参数
    windowNameChanged1 = pyqtSignal(str)  # 发送1P窗口名的信号
    windowNameChanged2 = pyqtSignal(str)  # 发生2P窗口名的信号

    first_or_second = 1  # 用来判断当前应该发生1P窗口名还是2P窗口名

    def __init__(self, parent=None):
        super().__init__(parent)


        # self.setText("拖动鼠标到窗口上，然后松开鼠标按钮")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.startPos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.startPos = event.pos()  # 记录标签上鼠标按下的位置

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.startPos:
            endPos = event.pos()
            self.setText(f"{endPos.x()}, {endPos.y()}")  # 更新标签文本显示当前位置

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            global_end_pos = event.globalPosition()  # 获取鼠标在屏幕上的全局位置
            found_windows = []

            def enum_windows_callback(hwnd, lParam):
                rect = win32gui.GetWindowRect(hwnd)
                if rect[0] <= global_end_pos.x() <= rect[2] and rect[1] <= global_end_pos.y() <= rect[3]:
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name == "DUIWindow":
                        found_windows.append(hwnd)

            # 遍历所有窗口
            win32gui.EnumWindows(enum_windows_callback, None)

            if found_windows:
                # 只取找到的第一个窗口的信息进行显示
                window_handle = found_windows[0]
                window_title = win32gui.GetWindowText(window_handle)

                # 获取窗口类名
                try:
                    class_name = win32gui.GetClassName(window_handle)  # 尝试获取窗口的类名
                except Exception as e:
                    class_name = "无法获取类名"  # 如果获取失败，设置类名为 '无法获取类名'

                # 发射信号，传递窗口标题
                if self.first_or_second == 1:
                    self.windowNameChanged1.emit(window_title)
                    self.first_or_second = 2
                    self.setText("双人: 请拖到2P窗口 | 单人: 再次拖到1P窗口")
                else:
                    self.windowNameChanged2.emit(window_title)
                    self.first_or_second = 1
                    self.setText("获取成功~")

                    # # 显示包含窗口标题、句柄和类名的消息框
                # QMessageBox.information(self, "窗口信息",
                #     f"窗口名: {window_title}\n窗口句柄: {window_handle}\n窗口类名: {class_name}")
            # else:
            #     QMessageBox.warning(self, "错误", "未找到类名为 'DUIWindow' 的窗口")

            self.startPos = None  # 重置鼠标拖动的起始位置为 None
