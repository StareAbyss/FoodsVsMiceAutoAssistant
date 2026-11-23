import json
import math
import os
import re
from dataclasses import dataclass

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from function.globals.get_paths import PATHS
from function.scattered.get_list_battle_plan import get_list_battle_plan, get_list_tweak_plan
from function.widget.SearchableComboBox import SearchableComboBox

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 每个类别（列组）内的子列顺序
SUB_HEADERS = ("关卡", "跳过", "卡组", "1P", "2P", "微调")
SUBCOL_STAGE = 0
SUBCOL_SKIP = 1
SUBCOL_DECK = 2
SUBCOL_1P = 3
SUBCOL_2P = 4
SUBCOL_TWEAK = 5
SUBCOLS = len(SUB_HEADERS)

PAGE_SIZE = 20
HEADER_ROWS = 2

# 卡组列是一个下拉框：自动选卡 + 6 个卡组编号
DECK_OPTIONS = ["自动选卡"] + [str(i) for i in range(1, 7)]

# JSON 缺失时的默认方案（文件名以 battle_plan/、tweak_plan/ 实际存在的为准）
DEFAULT_PLAN_1P = "2通用-烤串披萨-1P"
DEFAULT_PLAN_2P = "2通用-烤串披萨-2P"
DEFAULT_TWEAK = "!默认"

# 分类底色沿用原来的黄色半透明，按分组索引奇偶交替，使“间隔”表达分类
GROUP_COLORS = (QColor(255, 255, 0, 50), None)
# 跟随全局方案的关卡行底色
FOLLOW_GLOBAL_COLOR = QColor(0, 200, 0, 55)

# 类别的分组与分页规则：
# group_size：每几关一组；group_by_entry：data_dict 每个条目为一组；page_size：覆盖默认分页
CATEGORY_RULES = {
    "魔塔蛋糕-单人": {"group_size": 5},
    "魔塔蛋糕-双人": {"group_size": 5},
    "萌宠神殿": {"group_size": 5},
    "跨服副本": {"page_size": 16, "group_by_entry": True},
}

# 通配编号格式：例如 "MT-1-? (1-165)"
WILDCARD_RE = re.compile(r"^(?P<prefix>.+?)-\? \((?P<start>\d+)-(?P<end>\d+)\)$")

HELP_TEXT = (
    '当您在任务序列"战斗"任务中勾选"继承"后, 将启用此处设定接管\n'
    '将无视对应任务事项处进行的卡组策略和战斗方案设定\n'
    '\n'
    '优先采用"关卡方案". "未注册"前者则采用"全局方案"\n'
    '\n'
    '对于任何"关卡方案", 只要其与"全局方案"一致且不设跳过,\n'
    '它的相关设定将被清空为"未注册"状态, 自动跟随"全局方案"\n'
    '\n'
    'Ctrl+左键 保留已选项目并再选一项，Shift+左键 选中从上个被选中关卡到光标处的所有关卡。'
    '多选状态下，修改其中一个关卡的方案会同步到所有选中关卡。'
    '注意对于下拉选项框，失焦后才会提交您的修改。'
)

