"""准备房间卡片图像自动生成流程。"""

import time
import urllib.request
from pathlib import Path
from ..common.paths import PROJECT_ROOT
from ..common.excel import find_default_excel
from ..common.snapshot_files import latest_snapshot, resolve_excel_path
from ..common.download import fetch_sources, is_remote_url, USER_AGENT
from ..sources.snapshots import ensure_snapshots
from .models import PlannedCardImage
from .catalog import parse_excel_cards, read_blacklist_names, split_blacklisted_cards
from .chains import parse_evolution_chains, parse_fusion_chains, build_plan
from .reports import write_reports, write_card_stage_categories

def read_compose_xml(source: str | Path, timeout: int) -> bytes:
    source_text = str(source)
    if is_remote_url(source_text):
        request = urllib.request.Request(source_text, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    return Path(source).read_bytes()

def fetch_one(planned: PlannedCardImage, output_dir: Path, timeout: int, force: bool, downloader: str) -> tuple[str, str]:
    """获取一张准备房间模板，保留卡片工具的空路径失败状态。"""
    return fetch_sources(planned.excel_card.urls, output_dir / planned.filename, timeout, force, downloader, empty_status="失败")

def run_pipeline(args) -> int:
    if args.excel is not None:
        resolve_excel_path(args.excel)
    project_root = PROJECT_ROOT
    kinds = ("compose", "CardFusion") if args.skip_excel_update or args.excel is not None else ("excel", "compose", "CardFusion")
    refreshed = ensure_snapshots(kinds=kinds, excel_timeout=args.excel_update_timeout, xml_timeout=args.timeout)
    for kind, error in refreshed.errors.items():
        print(f"Warning: {kind} 更新失败，沿用已有快照: {error}")
    if args.excel:
        excel_path = args.excel
    else:
        excel_path = refreshed.files.get("excel") or find_default_excel(project_root)

    compose_source = args.compose or refreshed.files.get("compose") or latest_snapshot("compose")
    fusion_source = args.card_fusion or refreshed.files.get("CardFusion") or latest_snapshot("CardFusion")
    if compose_source is None or fusion_source is None:
        raise FileNotFoundError("resource/db 缺少 compose 或 CardFusion XML 快照")
    compose_bytes = read_compose_xml(compose_source, args.timeout)
    card_fusion_bytes = read_compose_xml(fusion_source, args.timeout)
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
    if not args.dry_run:
        write_card_stage_categories(args.category_output, matched_rows, args.output)

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
    if not args.dry_run:
        print(f"阶段类别配置: {args.category_output}")
    print("下载状态统计:", status_count)

    return 1 if any(row["状态"] == "失败" for row in download_rows) else 0
