import ctypes
import datetime
import time
from threading import Thread

import cv2
import numpy as np
import win32con
import win32gui
import win32ui

from function.globals.log import CUS_LOGGER

# try:
#     ctypes.windll.shcore.SetProcessDpiAwareness(2)  # 2 = Per-monitor v2 DPI awareness
# except:
#     print("无法设置DPI感知级别")


class WindowRecorder:
    def __init__(self, output_file="window_recording.mp4", handle=None, fps=30.0, window_title=None, see_time=False,
                 is_show=False):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = output_file + f"{timestamp}.mp4"
        self.fps = fps
        self.window_title = window_title
        self.recording = False
        self.recording_thread = None
        self.hwnd = handle
        self.out = None
        self.width = 0
        self.height = 0
        self.see_time = see_time
        self.is_show = is_show
        # 添加DC相关属性
        self.hwndDC = None
        self.mfcDC = None
        self.saveDC = None
        self.saveBitMap = None

    def start_recording(self):
        """开始录制指定窗口"""
        if self.recording:
            print("Already recording")
            return

        # 查找目标窗口
        if not self.hwnd:
            self.hwnd = win32gui.FindWindow(None, self.window_title)
        if not self.hwnd:
            raise ValueError(f"未找到标题包含 '{self.window_title}' 的窗口")

        # 获取窗口尺寸（物理像素）
        rect = win32gui.GetWindowRect(self.hwnd)
        self.width = rect[2] - rect[0]
        self.height = rect[3] - rect[1]
        # 获取DPI缩放因子
        try:
            user32 = ctypes.windll.user32
            hdc = user32.GetDC(None)
            LOGPIXELSX = 88
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, LOGPIXELSX)
            user32.ReleaseDC(None, hdc)
            # 计算缩放因子
            self.scale_factor = dpi / 96.0  # 96是标准DPI
            print(f"检测到DPI缩放因子: {self.scale_factor:.2f}")

            # 如果需要，可以调整尺寸以匹配实际物理像素
            self.width = int(self.width // self.scale_factor)
            self.height = int(self.height // self.scale_factor)

        except Exception as e:
            print(f"获取DPI信息失败: {e}")
            self.scale_factor = 1.0
        # 设置视频写入器
        self.out = cv2.VideoWriter(
            self.output_file,
            cv2.VideoWriter_fourcc(*'mp4v'),
            self.fps,
            (self.width, self.height)
        )

        # 启动录制线程
        self.recording = True
        self.recording_thread = Thread(target=self._record_window, daemon=True)
        self.recording_thread.start()

    def _record_window(self):
        """实际的窗口录制线程"""
        try:
            # 初始化DC资源
            self.hwndDC = win32gui.GetWindowDC(self.hwnd)
            if not self.hwndDC:
                print("无法获取窗口DC")
                return

            self.mfcDC = win32ui.CreateDCFromHandle(self.hwndDC)
            self.saveDC = self.mfcDC.CreateCompatibleDC()
            if not self.saveDC:
                print("创建兼容DC失败")
                return

            # 创建位图
            self.saveBitMap = win32ui.CreateBitmap()
            self.saveBitMap.CreateCompatibleBitmap(self.mfcDC, self.width, self.height)

            while self.recording:
                try:
                    # 选择位图对象
                    self.saveDC.SelectObject(self.saveBitMap)
                    # 拷贝图像
                    self.saveDC.BitBlt((0, 0), (self.width, self.height), self.mfcDC, (0, 0), win32con.SRCCOPY)

                    # 转换为numpy数组
                    bmpinfo = self.saveBitMap.GetInfo()
                    bmpstr = self.saveBitMap.GetBitmapBits(True)
                    img = np.frombuffer(bmpstr, dtype=np.uint8)
                    img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    if self.see_time:
                        # 添加时间戳（关键修改部分）
                        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                        current_time = datetime.datetime.now().strftime("%H:%M:%S")

                        # 配置参数（优化版）
                        font_scale = 0.5
                        font_thickness = 2
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        line_spacing = 15  # 行间距
                        h_padding = 6  # 水平内边距（原为12）
                        v_padding = 20  # 垂直内边距保持不变

                        # 获取文本尺寸
                        (text_width1, text_height1), _ = cv2.getTextSize(current_date, font, font_scale, font_thickness)
                        (text_width2, text_height2), _ = cv2.getTextSize(current_time, font, font_scale, font_thickness)

                        # 计算最大宽度和总高度
                        max_text_width = max(text_width1, text_width2)
                        total_text_height = text_height1 + text_height2 + line_spacing

                        # 优化背景框尺寸计算
                        rect_width = max_text_width + h_padding * 2  # 水平方向压缩
                        rect_height = total_text_height + v_padding * 2

                        # 绘制白色背景矩形（更紧凑）
                        cv2.rectangle(img,
                                      (5, 5),
                                      (5 + rect_width, 5 + rect_height),
                                      (255, 255, 255),
                                      -1)

                        # 优化文字绘制位置
                        line1_y = 5 + v_padding + text_height1
                        line2_y = line1_y + text_height2 + line_spacing

                        cv2.putText(img, current_date,
                                    (5 + h_padding, line1_y),  # 水平位置调整
                                    font,
                                    font_scale,
                                    (0, 0, 255),
                                    font_thickness)

                        cv2.putText(img, current_time,
                                    (5 + h_padding, line2_y),  # 水平位置调整
                                    font,
                                    font_scale,
                                    (0, 0, 255),
                                    font_thickness)

                    # 写入视频文件
                    self.out.write(img)
                    if self.is_show:
                        # 实时显示当前帧（可选）
                        cv2.imshow('Window Recorder', img)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            print("用户按 q 键，停止录制")
                            self.stop_recording()
                            break

                    # 控制帧率
                    time.sleep(1 / self.fps)
                except Exception as e:
                    print(f"录制单帧时发生错误: {e}")
                    continue

        except Exception as e:
            CUS_LOGGER.error(f"录制过程中发生错误: {e}")
            import traceback
            traceback.print_exc()  # 打印完整的错误堆栈
        finally:
            # 释放GDI资源
            try:
                if self.saveBitMap:
                    self.saveBitMap.DeleteObject()
            except:
                pass
            try:
                if self.saveDC:
                    self.saveDC.DeleteDC()
            except:
                pass
            try:
                if self.mfcDC:
                    self.mfcDC.DeleteDC()
            except:
                pass
            try:
                if self.hwndDC:
                    win32gui.ReleaseDC(self.hwnd, self.hwndDC)
            except:
                pass

            # 释放视频写入器
            if self.out:
                self.out.release()
                self.out = None
            print("视频写入器已释放")

    def stop_recording(self):
        if not self.recording:
            return
        self.recording = False
        if self.out:
            self.out.release()
            self.out = None
        print("视频写入器已释放")


if __name__ == "__main__":
    try:
        window_title = "aaa"
        output_file = "test_recording_class.mp4"
        fps = 10

        print("准备开始录制（5秒后自动停止）...")
        print(f"请在5秒内打开窗口：{window_title}")
        time.sleep(2)

        recorder = WindowRecorder(output_file, fps, window_title)
        recorder.start_recording()
        print(f"正在录制窗口：{window_title}")
        print("录制将持续5秒，请在目标窗口中进行一些操作")

        time.sleep(5)

        recorder.stop_recording()
        print("录制已完成！")
        print(f"视频已保存为：{output_file}")

    except Exception as e:
        print(f"发生错误: {str(e)}")