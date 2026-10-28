"""验证关卡房主规则在建房、邀请、方案、重试和退出中的一致性。"""

from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from function.core import todo
from function.core.faa import faa_action_interface_jump as stage_jump


class BattleHostSelectionTest(unittest.TestCase):
    def setUp(self):
        """隔离截图、点击和等待，保留任务编排与建房邀请的真实代码。"""
        self.tweak = "00000000-0000-0000-0000-000000000000"
        self.signal = SimpleNamespace(PRINT_TO_UI=SimpleNamespace(emit=Mock()))
        self.queue = Mock()
        self.matcher = Mock(return_value=True)
        templates = {
            "common": {"战斗": {
                "战斗前_创建房间.png": "create",
                "战斗前_开始按钮.png": "start",
                "战斗前_接受邀请.png": "accept",
            }},
            "stage": {"NO-1-7.png": "stage", "MU-1.png": "multiplayer"},
        }
        for module in (todo, stage_jump):
            self.enterContext(patch.object(module, "RESOURCE_P", templates))
            self.enterContext(patch.object(module, "T_ACTION_QUEUE_TIMER", self.queue))
            self.enterContext(patch.object(module, "loop_match_p_in_w", self.matcher))
        self.enterContext(patch.object(todo, "SIGNAL", self.signal))
        self.enterContext(patch.object(todo, "CUS_LOGGER", Mock()))
        self.enterContext(patch.object(todo.time, "sleep"))
        self.enterContext(patch.object(todo.g_resources, "RESOURCE_B", {"p1": {}, "p2": {}}))
        self.enterContext(patch.object(todo.g_resources, "RESOURCE_T", {self.tweak: {}}))
        self.enterContext(patch.object(todo.EXTRA, "BATTLE_PLAN_UUID_TO_PATH", {
            "p1": "1P.json", "p2": "2P.json",
        }))
        self.enterContext(patch.object(todo.EXTRA, "TWEAK_BATTLE_PLAN_UUID_TO_PATH", {
            self.tweak: "微调.json",
        }))

    def make_task(self):
        """创建无窗口副作用的双账号任务，返回保留真实邀请方法的任务对象。"""
        players = {}
        for pid in (1, 2):
            faa = SimpleNamespace(
                handle=pid, handle_360=pid + 10, random_seed=0, is_used_key=False,
                action_goto_stage=Mock(), action_goto_map=Mock(),
                action_change_activity_list=Mock(), action_exit=Mock(), set_battle_plan=Mock(),
                check_stage_id_is_true=Mock(return_value=True),
                check_stage_is_active=Mock(return_value=True), check_level=Mock(return_value=True),
            )

            def configure_player(faa=faa, **config):
                """同步角色与关卡，使真实跳转方法能读取当前任务的配置。"""
                faa.__dict__.update(config)
                faa.stage_info = {"id": config["stage_id"], "b_id": config["stage_id"]}

            faa.set_config_for_battle = Mock(side_effect=configure_player)
            players[pid] = faa
        task = SimpleNamespace(
            faa_dict=players, battle=Mock(return_value=(0, {}, 1)),
            batch_reload_game=Mock(return_value=None), output_player_loot=Mock(),
        )
        task.goto_stage_and_invite = MethodType(todo.ThreadTodo.goto_stage_and_invite, task)
        task.invite = MethodType(todo.ThreadTodo.invite, task)
        return task

    def run_battle(self, task, **overrides):
        """将覆盖参数合入有效战斗配置，返回真实单关流程的结果。"""
        options = {
            "stage_id": "MU-1-1", "player": [1, 2], "need_key": False, "max_times": 1,
            "dict_exit": {
                "other_time_player_a": ["房主中途退出"], "other_time_player_b": ["队友中途退出"],
                "last_time_player_a": ["房主末次退出"], "last_time_player_b": ["队友末次退出"],
            },
            "global_plan_active": False, "deck": 1, "battle_plan_1p": "p1", "battle_plan_2p": "p2",
            "quest_card": None, "ban_card_list": None, "max_card_num": None, "extra_title": None,
        }
        options.update(overrides)
        return todo.ThreadTodo.battle_1_1_n(task, **options)

    def test_mu_creates_and_invites_from_second_player_and_keeps_account_plans(self):
        """使用真实 MU 建房及邀请代码，检查两轮战斗和退出始终沿用 2P 房主。"""
        task = self.make_task()
        for faa in task.faa_dict.values():
            faa.action_goto_stage = MethodType(stage_jump.FAAActionInterfaceJump.action_goto_stage, faa)
        original_players = [1, 2]
        self.assertTrue(self.run_battle(task, player=original_players, max_times=2))
        self.assertEqual(original_players, [1, 2])
        for template, handle in (("create", 2), ("start", 2), ("accept", 1)):
            matches = [entry.kwargs for entry in self.matcher.call_args_list
                       if entry.kwargs["template"] == template]
            self.assertEqual(len(matches), 1, template)
            self.assertEqual(matches[0]["source_handle"], handle, template)
        invitation_clicks = [entry.kwargs["handle"] for entry in self.queue.add_click_to_queue.call_args_list
                             if entry.kwargs["x"] == 410]
        self.assertEqual(invitation_clicks, [2])
        task.battle.assert_has_calls([
            call(player_a=2, player_b=1, change_card=True),
            call(player_a=2, player_b=1, change_card=False),
        ])
        for pid in (1, 2):
            faa = task.faa_dict[pid]
            self.assertEqual(faa.is_main, pid == 2)
            self.assertTrue(faa.is_group)
            self.assertEqual(faa.set_battle_plan.call_count, 2)
            self.assertEqual(faa.set_battle_plan.call_args.kwargs["battle_plan_uuid"], f"p{pid}")
        task.faa_dict[2].action_exit.assert_has_calls([
            call(mode="房主中途退出"), call(mode="房主末次退出"),
        ])
        task.faa_dict[1].action_exit.assert_has_calls([
            call(mode="队友中途退出"), call(mode="队友末次退出"),
        ])
        self.assertTrue(any("【玩家-2P房主】" in entry.kwargs["text"]
                            for entry in self.signal.PRINT_TO_UI.emit.call_args_list))

    def test_normal_team_always_uses_second_player_without_changing_input(self):
        """普通关卡、公会副本和双人魔塔均由 2P 当房主，不改写任务中的原始顺序。"""
        for stage_id in ("MU-1-1", "NO-1-1", "GD-0-1", "MT-2-1"):
            for order in ([1, 2], [2, 1]):
                with self.subTest(stage_id=stage_id, order=order):
                    task = self.make_task()
                    original = list(order)
                    self.assertTrue(self.run_battle(task, stage_id=stage_id, player=order))
                    task.battle.assert_called_once_with(player_a=2, player_b=1, change_card=True)
                    self.assertTrue(task.faa_dict[2].is_main)
                    self.assertFalse(task.faa_dict[1].is_main)
                    self.assertEqual(order, original)

    def test_cross_server_always_uses_first_player(self):
        """跨服保留 1P 房主规则，使用专有进房流程。"""
        for order in ([1, 2], [2, 1]):
            with self.subTest(order=order):
                task = self.make_task()
                self.matcher.reset_mock()
                original = list(order)
                self.assertTrue(self.run_battle(task, stage_id="CS-1-1", player=order))
                task.battle.assert_called_once_with(player_a=1, player_b=2, change_card=True)
                self.assertTrue(task.faa_dict[1].is_main)
                self.assertFalse(task.faa_dict[2].is_main)
                self.matcher.assert_not_called()
                self.assertEqual(order, original)

    def test_single_player_keeps_selected_account(self):
        """单人任务继续使用选定账号，包括 2P 单人魔塔。"""
        for stage_id in ("MU-1-1", "NO-1-1", "MT-1-1"):
            for pid in (1, 2):
                with self.subTest(stage_id=stage_id, pid=pid):
                    task = self.make_task()
                    self.assertTrue(self.run_battle(task, stage_id=stage_id, player=[pid]))
                    task.battle.assert_called_once_with(player_a=pid, player_b=None, change_card=True)
                    self.assertFalse(task.faa_dict[pid].is_group)
                    task.faa_dict[3 - pid].set_config_for_battle.assert_not_called()

    def test_solo_stages_disable_group_before_host_selection(self):
        """单人魔塔、密室和世界 Boss 的组队输入降为 1P 单人，不再应用多人房主规则。"""
        for stage_id in ("MT-1-1", "MT-3-1", "WB-1-1"):
            for order in ([1, 2], [2, 1]):
                with self.subTest(stage_id=stage_id, order=order):
                    task = self.make_task()
                    self.signal.PRINT_TO_UI.emit.reset_mock()
                    original = list(order)
                    self.assertTrue(self.run_battle(task, stage_id=stage_id, player=order))
                    task.battle.assert_called_once_with(player_a=1, player_b=None, change_card=True)
                    self.assertFalse(task.faa_dict[1].is_group)
                    task.faa_dict[2].set_config_for_battle.assert_not_called()
                    self.assertEqual(order, original)
                    self.assertFalse(any("多人常规关卡" in entry.kwargs["text"]
                                         for entry in self.signal.PRINT_TO_UI.emit.call_args_list))

    def test_custom_room_keeps_user_host_and_skips_creation(self):
        """自建房按用户指定顺序开战，不触发自动建房邀请。"""
        for stage_id in ("MU-1-1", "CS-1-1"):
            for order in ([1, 2], [2, 1]):
                with self.subTest(stage_id=stage_id, order=order):
                    task = self.make_task()
                    original = list(order)
                    self.assertTrue(self.run_battle(task, stage_id=stage_id, player=order, is_cu=True))
                    task.battle.assert_called_once_with(player_a=order[0], player_b=order[1], change_card=True)
                    self.assertTrue(task.faa_dict[order[0]].is_main)
                    self.assertFalse(task.faa_dict[order[1]].is_main)
                    for faa in task.faa_dict.values():
                        faa.action_goto_stage.assert_not_called()
                    self.assertEqual(order, original)

    def test_failed_round_keeps_second_player_host_after_reload(self):
        """战斗失败刷新并重新进房后，房主、队友和刷新顺序保持一致。"""
        task = self.make_task()
        task.battle.side_effect = [(1, {}, 0), (0, {}, 1)]
        self.assertTrue(self.run_battle(task, max_times=2))
        task.batch_reload_game.assert_called_once_with(player=[2, 1])
        self.assertEqual(task.battle.call_args_list, [
            call(player_a=2, player_b=1, change_card=True),
            call(player_a=2, player_b=1, change_card=True),
        ])
        for faa in task.faa_dict.values():
            self.assertEqual(faa.action_goto_stage.call_count, 2)


if __name__ == "__main__":
    unittest.main()
