import queue
import threading
import time

import pywintypes
import win32file
import win32pipe


class TCEPipeCommunicationThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.pipe = None
        self.pipe_name = r'\\.\pipe\\' + "TCE_pipe"
        self.running = False
        self.send_queue = queue.Queue()  # 线程安全的发送队列
        self.complete_event = threading.Event()  # 用事件替代waiting标志

    def run(self):
        print("尝试连接天知强卡器")
        try:  # 添加 try-except 块来捕获管道创建和连接过程中的异常
            self.pipe = win32pipe.CreateNamedPipe(
                self.pipe_name,
                win32pipe.PIPE_ACCESS_DUPLEX,  # 双向管道
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                1,  # 最大实例数
                65536,  # 输出缓冲区大小
                65536,  # 输入缓冲区大小
                0,  # 默认超时时间
                None  # 安全属性
            )
            print("等待客户端连接...")
            win32pipe.ConnectNamedPipe(self.pipe, None)  # 阻塞，直到客户端连接
            print("客户端已连接！")
            self.running = True
        except pywintypes.error as e:
            print(f"管道创建或连接失败: {e}")
            self.running = False  # 如果连接失败，直接停止线程
            return
        except Exception as e:
            print(f"管道创建或连接过程中发生未知错误: {e}")
            self.running = False
            return
        while self.running:
            try:
                # 优先处理所有待发送消息
                while not self.send_queue.empty():
                    message = self.send_queue.get_nowait()
                    try:
                        win32file.WriteFile(self.pipe, message)
                        print(f"发送: {message}")
                    except pywintypes.error as e:
                        print(f"发送失败: {e}")
                        self.stop()
                        break
                _, _, messages_left = win32pipe.PeekNamedPipe(self.pipe, 0)
                if messages_left > 0:
                    # 非阻塞检查可读数据
                    try:
                        hr, data = win32file.ReadFile(self.pipe, 65536)
                        if hr == 0 and data:
                            decoded_data = data.decode('utf-8', errors='ignore')
                            print(f"收到: {decoded_data}")
                            if decoded_data == "complete":
                                self.complete_event.set()  # 通过事件通知完成
                    except pywintypes.error as e:
                        if e.args[0] == 2:  # No process is on the other end of the pipe.
                            print("管道另一端没有进程。")
                            self.stop()
                        elif e.args[0] == 109:  # The pipe has been ended.
                            print("管道已结束")
                            # 设置完成事件
                            self.complete_event.set()
                            self.stop()
                        elif e.args[0] == 234:  # ERROR_MORE_DATA
                            # 忽略此错误，继续读取
                            continue
                        else:
                            print(f"Pipe read error: {e}")
                            self.stop()  # 停止线程
                            break
            except Exception as e:
                print(f"Error in pipe thread: {e}")
                self.stop()  # 停止线程
                break
            time.sleep(1)

    def send_message(self, message):
        """线程安全的消息入队"""
        # 编码信息
        message = message.encode('utf-8')
        self.send_queue.put(message)
        return True

    def enhance_card(self, handle):
        message = f'enhance_card,{handle}'
        self.send_message(message)
        self.complete_event.clear()  # 重置事件状态
        self.complete_event.wait()  # 阻塞至任务完成

    def decompose_gem(self, handle):
        message = f'decompose_gem,{handle}'
        self.send_message(message)
        self.complete_event.clear()
        self.complete_event.wait()

    def stop(self):
        """
        停止线程。
        """
        self.running = False
        if self.pipe:
            try:
                win32file.CloseHandle(self.pipe)  # 关闭管道句柄
            except Exception as e:
                print(f"关闭管道时发生错误：{e}")
            self.pipe = None
        print("线程已停止")
