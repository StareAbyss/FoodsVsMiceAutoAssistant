"""更新 resource/db 下的三种资源快照；消费者只读取此处的文件。"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..common.paths import PROJECT_ROOT, DB_DIR
from ..common.snapshot_files import SNAPSHOT_PATTERNS, SNAPSHOT_FILENAMES, latest_snapshot

EXCEL_EXPORT_MODULE = "tool.image_resource_pipeline.sources.xiaye"
XML_URLS = {
    "compose": "https://q.ms.huanlecdn.com/7k7k/cdn.123u.com/config/compose.xml",
    "CardFusion": "https://q.ms.huanlecdn.com/7k7k/cdn.123u.com/config/CardFusion.xml",
}


@dataclass(frozen=True)
class RefreshResult:
    files: dict[str, Path | None]
    errors: dict[str, str]


_PROCESS_REFRESH_LOCK = threading.Lock()
_PROCESS_REFRESH_RESULTS: dict[tuple[Path, str], tuple[Path | None, str | None]] = {}






def _validate_excel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        if "xl/worksheets/sheet1.xml" not in archive.namelist() or archive.testzip() is not None:
            raise ValueError("Excel 不是完整的图像资源工作簿")
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        if len(sheet.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row")) < 2:
            raise ValueError("图像资源 Excel 没有有效数据行")


def _validate_xml(data: bytes, kind: str) -> None:
    root = ET.fromstring(data)
    if kind == "compose" and root.find("./Compose/Rule") is None:
        raise ValueError("compose.xml 缺少合成规则")
    if kind == "CardFusion" and root.find(".//fusion_tab") is None:
        raise ValueError("CardFusion.xml 缺少融合规则")


def _install_snapshot(source: Path, kind: str, db_dir: Path, stamp: str) -> Path:
    """先发布已验证的新文件，再只删除同种类的旧快照。"""
    target = db_dir / SNAPSHOT_FILENAMES[kind].format(stamp=stamp)
    if source != target:
        source.replace(target)
    resolved_dir = db_dir.resolve()
    for old in db_dir.iterdir():
        if old == target or not old.is_file() or not SNAPSHOT_PATTERNS[kind].fullmatch(old.name):
            continue
        if old.resolve().parent != resolved_dir:
            continue
        old.unlink()
    return target




def _refresh_excel(db_dir: Path, stamp: str, timeout: int) -> Path:
    with tempfile.TemporaryDirectory(prefix="resource-excel-", dir=db_dir) as temporary:
        result = subprocess.run(
            [sys.executable, "-m", EXCEL_EXPORT_MODULE, "--output-dir", temporary],
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode:
            # 子进程或其依赖可能混用 UTF-8/GBK；先收原始字节，避免 Windows
            # subprocess._readerthread 按系统 GBK 解码时抛 UnicodeDecodeError。
            output = (result.stderr or result.stdout or b"").decode("utf-8", errors="replace")
            lines = output.strip().splitlines()
            raise RuntimeError(lines[-1] if lines else "Excel 导出失败")
        candidates = list(Path(temporary).glob("点我获取更多图像资源 *.xlsx"))
        if len(candidates) != 1:
            raise ValueError("Excel 导出未产生唯一的工作簿")
        _validate_excel(candidates[0])
        # Windows 上 TemporaryDirectory 的受限 ACL 会随 move 保留；在 db_dir
        # 创建发布临时文件再复制内容，确保普通 FAA 进程也能读取成品。
        with tempfile.NamedTemporaryFile(prefix="excel-", suffix=".tmp", dir=db_dir, delete=False) as file:
            published_temporary = Path(file.name)
            with candidates[0].open("rb") as source:
                shutil.copyfileobj(source, file)
        try:
            return _install_snapshot(published_temporary, "excel", db_dir, stamp)
        finally:
            published_temporary.unlink(missing_ok=True)


def _refresh_xml(kind: str, db_dir: Path, stamp: str, timeout: int) -> Path:
    request = urllib.request.Request(XML_URLS[kind], headers={"User-Agent": "FoodsVsMousesAutoAssistant-resource-db/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    _validate_xml(data, kind)
    with tempfile.NamedTemporaryFile(prefix=f"{kind}-", suffix=".tmp", dir=db_dir, delete=False) as file:
        temporary = Path(file.name)
        file.write(data)
    try:
        return _install_snapshot(temporary, kind, db_dir, stamp)
    finally:
        temporary.unlink(missing_ok=True)


def refresh_snapshots(
    *,
    db_dir: Path = DB_DIR,
    kinds: tuple[str, ...] = ("excel", "compose", "CardFusion"),
    excel_timeout: int = 20,
    xml_timeout: int = 8,
) -> RefreshResult:
    """按类型独立刷新。失败不删除旧快照，也不妨碍其他类型继续更新。"""
    db_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path | None] = {}
    errors: dict[str, str] = {}
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    for kind in kinds:
        try:
            files[kind] = _refresh_excel(db_dir, stamp, excel_timeout) if kind == "excel" else _refresh_xml(kind, db_dir, stamp, xml_timeout)
        except (OSError, ValueError, RuntimeError, TimeoutError, ET.ParseError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
            errors[kind] = str(exc)
            files[kind] = latest_snapshot(kind, db_dir)
    return RefreshResult(files, errors)


def ensure_snapshots(
    *,
    db_dir: Path = DB_DIR,
    kinds: tuple[str, ...] = ("excel", "compose", "CardFusion"),
    excel_timeout: int = 20,
    xml_timeout: int = 8,
) -> RefreshResult:
    """每个进程对每种资源最多尝试一次更新，失败也不重复联网。"""
    resolved_dir = db_dir.resolve()
    with _PROCESS_REFRESH_LOCK:
        missing = tuple(kind for kind in dict.fromkeys(kinds) if (resolved_dir, kind) not in _PROCESS_REFRESH_RESULTS)
        if missing:
            refreshed = refresh_snapshots(
                db_dir=db_dir,
                kinds=missing,
                excel_timeout=excel_timeout,
                xml_timeout=xml_timeout,
            )
            for kind in missing:
                _PROCESS_REFRESH_RESULTS[(resolved_dir, kind)] = (
                    refreshed.files.get(kind),
                    refreshed.errors.get(kind),
                )
        files = {kind: _PROCESS_REFRESH_RESULTS[(resolved_dir, kind)][0] for kind in kinds}
        errors = {
            kind: error for kind in kinds
            if (error := _PROCESS_REFRESH_RESULTS[(resolved_dir, kind)][1]) is not None
        }
        return RefreshResult(files, errors)
