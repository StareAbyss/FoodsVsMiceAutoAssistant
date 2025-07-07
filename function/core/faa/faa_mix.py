from function.globals.loadings import loading
loading.update_progress(15,"正在加载FAA操作接口...")
from function.core.faa.faa_action_interface_jump import FAAActionInterfaceJump
from function.globals.loadings import loading
loading.update_progress(20,"正在加载奖励模块...")
from function.core.faa.faa_action_receive_quest_rewards import FAAActionReceiveQuestRewards
from function.globals.loadings import loading
loading.update_progress(25,"正在加载战斗模块...")
from function.core.faa.faa_battle import FAABattle
from function.globals.loadings import loading
loading.update_progress(30,"正在加载备战模块...")
from function.core.faa.faa_battle_preparation import BattlePreparation
from function.core.faa.faa_core import FAABase


class FAA(FAABase, FAAActionInterfaceJump, FAAActionReceiveQuestRewards, BattlePreparation, FAABattle):
    """
    FAA聚合类!
    """

    def __init__(self, **kwargs):
        FAABase.__init__(self, **kwargs)