# 原始关卡清单（类别 -> [(关卡名, 关卡编号), ...]）。
# "前缀-? (起-止)" 展开为连续关卡，"..." 按前后编号补齐缺失关卡。
data_dict = {
    "美味岛": [
        ["曲奇岛", "NO-1-1"], ["色拉岛-陆", "NO-1-2"], ["色拉岛-水", "NO-1-3"],
        ["慕斯岛", "NO-1-4"], ["香槟岛-陆", "NO-1-5"], ["香槟岛-水", "NO-1-6"],
        ["神殿", "NO-1-7"], ["布丁岛-日", "NO-1-8"], ["布丁岛-夜", "NO-1-9"],
        ["可可岛-日", "NO-1-10"], ["可可岛-夜", "NO-1-11"], ["咖喱岛-日", "NO-1-12"],
        ["咖喱岛-夜", "NO-1-13"], ["深渊", "NO-1-14"], ["美味漫游", "NO-1-15"],
    ],
    "火山岛": [
        ["芥末小屋-日", "NO-2-1"], ["芥末小屋-夜", "NO-2-2"], ["薄荷海滩-日", "NO-2-3"],
        ["薄荷海滩-夜", "NO-2-4"], ["芝士城堡", "NO-2-5"], ["炭烧雨林-日", "NO-2-6"],
        ["炭烧雨林-夜", "NO-2-7"], ["抹茶庄园-日", "NO-2-8"], ["抹茶庄园-夜", "NO-2-9"],
        ["玛奇朵港", "NO-2-10"], ["棉花糖天空-日", "NO-2-11"], ["棉花糖天空-夜", "NO-2-12"],
        ["果酱部落-日", "NO-2-13"], ["果酱部落-夜", "NO-2-14"], ["雪顶火山", "NO-2-15"],
        ["火山漫游", "NO-2-16"],
    ],
    "火山遗迹": [
        ["果仁瀑布", "NO-3-1"], ["榛子瀑布", "NO-3-2"], ["黑提丛林", "NO-3-3"],
        ["蓝莓丛林", "NO-3-4"], ["奶昔基地", "NO-3-5"], ["圣代基地", "NO-3-6"],
    ],
    "浮空岛": [
        ["茴香竹筏-日", "NO-4-1"], ["茴香竹筏-夜", "NO-4-2"], ["孜然断桥-日", "NO-4-3"],
        ["孜然断桥-夜", "NO-4-4"], ["卤料花园", "NO-4-5"], ["月桂天空-日", "NO-4-6"],
        ["月桂天空-夜", "NO-4-7"], ["香叶空港-日", "NO-4-8"], ["香叶空港-夜", "NO-4-9"],
        ["香料飞船", "NO-4-10"], ["花椒浮岛-日", "NO-4-11"], ["花椒浮岛-夜", "NO-4-12"],
        ["丁香彩虹-日", "NO-4-13"], ["丁香彩虹-夜", "NO-4-14"], ["十三香中心岛", "NO-4-15"],
        ["浮空漫游", "NO-4-16"],
    ],
    "海底旋涡": [
        ["金枪鱼洋流", "NO-5-1"], ["珊瑚洋流-日", "NO-5-2"], ["珊瑚洋流-夜", "NO-5-3"],
        ["北极贝湍流", "NO-5-4"], ["海葵洋流-日", "NO-5-5"], ["海葵洋流-夜", "NO-5-6"],
        ["天妇罗旋涡", "NO-5-7"],
    ],
    "星际穿越": [
        ["糖球空间站-日", "NO-6-1"], ["糖球空间站-夜", "NO-6-2"], ["苏打水星-日", "NO-6-3"],
        ["苏打水星-夜", "NO-6-4"], ["汉堡王星", "NO-6-5"], ["巴旦木星-日", "NO-6-6"],
        ["巴旦木星-夜", "NO-6-7"], ["冷萃星环-日", "NO-6-8"], ["冷萃星环-夜", "NO-6-9"],
        ["多拿滋星云", "NO-6-10"],
    ],
    "勇士副本": [
        ["洞君", "WA-0-1"], ["阿诺", "WA-0-2"], ["冰渣队长", "WA-0-3"], ["...", "..."],
        ["嗡嗡中尉", "WA-0-12"], ["暴躁杰克", "WA-0-13"], ["炽热金刚", "WA-0-14"],
        ["酷帅晓明", "WA-0-15"], ["闪亮baby", "WA-0-16"], ["美队鼠", "WA-0-17"],
        ["钢铁侠鼠", "WA-0-18"], ["绿巨人鼠", "WA-0-19"], ["蜘蛛侠鼠", "WA-0-20"],
        ["鼠国高铁", "WA-0-21"], ["电光水母鼠", "WA-0-22"], ["机械鲨鱼鼠", "WA-0-23"],
    ],
    "探险营地": [
        ["戚风营地-日", "EX-1-1"], ["戚风营地-夜", "EX-1-2"], ["冰啤酒吧-日", "EX-1-3"],
        ["冰啤酒吧-夜", "EX-1-4"], ["坚果高台-日", "EX-1-5"], ["坚果高台-夜", "EX-1-6"],
    ],
    "沙漠之旅": [
        ["芦荟沙丘-日", "EX-2-1"], ["芦荟沙丘-夜", "EX-2-2"], ["沙棘绿洲", "EX-2-3"],
        ["仙人掌盆地-日", "EX-2-4"], ["仙人掌盆地-夜", "EX-2-5"], ["蜥蜴戈壁", "EX-2-6"],
        ["鱼骨沙漠-日", "EX-2-7"], ["鱼骨沙漠-夜", "EX-2-8"], ["库库尔金字塔", "EX-2-9"],
    ],
    "雪山探险": [
        ["雪宝棒棒冰-日", "EX-3-1"], ["雪宝棒棒冰-夜", "EX-3-2"], ["冰巨人雪芭-日", "EX-3-3"],
        ["冰巨人雪芭-夜", "EX-3-4"], ["爱莎星冰乐", "EX-3-5"],
    ],
    "雷城探险": [
        ["动感街区-日", "EX-4-1"], ["动感街区-夜", "EX-4-2"], ["蛋糕钟楼-日", "EX-4-3"],
        ["蛋糕钟楼-夜", "EX-4-4"], ["莓莓音乐节-日", "EX-4-5"], ["莓莓音乐节-夜", "EX-4-6"],
    ],
    "漫游奇境": [
        ["兔子洞-日", "EX-5-1"], ["兔子洞-夜", "EX-5-2"], ["蘑菇小径-日", "EX-5-3"],
        ["蘑菇小径-夜", "EX-5-4"], ["午茶庭院", "EX-5-5"], ["玫瑰花园-日", "EX-5-6"],
        ["玫瑰花园-夜", "EX-5-7"], ["悬浮梦境", "EX-5-8"],
    ],
    "龙渊除厄": [
        ["松露大厅-日", "EX-6-1"], ["松露大厅-夜", "EX-6-2"], ["百味关", "EX-6-3"],
        ["赤霞渡-日", "EX-6-4"], ["赤霞渡-夜", "EX-6-5"], ["奶盖桥", "EX-6-6"],
    ],
    "跨服副本": [
        ["古堡", "CS-1-? (1-8)"], ["天空", "CS-2-? (1-8)"], ["炼狱", "CS-3-? (1-8)"],
        ["水火", "CS-4-? (1-8)"], ["巫毒", "CS-5-? (1-8)"], ["冰跨", "CS-6-? (1-8)"],
        ["沙漠", "CS-7-? (1-8)"],
    ],
    "魔塔蛋糕-单人": [
        ["魔塔", "MT-1-? (1-165)"],
    ],
    "魔塔蛋糕-双人": [
        ["魔塔", "MT-2-? (1-100)"],
    ],
    "魔塔密室": [
        ["魔塔", "MT-3-? (1-4)"],
    ],
    "萌宠神殿": [
        ["萌宠神殿", "PT-0-? (1-25)"],
    ],
    "多元奇遇（4-7未实装)": [
        ["谷神殿", "MU-1-1"], ["星渊岛", "MU-1-2"], ["琉璃沙堡", "MU-2-1"],
        ["吉拉朵港", "MU-2-2"], ["大火山", "MU-2-3"], ["大花园", "MU-4-1"],
        ["大飞船", "MU-4-2"], ["大十三香", "MU-4-3"],
    ],
    "其他": [
        ["悬赏关卡", "OR-0-? (1-4)"], ["公会副本", "GD-0-? (1-4)"],
        ["生肖副本", "CZ-0-? (1-4)"], ["欢乐假期", "HH-0-0"], ["巅峰对决", "WB-0-0"],
    ],
}


