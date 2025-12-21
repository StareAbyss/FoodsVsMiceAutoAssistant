import copy
from datetime import datetime, timedelta
from threading import Timer

from function.globals.log import CUS_LOGGER
from function.scattered.get_task_sequence_list import get_task_sequence_list
from function.globals import EXTRA


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
                # 获取任务序列索引（通过UUID查找或者直接使用索引）
                task_sequence_index = self._get_task_sequence_index(timer_opt["plan"])
                self.init_todo_timer(timer_index=i, tar_time=tar_time, task_sequence_index=task_sequence_index)
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

    def init_todo_timer(self, timer_index, tar_time, task_sequence_index):
        h = tar_time["h"]
        m = tar_time["m"]
        delta_seconds = calculate_sec_to_next_time(next_hour=h, next_minute=m)
        CUS_LOGGER.debug(
            f"[定时启动] 即将创建Timer, 下次启动时间{h:02d}:{m:02d}, 即 {delta_seconds} 秒后, 任务序列索引为 {task_sequence_index}")
        timer = Timer(
            interval=delta_seconds,
            function=self.call_back,
            kwargs={"timer_index": timer_index, "task_sequence_index": task_sequence_index, "tar_time": tar_time})
        self.todo_timers[timer_index] = timer

    def call_back(self, timer_index, task_sequence_index, tar_time):
        # 启动线程 - 使用负数索引来表示这是任务序列而不是方案
        self.thread_todo_start.emit(-task_sequence_index - 1)
        # 动态校准时间
        delta_seconds = 0
        while delta_seconds < 60:
            # 设定最短时间 防止重复调用
            h = tar_time["h"]
            m = tar_time["m"]
            delta_seconds = calculate_sec_to_next_time(next_hour=h, next_minute=m)
        CUS_LOGGER.debug(
            f"即将创建timer, 下次启动时间{h:02d}:{m:02d}, 即 {delta_seconds} 秒后, 任务序列索引为 {task_sequence_index}")
        # 回调 循环
        timer = Timer(
            interval=delta_seconds,
            function=self.call_back,
            kwargs={"timer_index": timer_index, "task_sequence_index": task_sequence_index, "tar_time": tar_time}
        )
        timer.start()
        # 覆盖原有的timer引用, 以防止内存泄漏
        self.todo_timers[timer_index] = timer
        
    def _get_task_sequence_index(self, plan_identifier):
        """
        根据计划标识符（UUID或索引）获取任务序列索引
        :param plan_identifier: 可能是UUID字符串或者是索引整数
        :return: 任务序列索引
        """
        # 确保任务序列UUID映射是最新的
        if hasattr(EXTRA, 'TASK_SEQUENCE_UUID_TO_PATH'):
            task_sequence_uuid_to_path = EXTRA.TASK_SEQUENCE_UUID_TO_PATH
            task_sequence_list = get_task_sequence_list(with_extension=False)
            
            # 如果是UUID字符串
            if isinstance(plan_identifier, str) and plan_identifier:
                # 通过UUID查找索引
                uuid_list = list(task_sequence_uuid_to_path.keys())
                try:
                    return uuid_list.index(plan_identifier)
                except ValueError:
                    pass  # 如果找不到UUID，回退到默认行为
            
            # 如果是索引（向后兼容）
            elif isinstance(plan_identifier, int):
                return plan_identifier
                
        # 默认返回0（第一个任务序列）
        return 0


def calculate_sec_to_next_time(next_hour, next_minute):
    # 获取当前时间
    now = datetime.now()

    # 构建下一次启动时间的datetime对象
    # 注意：这里假设启动时间是今天，如果已经过了今天的这个时间，则应该设置为明天的这个时间
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