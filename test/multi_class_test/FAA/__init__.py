from test.multi_class_test.FAA.base import FAABase
from test.multi_class_test.FAA.battle import BattleMixin
from test.multi_class_test.FAA.utils import UtilsMixin


class FAA(FAABase, BattleMixin, UtilsMixin):
    def __init__(self):
        super().__init__()
        self.player = 2
