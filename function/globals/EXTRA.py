import threading

from PyQt6 import QtGui

from function.globals.get_paths import PATHS
from function.scattered.ethical_core import ethical_core

"""
全局变量
请注意, 在python中, import全局变量有两种方式
1. 静态导入. 即 from function/globals/EXTRA import VALUE 修改无法应用到全局.
2. 动态导入, 即 from function/globals import EXTRA, 以 EXTRA.VALUE 进行使用, 可以正常修改和应用最新值.
"""

# 版本号
VERSION = "v2.2.0"

# 每秒点击次数
CLICK_PER_SECOND = 120

# FAA可以处理的游戏画面最低帧数
LOWEST_FPS = 10

# FAA卡片放满后的禁用时长 秒
FULL_BAN_TIME = 5

# FAA开局和结算加速时长 0则不加速
ACCELERATE_START_UP_VALUE = 0
ACCELERATE_SETTLEMENT_VALUE = 0

# FAA战斗最长时间 Min
MAX_BATTLE_TIME = 0

# 在双人作战时, 极寒冰沙 全局锁
SMOOTHIE_LOCK_TIME = 0
# GEM_SKILL_LOCK_TIME = 0

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


def get_q_font():
    # 读取字体文件
    font_id = QtGui.QFontDatabase.addApplicationFont(PATHS["font"] + "\\SmileySans-Oblique.ttf")
    QtGui.QFontDatabase.addApplicationFont(PATHS["font"] + "\\手书体.ttf")

    # 获取字体家族名称
    font_families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
    if not font_families:
        raise ValueError("Failed to load font file.")

    font_family = font_families[0]

    # 创建 QFont 对象并设置大小
    return QtGui.QFont(font_family, 11)


Q_FONT = get_q_font()
