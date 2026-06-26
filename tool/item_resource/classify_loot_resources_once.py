from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from item_resource_common import (
    DEFAULT_CLASSIFY_CSV,
    DEFAULT_LOOT_ROOT,
    classify_name_map,
    collect_pngs,
    find_default_excel,
    parse_target_items,
    sort_rows_by_type_name,
    write_csv,
)


OTHER_CATEGORY = "其他类型"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="一次性把现有战利品识别资源按 Excel 分类整理到子目录。")
    parser.add_argument("--excel", type=Path, default=None, help="资源 Excel，默认自动查找当前目录 xlsx")
    parser.add_argument("--loot-root", type=Path, default=DEFAULT_LOOT_ROOT, help="现有战利品资源目录")
    parser.add_argument("--plan", type=Path, default=DEFAULT_CLASSIFY_CSV, help="迁移计划 CSV")
    parser.add_argument("--apply", action="store_true", help="执行移动；默认只生成计划")
    return parser


def target_path_for(loot_root: Path, name_to_category: dict[str, str], source: Path) -> Path:
    category = name_to_category.get(source.stem, OTHER_CATEGORY)
    return loot_root / category / source.name


def main() -> int:
    args = build_arg_parser().parse_args()
    excel_path = args.excel or find_default_excel()
    items = parse_target_items(excel_path, include_manual_skill_books=True)
    name_to_category = classify_name_map(items)
    files = collect_pngs(args.loot_root)

    rows = []
    for name, source in sorted(files.items()):
        target = target_path_for(args.loot_root, name_to_category, source)
        status = "无需移动" if source == target else ("已移动" if args.apply else "计划移动")
        rows.append(
            {
                "状态": status,
                "名称": name,
                "分类": name_to_category.get(name, OTHER_CATEGORY),
                "原路径": str(source),
                "目标路径": str(target),
            }
        )

        if args.apply and source != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise FileExistsError(f"目标已存在，停止避免覆盖: {target}")
            shutil.move(str(source), str(target))

    rows = sort_rows_by_type_name(rows, type_key="分类", name_key="名称")
    write_csv(args.plan, rows, ["状态", "名称", "分类", "原路径", "目标路径"])
    print(f"Excel: {excel_path}")
    print(f"现有战利品资源: {len(files)}")
    print(f"迁移计划: {args.plan}")
    print("模式:", "执行移动" if args.apply else "仅 dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
