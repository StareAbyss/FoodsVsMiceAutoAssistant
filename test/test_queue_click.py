import queue
from time import sleep

# 创建一个队列来存储点击事件
click_queue = queue.PriorityQueue()


# 定义一个点击事件类
class ClickEvent:
    def __init__(self, x, y):
        self.x = x
        self.y = y


# 添加点击事件到队列中
click_queue.put(ClickEvent(10, 20))
click_queue.put(ClickEvent(30, 40))


# 定义一个函数来处理队列中的点击事件
def handle_click_queue():
    # 循环处理点击队列中的事件 先判断队列中是否有事件
    while not click_queue.empty():
        # 从队列中取出一个点击事件
        click = click_queue.get()
        # 处理点击事件
        print(f"Handling click at x={click.x}, y={click.y}")

        sleep(0.1)


# 调用函数处理点击队列
handle_click_queue()
