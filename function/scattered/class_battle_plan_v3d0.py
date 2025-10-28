import json
from dataclasses import dataclass, asdict
from typing import List, Union, Dict

from dacite import from_dict, Config

from function.globals.get_paths import PATHS


@dataclass
class MetaData:
    uuid: str
    tips: str
    player_position: List[str]
    version: str = "3.0"


@dataclass
class Card:
    card_id: int
    name: str


@dataclass
class TriggerWaveTimer:
    wave_id: int
    time: float
    type: str = "wave_timer"


@dataclass
class CardLoopConfig:
    card_id: int
    ergodic: bool
    queue: bool
    location: List[str]
    kun: int


@dataclass
class ActionLoopUseCards:
    cards: List[CardLoopConfig]
    type: str = "loop_use_cards"


@dataclass
class ActionInsertUseCard:
    card_id: int
    location: str
    before_shovel: bool
    after_shovel: bool
    after_shovel_time: int
    type: str = "insert_use_card"

@dataclass
class ActionShovel:
    time: float
    location: str
    type: str = "shovel"

@dataclass
class ActionUseGem:
    gem_id: int
    type: str = "insert_use_gem"
@dataclass
class ActionEscape:
    time: float
    type: str = "escape"
@dataclass
class ActionRandomSingleCard:
    card_index: int
    type: str = "random_single_card"
@dataclass
class ActionRandomMultiCard:
    card_indices: List[int]
    type: str = "random_multi_card"
@dataclass
class ActionBanCard:
    start_time: float
    end_time: float
    card_id: int
    type: str = "ban_card"

@dataclass
class Event:
    trigger: Union[TriggerWaveTimer]
    action: Union[ActionLoopUseCards, ActionInsertUseCard, ActionUseGem, ActionShovel, ActionBanCard, ActionEscape, ActionRandomSingleCard, ActionRandomMultiCard]


@dataclass
class BattlePlan:
    meta_data: MetaData = MetaData
    cards: List[Card] = List[Card]
    events: List[Event] = List[Event]


def json_to_obj(json_dict: dict) -> BattlePlan:
    """
    反序列化 JSON → 对象
    :param json_dict:
    :return:
    """

    # 解析整个结构
    return from_dict(
        data_class=BattlePlan,
        data=json_dict,
        config=Config(
            cast=[int],
            strict=True,
            type_hooks={}
        )
    )


def obj_to_json(plan: BattlePlan) -> dict:
    """
    序列化 对象 → JSON
    :param plan:
    :return:
    """

    # 使用 dataclasses.asdict 递归转换对象为字典
    dict_data = asdict(plan)

    # 移除 None 值字段（可选）
    cleaned_data = remove_none_fields(dict_data)

    return cleaned_data


def remove_none_fields(obj):
    """递归删除所有 None 值字段"""
    if isinstance(obj, dict):
        return {k: remove_none_fields(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [remove_none_fields(v) for v in obj]
    else:
        return obj


def convert_v2_to_v3(v2_data: Dict) -> Dict:
    """将V2战斗方案转换为V3格式
    :param v2_data: 旧版V2方案的字典数据
    :return 新版V3方案的字典数据
    """
    # ============================== 元数据处理 ==============================

    meta = {
        "uuid": v2_data["uuid"],
        "tips": v2_data["tips"] if v2_data.get("tips", None) else v2_data.get("tip", ""), # 部分小版本该参数有小变化
        "player_position": v2_data["player"],
        "version": "3.0"  # 根据需求可改为 "v3.0"
    }

    # ============================== 卡片列表处理 ==============================
    # 收集所有卡片ID和首次出现的名称
    card_id_name_map = {}

    # 先处理default卡片
    for card in v2_data["card"]["default"]:
        if card["id"] not in card_id_name_map:
            card_id_name_map[card["id"]] = card["name"]

    # 再处理wave卡片（按波次顺序处理）
    for wave_key in sorted(v2_data["card"]["wave"].keys(), key=int):
        for card in v2_data["card"]["wave"][wave_key]:
            if card["id"] not in card_id_name_map:
                card_id_name_map[card["id"]] = card["name"]

    # 构建新卡片列表
    cards = [{"card_id": cid, "name": name} for cid, name in card_id_name_map.items()]

    # ============================== 事件处理 ==============================
    events = []

    # 处理默认卡片（对应wave 0）
    if v2_data["card"]["default"]:
        trigger = {"wave_id": 0, "time": 0, "type": "wave_timer"}
        action = {
            "type": "loop_use_cards",
            "cards": [
                {
                    "card_id": c["id"],
                    "ergodic": c["ergodic"],
                    "queue": c["queue"],
                    "location": c["location"],
                    "kun": c.get("kun",0)  # 部分小版本该参数不存在
                } for c in v2_data["card"]["default"]
            ]
        }
        events.append({"trigger": trigger, "action": action})

    # 处理波次卡片（wave 1+）
    for wave_str, wave_cards in v2_data["card"]["wave"].items():
        wave_id = int(wave_str)  # 转换为整数波次
        trigger = {"wave_id": wave_id, "time": 0, "type": "wave_timer"}
        action = {
            "type": "loop_use_cards",
            "cards": [
                {
                    "card_id": c["id"],
                    "ergodic": c["ergodic"],
                    "queue": c["queue"],
                    "location": c["location"],
                    "kun": c["kun"]
                } for c in wave_cards
            ]
        }
        events.append({"trigger": trigger, "action": action})

    # ============================== 组装最终结构 ==============================
    return {
        "meta_data": meta,
        "cards": cards,
        "events": events
    }


if __name__ == '__main__':
    def test_load_v2_json_to_dict():
        # 读取 JSON 文件
        file_path = PATHS["battle_plan"] + "\\NO-6-10-1P 多拿滋.json"
        with open(file=file_path, mode='r', encoding='utf-8') as file:
            return json.load(file)


    def test_load_v3_json_to_dict():
        # 读取 JSON 文件
        file_path = PATHS["battle_plan"] + "\\新版方案示例-触发器和动作内联于事件.json"
        with open(file=file_path, mode='r', encoding='utf-8') as file:
            return json.load(file)


    def test_filter(obj_battle_plan):
        # 类型1 波次变阵
        filtered_events = [
            event for event in obj_battle_plan.events
            if (isinstance(event.trigger, TriggerWaveTimer) and
                event.trigger.type == "wave_timer" and
                event.trigger.time == 0 and
                isinstance(event.action, ActionLoopUseCards) and
                event.action.type == "loop_use_cards")
        ]
        print("波次变阵事件：", filtered_events)

        # 类型2 波次定时插卡
        filtered_events = [
            event for event in obj_battle_plan.events
            if (isinstance(event.trigger, TriggerWaveTimer) and
                event.trigger.type == "wave_timer" and
                isinstance(event.action, ActionInsertUseCard) and
                event.action.type == "insert_use_card")
        ]
        print("波次定时插入卡放事件：", filtered_events)

        # 类型3 波次定时宝石
        filtered_events = [
            event for event in obj_battle_plan.events
            if (isinstance(event.trigger, TriggerWaveTimer) and
                event.trigger.type == "wave_timer" and
                isinstance(event.action, ActionUseGem) and
                event.action.type == "insert_use_gem")
        ]
        print("波次定时宝石事件：", filtered_events)


    v2_json_dict = test_load_v2_json_to_dict()
    v3_json_dict = convert_v2_to_v3(v2_json_dict)
    obj_battle_plan = json_to_obj(v3_json_dict)
    print(obj_battle_plan)