# ---------------------------------------------------------------------------
# 数据层
# ---------------------------------------------------------------------------

@dataclass
class GlobalPlan:
    """全局方案只含卡组与 1P/2P；缺省关卡跟随它，三字段全相同的关卡会随它更新。"""
    deck: str = DECK_OPTIONS[0]
    plan_1p: str = DEFAULT_PLAN_1P
    plan_2p: str = DEFAULT_PLAN_2P

    def as_dict(self) -> dict:
        return {
            "deck": self.deck, "plan_1p": self.plan_1p, "plan_2p": self.plan_2p,
        }


@dataclass
class StageEntry:
    """总表中的一行关卡；override=False 时方案列跟随全局，跳过与微调始终独立。"""
    name: str
    code: str
    group_index: int | None = None
    override: bool = False
    skip: bool = False
    deck: str = DECK_OPTIONS[0]
    plan_1p: str = DEFAULT_PLAN_1P
    plan_2p: str = DEFAULT_PLAN_2P
    tweak: str = DEFAULT_TWEAK

    def as_dict(self) -> dict:
        return {
            "skip": self.skip, "deck": self.deck,
            "plan_1p": self.plan_1p, "plan_2p": self.plan_2p, "tweak": self.tweak,
        }


@dataclass
class CategoryBlock:
    """总表中的一个类别列组。"""
    name: str
    stages: list[StageEntry]
    page_size: int = PAGE_SIZE
    page: int = 0

    @property
    def page_count(self) -> int:
        return max(1, math.ceil(len(self.stages) / self.page_size))

    @property
    def paginated(self) -> bool:
        return self.page_count > 1

    def visible_stages(self) -> list[StageEntry]:
        start = self.page * self.page_size
        return self.stages[start:start + self.page_size]

    def stage_at(self, offset: int) -> StageEntry | None:
        stages = self.visible_stages()
        if 0 <= offset < len(stages):
            return stages[offset]
        return None


