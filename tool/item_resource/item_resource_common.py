from __future__ import annotations

import csv
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


EXCEL_NAME_PATTERN = "*.xlsx"
DEFAULT_OUTPUT_ROOT = Path("resource_other") / "图像资源_战利品_最新资源"
DEFAULT_LOOT_ROOT = Path("resource") / "image" / "item" / "战利品"
DEFAULT_COMPARE_SAME_CSV = DEFAULT_OUTPUT_ROOT / "现有与最新图像资源相同部分一览.csv"
DEFAULT_COMPARE_MISSING_CSV = DEFAULT_OUTPUT_ROOT / "现有与最新图像资源缺失图片一览.csv"
DEFAULT_COMPARE_EXTRA_CSV = DEFAULT_OUTPUT_ROOT / "现有与最新图像资源多出图片一览.csv"
DEFAULT_CLASSIFY_CSV = DEFAULT_OUTPUT_ROOT / "战利品分类迁移计划.csv"

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


def find_default_excel(root: Path = Path(".")) -> Path:
    """Find the resource xlsx while ignoring Excel lock files."""
    candidates = sorted(p for p in root.glob(EXCEL_NAME_PATTERN) if not p.name.startswith("~$"))
    if not candidates:
        raise FileNotFoundError("未找到 xlsx 文件")
    if len(candidates) == 1:
        return candidates[0]
    exact = [p for p in candidates if "图像资源" in p.name]
    return exact[0] if exact else candidates[0]


def safe_filename(name: str) -> str:
    """Keep the Excel display name, only replacing characters illegal on Windows."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(".")


def cell_column(cell_ref: str) -> str:
    return "".join(ch for ch in cell_ref if ch.isalpha())


def cell_value(cell: ET.Element, namespace: dict[str, str], shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//a:t", namespace))

    value_node = cell.find("a:v", namespace)
    if value_node is None:
        return ""

    raw_value = value_node.text or ""
    if cell_type == "s" and raw_value:
        return shared_strings[int(raw_value)]
    return raw_value


def read_xlsx_rows(excel_path: Path) -> list[dict[str, str]]:
    """Read the first worksheet of a simple xlsx file without third-party dependencies."""
    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(excel_path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", namespace):
                shared_strings.append("".join(node.text or "" for node in item.findall(".//a:t", namespace)))

        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows: list[dict[str, str]] = []
        for row in sheet.findall(".//a:sheetData/a:row", namespace):
            values: dict[str, str] = {}
            for cell in row.findall("a:c", namespace):
                values[cell_column(cell.attrib.get("r", ""))] = cell_value(cell, namespace, shared_strings)
            rows.append(values)
        return rows


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
        item_type = item_type_for_id(item_id)
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


def collect_pngs(root: Path) -> dict[str, Path]:
    """Collect png files recursively, keyed by filename stem."""
    files: dict[str, Path] = {}
    if not root.exists():
        return files
    for path in sorted(root.rglob("*.png")):
        files[path.stem] = path
    return files


def category_for_path(root: Path, path: Path) -> str:
    parent = path.parent
    if parent == root:
        return ""
    return str(parent.relative_to(root))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sort_rows_by_type_name(rows: list[dict[str, object]], type_key: str = "类型", name_key: str = "名称"):
    """Sort CSV rows by type first, then name."""
    return sorted(rows, key=lambda row: (str(row.get(type_key, "")), str(row.get(name_key, ""))))


def classify_name_map(items: list[ItemResource]) -> dict[str, str]:
    return {item.name: item.item_type for item in items}


def is_remote_url(source: str) -> bool:
    return urlparse(source).scheme in {"http", "https"}


def copy_local_source(source: str, target: Path) -> None:
    src = Path(source)
    if not src.exists():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
