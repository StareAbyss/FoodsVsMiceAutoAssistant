"""战利品范围筛选、ID 分类与人工精确例外。"""

from dataclasses import dataclass
from pathlib import Path
import re
from ..common.excel import read_xlsx_rows
from ..common.files import safe_filename

TYPE_RULES = [
    ("0x1232", "强化道具"),
    ("0x1234", "强化道具"),
    ("0x1241", "卡片合成道具"),
    ("0x1242", "卡片合成配方"),
    ("0x1250", "关卡门票"),
    ("0x1270", "宝石"),
    ("0x1480", "宝石"),
    ("0x13c0", "背包"),
    ("0x13c1", "背包"),
    ("0x122", "技能书-待分类"),
]

# 0x126 是包含大量非战利品的通用物品段，不能按整个前缀放行。
# 这里只收录已由维护者确认会从战利品界面掉落的精确例外。
MANUAL_ITEM_TYPES = {
    "龙渊之焰": "其他类型",
}

URL_COLUMNS = ("D", "E", "F", "G", "H")
RECIPE_SUFFIX = "配方"
SKILL_BOOK_RE = re.compile(r"-(初级|中级|高级|终极|究极)技能书$")
INVALID_URL_VALUES = {"", "-1", "None", "none", "NULL", "null"}

@dataclass(frozen=True)
class ItemResource:
    item_id: str
    name: str
    item_type: str
    urls: tuple[str, ...]
    source_row: int

    @property
    def filename(self) -> str:
        return f"{safe_filename(self.name)}.png"


def item_type_for_id(item_id: str) -> str | None:
    return next((item_type for prefix, item_type in TYPE_RULES if item_id.startswith(prefix)), None)


def skill_base_name(name: str) -> str:
    return SKILL_BOOK_RE.sub("", name)


def parse_target_items(excel_path: Path, include_manual_skill_books: bool = False) -> list[ItemResource]:
    """Parse target items with the same category rules as the curated loot resource tree."""
    rows = read_xlsx_rows(excel_path)
    raw_items: list[ItemResource] = []

    for row_number, row in enumerate(rows[1:], start=2):
        item_id = (row.get("A") or "").strip()
        name = (row.get("B") or "").strip()
        item_type = MANUAL_ITEM_TYPES.get(name) or item_type_for_id(item_id)
        if not item_type or not name:
            continue

        urls = tuple(
            value
            for value in ((row.get(column) or "").strip() for column in URL_COLUMNS)
            if value not in INVALID_URL_VALUES
        )
        raw_items.append(ItemResource(item_id=item_id, name=name, item_type=item_type, urls=urls, source_row=row_number))

    recipe_bases = {
        item.name[: -len(RECIPE_SUFFIX)]
        for item in raw_items
        if item.item_type == "卡片合成配方" and item.name.endswith(RECIPE_SUFFIX)
    }

    target_items: list[ItemResource] = []
    for item in raw_items:
        if item.item_type == "技能书-待分类":
            is_craftable_skill_book = skill_base_name(item.name) in recipe_bases
            if not is_craftable_skill_book and not include_manual_skill_books:
                continue
            item_type = "技能书-可合成卡片" if is_craftable_skill_book else "技能书-不可合成卡片"
            item = ItemResource(
                item_id=item.item_id,
                name=item.name,
                item_type=item_type,
                urls=item.urls,
                source_row=item.source_row,
            )
        target_items.append(item)
    return target_items


def classify_name_map(items: list[ItemResource]) -> dict[str, str]:
    return {item.name: item.item_type for item in items}
