"""准备房间卡片图像自动流水线命令行入口。"""

import argparse
from pathlib import Path
from .paths import DEFAULT_OUTPUT_DIR, DEFAULT_REPORT_DIR, DEFAULT_CATEGORY_OUTPUT, DEFAULT_BLACKLIST_PATH
from .workflow import run_pipeline

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="根据图像资源 Excel 和 compose.xml 生成准备房间卡片识别资源。")
    parser.add_argument("--excel", type=Path, default=None, help="指定 resource/db 内的图像资源 Excel")
    parser.add_argument("--compose", default=None, help="指定本地 compose.xml；默认刷新并读取 resource/db 快照")
    parser.add_argument("--card-fusion", default=None, help="指定本地 CardFusion.xml；默认刷新并读取 resource/db 快照")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR, help="准备房间卡片图片输出目录")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR, help="CSV 报告输出目录")
    parser.add_argument(
        "--category-output",
        type=Path,
        default=DEFAULT_CATEGORY_OUTPUT,
        help="卡片选择器使用的标准 JSON 金卡/融合卡类别表",
    )
    parser.add_argument("--blacklist", type=Path, default=DEFAULT_BLACKLIST_PATH, help="未实装卡片黑名单 CSV")
    parser.add_argument("--timeout", type=int, default=20, help="单个网络请求超时秒数")
    parser.add_argument("--excel-update-timeout", type=int, default=300, help="获取最新 Excel 的超时秒数")
    parser.add_argument("--skip-excel-update", action="store_true", help="不调用图像资源 Excel 导出工具，只使用本地最近 Excel")
    parser.add_argument("--sleep", type=float, default=0.03, help="每张图片下载后的暂停秒数")
    parser.add_argument("--force", action="store_true", help="覆盖已存在图片")
    parser.add_argument("--dry-run", action="store_true", help="只生成 CSV，不下载图片")
    parser.add_argument(
        "--downloader",
        choices=["auto", "urllib", "curl"],
        default="auto",
        help="远程下载器；auto 会在 urllib 失败后尝试 curl",
    )
    return parser

def main() -> int:
    """解析命令行参数并执行卡片资源流水线。"""
    return run_pipeline(build_arg_parser().parse_args())

if __name__ == "__main__":
    raise SystemExit(main())
