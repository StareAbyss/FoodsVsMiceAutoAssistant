"""用完整背包快照验证十三香开关和排序边界，不连接游戏窗口。"""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from function.globals import g_resources
from function.scattered import bag_operations as bag


class ThirteenSpiceTests(unittest.TestCase):
    def run_inventory(self, cells, enabled=True):
        """运行真实消费计划，替换截图、点击及数量扣减。"""
        image = np.zeros((26, 31, 4), dtype=np.uint8)
        resources = {"背包_装备_需使用的": {}, "卡牌包": {"卡.png": image},
                     "十三香礼包": {"礼包.png": image}}
        row = bag._BagRow(88, tuple(cells), b"page")
        scanner = Mock()
        scanner.scan.return_value = (row,)
        viewer = Mock(offset=0, first_phase=88)
        viewer.iterate.return_value = [bag._BagPage(88, 108, 413, (row,))]
        session = Mock(used={})
        session.pending.return_value = True
        session.use.return_value = 0
        faa = SimpleNamespace(action_bottom_menu=Mock(return_value=True), action_exit=Mock())
        with patch.dict(g_resources.RESOURCE_CP, resources, clear=True), \
                patch.object(bag, "_BagPages", side_effect=[scanner, viewer] * 3), \
                patch.object(bag, "_BagUseSession", return_value=session), \
                patch.object(bag.time, "sleep"), \
                patch.object(bag, "sort_equipment_inventory"), \
                patch.object(bag, "close_bag_reward_windows"):
            bag.use_bag_consumables(faa, open_thirteen_spice=enabled)
        return session, viewer, faa

    def test_disabled_does_not_open_bag_when_whitelist_empty(self):
        session, viewer, faa = self.run_inventory([], enabled=False)
        faa.action_bottom_menu.assert_not_called()
        session.use.assert_not_called()

    def test_only_bound_gifts_after_last_bound_card_are_used(self):
        gift = bag.BagItem("十三香礼包/礼包.png", 2, True)
        card = bag.BagItem("卡牌包/卡.png", 1, True)
        session, viewer, _ = self.run_inventory([
            gift, card, gift, card, gift,
            bag.BagItem("十三香礼包/礼包.png", 2, False),
        ])
        self.assertEqual(session.use.call_count, 3)
        for call in session.use.call_args_list:
            self.assertEqual(call.args, ("十三香礼包/礼包.png", (686, 112)))
        self.assertEqual(viewer.verify.call_count, 3)

    def test_no_card_does_not_use_generic_gift(self):
        session, _, _ = self.run_inventory([bag.BagItem("十三香礼包/礼包.png", 1, True)])
        session.use.assert_not_called()

    def test_unbound_card_does_not_establish_boundary(self):
        session, _, _ = self.run_inventory([
            bag.BagItem("卡牌包/卡.png", 1, False),
            bag.BagItem("十三香礼包/礼包.png", 1, True),
        ])
        session.use.assert_not_called()

    def test_option_is_rejected_for_targeted_use_and_scan(self):
        for kwargs in ({"items": {"A": 1}}, {"scan_only": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                bag.use_bag_consumables(Mock(), open_thirteen_spice=True, **kwargs)


if __name__ == "__main__":
    unittest.main()
