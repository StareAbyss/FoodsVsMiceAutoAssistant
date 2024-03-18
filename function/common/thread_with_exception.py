import ctypes
import threading


class ThreadWithException(threading.Thread):
    def __init__(self, target, kwargs=None, name="My Thread", is_print=True):
        """
        重写的线程方法, 通过抛出异常来实现结束线程, 该方法会立刻中断run方法, 完全不管循环是否进行完一轮, 且可以捕获结束参数
        :param target: 目标函数
        :param kwargs: 目标函数参数(字典形式)
        :param name: 线程名称(用于print)
        :param is_print: 是否print一些线程本身的调试信息
        """
        super().__init__()
        threading.Thread.__init__(self)

        # 转化None 为空字典
        if kwargs is None:
            kwargs = {}

        # 默认参数
        self.target = target
        self.kwargs = kwargs
        self.name = name
        self.is_print = is_print

        # 额外参数
        self.return_value = None  # 用于获取函数返回值

    def run(self):
        try:
            if self.is_print:
                print("[{}] start".format(self.name))
            self.return_value = self.target(**self.kwargs)
        finally:
            if self.is_print:
                print("[{}] end".format(self.name))

    def get_id(self):
        """获取进程的唯一id"""
        # returns id of the respective thread
        if hasattr(self, '_thread_id'):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id

    def get_return_value(self):
        threading.Thread.join(self)  # 等待 目标函数 执行完毕
        try:
            return self.return_value
        except Exception:
            print(Exception)
            return None

    def raise_exception(self):
        """发送错误 终止线程"""
        thread_id = self.get_id()
        # 精髓就是这句话，给线程发过去一个exceptions，线程就那边响应完就停了
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id,
                                                         ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print('Exception raise failure')

    def stop(self):
        """等效的终止线程"""
        self.raise_exception()
