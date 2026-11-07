"""两套图片流程共用的资源 Excel 读取与快照选择。"""

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from .paths import PROJECT_ROOT
from .snapshot_files import latest_snapshot

URL_COLUMNS = ("D", "E", "F", "G", "H")
INVALID_URL_VALUES = {"", "-1", "None", "none", "NULL", "null"}

def find_default_excel(root: Path = PROJECT_ROOT) -> Path:
    """只读取项目 resource/db 中日期最新的合法 Excel 快照。"""
    excel = latest_snapshot("excel", root / "resource" / "db")
    if excel is None:
        raise FileNotFoundError("resource/db 缺少图像资源 Excel，请先运行资源快照获取工具")
    return excel


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

def find_latest_existing_excel(root: Path) -> Path | None:
    """只选择指定项目 resource/db 内日期最新的合法快照。"""
    return latest_snapshot("excel", root / "resource" / "db")
