from function.core.faa.faa_action_interface_jump import FAAActionInterfaceJump
from function.core.faa.faa_action_receive_quest_rewards import FAAActionReceiveQuestRewards
from function.core.faa.faa_battle import FAABattle
from function.core.faa.faa_battle_preparation import BattlePreparation
from function.core.faa.faa_core import FAABase


class FAA(FAABase, FAAActionInterfaceJump, FAAActionReceiveQuestRewards, BattlePreparation, FAABattle):
    """
    FAA聚合类!
    """

    def __init__(self, **kwargs):
        FAABase.__init__(self, **kwargs)
