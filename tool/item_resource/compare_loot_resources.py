from __future__ import annotations

import argparse
import sys
from pathlib import Path

from item_resource_common import (
    DEFAULT_COMPARE_EXTRA_CSV,
    DEFAULT_COMPARE_MISSING_CSV,
    DEFAULT_COMPARE_SAME_CSV,
    DEFAULT_LOOT_ROOT,
    DEFAULT_OUTPUT_ROOT,
    category_for_path,
    collect_pngs,
    sort_rows_by_type_name,
    write_csv,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="对比最新分类资源和现有战利品识别资源。")
    parser.add_argument("--latest-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="最新资源根目录")
    parser.add_argument("--loot-root", type=Path, default=DEFAULT_LOOT_ROOT, help="现有战利品资源根目录")
    parser.add_argument("--same-output", type=Path, default=DEFAULT_COMPARE_SAME_CSV, help="相同部分 CSV")
    parser.add_argument("--missing-output", type=Path, default=DEFAULT_COMPARE_MISSING_CSV, help="缺失图片 CSV")
    parser.add_argument("--extra-output", type=Path, default=DEFAULT_COMPARE_EXTRA_CSV, help="多出图片 CSV")
    return parser


def build_same_rows(latest_root: Path, loot_root: Path, latest_files: dict[str, Path], loot_files: dict[str, Path]):
    rows = []
    for name in sorted(set(latest_files) & set(loot_files)):
        latest_path = latest_files[name]
        loot_path = loot_files[name]
        rows.append(
            {
                "类型": category_for_path(latest_root, latest_path),
                "名称": name,
                "最新资源路径": str(latest_path),
                "现有资源路径": str(loot_path),
                "现有分类": category_for_path(loot_root, loot_path),
            }
        )
    return sort_rows_by_type_name(rows)


def build_missing_rows(latest_root: Path, latest_files: dict[str, Path], loot_files: dict[str, Path]):
    rows = []
    for name in sorted(set(latest_files) - set(loot_files)):
        latest_path = latest_files[name]
        rows.append(
            {
                "类型": category_for_path(latest_root, latest_path),
                "名称": name,
                "最新资源路径": str(latest_path),
            }
        )
    return sort_rows_by_type_name(rows)


def build_extra_rows(loot_root: Path, latest_files: dict[str, Path], loot_files: dict[str, Path]):
    rows = []
    for name in sorted(set(loot_files) - set(latest_files)):
        loot_path = loot_files[name]
        rows.append(
            {
                "类型": category_for_path(loot_root, loot_path),
                "名称": name,
                "现有资源路径": str(loot_path),
            }
        )
    return sort_rows_by_type_name(rows)


def main() -> int:
    args = build_arg_parser().parse_args()
    latest_files = collect_pngs(args.latest_root)
    loot_files = collect_pngs(args.loot_root)

    same_rows = build_same_rows(args.latest_root, args.loot_root, latest_files, loot_files)
    missing_rows = build_missing_rows(args.latest_root, latest_files, loot_files)
    extra_rows = build_extra_rows(args.loot_root, latest_files, loot_files)

    write_csv(args.same_output, same_rows, ["类型", "名称", "最新资源路径", "现有资源路径", "现有分类"])
    write_csv(args.missing_output, missing_rows, ["类型", "名称", "最新资源路径"])
    write_csv(args.extra_output, extra_rows, ["类型", "名称", "现有资源路径"])

    print(f"最新资源: {len(latest_files)}")
    print(f"现有资源: {len(loot_files)}")
    print(f"相同: {len(same_rows)}")
    print(f"缺失: {len(missing_rows)}")
    print(f"多出: {len(extra_rows)}")
    print(f"相同 CSV: {args.same_output}")
    print(f"缺失 CSV: {args.missing_output}")
    print(f"多出 CSV: {args.extra_output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
