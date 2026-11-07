"""从资源表读取卡片名称，并应用未实装卡片名单。"""

import csv
from pathlib import Path
from ..common.excel import read_xlsx_rows, URL_COLUMNS as IMAGE_RESOURCE_COLUMNS, INVALID_URL_VALUES as EMPTY_RESOURCE_VALUES
from .models import ExcelCard

CARD_PREPARE_ROOM_URL_TEMPLATE = (
    "https://q.ms.huanlecdn.com/4399/cdn.123u.com/images/1/1/{item_id}.png"
)

def build_card_prepare_room_url(item_id: str) -> str:
    """
    根据卡片 ID 生成准备房间待选图片的固定 CDN 地址。

    图像资源 Excel 的 D-H 列可能漏填或混入卡片立绘地址；卡片待选图实际
    统一存放在 `/images/1/1/`，因此只使用 Excel 的 ID 与名称映射。

    Args:
        item_id: Excel A 列中的卡片 ID，例如 `0x1112059e`。

    Returns:
        对应卡片的 40×50 准备房间待选图片 URL。
    """
    return CARD_PREPARE_ROOM_URL_TEMPLATE.format(item_id=item_id)


def parse_excel_cards(excel_path: Path) -> dict[str, ExcelCard]:
    """
    从图像资源 Excel 读取卡片 ID 与名称映射。

    D-H 列只用于确认该条目确实提供了图像资源，不采用其中可能类型错误的 URL。
    卡片待选图 URL 始终由 ID 按固定规则生成。

    Args:
        excel_path: 图像资源 Excel 文件路径。

    Returns:
        以卡片 ID 为键的 Excel 卡片信息。
    """
    rows = read_xlsx_rows(excel_path)
    cards: dict[str, ExcelCard] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        item_id = (row.get("A") or "").strip()
        name = (row.get("B") or "").strip()
        if not item_id.startswith("0x11") or not name:
            continue

        has_image_resource = any(
            (row.get(column) or "").strip() not in EMPTY_RESOURCE_VALUES
            for column in IMAGE_RESOURCE_COLUMNS
        )
        if not has_image_resource:
            continue

        cards[item_id] = ExcelCard(
            item_id=item_id,
            name=name,
            urls=(build_card_prepare_room_url(item_id),),
            source_row=row_number,
        )
    return cards


def read_blacklist_names(path: Path) -> set[str]:
    """读取黑名单匹配项；兼容卡片名称和精确 ID，不展开同名卡片。"""
    if not path.is_file():
        return set()

    names: set[str] = set()
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames:
            name_field = "名称" if "名称" in reader.fieldnames else reader.fieldnames[0]
            for row in reader:
                name = (row.get(name_field) or "").strip()
                if name:
                    names.add(name)
            return names

    with path.open("r", encoding="utf-8-sig") as file:
        for line in file:
            name = line.strip().strip(",")
            if name:
                names.add(name)
    return names


def split_blacklisted_cards(
    excel_cards: dict[str, ExcelCard],
    blacklist_names: set[str],
) -> tuple[dict[str, ExcelCard], list[dict[str, object]]]:
    """按名称或精确 ID 屏蔽未实装、已废弃卡片，保留未命中的同名 ID。"""
    active_cards: dict[str, ExcelCard] = {}
    blocked_rows: list[dict[str, object]] = []
    for card in excel_cards.values():
        # 旧版独立极寒冰沙与冰激凌二转同名，必须按旧 ID 屏蔽，不能误伤二转卡面。
        if card.name in blacklist_names or card.item_id in blacklist_names:
            blocked_rows.append(
                {
                    "Excel ID": card.item_id,
                    "Excel名称": card.name,
                    "Excel行": card.source_row,
                    "屏蔽原因": "卡片未实装黑名单",
                    "候选URL": " | ".join(card.urls),
                }
            )
            continue
        active_cards[card.item_id] = card
    return active_cards, blocked_rows
