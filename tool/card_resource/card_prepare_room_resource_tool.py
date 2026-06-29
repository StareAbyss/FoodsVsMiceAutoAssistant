from __future__ import annotations

import argparse
import csv
import locale
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_COMPOSE_URL = "https://q.ms.huanlecdn.com/4399/cdn.123u.com/config/compose.xml"
DEFAULT_CARD_FUSION_URL = "https://q.ms.huanlecdn.com/4399/cdn.123u.com/config/CardFusion.xml"
DEFAULT_OUTPUT_DIR = Path("resource") / "image" / "card" / "准备房间"
DEFAULT_REPORT_DIR = Path("resource_other") / "图像资源_卡片准备房间_最新资源"
DEFAULT_BLACKLIST_PATH = Path(__file__).with_name("card_prepare_room_card_blacklist.csv")
EXCEL_FILE_PATTERN = "点我获取更多图像资源 *.xlsx"
EXCEL_GENERATOR_SCRIPT = "card_image_url_get.py"
URL_COLUMNS = ("D", "E", "F", "G", "H")
INVALID_URL_VALUES = {"", "-1", "None", "none", "NULL", "null"}
USER_AGENT = "FoodsVsMousesAutoAssistant-card-resource-tool/1.0"
SUBPROCESS_TEXT_ENCODING = locale.getpreferredencoding(False) or "utf-8"
OBSOLETE_REPORTS = (
    "找到进化树但没有对应名称卡片一览.csv",
    "找到卡片名称但没有对应进化树一览.csv",
)


@dataclass(frozen=True)
class ExcelCard:
    item_id: str
    name: str
    urls: tuple[str, ...]
    source_row: int


@dataclass(frozen=True)
class EvolutionNode:
    item_id: str
    xml_name: str
    probability: str


@dataclass(frozen=True)
class FusionStep:
    stage_index: int
    stage_name: str
    main_id: str
    cost_id: str
    obtain_id: str
    obtain_name: str
    upgrade: str


@dataclass(frozen=True)
class FusionChain:
    main_id: str
    steps: tuple[FusionStep, ...]


@dataclass(frozen=True)
class PlannedCardImage:
    base_id: str
    base_name: str
    node: EvolutionNode
    index: int
    excel_card: ExcelCard
    chain_type: str

    @property
    def filename(self) -> str:
        return f"{safe_filename(self.base_name)}-{self.index}.png"


def safe_filename(name: str) -> str:
    return "".join("_" if ch in '<>:"/\\|?*' or ord(ch) < 32 else ch for ch in name).strip().rstrip(".")


def is_remote_url(source: str) -> bool:
    return urlparse(source).scheme in {"http", "https"}


def find_project_root(start: Path) -> Path:
    for path in [start.resolve(), *start.resolve().parents]:
        if (path / EXCEL_GENERATOR_SCRIPT).is_file() and (path / "pyproject.toml").is_file():
            return path
    return start.resolve()


