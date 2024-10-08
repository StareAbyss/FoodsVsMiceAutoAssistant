import threading
import time

# 创建一个全局变量
shared_resource = 0

# 创建一个锁对象
lock = threading.Lock()


def worker():
    global shared_resource

    with lock:
        print(f"Thread {threading.current_thread().name} acquiring lock")
        # 执行临界区代码
        shared_resource += 1
        print(f"Thread {threading.current_thread().name} incremented shared_resource to {shared_resource}")
        time.sleep(1)  # 模拟耗时操作
        print(f"Thread {threading.current_thread().name} releasing lock")


# 创建多个线程
threads = []
for i in range(5):
    t = threading.Thread(target=worker, name=f"Thread-{i}")
    threads.append(t)
    t.start()

# 等待所有线程完成
for t in threads:
    t.join()

print(f"Final value of shared_resource: {shared_resource}")
