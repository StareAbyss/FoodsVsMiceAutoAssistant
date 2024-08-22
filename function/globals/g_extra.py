import threading


class GlobalExtraBiuld:
    def __init__(self):

        # 在双人作战时, 极寒冰沙 全局锁
        self.smoothie_lock_time = 0

        # 在多线程双人时, 文件读写 全局锁, 一般是用于json读写, 也被用于logs中loots unmatched 的读写
        self.file_lock = threading.Lock()

        # 额外战斗中日志 会详细显示每秒的卡片状态和当前放了哪张卡
        self.extra_log_battle = False

        # 额外战斗中日志 会详细显示match图片的细节
        self.extra_log_match = True

        # 储存战斗方案的 uuid -> 具体路径
        self.battle_plan_uuid_to_path = {}

        # 储存战斗方案uuid list顺序和文件夹中顺序完全一致!
        self.battle_plan_uuid_list = []


GLOBAL_EXTRA = GlobalExtraBiuld()
