from dataclasses import dataclass
from typing import List, Dict

from function.core_battle.card import Card


class CardLoopConfig:
    id: int
    name: str
    ergodic: bool
    queue: bool
    location: List[str]
    kun: int


@dataclass
class Card:
    default: List[CardLoopConfig]
    wave: Dict[str, List[Card]]


@dataclass
class BattlePlan:
    player: List[str]
    card: Card
    tips: str
    uuid: str