def find_latest_existing_excel(root: Path) -> Path | None:
    candidates = sorted(
        (path for path in root.glob(EXCEL_FILE_PATTERN) if not path.name.startswith("~$")),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def find_default_excel(root: Path) -> Path:
    latest_resource_excel = find_latest_existing_excel(root)
    if latest_resource_excel:
        return latest_resource_excel

    candidates = sorted(
        (path for path in root.glob("*.xlsx") if not path.name.startswith("~$")),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("未找到图像资源 Excel 文件")
    exact = [path for path in candidates if "图像资源" in path.name]
    return exact[0] if exact else candidates[0]


def get_latest_excel_file(project_root: Path, timeout: int) -> Path:
    excel_script = project_root / EXCEL_GENERATOR_SCRIPT
    if not excel_script.is_file():
        print(f"Warning: Excel generator not found: {excel_script}")
        return find_default_excel(project_root)

    print("正在获取最新的图像资源 Excel...")
    try:
        result = subprocess.run(
            [sys.executable, str(excel_script)],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding=SUBPROCESS_TEXT_ENCODING,
            errors="replace",
            timeout=timeout,
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("警告:", result.stderr)
        if result.returncode != 0:
            print(f"Warning: 图像资源脚本执行失败，返回码: {result.returncode}")
            print("Warning: 开发者请先执行 `uv sync --group dev` 安装资源生成依赖。")
            return find_default_excel(project_root)
    except subprocess.TimeoutExpired:
        print("Warning: 图像资源脚本执行超时，将使用已有的最近文件")
        return find_default_excel(project_root)
    except Exception as exc:
        print(f"Warning: 获取图像资源文件时出错: {exc}")
        return find_default_excel(project_root)

    expected_file = project_root / f"点我获取更多图像资源 {datetime.now().strftime('%Y-%m-%d')}.xlsx"
    if expected_file.exists():
        return expected_file

    print(f"Warning: 未找到今天生成的文件: {expected_file.name}")
    return find_default_excel(project_root)


def cell_column(cell_ref: str) -> str:
    return "".join(ch for ch in cell_ref if ch.isalpha())


def cell_value(cell: ET.Element, namespace: dict[str, str], shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//a:t", namespace))

    value_node = cell.find("a:v", namespace)
    if value_node is None:
        return ""

    raw_value = value_node.text or ""
    if cell_type == "s" and raw_value:
        return shared_strings[int(raw_value)]
    return raw_value


def read_xlsx_rows(excel_path: Path) -> list[dict[str, str]]:
    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(excel_path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", namespace):
                shared_strings.append("".join(node.text or "" for node in item.findall(".//a:t", namespace)))

        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows: list[dict[str, str]] = []
        for row in sheet.findall(".//a:sheetData/a:row", namespace):
            values: dict[str, str] = {}
            for cell in row.findall("a:c", namespace):
                values[cell_column(cell.attrib.get("r", ""))] = cell_value(cell, namespace, shared_strings)
            rows.append(values)
        return rows


def parse_excel_cards(excel_path: Path) -> dict[str, ExcelCard]:
    rows = read_xlsx_rows(excel_path)
    cards: dict[str, ExcelCard] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        item_id = (row.get("A") or "").strip()
        name = (row.get("B") or "").strip()
        if not item_id.startswith("0x11") or not name:
            continue

        urls = tuple(
            value
            for value in ((row.get(column) or "").strip() for column in URL_COLUMNS)
            if value not in INVALID_URL_VALUES
        )
        if not urls:
            continue
        cards[item_id] = ExcelCard(item_id=item_id, name=name, urls=urls, source_row=row_number)
    return cards


def read_blacklist_names(path: Path) -> set[str]:
    if not path.is_file():
        return set()

    names: set[str] = set()
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames:
            name_field = "名称" if "名称" in reader.fieldnames else reader.fieldnames[0]
            for row in reader:
                name = (row.get(name_field) or "").strip()
                if name:
                    names.add(name)
            return names

    with path.open("r", encoding="utf-8-sig") as file:
        for line in file:
            name = line.strip().strip(",")
            if name:
                names.add(name)
    return names


def split_blacklisted_cards(
    excel_cards: dict[str, ExcelCard],
    blacklist_names: set[str],
) -> tuple[dict[str, ExcelCard], list[dict[str, object]]]:
    active_cards: dict[str, ExcelCard] = {}
    blocked_rows: list[dict[str, object]] = []
    for card in excel_cards.values():
        if card.name in blacklist_names:
            blocked_rows.append(
                {
                    "Excel ID": card.item_id,
                    "Excel名称": card.name,
                    "Excel行": card.source_row,
                    "屏蔽原因": "卡片未实装黑名单",
                    "候选URL": " | ".join(card.urls),
                }
            )
            continue
        active_cards[card.item_id] = card
    return active_cards, blocked_rows


def read_compose_xml(source: str | Path, timeout: int) -> bytes:
    source_text = str(source)
    if is_remote_url(source_text):
        request = urllib.request.Request(source_text, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    return Path(source).read_bytes()


def parse_evolution_chains(compose_bytes: bytes) -> list[list[EvolutionNode]]:
    root = ET.fromstring(compose_bytes)
    children: dict[str, list[EvolutionNode]] = defaultdict(list)
    parent_ids: set[str] = set()
    raw_names: dict[str, str] = {}

    for translate in root.findall(".//Translate"):
        raw_item = translate.find(".//raw_item")
        if raw_item is None:
            continue

        raw_id = (raw_item.get("id") or "").replace(" ", "")
        target_id = (translate.get("id") or "").replace(" ", "")
        raw_name = (raw_item.get("desc") or "").strip()
        target_name = (translate.get("desc") or "").strip()
        probability = (translate.get("probability") or "").strip()
        if not raw_id or not target_id:
            continue

        raw_names.setdefault(raw_id, raw_name)
        children[raw_id].append(EvolutionNode(target_id, target_name, probability))
        parent_ids.add(target_id)

    roots = sorted(item_id for item_id in children if item_id not in parent_ids)
    chains: list[list[EvolutionNode]] = []

    def walk(node: EvolutionNode, path: list[EvolutionNode], seen: set[str]) -> None:
        next_nodes = children.get(node.item_id, [])
        if not next_nodes:
            chains.append(path)
            return
        for next_node in sorted(next_nodes, key=lambda item: item.item_id):
            if next_node.item_id in seen:
                continue
            walk(next_node, path + [next_node], seen | {next_node.item_id})

    for root_id in roots:
        root_node = EvolutionNode(root_id, raw_names.get(root_id, ""), "root")
        walk(root_node, [root_node], {root_id})

    # compose.xml 中存在少量重复边；按 ID 链路去重，避免重复下载/报告。
    unique: dict[tuple[str, ...], list[EvolutionNode]] = {}
    for chain in chains:
        unique.setdefault(tuple(node.item_id for node in chain), chain)
    return list(unique.values())


def parse_fusion_tab(tab: ET.Element, stage_index: int) -> list[FusionStep]:
    stage_name = tab.get("name") or f"融合{stage_index}"
    steps: list[FusionStep] = []
    for element in tab.findall(".//element"):
        cost_item = element.find(".//cost/item")
        obtain = element.find(".//obtain")
        if cost_item is None or obtain is None:
            continue

        main_id = (element.get("main_id") or "").replace(" ", "")
        cost_id = (cost_item.get("item_id") or "").replace(" ", "")
        obtain_id = (obtain.get("id") or "").replace(" ", "")
        obtain_name = (obtain.get("name") or "").strip()
        upgrade = (obtain.get("desc") or "").strip()
        if not main_id or not cost_id or not obtain_id:
            continue

        steps.append(
            FusionStep(
                stage_index=stage_index,
                stage_name=stage_name,
                main_id=main_id,
                cost_id=cost_id,
                obtain_id=obtain_id,
                obtain_name=obtain_name,
                upgrade=upgrade,
            )
        )
    return steps


def parse_fusion_chains(card_fusion_bytes: bytes) -> list[FusionChain]:
    root = ET.fromstring(card_fusion_bytes)
    tabs = {tab.get("type"): tab for tab in root.findall(".//fusion_tab")}
    low_tab = tabs.get("13")
    medium_tab = tabs.get("14")
    high_tab = tabs.get("15")
    if low_tab is None or medium_tab is None or high_tab is None:
        return []

    low_steps = parse_fusion_tab(low_tab, 1)
    medium_steps_by_main = {step.main_id: step for step in parse_fusion_tab(medium_tab, 2)}
    high_steps_by_main = {step.main_id: step for step in parse_fusion_tab(high_tab, 3)}

    chains: list[FusionChain] = []
    for low_step in low_steps:
        medium_step = medium_steps_by_main.get(low_step.obtain_id)
        if medium_step is None:
            continue
        high_step = high_steps_by_main.get(medium_step.obtain_id)
        if high_step is None:
            continue
        chains.append(FusionChain(main_id=low_step.main_id, steps=(low_step, medium_step, high_step)))
    return chains


def extract_gold_card_title(name: str) -> str:
    """从金卡高转职名称中提取识别资源使用的称号名。"""
    if "·" in name:
        return name.split("·", 1)[0].strip()

    if name.startswith("至尊"):
        return name.removeprefix("至尊").strip()

    return ""


def is_gold_card_chain(chain: list[EvolutionNode], base_name: str) -> bool:
    """金卡通常是神使起步、圣神过渡，并在高转职中出现称号名。"""
    names = [node.xml_name for node in chain]
    return (
        len(chain) >= 3
        and (
            base_name.endswith("神使")
            or any(name.endswith("圣神") for name in names[1:3])
            or any(name.startswith("至尊") for name in names[2:])
        )
    )


def base_name_for_chain(chain: list[EvolutionNode], excel_cards: dict[str, ExcelCard]) -> str:
    base = chain[0]
    base_card = excel_cards.get(base.item_id)
    base_name = base_card.name if base_card else base.xml_name
    if not is_gold_card_chain(chain, base_name):
        return base_name

    for node in chain[2:]:
        title = extract_gold_card_title(node.xml_name)
        if title:
            return title
    return base_name


def build_plan(
    chains: list[list[EvolutionNode]],
    fusion_chains: list[FusionChain],
    excel_cards: dict[str, ExcelCard],
) -> tuple[list[PlannedCardImage], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    planned: list[PlannedCardImage] = []
    matched_rows: list[dict[str, object]] = []
    fusion_rows: list[dict[str, object]] = []
    single_rows: list[dict[str, object]] = []
    tree_ids: set[str] = set()

    for chain in chains:
        base = chain[0]
        base_name = base_name_for_chain(chain, excel_cards)

        for index, node in enumerate(chain):
            tree_ids.add(node.item_id)
            excel_card = excel_cards.get(node.item_id)
            if excel_card is None:
                continue

            planned_card = PlannedCardImage(
                base_id=base.item_id,
                base_name=base_name,
                node=node,
                index=index,
                excel_card=excel_card,
                chain_type="普通进化",
            )
            planned.append(planned_card)
            matched_rows.append(
                {
                    "链路类型": planned_card.chain_type,
                    "融合阶段": "",
                    "融合来源二转卡片ID": "",
                    "融合来源二转卡片名称": "",
                    "基础卡片ID": base.item_id,
                    "基础卡片名称": base_name,
                    "序号": index,
                    "进化树ID": node.item_id,
                    "进化树名称": node.xml_name,
                    "素材卡片ID": "",
                    "素材卡片名称": "",
                    "融合词条": "",
                    "Excel名称": excel_card.name,
                    "Excel行": excel_card.source_row,
                    "目标文件名": planned_card.filename,
                    "候选URL": " | ".join(excel_card.urls),
                }
            )

    fusion_ids: set[str] = set()
    for fusion_chain in fusion_chains:
        source_card = excel_cards.get(fusion_chain.main_id)
        if source_card is None:
            continue

        fusion_cards = [excel_cards.get(step.obtain_id) for step in fusion_chain.steps]
        if any(card is None for card in fusion_cards):
            continue

        chain_cards = [card for card in fusion_cards if card is not None]
        chain_steps = list(fusion_chain.steps)
        base_card = chain_cards[0]
        fusion_ids.update(card.item_id for card in chain_cards)
        for index, (card, step) in enumerate(zip(chain_cards, chain_steps)):
            node = EvolutionNode(card.item_id, card.name, "fusion")
            planned_card = PlannedCardImage(
                base_id=base_card.item_id,
                base_name=base_card.name,
                node=node,
                index=index,
                excel_card=card,
                chain_type="融合卡",
            )
            planned.append(planned_card)
            cost_card = excel_cards.get(step.cost_id) if step is not None else None
            row = {
                "链路类型": planned_card.chain_type,
                "融合阶段": step.stage_name,
                "融合来源二转卡片ID": source_card.item_id,
                "融合来源二转卡片名称": source_card.name,
                "基础卡片ID": base_card.item_id,
                "基础卡片名称": base_card.name,
                "序号": index,
                "进化树ID": card.item_id,
                "进化树名称": card.name,
                "素材卡片ID": step.cost_id,
                "素材卡片名称": cost_card.name if cost_card is not None else "",
                "融合词条": step.upgrade,
                "Excel名称": card.name,
                "Excel行": card.source_row,
                "目标文件名": planned_card.filename,
                "候选URL": " | ".join(card.urls),
            }
            matched_rows.append(row)
            fusion_rows.append(row)

    cards_without_regular_tree = sorted(
        (card for card in excel_cards.values() if card.item_id not in tree_ids and card.item_id not in fusion_ids),
        key=lambda card: int(card.item_id, 16),
    )
    for card in cards_without_regular_tree:
        node = EvolutionNode(card.item_id, card.name, "single")
        planned_card = PlannedCardImage(
            base_id=card.item_id,
            base_name=card.name,
            node=node,
            index=0,
            excel_card=card,
            chain_type="单独卡",
        )
        planned.append(planned_card)
        row = {
            "链路类型": planned_card.chain_type,
            "融合阶段": "",
            "融合来源二转卡片ID": "",
            "融合来源二转卡片名称": "",
            "基础卡片ID": card.item_id,
            "基础卡片名称": card.name,
            "序号": 0,
            "进化树ID": card.item_id,
            "进化树名称": card.name,
            "素材卡片ID": "",
            "素材卡片名称": "",
            "融合词条": "",
            "Excel名称": card.name,
            "Excel行": card.source_row,
            "目标文件名": planned_card.filename,
            "候选URL": " | ".join(card.urls),
        }
        matched_rows.append(row)
        single_rows.append(row)

    return planned, matched_rows, fusion_rows, single_rows


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


def fetch_one(planned: PlannedCardImage, output_dir: Path, timeout: int, force: bool, downloader: str) -> tuple[str, str]:
    target = output_dir / planned.filename
    if target.exists() and not force:
        return "已存在", ""

    last_error = ""
    for url in planned.excel_card.urls:
        try:
            if is_remote_url(url):
                download_remote_source(url, target, timeout, downloader)
            else:
                source = Path(url)
                if not source.is_file():
                    raise FileNotFoundError(url)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            return "已下载", url
        except Exception as exc:
            last_error = f"{url} -> {exc}"
    return "失败", last_error


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="根据图像资源 Excel 和 compose.xml 生成准备房间卡片识别资源。")
    parser.add_argument("--excel", type=Path, default=None, help="图像资源 Excel；传入后不会自动重新获取")
    parser.add_argument("--compose", default=DEFAULT_COMPOSE_URL, help="compose.xml URL 或本地路径")
    parser.add_argument("--card-fusion", default=DEFAULT_CARD_FUSION_URL, help="CardFusion.xml URL 或本地路径")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR, help="准备房间卡片图片输出目录")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR, help="CSV 报告输出目录")
    parser.add_argument("--blacklist", type=Path, default=DEFAULT_BLACKLIST_PATH, help="未实装卡片黑名单 CSV")
    parser.add_argument("--timeout", type=int, default=20, help="单个网络请求超时秒数")
    parser.add_argument("--excel-update-timeout", type=int, default=300, help="获取最新 Excel 的超时秒数")
    parser.add_argument("--skip-excel-update", action="store_true", help="不调用 card_image_url_get.py，只使用本地最近 Excel")
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
    args = build_arg_parser().parse_args()
    project_root = find_project_root(Path.cwd())
    if args.excel:
        excel_path = args.excel
    elif args.skip_excel_update:
        excel_path = find_default_excel(project_root)
    else:
        excel_path = get_latest_excel_file(project_root, args.excel_update_timeout)

    compose_bytes = read_compose_xml(args.compose, args.timeout)
    card_fusion_bytes = read_compose_xml(args.card_fusion, args.timeout)
    all_excel_cards = parse_excel_cards(excel_path)
    blacklist_names = read_blacklist_names(args.blacklist)
    blacklist_copy_rows = [{"名称": name} for name in blacklist_names]
    excel_cards, blocked_rows = split_blacklisted_cards(all_excel_cards, blacklist_names)
    chains = parse_evolution_chains(compose_bytes)
    fusion_chains = parse_fusion_chains(card_fusion_bytes)
    planned, matched_rows, fusion_rows, single_rows = build_plan(chains, fusion_chains, excel_cards)

    download_rows: list[dict[str, object]] = []
    status_count: dict[str, int] = {}
    for planned_card in planned:
        target = args.output / planned_card.filename
        if args.dry_run:
            status, used_url = "计划下载", planned_card.excel_card.urls[0] if planned_card.excel_card.urls else ""
        else:
            status, used_url = fetch_one(planned_card, args.output, args.timeout, args.force, args.downloader)
            time.sleep(args.sleep)
        status_count[status] = status_count.get(status, 0) + 1
        download_rows.append(
            {
                "状态": status,
                "链路类型": planned_card.chain_type,
                "基础卡片名称": planned_card.base_name,
                "序号": planned_card.index,
                "进化树ID": planned_card.node.item_id,
                "进化树名称": planned_card.node.xml_name,
                "Excel名称": planned_card.excel_card.name,
                "目标路径": str(target),
                "使用URL或错误": used_url,
            }
        )

    write_reports(args.report_dir, matched_rows, fusion_rows, single_rows, blocked_rows, blacklist_copy_rows, download_rows)

    print(f"Excel: {excel_path}")
    print(f"Compose: {args.compose}")
    print(f"CardFusion: {args.card_fusion}")
    print(f"黑名单: {args.blacklist}")
    print(f"进化树链路: {len(chains)}")
    print(f"融合链路: {len(fusion_chains)}")
    print(f"匹配图片: {len(planned)}")
    print(f"黑名单屏蔽: {len(blocked_rows)}")
    print(f"融合卡图片: {len(fusion_rows)}")
    print(f"单独卡图片: {len(single_rows)}")
    print(f"输出目录: {args.output}")
    print(f"报告目录: {args.report_dir}")
    print("下载状态统计:", status_count)

    return 1 if any(row["状态"] == "失败" for row in download_rows) else 0


if __name__ == "__main__":
    sys.exit(main())
