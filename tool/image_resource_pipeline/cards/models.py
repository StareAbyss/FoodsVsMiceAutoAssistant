"""准备房间卡片、进化链与融合链的数据结构。"""

from dataclasses import dataclass
from ..common.files import safe_filename

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