def load_stage_name_map() -> dict[str, str]:
    """按 extra > online > base 的优先级合并关卡信息，返回 {关卡号: 名称}。"""
    def walk(info: dict, out: dict) -> None:
        for type_id, category in info.items():
            if type_id in ("default", "name", "tooltip", "update_time") or not isinstance(category, dict):
                continue
            for map_id, stage_map in category.items():
                if map_id in ("name", "tooltip") or not isinstance(stage_map, dict):
                    continue
                for stage_id, stage in stage_map.items():
                    if stage_id in ("name", "tooltip"):
                        continue
                    if isinstance(stage, dict) and stage.get("name"):
                        out[f"{type_id}-{map_id}-{stage_id}"] = stage["name"]

    name_map: dict[str, str] = {}
    for file_name in ("stage_info.json", "stage_info_online.json", "stage_info_extra.json"):
        path = os.path.join(PATHS["config"], file_name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="UTF-8") as file:
                walk(json.load(file), name_map)
        except (json.JSONDecodeError, OSError):
            continue
    return name_map


def _codes_between(prev_code: str | None, next_code: str | None) -> list[str]:
    """补齐两个同前缀编号之间的缺失关卡号。"""
    if not prev_code or not next_code:
        return []
    prev_parts = prev_code.rsplit("-", 1)
    next_parts = next_code.rsplit("-", 1)
    if len(prev_parts) != 2 or len(next_parts) != 2 or prev_parts[0] != next_parts[0]:
        return []
    try:
        start, end = int(prev_parts[1]), int(next_parts[1])
    except ValueError:
        return []
    return [f"{prev_parts[0]}-{k}" for k in range(start + 1, end)]


def build_categories(name_map: dict[str, str]) -> list[CategoryBlock]:
    """把 data_dict 展开成类别列组，并计算每关的分组索引。"""
    categories: list[CategoryBlock] = []
    for cat_name, entries in data_dict.items():
        rule = CATEGORY_RULES.get(cat_name, {})
        page_size = rule.get("page_size", PAGE_SIZE)
        group_size = rule.get("group_size")
        group_by_entry = rule.get("group_by_entry", False)
        short_floor = group_size is not None

        stages: list[StageEntry] = []
        prev_code: str | None = None
        entry_index = 0
        index = 0
        while index < len(entries):
            name, code = entries[index]

            if code == "...":
                next_code = None
                for _, later_code in entries[index + 1:]:
                    if later_code != "...":
                        next_code = later_code
                        break
                for missing in _codes_between(prev_code, next_code):
                    stages.append(StageEntry(name=name_map.get(missing, missing), code=missing))
                index += 1
                continue

            match = WILDCARD_RE.match(code)
            if match:
                prefix = match.group("prefix")
                start = int(match.group("start"))
                end = int(match.group("end"))
                for n in range(start, end + 1):
                    code_full = f"{prefix}-{n}"
                    stage_name = f"第{n}层" if short_floor else name_map.get(code_full, code_full)
                    if group_size:
                        group_index = (n - 1) // group_size
                    elif group_by_entry:
                        group_index = entry_index
                    else:
                        group_index = None
                    stages.append(StageEntry(name=stage_name, code=code_full, group_index=group_index))
                prev_code = f"{prefix}-{end}"
            else:
                group_index = entry_index if group_by_entry else None
                stages.append(StageEntry(name=name, code=code, group_index=group_index))
                prev_code = code

            entry_index += 1
            index += 1

        categories.append(CategoryBlock(name=cat_name, stages=stages, page_size=page_size))
    return categories


# ---------------------------------------------------------------------------
# Model / View / Delegate
# ---------------------------------------------------------------------------

