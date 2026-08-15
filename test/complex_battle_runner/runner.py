"""
从当前 settings 启动一场可自由配置的复杂关卡实战测试。

本文件封装实现细节，由同目录的 ``main.py`` 提供配置与直接运行入口。
"""

from __future__ import annotations

import copy
import json
import random
import sys
import threading
import traceback
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


class BattleRunnerStopped(RuntimeError):
    """正式流程通过 ``SIGNAL.END`` 要求测试入口立即停止。"""


class _ConsolePrint:
    """把正式流程的用户提示转发到测试控制台。"""

    @staticmethod
    def emit(text="", *args, **kwargs):
        print(text, flush=True)


class _ConsoleImage:
    """控制台不展示战利品图片，仅提示正式流程已经生成汇总图。"""

    @staticmethod
    def emit(image=None, *args, **kwargs):
        shape = getattr(image, "shape", None)
        print(f"[复杂关卡测试] 已生成战利品汇总图，尺寸：{shape}", flush=True)


class _ConsoleDialog:
    """把正式流程的弹窗内容转发到测试控制台。"""

    @staticmethod
    def emit(title="FAA 提示", text="", *args, **kwargs):
        print(f"[{title}] {text}", file=sys.stderr, flush=True)


class _ConsoleEnd:
    """把主界面的“终止全部任务”信号转换为可追踪的测试异常。"""

    @staticmethod
    def emit(*args, **kwargs):
        raise BattleRunnerStopped("FAA 正式流程请求终止本次测试")


def load_json(path: Path) -> dict:
    """
    读取测试入口所需的 JSON 文件。

    Args:
        path: 要读取的 JSON 文件绝对路径。

    Returns:
        JSON 顶层对象。

    Raises:
        ValueError: 文件不是合法 JSON 或顶层不是对象。
    """
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"无法读取 JSON：{path}\n{error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象：{path}")
    return data


def load_plan_library(directory: Path, plan_kind: str) -> tuple[dict, dict, dict]:
    """
    只读加载方案目录，并同时建立名称与 UUID 索引。

    测试入口不调用主界面的自动修复函数，避免一次实战测试因为历史 UUID
    冲突而改写用户文件；遇到非法或冲突方案时直接报出具体路径。

    Args:
        directory: 战斗方案或微调方案目录。
        plan_kind: 用于错误信息的方案类型名称。

    Returns:
        ``(名称到 UUID, UUID 到路径, UUID 到 JSON 数据)``。

    Raises:
        ValueError: 方案缺少 UUID、UUID 重复或 JSON 无法解析。
    """
    name_to_uuid = {}
    uuid_to_path = {}
    uuid_to_data = {}

    for path in sorted(directory.glob("*.json"), key=lambda item: item.name.lower()):
        data = load_json(path)
        plan_uuid = data.get("meta_data", {}).get("uuid")
        if not isinstance(plan_uuid, str) or not plan_uuid:
            raise ValueError(f"{plan_kind}缺少有效 UUID：{path}")
        if plan_uuid in uuid_to_path:
            raise ValueError(
                f"{plan_kind} UUID 冲突：\n"
                f"- {uuid_to_path[plan_uuid]}\n"
                f"- {path}\n"
                f"UUID: {plan_uuid}"
            )
        name_to_uuid[path.stem] = plan_uuid
        uuid_to_path[plan_uuid] = str(path)
        uuid_to_data[plan_uuid] = data

    return name_to_uuid, uuid_to_path, uuid_to_data


def resolve_plan_reference(reference, name_to_uuid: dict, uuid_to_path: dict, plan_kind: str) -> str:
    """
    把方便人工填写的方案文件名或 UUID 统一转换为 UUID。

    Args:
        reference: 方案文件名、带 ``.json`` 的文件名或 UUID。
        name_to_uuid: 方案名称到 UUID 的索引。
        uuid_to_path: UUID 到方案路径的索引。
        plan_kind: 用于错误信息的方案类型名称。

    Returns:
        已确认存在的方案 UUID。

    Raises:
        ValueError: 引用为空或找不到对应方案。
    """
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError(f"{plan_kind}不能为空")

    reference = reference.strip()
    if reference in uuid_to_path:
        return reference

    plan_name = Path(reference).stem if reference.lower().endswith(".json") else reference
    if plan_name in name_to_uuid:
        return name_to_uuid[plan_name]

    similar_names = [name for name in name_to_uuid if plan_name.lower() in name.lower()][:10]
    hint = f"\n名称相近的方案：{similar_names}" if similar_names else ""
    raise ValueError(f"找不到{plan_kind}：{reference}{hint}")


