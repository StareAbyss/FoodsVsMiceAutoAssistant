"""修改 ``main`` 中的配置后，直接运行本文件进行一次复杂关卡实战测试。"""

import argparse
import sys
import traceback
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from test.complex_battle_runner.runner import BattleRunnerStopped, run_complex_battle


def main() -> int:
    """配置并运行一场复杂关卡战斗。"""

    # 直接读取当前 FAA 使用的 settings。窗口名、等级、点击频率、自动战斗、
    # 加速和高级战斗等全局行为都会沿用，不需要在测试中重复填写。
    settings_file = "config/settings.json"

    # ==================== 通常只需要修改下面这个字典 ====================
    config = {
        # 关卡代号同时决定地图和具体关卡，例如 NO-1-1、EX-2-9、CS-5-5。
        "stage_id": "NO-5-1",

        # [2, 1]：常规双人关卡，2P 房主；[1, 2]：1P 房主；
        # [1] / [2]：对应角色单人。特殊关卡仍会沿用正式流程的修正规则。
        "player": [2, 1],
        "max_times": 1,
        "need_key": True,

        # 0 表示自动带卡；1..6 表示使用对应的手动卡组。
        "deck": 0,

        # 支持填写方案文件名（不用写 .json）或 UUID。
        "battle_plan_1p": "2通用-烤串披萨-1P",
        "battle_plan_2p": "2通用-烤串披萨-2P",
        "battle_plan_tweak": "!默认",

        # None 表示没有任务卡；示例："咖啡粉"。
        "quest_card": "苏打气泡",

        # 示例：["咖啡粉", "酒杯灯"]。空列表表示不额外禁卡。
        "ban_card_list": [],

        # None 表示不限卡。1、2 会由正式任务入口按规则修订为 3。
        "max_card_num": 8,

        # False 才会严格使用上面填写的方案；True 会允许
        # stage_plan.json 覆盖方案、卡组和微调方案。
        "global_plan_active": False,

        # 自建房测试时设为 True；普通地图跳转保持 False。
        "is_cu": False,

        # 完成最后一场后沿用任务序列最常见的退出方式。
        # 魔塔、勇士等特殊地图会由正式流程覆盖。
        "dict_exit": {
            "other_time_player_a": [],
            "other_time_player_b": [],
            "last_time_player_a": ["竞技岛"],
            "last_time_player_b": ["竞技岛"],
        },
    }
    # ==================== 战斗配置到这里结束 ====================

    parser = argparse.ArgumentParser(description="FAA 复杂关卡人工实战测试入口")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只校验 settings、方案和窗口，不执行任何点击",
    )
    args = parser.parse_args()

    try:
        return run_complex_battle(
            config=config,
            settings_file=settings_file,
            check_only=args.check,
        )
    except (BattleRunnerStopped, ValueError) as error:
        print(f"[复杂关卡测试] 已停止：{error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("[复杂关卡测试] 用户请求中止。", file=sys.stderr)
        return 130
    except BaseException:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
