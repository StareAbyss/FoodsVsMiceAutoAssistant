import random
import sys

import win32con
import win32gui
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QApplication

from function.core.FAA import FAA
from function.core.QMW_2_log import QMainWindowLog
from function.core.QMW_EditorOfBattlePlan import QMWEditorOfBattlePlan
from function.core.QMW_TipBattle import QMWTipBattle
from function.core.QMW_TipStageID import QMWTipStageID
from function.core.QMW_TipWarmGift import QMWTipWarmGift
from function.core.Todo import ThreadTodo
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.TodoTimerManager import TodoTimerManager
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_channel_name import get_channel_name


class QMainWindowService(QMainWindowLog):
    signal_todo_end = pyqtSignal()
    signal_todo_start = pyqtSignal(int)  # 可通过该信号以某个 方案id 开启一趟流程

    def __init__(self):
        # 继承父类构造方法
        super().__init__()

        # 线程或线程管理实例
        self.thread_todo_1 = None
        self.thread_todo_2 = None  # 仅用于单人多线程时, 运行2P任务
        self.todo_timer_manager = TodoTimerManager(
            opt=self.opt,
            func_thread_todo_start=self.signal_todo_start
        )

        # 线程状态
        self.thread_todo_running = False
        self.todo_timer_running = False

        self.reply = None
        self.faa = [None, None, None]

        # 链接todo中止函数
        self.signal_todo_end.connect(self.todo_end)

        # 链接todo开始函数
        self.signal_todo_start.connect(self.todo_start)

        # 额外窗口 - 战斗方案编辑器
        self.window_editor = QMWEditorOfBattlePlan()
        self.OpenEditorOfBattlePlan_Button.clicked.connect(self.click_btn_open_editor)

        # 额外窗口 - 温馨礼包提示
        self.window_tip_warm_gift = QMWTipWarmGift()
        self.GetWarmGift_Button.clicked.connect(self.click_btn_tip_warm_gift)

        # 额外窗口 - 关卡代号提示
        self.window_tip_stage_id = QMWTipStageID()
        self.TipStageID_Button.clicked.connect(self.click_btn_tip_stage_id)

        # 额外窗口 - 战斗模式介绍
        self.window_tip_battle_is_show = False
        self.window_tip_battle = QMWTipBattle()
        self.TipBattle_Button.clicked.connect(self.click_btn_tip_battle)

        # 启动按钮 函数绑定
        self.Button_Start.clicked.connect(self.todo_click_btn)
        self.Button_StartTimer.clicked.connect(self.todo_timer_click_btn)
        self.Button_Save.clicked.connect(self.click_btn_save)

        # 方案修改按钮 函数绑定
        self.Button_DeletePlan.clicked.connect(self.delete_current_plan)
        self.Button_RenamePlan.clicked.connect(self.rename_current_plan)
        self.Button_CreatePlan.clicked.connect(self.create_new_plan)

        # 当前方案变化 函数绑定
        self.CurrentPlan.currentIndexChanged.connect(self.opt_to_ui_todo_plans)

        # 隐藏(拖动)窗口到屏幕视图外 函数绑定
        self.Button_Hide.clicked.connect(self.click_btn_hide_window)
        self.game_window_is_hide = False

    def todo_start(self, plan_index=None):
        """
        todo线程的启动函数
        手动启动时 plan_index为 none
        自动启动时 plan_index为 int 即对应的战斗方案的值
        """

        # 根据输入判断当前需要运行的方案的index
        if plan_index:
            running_todo_plan_index = plan_index
        else:
            running_todo_plan_index = self.CurrentPlan.currentIndex()

        # 先检测是否已经在启动状态, 如果是, 立刻关闭 然后继续执行
        if self.thread_todo_running:
            self.signal_print_to_ui.emit("[定时任务] 检测到线程已启动, 正在关闭", color="#C80000")
            self.todo_end()

        # 先读取界面上的方案
        self.ui_to_opt()

        # 获取窗口名称
        channel_1p, channel_2p = get_channel_name(
            game_name=self.opt["base_settings"]["game_name"],
            name_1p=self.opt["base_settings"]["name_1p"],
            name_2p=self.opt["base_settings"]["name_2p"])

        """防呆测试"""
        # 不通过就直接结束弹窗
        handles = {
            1: faa_get_handle(channel=channel_1p, mode="360"),
            2: faa_get_handle(channel=channel_2p, mode="360")}
        for player, handle in handles.items():
            if handle is None or handle == 0:
                # 报错弹窗
                self.signal_dialog.emit(
                    "出错！(╬◣д◢)",
                    f"{player}P存在错误的窗口名或游戏名称, 请参考 [使用前看我!.pdf] 或 [README.md]")
                return

        """UI处理"""
        # 设置flag
        self.thread_todo_running = True
        # 设置按钮文本
        self.Button_Start.setText("终止任务\nStop")
        if self.todo_timer_running:
            self.signal_print_to_ui.emit("", time=False)
            self.signal_print_to_ui.emit("[定时任务] 本次启动为 定时自启动 不清屏", color="#C80000")
        else:
            # 清屏并输出(仅限手动)
            self.TextBrowser.clear()
            self.start_print()
        # 设置输出文本
        self.signal_print_to_ui.emit("", time=False)
        self.signal_print_to_ui.emit("[任务事项] 链接开始 Todo线程开启", color="#C80000")
        # 当前正在运行 的 文本 修改
        running_todo_plan_name = self.opt["todo_plans"][running_todo_plan_index]["name"]
        self.Label_RunningState.setText(f"任务事项线程状态: 正在运行       运行方案: {running_todo_plan_name}")

        """线程处理"""
        # 启动点击处理线程
        T_ACTION_QUEUE_TIMER.start()

        # 生成随机数种子
        random_seed = random.randint(-100, 100)

        # 开始创建faa
        faa = [None, None, None]
        faa[1] = FAA(
            channel=channel_1p,
            player=1,
            character_level=self.opt["base_settings"]["level_1p"],
            is_auto_battle=self.opt["advanced_settings"]["auto_use_card"],  # bool 自动战斗
            is_auto_pickup=self.opt["advanced_settings"]["auto_pickup_1p"],
            random_seed=random_seed,
            signal_dict=self.signal_dict)
        faa[2] = FAA(
            channel=channel_2p,
            player=2,
            character_level=self.opt["base_settings"]["level_2p"],
            is_auto_battle=self.opt["advanced_settings"]["auto_use_card"],
            is_auto_pickup=self.opt["advanced_settings"]["auto_pickup_2p"],
            random_seed=random_seed,
            signal_dict=self.signal_dict)

        # 创建新的todo并启动线程
        self.thread_todo_1 = ThreadTodo(
            faa=faa,
            opt=self.opt,
            running_todo_plan_index=running_todo_plan_index,
            signal_dict=self.signal_dict,
            todo_id=1)
        # 用于双人多线程的todo
        self.thread_todo_2 = ThreadTodo(
            faa=faa,
            opt=self.opt,
            running_todo_plan_index=running_todo_plan_index,
            signal_dict=self.signal_dict,
            todo_id=2)

        # 链接信号以进行多线程单人
        self.thread_todo_1.signal_start_todo_2_battle.connect(self.thread_todo_2.set_extra_opt_and_start)
        self.thread_todo_2.signal_todo_lock.connect(self.thread_todo_1.change_lock)
        self.thread_todo_1.signal_todo_lock.connect(self.thread_todo_2.change_lock)
        self.thread_todo_1.start()

    def todo_end(self):
        """
            线程已经激活 则从外到内中断,再从内到外销毁
            thread_todo (QThread)
               |- thread_1p (ThreadWithException)
               |- thread_2p (ThreadWithException)
        """

        """线程处理"""
        for thread_0 in [self.thread_todo_1, self.thread_todo_2]:
            # 暂停外部线程
            thread_0.pause()

            # 中断[内部战斗线程]
            # Q thread 线程 stop方法需要自己手写

            manager = thread_0.thread_card_manager
            if manager is not None:
                manager.stop()

            # python 默认线程 可用stop线程
            for thread in [thread_0.thread_1p, thread_0.thread_2p]:
                if thread is not None:
                    thread.stop()
                    thread.join()  # 等待线程确实中断 Threading

            # 中断 销毁 [任务线程]
            thread_0.terminate()
            thread_0.wait()  # 等待线程确实中断 QThread
            thread_0.deleteLater()

        # 中止[动作处理线程]
        T_ACTION_QUEUE_TIMER.stop()

        """UI处理"""
        # 设置flag
        self.thread_todo_running = False
        # 设置按钮文本
        self.Button_Start.setText("开始任务\nLink Start")
        # 设置输出文本
        self.signal_print_to_ui.emit("[任务事项] 已关闭全部线程", color="#C80000")
        # 当前正在运行 的 文本 修改
        self.Label_RunningState.setText(f"任务事项线程状态: 未运行")

    def todo_click_btn(self):
        """战斗开始函数"""

        # 线程没有激活
        if not self.thread_todo_running:
            self.todo_start()
        else:
            self.todo_end()

    def todo_timer_start(self):
        # 先读取界面上的方案
        self.ui_to_opt()
        # 清屏并输出
        self.TextBrowser.clear()
        self.start_print()
        # 设置按钮文本
        self.Button_StartTimer.setText("关闭定时任务\nTimer Stop")
        # 设置输出文本
        self.signal_print_to_ui.emit("", time=False)
        self.signal_print_to_ui.emit("[定时任务] 已启动!", color="#C80000")
        # 设置Flag
        self.todo_timer_running = True
        # 新设todo timer manager的opt
        self.todo_timer_manager.set_opt(self.opt)
        # 启动线程群
        self.todo_timer_manager.start()
        # 锁定相关设置的ui
        for i in range(1, 6):
            for comp in ['Active', 'H', 'M', 'Plan']:
                getattr(self, f'Timer{i}_{comp}').setEnabled(False)

    def todo_timer_stop(self):
        # 设置按钮文本
        self.Button_StartTimer.setText("启动定时任务\nTimer Start")
        # 设置输出文本
        self.signal_print_to_ui.emit("", time=False)
        self.signal_print_to_ui.emit("[定时任务] 定时作战已关闭!", color="#C80000")
        # 设置Flag
        self.todo_timer_running = False
        # 关闭线程群
        self.todo_timer_manager.stop()
        # 解锁相关设置的ui
        for i in range(1, 6):
            for comp in ['Active', 'H', 'M', 'Plan']:
                getattr(self, f'Timer{i}_{comp}').setEnabled(True)

    def todo_timer_click_btn(self):
        """开始计时器"""

        if not self.todo_timer_running:
            # 线程没有激活
            self.todo_timer_start()
        else:
            self.todo_timer_stop()

    def click_btn_open_editor(self):
        self.window_editor.set_my_font(self.font)
        self.window_editor.show()

    def click_btn_tip_warm_gift(self):
        self.window_tip_warm_gift.setFont(self.font)
        self.window_tip_warm_gift.show()

    def click_btn_tip_stage_id(self):
        self.window_tip_stage_id.setFont(self.font)
        self.window_tip_stage_id.show()

    def click_btn_tip_battle(self):
        self.window_tip_battle.setFont(self.font)
        if self.window_tip_battle_is_show:
            self.window_tip_battle.hide()
            self.window_tip_battle_is_show = False
        else:
            self.window_tip_battle.show()
            self.window_tip_battle_is_show = True

    def click_btn_hide_window(self):
        """因为 Flash 在窗口外无法正常渲染画面(Chrome可以), 所以老板键只能做成z轴设为最低级"""
        # 获取窗口名称
        channel_1p, channel_2p = get_channel_name(
            game_name=self.opt["base_settings"]["game_name"],
            name_1p=self.opt["base_settings"]["name_1p"],
            name_2p=self.opt["base_settings"]["name_2p"])

        # 不通过就直接结束弹窗
        handles = {
            1: faa_get_handle(channel=channel_1p, mode="360"),
            2: faa_get_handle(channel=channel_2p, mode="360")}
        for player, handle in handles.items():
            if handle is None or handle == 0:
                # 报错弹窗
                self.signal_dialog.emit(
                    "出错！(╬◣д◢)",
                    f"{player}P存在错误的窗口名或游戏名称, 请参考 [使用前看我!.pdf] 或 [README.md]")
                return

        if self.game_window_is_hide:
            for p_id in [1, 2]:
                handle = handles[p_id]
                # 激活目标窗口
                win32gui.SetForegroundWindow(handle)
                # 将窗口置于顶部
                win32gui.SetWindowPos(
                    handle,
                    win32con.HWND_TOP,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                )
                # win32gui.ShowWindow(handle, win32con.SW_SHOW)
                # 也许有一天能写出真正的老板键 大概
            # 把FAA窗口置顶
            # 激活目标窗口
            handle = self.winId()
            win32gui.SetForegroundWindow(handle)
            # 将窗口置于顶部
            win32gui.SetWindowPos(
                handle,
                win32con.HWND_TOP,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            self.game_window_is_hide = False
        else:
            for p_id in [1, 2]:
                handle = handles[p_id]
                # 将窗口置于Z序的底部，但不改变活动状态
                win32gui.SetWindowPos(
                    handle,
                    win32con.HWND_BOTTOM,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                # win32gui.ShowWindow(handle,0)
                # 也许有一天能写出真正的老板键 大概
            self.game_window_is_hide = True


def faa_start_main():
    # 实例化 PyQt后台管理
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # 启用高DPI缩放
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # 使用高DPI图标和图像

    # 实例化 主窗口
    window = QMainWindowService()

    # 主窗口 实现
    window.show()

    # 运行主循环，必须调用此函数才可以开始事件处理
    sys.exit(app.exec_())


if __name__ == "__main__":
    faa_start_main()