def validate_battle_config(config: dict) -> None:
    """
    在接触游戏窗口之前检查容易误填的实战参数。

    Args:
        config: ``main`` 函数中定义的战斗配置。

    Raises:
        ValueError: 参数结构或取值不符合正式战斗入口要求。
    """
    required_keys = {
        "stage_id", "player", "max_times", "need_key", "deck",
        "battle_plan_1p", "battle_plan_2p", "battle_plan_tweak",
        "quest_card", "ban_card_list", "max_card_num",
        "global_plan_active", "is_cu", "dict_exit",
    }
    missing_keys = sorted(required_keys - config.keys())
    if missing_keys:
        raise ValueError(f"战斗配置缺少字段：{missing_keys}")

    if not isinstance(config["stage_id"], str) or not config["stage_id"].strip():
        raise ValueError("stage_id 必须是非空关卡代号")
    if config["player"] not in ([1], [2], [1, 2], [2, 1]):
        raise ValueError("player 只允许填写 [1]、[2]、[1, 2] 或 [2, 1]")
    if not isinstance(config["max_times"], int) or config["max_times"] < 1:
        raise ValueError("max_times 必须是大于等于 1 的整数")
    if not isinstance(config["deck"], int) or not 0 <= config["deck"] <= 6:
        raise ValueError("deck 只允许填写 0..6；0 表示自动带卡")
    if not isinstance(config["ban_card_list"], list):
        raise ValueError("ban_card_list 必须是列表")
    if config["max_card_num"] is not None and (
            not isinstance(config["max_card_num"], int) or isinstance(config["max_card_num"], bool)
    ):
        raise ValueError("max_card_num 只能是整数或 None")

    exit_config = config["dict_exit"]
    required_exit_keys = {
        "other_time_player_a", "other_time_player_b",
        "last_time_player_a", "last_time_player_b",
    }
    if not isinstance(exit_config, dict) or required_exit_keys - exit_config.keys():
        raise ValueError(f"dict_exit 必须包含字段：{sorted(required_exit_keys)}")
    if any(not isinstance(exit_config[key], list) for key in required_exit_keys):
        raise ValueError("dict_exit 中的四个退出动作字段都必须是列表")


def install_console_signals() -> None:
    """为无主界面的测试入口安装正式流程需要的信号替身。"""
    from function.globals import SIGNAL

    SIGNAL.PRINT_TO_UI = _ConsolePrint()
    SIGNAL.IMAGE_TO_UI = _ConsoleImage()
    SIGNAL.DIALOG = _ConsoleDialog()
    SIGNAL.END = _ConsoleEnd()


