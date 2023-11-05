import ctypes
import threading
import time


class ThreadWithException(threading.Thread):
    """重写的线程方法, 通过抛出异常来实现结束线程, 该方法会立刻中断run方法, 完全不管循环是否进行完一轮"""

    def __init__(self, target, kwargs=None, name=None, ):
        super().__init__()

        threading.Thread.__init__(self)

        self.target = target

        if kwargs:
            self.kwargs = kwargs
        else:
            self.kwargs = {}

        if name:
            self.name = name
        else:
            self.name = "My Thread"

    def run(self):
        try:
            print("[{}] start".format(self.name))
            self.target(**self.kwargs)
        finally:
            print("[{}] end".format(self.name))

    def get_id(self):
        """获取进程的唯一id"""
        # returns id of the respective thread
        if hasattr(self, '_thread_id'):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id

    def raise_exception(self):
        """发送错误 终止线程"""
        thread_id = self.get_id()
        # 精髓就是这句话，给线程发过去一个exceptions，线程就那边响应完就停了
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print('Exception raise failure')

    def stop(self):
        """等效的终止线程"""
        self.raise_exception()


def f1(b):
    while True:
        time.sleep(b)
        print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))


def f2():
    t1 = ThreadWithException(target=f1, name="nesting_2", kwargs={"b": 1})
    t2 = ThreadWithException(target=f1, name="nesting_2", kwargs={"b": 1})
    t1.start()
    t2.start()
    time.sleep(5)

    t1.stop()
    t1.join()


if __name__ == '__main__':
    t2 = ThreadWithException(target=f2, name="nesting_1", kwargs={})
    t2.start()
