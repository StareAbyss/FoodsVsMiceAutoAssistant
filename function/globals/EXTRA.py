import itertools
import threading

from function.globals.loadings import loading

loading.update_progress(18,"正在载入全局设置...")
from PyQt6 import QtGui

from function.globals.get_paths import PATHS
from function.scattered.ethical_core import ethical_core

"""
全局变量
请注意, 在python中, import全局变量有两种方式
1. 静态导入. 即 from function/globals/EXTRA import VALUE 修改无法应用到全局.
2. 动态导入, 即 from function/globals import EXTRA, 以 EXTRA.VALUE 进行使用, 可以正常修改和应用最新值.
"""


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


def get_true_stage_id():

    def generate_stage_ids(prefix: str, part2_range: list, part3_range: list) -> list:
        """
        生成指定规则的关卡代号列表

        :param prefix: 前缀标识（如："CS"、"MT"）
        :param part2_range: 第二部分取值范围 [起始, 结束]
        :param part3_range: 第三部分取值范围 [起始, 结束]
        :return: 符合规则的所有组合列表
        """
        # 生成数字序列
        part2_values = range(part2_range[0], part2_range[1] + 1)
        part3_values = range(part3_range[0], part3_range[1] + 1)

        # 生成所有组合
        combinations = itertools.product(part2_values, part3_values)

        # 格式化为字符串
        return [f"{prefix}-{p2}-{p3}" for p2, p3 in combinations]

    stage_ids = []

    # 常规
    stage_ids += generate_stage_ids("NO", [1, 1], [1, 15])
    stage_ids += generate_stage_ids("NO", [2, 2], [1, 16])
    stage_ids += generate_stage_ids("NO", [3, 3], [1, 6])
    stage_ids += generate_stage_ids("NO", [4, 4], [1, 16])
    stage_ids += generate_stage_ids("NO", [5, 5], [1, 7])
    stage_ids += generate_stage_ids("NO", [6, 6], [1, 10])
    # 勇士
    stage_ids += generate_stage_ids("WA", [0, 0], [1, 23])
    # 番外
    stage_ids += generate_stage_ids("EX", [1, 1], [1, 6])
    stage_ids += generate_stage_ids("EX", [2, 2], [1, 9])
    stage_ids += generate_stage_ids("EX", [3, 3], [1, 5])
    stage_ids += generate_stage_ids("EX", [4, 4], [1, 6])
    stage_ids += generate_stage_ids("EX", [5, 5], [1, 8])
    # 跨服
    stage_ids += generate_stage_ids("CS", [1, 7], [1, 8])
    # 魔塔
    stage_ids += generate_stage_ids("MT", [1, 1], [0, 165])  # 0为爬塔模式
    stage_ids += generate_stage_ids("MT", [2, 2], [0, 100])  # 0为爬塔模式
    stage_ids += generate_stage_ids("MT", [3, 3], [1, 4])
    # 宠物
    stage_ids += generate_stage_ids("PT", [0, 0], [0, 25])  # 0为爬塔模式
    # 悬赏
    stage_ids += generate_stage_ids("OR", [0, 0], [1, 4])
    # 公会副本
    stage_ids += generate_stage_ids("GD", [0, 0], [1, 4])
    # 假期
    stage_ids += ["HH-0-0"]
    # 世界boss
    stage_ids += generate_stage_ids("WB", [0, 0], [0, 100])
    # 多元奇遇
    stage_ids += generate_stage_ids("MU", [1, 1], [1, 2])
    stage_ids += generate_stage_ids("MU", [2, 2], [1, 3])
    stage_ids += generate_stage_ids("MU", [4, 4], [1, 3])
    # 生肖
    stage_ids += generate_stage_ids("CZ", [0, 0], [1, 4])

    return stage_ids


# 版本号
VERSION = "v2.3.0"

# 缩放倍率
ZOOM_RATE = 1.0

# 样式
THEME = "dark"

# 翻牌次数
FLOP_TIMES = 2

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
TWEAK_BATTLE_PLAN_UUID_TO_PATH = {}

# 储存任务序列的 uuid -> 具体路径 key是保持了插入顺序因此是有序的
TASK_SEQUENCE_UUID_TO_PATH = {}

# 米苏物流url
MISU_LOGISTICS = ""

# 伦理模式
ETHICAL_MODE = ethical_core()
print("伦理模块开启:", ETHICAL_MODE)

# 正确的关卡id们
TRUE_STAGE_ID = get_true_stage_id()

Q_FONT = get_q_font()
