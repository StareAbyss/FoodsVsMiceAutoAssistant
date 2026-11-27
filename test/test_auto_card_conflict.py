import unittest
from unittest.mock import patch

from function.core.faa.battle_card_roles import (
    ROLE_PLAN,
    ROLE_PRIMARY_MAT,
    ROLE_QUEST,
    ROLE_TIMER,
)
from function.core.faa.tweak_plan import (
    get_auto_card_target_names,
    get_auto_timer_target_names,
)


def make_battle_plan(card_names=None, action_cards=None):
    card_names = card_names or []
    action_cards = action_cards or []
    return {
        "cards": [
            {"card_id": index, "name": name}
            for index, name in enumerate(card_names, start=1)
        ],
        "events": [
            {
                "trigger": {"type": "wave_timer", "wave_id": 0},
                "action": {"type": "loop_use_cards", "cards": action_cards},
            }
        ],
    }


class AutoCardConflictTest(unittest.TestCase):
    def setUp(self):
        self.stage_mat_card_names = ["木盘子", "麦芽糖浆"]
        self.card_types = [
            {
                "key": ["冷却辅助", "冷却拐"],
                "value": ["时间神", "转龙壶", "美味计时器"],
            },
            {
                "key": ["复制辅助"],
                "value": ["幻幻鸡", "创造神"],
            },
        ]
        self.safe_kun_action = {
            "card_id": 1,
            "location": [
                f"{column}-{row}"
                for column in range(2, 5)
                for row in range(2, 5)
            ],
            "kun": 2,
        }

    def targets(self, card_names):
        plan = make_battle_plan(card_names, [self.safe_kun_action])
        auto_targets = get_auto_card_target_names(
            stage_mat_card_names=self.stage_mat_card_names,
            battle_plan_tweak={"meta_data": {"enable_auto_card": {"timer": True}}},
            battle_plan=plan,
            card_types=self.card_types,
        )
        timer_targets = get_auto_timer_target_names(
            battle_plan_tweak={"meta_data": {"enable_auto_card": {"timer": True}}},
            battle_plan=plan,
            card_types=self.card_types,
        )
        return (*auto_targets, timer_targets)

    def test_direct_cards_cancel_only_their_automatic_features(self):
        self.assertEqual(
            self.targets(["木盘子-3", "极寒冰沙-2", "幻幻鸡", "美味计时器"]),
            (["麦芽糖浆"], [], ["创造神"], []),
        )

    def test_card_type_candidates_cancel_copy_and_timer_features(self):
        self.assertEqual(
            self.targets(["冷却辅助", "复制辅助"]),
            (["木盘子", "麦芽糖浆"], ["冰激凌"], [], []),
        )

    def test_manual_deck_does_not_trust_plan_names_for_auxiliary_presence(self):
        """手动卡组名称可与方案无关，开场识图不能据方案名排除辅助卡。"""
        plan = make_battle_plan(
            ["木盘子-3", "极寒冰沙-2", "幻幻鸡", "美味计时器"],
            [self.safe_kun_action],
        )
        tweak = {"meta_data": {"enable_auto_card": {"timer": True}}}
        auto_targets = get_auto_card_target_names(
            stage_mat_card_names=self.stage_mat_card_names,
            battle_plan_tweak=tweak,
            battle_plan=plan,
            card_types=self.card_types,
            exclude_plan_cards=False,
        )
        timer_targets = get_auto_timer_target_names(
            battle_plan_tweak=tweak,
            battle_plan=plan,
            card_types=self.card_types,
            exclude_plan_cards=False,
        )

        self.assertEqual(auto_targets[0], self.stage_mat_card_names)
        self.assertEqual(auto_targets[1], ["冰激凌"])
        self.assertIn("幻幻鸡", auto_targets[2])
        self.assertEqual(timer_targets, ["美味计时器"])

    def test_runtime_discovers_all_available_card_stages(self):
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.card_types = []
        resources = {
            "card": {
                "准备房间": {
                    "用户自制卡-0.png": None,
                    "用户自制卡-2.png": None,
                    "用户自制卡-4.png": None,
                }
            }
        }

        with patch.object(faa_battle_preparation, "RESOURCE_P", resources):
            targets = preparation._card_name_to_tar_list("用户自制卡")

        self.assertEqual(targets, ["用户自制卡-4", "用户自制卡-2", "用户自制卡-0"])
        self.assertIsNotNone(app)

    def test_auto_carry_keeps_plan_ids_before_added_cards(self):
        """承载保留优先级最高，但物理排列仍必须让方案卡从 ID=1 开始。"""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.stage_info = {"mat_card": ["木盘子", "麦芽糖浆"]}
        preparation.battle_plan_tweak = {}
        preparation.battle_plan = {
            "cards": [
                {"card_id": 2, "name": "用户卡二"},
                {"card_id": 1, "name": "用户卡一"},
            ]
        }
        preparation.card_types = []
        preparation.max_card_num = 3
        preparation.ban_card_list = []
        preparation.print_debug = lambda text: None

        with (
            patch.object(
                faa_battle_preparation,
                "get_auto_card_target_names",
                return_value=(["木盘子", "麦芽糖浆"], ["冰激凌"], ["创造神", "幻幻鸡"]),
            ),
            patch.object(
                faa_battle_preparation,
                "get_auto_timer_target_names",
                return_value=["美味计时器"],
            ),
        ):
            required = preparation._auto_carry_card_get_card_name_list_from_battle_plan()
            required = preparation._auto_carry_card_apply_limit(required)

        self.assertEqual(
            [card["name"] for card in required],
            ["用户卡一", "用户卡二", "木盘子"],
        )
        self.assertEqual([card["can_failed"] for card in required], [False, False, False])
        self.assertIsNotNone(app)

    def test_card_limit_drops_optional_cards_only_until_limit_is_met(self):
        """附加卡优先级最低，但限卡仍有空位时可以保留最靠前的一张。"""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.stage_info = {"mat_card": ["木盘子", "麦芽糖浆"]}
        preparation.battle_plan_tweak = {}
        preparation.battle_plan = {
            "cards": [{"card_id": 1, "name": "用户卡"}]
        }
        preparation.card_types = []
        preparation.max_card_num = 3
        preparation.ban_card_list = []
        preparation.print_debug = lambda text: None

        with (
            patch.object(
                faa_battle_preparation,
                "get_auto_card_target_names",
                return_value=(["木盘子", "麦芽糖浆"], ["冰激凌"], ["创造神", "幻幻鸡"]),
            ),
            patch.object(
                faa_battle_preparation,
                "get_auto_timer_target_names",
                return_value=["美味计时器"],
            ),
        ):
            required = preparation._auto_carry_card_get_card_name_list_from_battle_plan()
            required = preparation._auto_carry_card_apply_limit(required)

        self.assertEqual(
            [card["name"] for card in required],
            ["用户卡", "木盘子", "美味计时器"],
        )
        self.assertIsNotNone(app)

    def test_quest_card_is_retained_between_plan_and_mat(self):
        """任务卡保留优先级仅低于承载，但物理位置必须位于方案与承载之间。"""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.quest_card = "任务卡"
        preparation.max_card_num = 3
        preparation.stage_info = {
            "mat_card": ["麦芽糖-1"],
            "mat_card_type": "海底",
        }
        preparation.ban_card_list = []
        preparation.print_debug = lambda text: None
        preparation._card_name_to_tar_list = lambda card_name: [f"{card_name}-0"]
        required = [
            {
                "name": "用户卡一",
                "names": ["用户卡一-0"],
                "can_failed": False,
                "source": "battle_plan",
                "plan_id": 1,
                "roles": [ROLE_PLAN],
            },
            {
                "name": "用户卡二",
                "names": ["用户卡二-0"],
                "can_failed": False,
                "source": "battle_plan",
                "plan_id": 2,
                "roles": [ROLE_PLAN],
            },
            {
                "name": "有效承载",
                "names": ["麦芽糖-1"],
                "can_failed": False,
                "source": "mat",
                "plan_id": None,
                "roles": [ROLE_PRIMARY_MAT],
            },
            {
                "name": "美味计时器",
                "names": ["美味计时器-1"],
                "can_failed": True,
                "source": "extra",
                "plan_id": None,
                "roles": [ROLE_TIMER],
            },
        ]

        preparation._auto_carry_card_add_quest_card(required)
        required = preparation._auto_carry_card_apply_limit(required)

        self.assertEqual(
            [card["name"] for card in required],
            ["用户卡一", "任务卡", "有效承载"],
        )
        self.assertIsNotNone(app)

    def test_plan_card_candidates_are_narrowed_to_quest_card(self):
        """类型卡承担任务要求时必须只剩任务卡候选，不能残留更高优先级卡。"""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.quest_card = "油灯"
        preparation.print_debug = lambda text: None
        preparation._card_name_to_tar_list = lambda card_name: ["油灯-1", "油灯-0"]
        required = [
            {
                "name": "照明",
                "names": [
                    "萤火蛇-2", "萤火蛇-1", "防萤草灯笼-2", "油灯-1",
                ],
                "source": "battle_plan",
                "roles": [ROLE_PLAN],
            }
        ]

        preparation._auto_carry_card_add_quest_card(required)

        self.assertEqual(required[0]["names"], ["油灯-1"])
        self.assertIn(ROLE_QUEST, required[0]["roles"])
        self.assertEqual(preparation.quest_card, "油灯")
        self.assertIsNotNone(app)

    def test_only_first_matching_plan_card_is_narrowed_for_quest(self):
        """多张方案类型卡都包含任务卡时，只强制 card_id 更小的第一张。"""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.quest_card = "油灯"
        preparation.print_debug = lambda text: None
        preparation._card_name_to_tar_list = lambda card_name: ["油灯-1"]
        required = [
            {
                "name": "照明一",
                "names": ["萤火蛇-1", "油灯-1"],
                "source": "battle_plan",
                "roles": [ROLE_PLAN],
            },
            {
                "name": "照明二",
                "names": ["防萤草灯笼-2", "油灯-1"],
                "source": "battle_plan",
                "roles": [ROLE_PLAN],
            },
        ]

        preparation._auto_carry_card_add_quest_card(required)

        self.assertEqual(required[0]["names"], ["油灯-1"])
        self.assertEqual(required[1]["names"], ["防萤草灯笼-2", "油灯-1"])
        self.assertIsNotNone(app)

    def test_matching_extra_card_gains_quest_role_and_priority(self):
        """自动附加卡承担任务后成为必要卡，不再重复插入同名任务卡。"""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.quest_card = "美味计时器"
        preparation.print_debug = lambda text: None
        preparation._card_name_to_tar_list = lambda card_name: ["美味计时器-1"]
        required = [
            {
                "name": "用户方案卡",
                "names": ["用户方案卡-0"],
                "source": "battle_plan",
                "roles": [ROLE_PLAN],
            },
            {
                "name": "美味计时器",
                "names": ["美味计时器-1"],
                "source": "extra",
                "can_failed": True,
                "roles": [ROLE_TIMER],
            },
        ]

        preparation._auto_carry_card_add_quest_card(required)

        self.assertEqual(
            [(card["name"], card["source"]) for card in required],
            [
                ("用户方案卡", "battle_plan"),
                ("美味计时器", "extra"),
            ],
        )
        self.assertEqual(required[1]["roles"], [ROLE_TIMER, ROLE_QUEST])
        self.assertFalse(required[1]["can_failed"])
        self.assertEqual(preparation.quest_card, "美味计时器")
        self.assertIsNotNone(app)

    def test_first_mat_can_also_be_the_quest_card(self):
        """第一承载与任务卡重复时只保留一个必要实体卡。"""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.quest_card = "木盘子"
        preparation.max_card_num = 3
        preparation.stage_info = {
            "mat_card": ["木盘子", "麦芽糖"],
            "mat_card_type": "水面",
        }
        preparation.battle_plan = make_battle_plan(["用户卡1", "用户卡2"])
        preparation.battle_plan_tweak = {}
        preparation.card_types = []
        preparation.ban_card_list = []
        preparation.print_debug = lambda text: None

        def expand(card_name):
            return {
                "木盘子": ["木盘子-2"],
                "麦芽糖": ["麦芽糖-1"],
                "有效承载": ["木盘子-2", "麦芽糖-1"],
            }.get(card_name, [f"{card_name}-0"])

        preparation._card_name_to_tar_list = expand
        with (
            patch.object(
                faa_battle_preparation,
                "get_auto_card_target_names",
                return_value=(["木盘子", "麦芽糖"], [], []),
            ),
            patch.object(
                faa_battle_preparation,
                "get_auto_timer_target_names",
                return_value=[],
            ),
        ):
            required = preparation._auto_carry_card_get_card_name_list_from_battle_plan()
            for card in required:
                card["names"] = expand(card["name"])
            preparation._auto_carry_card_add_quest_card(required)
            required = preparation._auto_carry_card_apply_limit(required)

        quest_cards = [card for card in required if ROLE_QUEST in card["roles"]]
        self.assertEqual(len(quest_cards), 1)
        self.assertEqual(
            quest_cards[0]["roles"],
            [ROLE_PRIMARY_MAT, ROLE_QUEST],
        )
        self.assertEqual(len(required), 3)
        self.assertIsNotNone(app)

    def test_high_plan_id_quest_card_is_retained_by_role(self):
        """高方案 ID 的类型卡承担任务后不能再被普通 ID 截断。"""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.quest_card = "油灯"
        preparation.max_card_num = 3
        preparation.stage_info = {"mat_card": [], "mat_card_type": ""}
        preparation.battle_plan = make_battle_plan(
            ["用户卡1", "用户卡2", "用户卡3", "用户卡4", "照明"]
        )
        preparation.battle_plan_tweak = {}
        preparation.card_types = []
        preparation.ban_card_list = []
        preparation.print_debug = lambda text: None

        def expand(card_name):
            if card_name == "照明":
                return ["萤火蛇-1", "油灯-1"]
            if card_name == "油灯":
                return ["油灯-1"]
            return [f"{card_name}-0"]

        preparation._card_name_to_tar_list = expand
        with (
            patch.object(
                faa_battle_preparation,
                "get_auto_card_target_names",
                return_value=([], [], []),
            ),
            patch.object(
                faa_battle_preparation,
                "get_auto_timer_target_names",
                return_value=[],
            ),
        ):
            required = preparation._auto_carry_card_get_card_name_list_from_battle_plan()
            for card in required:
                card["names"] = expand(card["name"])
            preparation._auto_carry_card_add_quest_card(required)
            required = preparation._auto_carry_card_apply_limit(required)

        self.assertEqual(
            [card["plan_id"] for card in required],
            [1, 2, 5],
        )
        self.assertIn(ROLE_QUEST, required[-1]["roles"])
        self.assertEqual(required[-1]["names"], ["油灯-1"])
        self.assertIsNotNone(app)

    def test_manual_quest_failure_keeps_requirement_for_battle_scan(self):
        """手动添加失败按灰色已携带处理，不得再把任务状态改成 None。"""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from function.core.faa import faa_battle_preparation

        preparation = faa_battle_preparation.BattlePreparation.__new__(
            faa_battle_preparation.BattlePreparation
        )
        preparation.player = 1
        preparation.quest_card = "油灯"
        preparation.max_card_num = 3
        preparation.stage_info = {"mat_card": [], "mat_card_type": ""}
        preparation.battle_plan = make_battle_plan(["方案卡1", "方案卡2"])
        preparation.print_debug = lambda text: None
        preparation._add_card = lambda card_name: False

        with patch.object(
                faa_battle_preparation.SIGNAL,
                "PRINT_TO_UI",
        ) as print_signal:
            result = preparation._manual_carry_add_quest_card()

        preparation._build_manual_battle_card_plan(result)

        self.assertFalse(result)
        self.assertEqual(preparation.quest_card, "油灯")
        quest_owner = next(
            card for card in preparation.battle_card_plan
            if ROLE_QUEST in card["roles"]
        )
        self.assertIsNone(quest_owner["slot_id"])
        self.assertTrue(quest_owner["assumed_existing"])
        self.assertTrue(preparation.manual_quest_card_assumed)
        print_signal.emit.assert_called_once()
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
