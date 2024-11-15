import threading

from function.scattered.ethical_core import ethical_core

"""
全局变量
请注意, 在python中, import全局变量有两种方式
1. 静态导入. 即 from function/globals/EXTRA import VALUE 修改无法应用到全局.
2. 动态导入, 即 from function/globals import EXTRA, 以 EXTRA.VALUE 进行使用, 可以正常修改和应用最新值.
"""

# 版本号
VERSION = "v1.6.0"

# 每秒点击次数
CLICK_PER_SECOND = 120

# FAA可以处理的游戏画面最低帧数
LOWEST_FPS = 10

# 在双人作战时, 极寒冰沙 全局锁
SMOOTHIE_LOCK_TIME = 0

# 在多线程双人时, 文件读写 全局锁, 一般是用于json读写, 也被用于logs中loots unmatched 的读写
FILE_LOCK = threading.Lock()

# 额外日志 - 战斗中 会详细显示每秒的卡片状态和当前放了哪张卡
EXTRA_LOG_BATTLE = False  # 默认 False

# 额外日志 - 战斗中 会详细显示match图片的细节
EXTRA_LOG_MATCH = True  # 默认 True

# 储存战斗方案的 uuid -> 具体路径 key是保持了插入顺序因此是有序的
BATTLE_PLAN_UUID_TO_PATH = {}

# 米苏物流url
MISU_LOGISTICS = ""

# 伦理模式
ETHICAL_MODE = ethical_core()
print("伦理模块开启:", ETHICAL_MODE)
