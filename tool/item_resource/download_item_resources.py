from __future__ import annotations

import argparse
import sys
import time
import shutil
import subprocess
import urllib.request
from pathlib import Path

from item_resource_common import (
    DEFAULT_OUTPUT_ROOT,
    copy_local_source,
    find_default_excel,
    is_remote_url,
    parse_target_items,
    sort_rows_by_type_name,
    write_csv,
)


USER_AGENT = "FoodsVsMousesAutoAssistant-resource-tool/1.0"


def download_url(url: str, target: Path, timeout: int) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    if not data:
        raise ValueError("empty response")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def download_url_with_curl(url: str, target: Path, timeout: int) -> None:
    curl_path = shutil.which("curl.exe") or shutil.which("curl")
    if not curl_path:
        raise FileNotFoundError("curl.exe not found")

    target.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [curl_path, "-L", "--fail", "--silent", "--show-error", "--max-time", str(timeout), "-o", str(target), url],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        if target.exists():
            target.unlink()
        raise RuntimeError((completed.stderr or completed.stdout or f"curl exit {completed.returncode}").strip())
    if not target.exists() or target.stat().st_size == 0:
        raise ValueError("curl wrote empty file")


def download_remote_source(url: str, target: Path, timeout: int, downloader: str) -> None:
    if downloader == "urllib":
        download_url(url, target, timeout)
        return
    if downloader == "curl":
        download_url_with_curl(url, target, timeout)
        return

    try:
        download_url(url, target, timeout)
    except Exception:
        download_url_with_curl(url, target, timeout)


def fetch_one(item, output_root: Path, timeout: int, force: bool, downloader: str) -> tuple[str, str]:
    target = output_root / item.item_type / item.filename
    if target.exists() and not force:
        return "已存在", ""

    if not item.urls:
        return "无路径", ""

    last_error = ""
    for source in item.urls:
        try:
            if is_remote_url(source):
                download_remote_source(source, target, timeout, downloader)
            else:
                copy_local_source(source, target)
            return "已下载", source
        except Exception as exc:
            last_error = f"{source} -> {exc}"
            continue
    return "失败", last_error


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="下载 Excel 中的战利品相关图片资源。")
    parser.add_argument("--excel", type=Path, default=None, help="资源 Excel，默认自动查找当前目录 xlsx")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ROOT, help="输出目录")
    parser.add_argument("--timeout", type=int, default=20, help="单个 URL 超时时间，秒")
    parser.add_argument("--sleep", type=float, default=0.05, help="每次请求后的暂停秒数")
    parser.add_argument("--force", action="store_true", help="覆盖已存在文件")
    parser.add_argument(
        "--downloader",
        choices=["auto", "urllib", "curl"],
        default="auto",
        help="远程下载器；auto 会在 urllib 失败后尝试 curl",
    )
    parser.add_argument("--dry-run", action="store_true", help="只生成清单，不下载")
    parser.add_argument("--manifest", type=Path, default=None, help="下载清单 CSV 路径")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    excel_path = args.excel or find_default_excel()
    output_root = args.output
    manifest_path = args.manifest or output_root / "下载清单.csv"

    items = parse_target_items(excel_path)
    rows = []
    status_count: dict[str, int] = {}

    for item in items:
        target = output_root / item.item_type / item.filename
        if args.dry_run:
            status, used_source = "计划下载", item.urls[0] if item.urls else ""
        else:
            status, used_source = fetch_one(item, output_root, args.timeout, args.force, args.downloader)
            time.sleep(args.sleep)

        status_count[status] = status_count.get(status, 0) + 1
        rows.append(
            {
                "状态": status,
                "id": item.item_id,
                "名称": item.name,
                "类型": item.item_type,
                "Excel行": item.source_row,
                "目标路径": str(target),
                "使用路径或错误": used_source,
                "候选路径": " | ".join(item.urls),
            }
        )

    rows = sort_rows_by_type_name(rows, type_key="类型", name_key="名称")
    write_csv(
        manifest_path,
        rows,
        ["状态", "id", "名称", "类型", "Excel行", "目标路径", "使用路径或错误", "候选路径"],
    )
    print(f"Excel: {excel_path}")
    print(f"目标条目: {len(items)}")
    print(f"输出目录: {output_root}")
    print(f"清单: {manifest_path}")
    print("状态统计:", status_count)
    return 1 if any(row["状态"] == "失败" for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
