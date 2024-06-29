class ExtraGlobals:
    def __init__(self):
        # 在双人作战时, 极寒冰沙 全局锁
        self.smoothie_lock_time = 0
        # 在多线程双人时, 文件读写 全局锁
        self.file_is_reading_or_writing = False
        # 额外战斗中日志 会详细显示每秒的卡片状态和当前放了哪张卡
        self.battle_extra_log = False


EXTRA_GLOBALS = ExtraGlobals()