class StagePlanTableModel(QAbstractTableModel):
    """把「类别列组 + 关卡行」铺成一张二维总表。"""

    def __init__(self, categories: list[CategoryBlock], parent=None):
        super().__init__(parent)
        self.categories = categories
        self._header_font = QFont()
        self._header_font.setBold(True)
        self._muted_color = QColor(140, 140, 140)
        self.global_plan = GlobalPlan()

    @staticmethod
    def _fields(obj) -> dict:
        """参与全局同步的三个方案字段。"""
        return {
            "deck": obj.deck, "plan_1p": obj.plan_1p, "plan_2p": obj.plan_2p,
        }

    def _source(self, stage: StageEntry):
        # 设了跳过的关卡不跟随全局，方案列显示自身保存的值
        return stage if (stage.override or stage.skip) else self.global_plan

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else HEADER_ROWS + max(c.page_size for c in self.categories)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.categories) * SUBCOLS

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        cat = self.categories[col // SUBCOLS]
        sub = col % SUBCOLS

        if row == 0:
            return self._category_header_data(cat, sub, role)
        if row == 1:
            return self._subheader_data(sub, role)

        stage = cat.stage_at(row - HEADER_ROWS)
        if stage is None:
            return None

        if role == Qt.ItemDataRole.BackgroundRole:
            # 绿色只标注跟随全局的卡组/1P/2P 三列；其余列仍按分组交替黄色
            if sub in (SUBCOL_DECK, SUBCOL_1P, SUBCOL_2P) and not stage.override and not stage.skip:
                return FOLLOW_GLOBAL_COLOR
            if stage.group_index is not None:
                return GROUP_COLORS[stage.group_index % 2]

        if sub == SUBCOL_STAGE:
            if role == Qt.ItemDataRole.DisplayRole:
                return stage.name
            if role == Qt.ItemDataRole.ToolTipRole:
                return stage.code
            return None

        source = self._source(stage)
        if sub == SUBCOL_SKIP:
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if stage.skip else Qt.CheckState.Unchecked
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
            return None

        value = {
            SUBCOL_DECK: source.deck,
            SUBCOL_1P: source.plan_1p,
            SUBCOL_2P: source.plan_2p,
            SUBCOL_TWEAK: stage.tweak,
        }.get(sub)
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def _category_header_data(self, cat: CategoryBlock, sub: int, role):
        if role == Qt.ItemDataRole.FontRole:
            return self._header_font
        if sub == SUBCOL_STAGE:
            if role == Qt.ItemDataRole.DisplayRole:
                return cat.name
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
        if cat.paginated and sub == SUBCOL_1P:
            if role == Qt.ItemDataRole.DisplayRole:
                return f"{cat.page + 1}/{cat.page_count}"
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
        return None

    def _subheader_data(self, sub: int, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return SUB_HEADERS[sub]
        if role == Qt.ItemDataRole.FontRole:
            return self._header_font
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        row, col = index.row(), index.column()
        if row < HEADER_ROWS:
            return Qt.ItemFlag.NoItemFlags
        cat = self.categories[col // SUBCOLS]
        stage = cat.stage_at(row - HEADER_ROWS)
        if stage is None:
            return Qt.ItemFlag.NoItemFlags
        sub = col % SUBCOLS
        if sub == SUBCOL_STAGE:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if sub == SUBCOL_SKIP:
            return (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable)
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        row, col = index.row(), index.column()
        if row < HEADER_ROWS:
            return False
        cat = self.categories[col // SUBCOLS]
        stage = cat.stage_at(row - HEADER_ROWS)
        if stage is None:
            return False
        sub = col % SUBCOLS

        field = {
            SUBCOL_SKIP: "skip", SUBCOL_DECK: "deck",
            SUBCOL_1P: "plan_1p", SUBCOL_2P: "plan_2p", SUBCOL_TWEAK: "tweak",
        }.get(sub)
        if field is None:
            return False
        if role == Qt.ItemDataRole.CheckStateRole and field != "skip":
            return False
        if role == Qt.ItemDataRole.EditRole and field == "skip":
            return False
        if role not in (Qt.ItemDataRole.EditRole, Qt.ItemDataRole.CheckStateRole):
            return False

        # 只有方案三字段涉及“跟随全局”；跳过与微调始终是关卡独立字段
        if field in self._fields(self.global_plan):
            if not stage.override:
                for key, item in self._fields(self.global_plan).items():
                    setattr(stage, key, item)
                stage.override = True
            setattr(stage, field, value)
            if self._fields(stage) == self._fields(self.global_plan):
                stage.override = False
        else:
            if role == Qt.ItemDataRole.CheckStateRole:
                checked = value if isinstance(value, bool) else value in (
                    Qt.CheckState.Checked, Qt.CheckState.Checked.value)
                setattr(stage, field, checked)
                if field == "skip" and checked and not stage.override:
                    # 勾选跳过后脱离全局，先固化当前全局方案，避免显示跳变
                    for key, item in self._fields(self.global_plan).items():
                        setattr(stage, key, item)
            else:
                setattr(stage, field, value)

        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole,
                                             Qt.ItemDataRole.DisplayRole,
                                             Qt.ItemDataRole.EditRole])
        return True

    def set_global(self, field: str, value) -> None:
        """修改全局方案；未跳过且方案三字段都与旧全局相同的关卡整体更新为新全局。"""
        old_fields = self._fields(self.global_plan)
        setattr(self.global_plan, field, value)
        new_fields = self._fields(self.global_plan)
        if old_fields == new_fields:
            return
        for cat in self.categories:
            for stage in cat.stages:
                if not stage.skip and self._fields(stage) == old_fields:
                    for key, item in new_fields.items():
                        setattr(stage, key, item)
        top_left = self.index(HEADER_ROWS, 0)
        bottom_right = self.index(self.rowCount() - 1, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole,
                                                       Qt.ItemDataRole.DisplayRole,
                                                       Qt.ItemDataRole.EditRole])

    def set_page(self, category_index: int, page: int) -> None:
        cat = self.categories[category_index]
        page = max(0, min(page, cat.page_count - 1))
        if page == cat.page:
            return
        cat.page = page
        start_col = category_index * SUBCOLS
        self.dataChanged.emit(
            self.index(0, start_col),
            self.index(HEADER_ROWS + cat.page_size - 1, start_col + SUBCOLS - 1),
        )


class PlanComboDelegate(QStyledItemDelegate):
    """把方案单元格始终绘制成下拉框外观，编辑时立即弹出列表，并支持多选同步。"""

    def __init__(self, options: dict, parent=None):
        super().__init__(parent)
        self.options = options
        self.view: QTableView | None = None

    def paint(self, painter, option, index):
        # 表头行与翻页器保持原生外观，不画成下拉框
        if index.row() < HEADER_ROWS:
            super().paint(painter, option, index)
            return

        value = index.data(Qt.ItemDataRole.DisplayRole) or ""
        neutral_palette = QApplication.palette()

        panel = QStyleOptionViewItem(option)
        self.initStyleOption(panel, index)
        panel.text = ""
        panel.icon = QIcon()
        style = option.widget.style() if option.widget is not None else QApplication.style()
        if style is None:
            return
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, panel, painter, option.widget)

        # 下拉外观使用中性 palette，避免黄色分组底色污染弹层
        combo = QStyleOptionComboBox()
        combo.rect = option.rect.adjusted(1, 1, -1, -1)
        combo.currentText = value
        combo.editable = False
        combo.palette = neutral_palette
        combo.state = option.state
        style.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, combo, painter, option.widget)
        style.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, combo, painter, option.widget)

    def createEditor(self, parent, option, index) -> QComboBox:
        sub = index.column() % SUBCOLS
        opts = self.options.get(sub, [])
        if sub == SUBCOL_DECK:
            combo = QComboBox(parent)
            combo.addItems(opts)
        else:
            combo = SearchableComboBox(opts, parent)
        # 编辑态与弹层使用系统默认 palette，不继承单元格的黄色底色
        neutral_palette = QApplication.palette()
        combo.setPalette(neutral_palette)
        popup_view = combo.view()
        if popup_view is not None:
            popup_view.setPalette(neutral_palette)
        # 延迟到点击流程结束后再展开，避免弹层被同一次点击的释放事件收起
        QTimer.singleShot(30, combo.showPopup)
        return combo

    def setEditorData(self, editor: QComboBox, index):
        value = index.data(Qt.ItemDataRole.EditRole) or ""
        idx = editor.findText(value)
        editor.setCurrentIndex(idx if idx >= 0 else 0)

    def setModelData(self, editor: QComboBox, model: QAbstractTableModel, index):
        value = editor.currentText()
        model.setData(index, value, Qt.ItemDataRole.EditRole)
        if self.view is None:
            return
        selection_model = self.view.selectionModel()
        if selection_model is None:
            return
        sub = index.column() % SUBCOLS
        seen: set[tuple[int, int]] = set()
        for selected in selection_model.selectedIndexes():
            if not selected.isValid() or selected.row() < HEADER_ROWS:
                continue
            # 选中项所在的“关卡位置”= 行 + 类别列组，与选中了哪个子列无关
            key = (selected.row(), selected.column() // SUBCOLS)
            if key in seen:
                continue
            seen.add(key)
            target = model.index(key[0], key[1] * SUBCOLS + sub)
            if target != index:
                model.setData(target, value, Qt.ItemDataRole.EditRole)


class StagePlanTableView(QTableView):
    """无修饰键单击可编辑单元格直接编辑；Ctrl/Shift 留给多选与框选。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending_edit: QModelIndex | None = None

    def mousePressEvent(self, event):
        self._pending_edit = None
        if event.button() == Qt.MouseButton.LeftButton:
            modifiers = event.modifiers()
            if not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
                model = self.model()
                selection_model = self.selectionModel()
                index = self.indexAt(event.pos())
                if model is not None and selection_model is not None and index.isValid() and index.row() >= HEADER_ROWS:
                    if model.flags(index) & Qt.ItemFlag.ItemIsEditable:
                        # 已有多选时保留选择，避免点击下拉框把多选清掉
                        if len(selection_model.selectedIndexes()) <= 1:
                            self.setCurrentIndex(index)
                        # 按住时只记录目标，等释放后再编辑，避免弹层被点击流程关掉
                        self._pending_edit = index
                        return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        pending = self._pending_edit
        self._pending_edit = None
        if pending is not None and pending.isValid():
            self.edit(pending)
            return
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# 窗口
# ---------------------------------------------------------------------------

class QMWEditorOfStagePlan(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("全局方案&战斗方案编辑")
        self.resize(1500, 720)

        self._config_names = ["默认方案"]  # TODO: 下一步接入独立 JSON 配置后从这里读取
        self._name_map = load_stage_name_map()
        self._battle_plan_names = self._safe_plan_names(get_list_battle_plan)
        self._tweak_plan_names = self._safe_plan_names(get_list_tweak_plan)
        self._syncing_check = False

        self._plan_options = {
            SUBCOL_DECK: list(DECK_OPTIONS),
            SUBCOL_1P: list(self._battle_plan_names),
            SUBCOL_2P: list(self._battle_plan_names),
            SUBCOL_TWEAK: list(self._tweak_plan_names),
        }

        self.init_ui()

    @staticmethod
    def _safe_plan_names(getter) -> list[str]:
        try:
            return getter(with_extension=False)
        except OSError:
            return []

    def refresh_plan_lists(self) -> None:
        """重新读取方案清单，使新建/重命名后的方案立即进入下拉。"""
        self._battle_plan_names = self._safe_plan_names(get_list_battle_plan)
        self._tweak_plan_names = self._safe_plan_names(get_list_tweak_plan)
        self._plan_options[SUBCOL_1P] = list(self._battle_plan_names)
        self._plan_options[SUBCOL_2P] = list(self._battle_plan_names)
        self._plan_options[SUBCOL_TWEAK] = list(self._tweak_plan_names)

    def init_ui(self):
        self.model = StagePlanTableModel(build_categories(self._name_map))
        self.view = StagePlanTableView()
        self.view.setModel(self.model)
        self._setup_view()

        help_label = QLabel(HELP_TEXT)
        help_label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(help_label)
        layout.addLayout(self._build_config_bar())
        layout.addLayout(self._build_global_bar())
        layout.addWidget(self.view, 1)

        main_widget = QWidget()
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

    def _build_global_bar(self) -> QHBoxLayout:
        """表格上方的全局方案编辑区。"""
        bar = QHBoxLayout()
        bar.addWidget(QLabel("全局方案："))

        self.global_deck = QComboBox()
        self.global_deck.addItems(DECK_OPTIONS)
        self.global_deck.setCurrentText(self.model.global_plan.deck)
        self.global_deck.currentTextChanged.connect(lambda text: self.model.set_global("deck", text))
        bar.addWidget(QLabel("卡组"))
        bar.addWidget(self.global_deck)

        for label, field, items in (
            ("1P", "plan_1p", list(self._battle_plan_names)),
            ("2P", "plan_2p", list(self._battle_plan_names)),
        ):
            combo = SearchableComboBox(items)
            combo.setCurrentText(getattr(self.model.global_plan, field))
            combo.currentTextChanged.connect(lambda text, f=field: self.model.set_global(f, text))
            setattr(self, f"global_{field}", combo)
            bar.addWidget(QLabel(label))
            bar.addWidget(combo)

        bar.addStretch(1)
        return bar

    def _build_config_bar(self) -> QHBoxLayout:
        """顶部“可切换 JSON 配置”工具栏（本轮只做 UI，不落盘）。"""
        bar = QHBoxLayout()
        bar.addWidget(QLabel("总表配置："))

        self.config_combo = QComboBox()
        self.config_combo.addItems(self._config_names)
        self.config_combo.currentIndexChanged.connect(self._on_config_changed)
        bar.addWidget(self.config_combo)

        self.btn_new_config = QPushButton("新建")
        self.btn_new_config.clicked.connect(self._new_config)
        self.btn_rename_config = QPushButton("重命名")
        self.btn_rename_config.clicked.connect(self._rename_config)
        self.btn_delete_config = QPushButton("删除")
        self.btn_delete_config.clicked.connect(self._delete_config)
        bar.addWidget(self.btn_new_config)
        bar.addWidget(self.btn_rename_config)
        bar.addWidget(self.btn_delete_config)
        bar.addStretch(1)
        return bar

    def _setup_view(self):
        view = self.view
        horizontal_header = view.horizontalHeader()
        vertical_header = view.verticalHeader()
        if horizontal_header is not None:
            horizontal_header.setVisible(False)
        if vertical_header is not None:
            vertical_header.setVisible(False)

        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.setEditTriggers(
            QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        view.setShowGrid(True)
        # 选中项统一浅蓝，覆盖黄色分组底色
        view.setStyleSheet(
            "QTableView::item:selected { background-color: #ADD8E6; color: #000000; }"
        )

        widths = {
            SUBCOL_STAGE: 92, SUBCOL_SKIP: 26, SUBCOL_DECK: 84,
            SUBCOL_1P: 165, SUBCOL_2P: 165, SUBCOL_TWEAK: 110,
        }
        for col in range(self.model.columnCount()):
            view.setColumnWidth(col, widths[col % SUBCOLS])

        if vertical_header is not None:
            vertical_header.setDefaultSectionSize(24)
        view.setRowHeight(0, 30)
        view.setRowHeight(1, 24)

        self._delegate = PlanComboDelegate(self._plan_options, view)
        self._delegate.view = view
        for sub in (SUBCOL_DECK, SUBCOL_1P, SUBCOL_2P, SUBCOL_TWEAK):
            for col in range(sub, self.model.columnCount(), SUBCOLS):
                view.setItemDelegateForColumn(col, self._delegate)

        for ci, cat in enumerate(self.model.categories):
            if not cat.paginated:
                view.setSpan(0, ci * SUBCOLS, 1, SUBCOLS)

        self._page_buttons: dict[int, tuple[QToolButton, QToolButton]] = {}
        for ci, cat in enumerate(self.model.categories):
            if cat.paginated:
                self._create_page_nav(ci)

        self.model.dataChanged.connect(self._update_page_buttons)
        self.model.dataChanged.connect(self._on_data_changed)

    def _create_page_nav(self, category_index: int):
        start = category_index * SUBCOLS
        height = self.view.rowHeight(0)

        prev = QToolButton()
        prev.setText("◀")
        prev.setAutoRaise(True)
        prev.setFixedSize(self.view.columnWidth(start + SUBCOL_DECK), height)
        prev.clicked.connect(lambda: self._flip_page(category_index, -1))

        next_btn = QToolButton()
        next_btn.setText("▶")
        next_btn.setAutoRaise(True)
        next_btn.setFixedSize(self.view.columnWidth(start + SUBCOL_2P), height)
        next_btn.clicked.connect(lambda: self._flip_page(category_index, 1))

        self.view.setIndexWidget(self.model.index(0, start + SUBCOL_DECK), prev)
        self.view.setIndexWidget(self.model.index(0, start + SUBCOL_2P), next_btn)
        self._page_buttons[category_index] = (prev, next_btn)
        self._update_page_buttons()

    def _flip_page(self, category_index: int, delta: int):
        cat = self.model.categories[category_index]
        self.model.set_page(category_index, cat.page + delta)

    def _update_page_buttons(self):
        for ci, (prev, next_btn) in self._page_buttons.items():
            cat = self.model.categories[ci]
            prev.setEnabled(cat.page > 0)
            next_btn.setEnabled(cat.page < cat.page_count - 1)

    def _on_data_changed(self, top_left, bottom_right, roles):
        """checkbox 由视图直接改模型，这里负责把勾选同步到所有选中关卡。"""
        if self._syncing_check or not roles or Qt.ItemDataRole.CheckStateRole not in roles:
            return
        sub = top_left.column() % SUBCOLS
        if sub != SUBCOL_SKIP or top_left.row() < HEADER_ROWS:
            return
        selection_model = self.view.selectionModel()
        if selection_model is None:
            return
        value = self.model.data(top_left, Qt.ItemDataRole.CheckStateRole)
        self._syncing_check = True
        try:
            seen: set[tuple[int, int]] = set()
            for selected in selection_model.selectedIndexes():
                if not selected.isValid() or selected.row() < HEADER_ROWS:
                    continue
                key = (selected.row(), selected.column() // SUBCOLS)
                if key in seen:
                    continue
                seen.add(key)
                target = self.model.index(key[0], key[1] * SUBCOLS + sub)
                if target != top_left:
                    self.model.setData(target, value, Qt.ItemDataRole.CheckStateRole)
        finally:
            self._syncing_check = False

    # ---- 配置切换（UI 结构） ----
    def _on_config_changed(self, index: int):
        if index < 0:
            return
        # TODO: 下一步接入独立 JSON 配置后，切换时载入对应总表数据
        self.setWindowTitle(f"全局方案&战斗方案编辑 - {self._config_names[index]}")

    def _new_config(self):
        name, ok = QInputDialog.getText(self, "新建总表", "输入总表名称：")
        name = name.strip()
        if not ok or not name:
            return
        if name in self._config_names:
            QMessageBox.warning(self, "提示", "该名称已存在。")
            return
        self._config_names.append(name)
        self.config_combo.addItem(name)
        self.config_combo.setCurrentText(name)

    def _rename_config(self):
        current = self.config_combo.currentText()
        name, ok = QInputDialog.getText(self, "重命名总表", "输入新名称：", text=current)
        name = name.strip()
        if not ok or not name:
            return
        if name in self._config_names:
            QMessageBox.warning(self, "提示", "该名称已存在。")
            return
        index = self.config_combo.currentIndex()
        self._config_names[index] = name
        self.config_combo.setItemText(index, name)

    def _delete_config(self):
        if len(self._config_names) <= 1:
            QMessageBox.warning(self, "提示", "至少保留一个总表。")
            return
        index = self.config_combo.currentIndex()
        name = self.config_combo.itemText(index)
        ret = QMessageBox.question(
            self, "删除总表", f"确定删除总表「{name}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        self._config_names.pop(index)
        self.config_combo.removeItem(index)

    def showEvent(self, event):
        self.refresh_plan_lists()
        super().showEvent(event)
