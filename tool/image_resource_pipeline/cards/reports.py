"""输出卡片链路报告与卡片选择器的类别配置。"""

import json
from collections import defaultdict
from pathlib import Path
from ..common.files import write_csv

OBSOLETE_REPORTS = (
    "找到进化树但没有对应名称卡片一览.csv",
    "找到卡片名称但没有对应进化树一览.csv",
)

def build_card_stage_categories(
        matched_rows: list[dict[str, object]],
        image_dir: Path,
) -> dict[str, list[str]]:
    """
    根据本次链路解析结果构建金卡、融合卡的最小例外类别表。

    普通卡和未知卡不写入配置，运行时直接根据图片文件名发现，并默认
    使用普通转职批注。类别表仅保留图片名称无法表达的两类例外。
    """
    rows_by_card: dict[str, list[dict[str, object]]] = defaultdict(list)
    available_cards: set[str] = set()
    for row in matched_rows:
        base_name = str(row.get("基础卡片名称", "")).strip()
        target_filename = str(row.get("目标文件名", "")).strip()
        if base_name:
            rows_by_card[base_name].append(row)
        if base_name and target_filename and (image_dir / target_filename).is_file():
            available_cards.add(base_name)

    categories: dict[str, list[str]] = {"gold": [], "fusion": []}
    for base_name, rows in sorted(rows_by_card.items()):
        if base_name not in available_cards:
            continue

        chain_types = {str(row.get("链路类型", "")).strip() for row in rows}
        evolution_names = [
            str(row.get("进化树名称", "")).strip()
            for row in sorted(rows, key=lambda item: int(item.get("序号", 0) or 0))
            if str(row.get("进化树名称", "")).strip()
        ]
        if "融合卡" in chain_types:
            categories["fusion"].append(base_name)
        elif len(evolution_names) >= 3 and (
                evolution_names[0].endswith("神使")
                or any(name.endswith("圣神") for name in evolution_names[1:3])
                or any(name.startswith("至尊") for name in evolution_names[2:])
        ):
            categories["gold"].append(base_name)

    return categories


def write_card_stage_categories(
        category_output: Path,
        matched_rows: list[dict[str, object]],
        image_dir: Path,
) -> None:
    """以标准 JSON 格式原子更新卡片阶段类别表。"""
    categories = build_card_stage_categories(matched_rows, image_dir)
    category_output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = category_output.with_suffix(category_output.suffix + ".tmp")
    temporary_output.write_text(
        json.dumps(categories, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_output.replace(category_output)


def remove_obsolete_reports(report_dir: Path) -> None:
    for filename in OBSOLETE_REPORTS:
        path = report_dir / filename
        if path.is_file():
            path.unlink()


def write_reports(
    report_dir: Path,
    matched_rows: list[dict[str, object]],
    fusion_rows: list[dict[str, object]],
    single_rows: list[dict[str, object]],
    blocked_rows: list[dict[str, object]],
    blacklist_copy_rows: list[dict[str, object]],
    download_rows: list[dict[str, object]],
) -> None:
    remove_obsolete_reports(report_dir)
    sort_key = lambda row: (str(row.get("基础卡片名称", "")), int(row.get("序号", 0) or 0), str(row))
    matched_fieldnames = [
        "链路类型",
        "融合阶段",
        "融合来源二转卡片ID",
        "融合来源二转卡片名称",
        "基础卡片ID",
        "基础卡片名称",
        "序号",
        "进化树ID",
        "进化树名称",
        "素材卡片ID",
        "素材卡片名称",
        "融合词条",
        "Excel名称",
        "Excel行",
        "目标文件名",
        "候选URL",
    ]
    write_csv(
        report_dir / "正常找到进化树和卡片名称一览.csv",
        sorted(matched_rows, key=sort_key),
        matched_fieldnames,
    )
    write_csv(
        report_dir / "融合卡链路清单.csv",
        sorted(fusion_rows, key=sort_key),
        matched_fieldnames,
    )
    write_csv(
        report_dir / "单独卡清单.csv",
        sorted(single_rows, key=sort_key),
        matched_fieldnames,
    )
    write_csv(
        report_dir / "黑名单屏蔽卡片一览.csv",
        sorted(blocked_rows, key=lambda row: (str(row.get("Excel名称", "")), str(row.get("Excel ID", "")))),
        ["Excel ID", "Excel名称", "Excel行", "屏蔽原因", "候选URL"],
    )
    write_csv(
        report_dir / "卡片未实装黑名单拷贝.csv",
        sorted(blacklist_copy_rows, key=lambda row: str(row.get("名称", ""))),
        ["名称"],
    )
    write_csv(
        report_dir / "卡片准备房间资源下载清单.csv",
        sorted(
            download_rows,
            key=lambda row: (str(row.get("链路类型", "")), str(row.get("基础卡片名称", "")), int(row.get("序号", 0) or 0)),
        ),
        ["状态", "链路类型", "基础卡片名称", "序号", "进化树ID", "进化树名称", "Excel名称", "目标路径", "使用URL或错误"],
    )
