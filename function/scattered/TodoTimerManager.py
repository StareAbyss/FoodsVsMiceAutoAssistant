import copy
from datetime import datetime, timedelta
from threading import Timer

from function.globals.log import CUS_LOGGER


class TodoTimerManager:
    def __init__(self, opt, func_thread_todo_start):
        self.todo_timers = {}

        self.thread_todo_start = func_thread_todo_start

        self.opt = copy.deepcopy(opt)  # 深拷贝 意味着开始运行后再配置不会有反应

    def start(self):
        # 初始化timers
        for i in range(1, 6):
            timer_opt = self.opt["timer"][str(i)]
            if timer_opt["active"]:
                tar_time = {"h": timer_opt["h"], "m": timer_opt["m"]}
                plan_index = timer_opt["plan"]
                self.init_todo_timer(timer_index=i, tar_time=tar_time, plan_index=plan_index)
        # 开始timers
        for key, timer in self.todo_timers.items():
            timer.start()

    def stop(self):
        # 中止所有的timer
        for key, timer in self.todo_timers.items():
            timer.cancel()
        # 删除引用 清理内存
        self.todo_timers.clear()
        # 错误示范 这东西不要清理
        # self.opt = None

    def set_opt(self, opt):
        self.opt = copy.deepcopy(opt)  # 深拷贝 意味着开始运行后再配置不会有反应

    def init_todo_timer(self, timer_index, tar_time, plan_index):
        h = tar_time["h"]
        m = tar_time["m"]
        delta_seconds = calculate_sec_to_next_time(next_hour=h, next_minute=m)
        CUS_LOGGER.debug(
            f"即将创建timer, 下次启动时间{h:02d}:{m:02d}, 即 {delta_seconds} 秒后, 计划索引为 {plan_index}")
        timer = Timer(
            interval=delta_seconds,
            function=self.call_back,
            kwargs={"timer_index": timer_index, "plan_index": plan_index, "tar_time": tar_time})
        self.todo_timers[timer_index] = timer

    def call_back(self, timer_index, plan_index, tar_time):
        # 启动线程
        self.thread_todo_start.emit(plan_index)
        # 动态校准时间
        delta_seconds = 0
        while delta_seconds < 60:
            # 设定最短时间 防止重复调用
            h = tar_time["h"]
            m = tar_time["m"]
            delta_seconds = calculate_sec_to_next_time(next_hour=h, next_minute=m)
        CUS_LOGGER.debug(
            f"即将创建timer, 下次启动时间{h:02d}:{m:02d}, 即 {delta_seconds} 秒后, 计划索引为 {plan_index}")
        # 回调 循环
        timer = Timer(
            interval=delta_seconds,
            function=self.call_back,
            kwargs={"timer_index": timer_index, "plan_index": plan_index, "tar_time": tar_time}
        )
        timer.start()
        # 覆盖原有的timer引用, 以防止内存泄漏
        self.todo_timers[timer_index] = timer


def calculate_sec_to_next_time(next_hour, next_minute):
    # 获取当前时间
    now = datetime.now()

    # 构建下一次启动时间的datetime对象
    # 注意：这里假设启动时间是今天，如果已经过了今天的这个时间，则应该设置为明天
    next_time = now.replace(hour=next_hour, minute=next_minute, second=0, microsecond=0)
    if next_time < now:
        # 如果计算出的下一次启动时间已经在过去了，那么将它设置为明天的这个时间
        next_time += timedelta(days=1)

    # 计算差值
    delta_seconds = int((next_time - now).total_seconds())

    if __name__ == '__main__':
        print(f"从现在到下一次启动时间还需要经过的秒数: {delta_seconds}秒")

    return delta_seconds


if __name__ == '__main__':
    calculate_sec_to_next_time(next_hour=9, next_minute=4)
