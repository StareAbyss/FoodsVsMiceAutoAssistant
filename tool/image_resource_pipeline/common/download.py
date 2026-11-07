"""共用 urllib/curl 下载与本地图片复制。"""

import shutil
import subprocess
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from .files import copy_local_source

USER_AGENT = "FoodsVsMousesAutoAssistant-image-resource-pipeline/1.0"

def is_remote_url(source: str) -> bool:
    return urlparse(source).scheme in {"http", "https"}

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
        check=False,
    )
    if completed.returncode != 0:
        if target.exists():
            target.unlink()
        output = (completed.stderr or completed.stdout or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(output or f"curl exit {completed.returncode}")
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


def fetch_sources(urls: tuple[str, ...], target: Path, timeout: int, force: bool, downloader: str,
                  empty_status: str = "无路径") -> tuple[str, str]:
    """按候选路径顺序获取一张图片，返回状态与使用的路径或最终错误。"""
    if target.exists() and not force:
        return "已存在", ""
    if not urls:
        return empty_status, ""
    last_error = ""
    for source in urls:
        try:
            if is_remote_url(source):
                download_remote_source(source, target, timeout, downloader)
            else:
                copy_local_source(source, target)
            return "已下载", source
        except Exception as exc:
            last_error = f"{source} -> {exc}"
    return "失败", last_error
