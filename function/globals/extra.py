class ExtraGlobals:
    def __init__(self):
        self.smoothie_lock_time = 0
        # 在多线程双人时, 文件读写 全局锁
        self.file_is_reading_or_writing = False


EXTRA_GLOBALS = ExtraGlobals()
