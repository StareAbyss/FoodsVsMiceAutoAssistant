from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .paths import DEFAULT_CLASSIFY_CSV, DEFAULT_LOOT_ROOT
from .classification import classify_name_map, parse_target_items
from ..common.files import collect_pngs, sort_rows_by_type_name, write_csv
from ..common.excel import find_default_excel
from ..common.snapshot_files import resolve_excel_path


OTHER_CATEGORY = "其他类型"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="一次性把现有战利品识别资源按 Excel 分类整理到子目录。")
    parser.add_argument("--excel", type=Path, default=None, help="resource/db 内的资源 Excel，默认选择最新快照")
    parser.add_argument("--loot-root", type=Path, default=DEFAULT_LOOT_ROOT, help="现有战利品资源目录")
    parser.add_argument("--plan", type=Path, default=DEFAULT_CLASSIFY_CSV, help="迁移计划 CSV")
    parser.add_argument("--apply", action="store_true", help="执行移动；默认只生成计划")
    return parser


def target_path_for(loot_root: Path, name_to_category: dict[str, str], source: Path) -> Path:
    category = name_to_category.get(source.stem, OTHER_CATEGORY)
    return loot_root / category / source.name


def main() -> int:
    args = build_arg_parser().parse_args()
    if args.excel is not None:
        resolve_excel_path(args.excel)
    from ..sources.snapshots import ensure_snapshots

    # 显式指定 db 快照时不刷新 Excel，避免发布新快照时删掉本次指定的输入。
    kinds = ("compose", "CardFusion") if args.excel is not None else ("excel", "compose", "CardFusion")
    refreshed = ensure_snapshots(kinds=kinds)
    for kind, error in refreshed.errors.items():
        print(f"Warning: {kind} 更新失败，沿用已有快照: {error}")
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