def initialize_runtime(settings: dict, config: dict):
    """
    按 FAA 主界面的顺序初始化资源、方案、窗口与战斗线程。

    Args:
        settings: 当前 ``config/settings.json`` 内容。
        config: 已通过基础校验的战斗配置。

    Returns:
        ``(QApplication, ThreadTodo, quest, 动作队列)``。

    Raises:
        ValueError: settings 缺少运行字段、方案不存在或游戏窗口未找到。
    """
    try:
        base_settings = settings["base_settings"]
        advanced_settings = settings["advanced_settings"]
        settings["senior_settings"]
    except KeyError as error:
        raise ValueError(f"当前 settings 缺少正式战斗所需字段：{error}") from error

    from PyQt6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])

    # 点击频率必须在动作队列和 FAA 实例创建前写入 EXTRA，否则它们会继续
    # 使用模块导入时的默认值，和当前 settings 的实战行为不一致。
    from function.globals import EXTRA

    EXTRA.CLICK_PER_SECOND = (
        advanced_settings.get("cus_cps_value", 120)
        if advanced_settings.get("cus_cps_active", False)
        else 120
    )

    install_console_signals()

    from function.globals import g_resources

    battle_names, battle_paths, battle_data = load_plan_library(
        REPOSITORY_ROOT / "battle_plan",
        "战斗方案",
    )
    tweak_names, tweak_paths, tweak_data = load_plan_library(
        REPOSITORY_ROOT / "tweak_plan",
        "微调方案",
    )

    resolved_config = copy.deepcopy(config)
    resolved_config["battle_plan_1p"] = resolve_plan_reference(
        config["battle_plan_1p"], battle_names, battle_paths, "1P 战斗方案"
    )
    resolved_config["battle_plan_2p"] = resolve_plan_reference(
        config["battle_plan_2p"], battle_names, battle_paths, "2P 战斗方案"
    )
    resolved_config["battle_plan_tweak"] = resolve_plan_reference(
        config["battle_plan_tweak"], tweak_names, tweak_paths, "战斗微调方案"
    )

    # 正式代码通过这些全局索引读取方案和打印名称。这里采用只读扫描结果，
    # 不运行会自动改写冲突 UUID 的主界面修复逻辑。
    EXTRA.BATTLE_PLAN_UUID_TO_PATH = battle_paths
    EXTRA.TWEAK_BATTLE_PLAN_UUID_TO_PATH = tweak_paths
    g_resources.RESOURCE_B = battle_data
    g_resources.RESOURCE_T = tweak_data

    from function.common.get_system_dpi import get_system_dpi
    from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

    EXTRA.ZOOM_RATE = get_system_dpi() / 96
    T_ACTION_QUEUE_TIMER.set_zoom_rate(EXTRA.ZOOM_RATE)

    from function.scattered.get_channel_name import get_channel_name

    channel_1p, channel_2p = get_channel_name(
        game_name=base_settings["game_name"],
        name_1p=base_settings["name_1p"],
        name_2p=base_settings["name_2p"],
    )

    from function.core.faa.faa_mix import FAA

    random_seed = random.randint(-100, 100)
    the_360_lock = threading.Lock()
    faa_dict = {
        1: FAA(
            channel=channel_1p,
            player=1,
            opt=settings,
            the_360_lock=the_360_lock,
            random_seed=random_seed,
        ),
        2: FAA(
            channel=channel_2p,
            player=2,
            opt=settings,
            the_360_lock=the_360_lock,
            random_seed=random_seed,
        ),
    }

    missing_windows = []
    for player_id, faa in faa_dict.items():
        if not faa.handle_360 or not faa.handle_browser or not faa.handle:
            missing_windows.append(
                f"{player_id}P：频道名“{faa.channel}”，"
                f"360={faa.handle_360}, browser={faa.handle_browser}, flash={faa.handle}"
            )
    if missing_windows:
        raise ValueError(
            "没有找到 settings 对应的完整游戏窗口。请把两个角色放在初始界面后重试：\n"
            + "\n".join(missing_windows)
        )

    from function.core.todo import ThreadTodo

    class ComplexBattleThread(ThreadTodo):
        """只执行配置中这一场战斗，不进入任务序列或刷新流程。"""

        def __init__(self):
            super().__init__(faa_dict=faa_dict, opt=settings, todo_id=1)
            self.failure = None

        def run(self):
            try:
                self.battle_1_n_n(
                    quest_list=[resolved_config],
                    extra_title="复杂关卡测试",
                )
            except BaseException as error:
                self.failure = (error, traceback.format_exc())

        def batch_reload_game(self, player=None):
            """
            屏蔽正式流程的异常恢复刷新。

            该人工入口约定两个角色已经位于初始界面，只验证进入地图及战斗
            本身。发生邀请、进房或选卡异常时保留正式流程的错误分支，但不
            刷新游戏，以免一次测试改变开发者提前准备好的窗口状态。

            Args:
                player: 正式恢复流程原本准备刷新的玩家列表；仅用于提示。
            """
            print(
                f"[复杂关卡测试] 正式流程请求刷新玩家 {player}，"
                "测试入口已按约定跳过刷新。",
                file=sys.stderr,
                flush=True,
            )

    todo = ComplexBattleThread()
    return application, todo, resolved_config, T_ACTION_QUEUE_TIMER


def describe_config(config: dict) -> None:
    """在控制台打印即将交给正式战斗入口的关键参数。"""
    print("[复杂关卡测试] 配置校验完成：")
    print(f"  关卡：{config['stage_id']}")
    print(f"  玩家顺序：{config['player']}")
    print(f"  卡组：{'自动带卡' if config['deck'] == 0 else config['deck']}")
    print(f"  1P 方案 UUID：{config['battle_plan_1p']}")
    print(f"  2P 方案 UUID：{config['battle_plan_2p']}")
    print(f"  微调方案 UUID：{config['battle_plan_tweak']}")
    print(f"  任务卡：{config['quest_card']}")
    print(f"  禁用卡：{config['ban_card_list']}")
    print(f"  限制数：{config['max_card_num']}")


def run_complex_battle(config: dict, settings_file: str, check_only: bool = False) -> int:
    """
    校验配置，并按需执行一次完整战斗。

    Args:
        config: ``main.py`` 中定义的本次战斗参数。
        settings_file: 要沿用的 FAA settings 文件（相对项目根目录）。
        check_only: 为 True 时只读加载并验证 settings、方案和窗口，不点击游戏。

    Returns:
        0 表示成功，1 表示配置或战斗流程失败。
    """
    validate_battle_config(config)
    settings_path = REPOSITORY_ROOT / settings_file
    settings = load_json(settings_path)
    application, todo, resolved_config, action_queue = initialize_runtime(
        settings=settings,
        config=config,
    )
    describe_config(resolved_config)

    if check_only:
        print("[复杂关卡测试] 仅校验模式，不会点击游戏窗口。")
        return 0

    print("[复杂关卡测试] 即将进入地图并开始战斗。按 Ctrl+C 可请求中止。")
    todo.finished.connect(application.quit)
    action_queue.start()
    try:
        todo.start()
        application.exec()
        todo.wait()
    finally:
        if todo.isRunning():
            todo.stop()
        if action_queue.isRunning():
            action_queue.stop()

    if todo.failure is not None:
        error, failure_traceback = todo.failure
        print(failure_traceback, file=sys.stderr)
        raise error

    print("[复杂关卡测试] 战斗入口执行完成。")
    return 0
