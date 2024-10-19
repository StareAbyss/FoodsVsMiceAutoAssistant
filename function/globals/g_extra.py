import threading

from function.scattered.ethical_core import ethical_core


class GlobalExtraBiuld:
    """
    全局变量集合
    请注意, 在python中, import全局变量有两种方式
    1. 静态导入. 即 from function/globals/g_extra import GLOBAL_EXTRA 对其进行的修改无法应用到全局 仅用于导入部分完全不变的值.
    2. 动态导入, 即 from function/globals import g_extra, 以 g_extra.GLOBAL_EXTRA 进行使用, 可以正常修改和应用最新值.
    """
    def __init__(self):

        # 每秒点击次数
        self.click_per_second = 160

        # FAA可以处理的游戏画面最低帧数
        self.lowest_fps = 10

        # 在双人作战时, 极寒冰沙 全局锁
        self.smoothie_lock_time = 0

        # 在多线程双人时, 文件读写 全局锁, 一般是用于json读写, 也被用于logs中loots unmatched 的读写
        self.file_lock = threading.Lock()

        # 额外日志 - 战斗中 会详细显示每秒的卡片状态和当前放了哪张卡
        self.extra_log_battle = False  # 默认 False

        # 额外日志 - 战斗中 会详细显示match图片的细节
        self.extra_log_match = True  # 默认 True

        # 储存战斗方案的 uuid -> 具体路径
        self.battle_plan_uuid_to_path = {}

        # 储存战斗方案uuid list顺序和文件夹中顺序完全一致!
        self.battle_plan_uuid_list = []

        # 米苏物流url
        self.misu_logistics = ""

        # 伦理模式
        self.ethical_mode = ethical_core()
        print("伦理模块开启:", self.ethical_mode)


GLOBAL_EXTRA = GlobalExtraBiuld()
