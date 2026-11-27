"""解析进化与融合规则，生成准备房间卡片模板计划。"""

import xml.etree.ElementTree as ET
from collections import defaultdict
from .models import ExcelCard, EvolutionNode, FusionStep, FusionChain, PlannedCardImage

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
