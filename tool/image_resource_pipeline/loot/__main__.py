"""战利品图像资源自动流水线命令行入口。"""

import argparse
from pathlib import Path
from ..common.excel import find_default_excel
from ..common.snapshot_files import resolve_excel_path
from ..common.download import fetch_sources
from .paths import (DEFAULT_OUTPUT_ROOT, DEFAULT_LOOT_ROOT, DEFAULT_LOOT_BLACKLIST_CSV,
                    DEFAULT_LOOT_WHITELIST_CSV, DEFAULT_LOOT_UNKNOWN_CSV,
                    DEFAULT_FAILED_ROOT, DEFAULT_LOOT_MASK, DEFAULT_REPORT_ROOT)

def fetch_one(item, output_root: Path, timeout: int, force: bool, downloader: str) -> tuple[str, str]:
    """将物品图片获取到指定的分类目录。"""
    return fetch_sources(item.urls, output_root / item.item_type / item.filename, timeout, force, downloader)

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="获取战利品候选、匹配失败样本，并按人工黑白名单同步正式库。")
    parser.add_argument("--excel", type=Path, default=None, help="resource/db 内的资源 Excel，默认选择最新快照")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ROOT, help="输出目录")
    parser.add_argument("--loot-root", type=Path, default=DEFAULT_LOOT_ROOT, help="正式战利品目录")
    parser.add_argument("--whitelist", type=Path, default=DEFAULT_LOOT_WHITELIST_CSV, help="人工白名单")
    parser.add_argument("--blacklist", type=Path, default=DEFAULT_LOOT_BLACKLIST_CSV, help="人工黑名单")
    parser.add_argument("--unclassified", type=Path, default=DEFAULT_LOOT_UNKNOWN_CSV, help="自动生成的未分类名单")
    parser.add_argument("--failed-root", type=Path, default=DEFAULT_FAILED_ROOT, help="只读的失败样本目录")
    parser.add_argument("--loot-mask", type=Path, default=DEFAULT_LOOT_MASK)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--offline", action="store_true", help="不联网刷新或下载，仅使用本地快照与候选图片")
    parser.add_argument("--timeout", type=int, default=20, help="单个 URL 超时时间，秒")
    parser.add_argument("--sleep", type=float, default=0.05, help="每次请求后的暂停秒数")
    parser.add_argument("--force", action="store_true", help="覆盖已存在文件")
    parser.add_argument(
        "--downloader",
        choices=["auto", "urllib", "curl"],
        default="auto",
        help="远程下载器；auto 会在 urllib 失败后尝试 curl",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印分类预览，不下载、同步或清理图片")
    parser.add_argument("--manifest", type=Path, default=None, help="下载清单 CSV 路径")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    if args.excel is not None:
        resolve_excel_path(args.excel)
    from ..sources.snapshots import ensure_snapshots

    # 显式指定 db 快照时不刷新 Excel，避免发布新快照时删掉本次指定的输入。
    kinds = ("compose", "CardFusion") if args.excel is not None else ("excel", "compose", "CardFusion")
    if not args.offline and not args.dry_run:
        refreshed = ensure_snapshots(kinds=kinds)
        for kind, error in refreshed.errors.items():
            print(f"Warning: {kind} 更新失败，沿用已有快照: {error}")
    excel_path = args.excel or find_default_excel()
    from .workflow import run_pipeline

    return run_pipeline(args, excel_path, fetch_one)


if __name__ == "__main__":
    raise SystemExit(main())
