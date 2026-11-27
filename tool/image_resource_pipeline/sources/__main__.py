"""统一刷新原始数据快照的公开入口。"""

import argparse
from .snapshots import ensure_snapshots

def main() -> int:
    """按所选类型刷新快照，失败时清楚报告是否沿用旧数据。"""
    parser = argparse.ArgumentParser(description="更新 resource/db 下的图像资源原始数据")
    parser.add_argument("--excel-only", action="store_true", help="只刷新图像资源 Excel")
    args = parser.parse_args()
    result = ensure_snapshots(kinds=("excel",) if args.excel_only else ("excel", "compose", "CardFusion"))
    for kind, path in result.files.items():
        state = "沿用旧快照" if kind in result.errors and path else ("不可用" if path is None else "已更新")
        print(f"{kind}: {state} {path or ''}")
        if kind in result.errors:
            print(f"  原因: {result.errors[kind]}")
    return 0 if all(result.files.values()) else 1

if __name__ == "__main__":
    raise SystemExit(main())
