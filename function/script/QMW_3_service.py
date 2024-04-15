import random
import sys

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QApplication

from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.TodoTimerManager import TodoTimerManager
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_channel_name import get_channel_name
from function.script.FAA import FAA
from function.script.QMW_2_log import QMainWindowLog
from function.script.ThreadTodo import ThreadTodo
from function.tools.editor_of_battle_plan import JsonEditor


class QMainWindowService(QMainWindowLog):
    signal_end = pyqtSignal()
    signal_todo_start = pyqtSignal()
    signal_change_current_todo_plan = pyqtSignal(int)

    def __init__(self):
        # 继承父类构造方法
        super().__init__()
        # 线程或线程管理实例
        self.thread_todo_1 = None
        self.todo_timer_manager = TodoTimerManager(
            opt=self.opt,
            function_change_current_todo_plan=self.signal_change_current_todo_plan,
            function_thread_todo_start=self.signal_todo_start
        )

        # 线程状态
        self.thread_todo_running = False
        self.todo_timer_running = False

        self.reply = None
        self.faa = [None, None, None]

        # 链接中止函数
        self.signal_end.connect(self.todo_end)

        # 编辑器窗口
        self.window_editor = JsonEditor()

        #
        self.signal_change_current_todo_plan.connect(self.change_current_todo_plan)
        self.signal_todo_start.connect(self.todo_start)

        # 启动按钮函数绑定
        self.Button_Start.clicked.connect(self.todo_click_btn)
        self.Button_StartTimer.clicked.connect(self.todo_timer_click_btn)
        self.Button_Save.clicked.connect(self.click_btn_save)

        # 方案修改按钮函数绑定
        self.Button_DeletePlan.clicked.connect(self.delete_current_plan)
        self.Button_RenamePlan.clicked.connect(self.rename_current_plan)
        self.Button_CreatePlan.clicked.connect(self.create_new_plan)

        # 当前方案变化 函数绑定
        self.CurrentPlan.currentIndexChanged.connect(self.opt_to_ui_todo_plans)
        self.OpenEditorOfBattlePlan_Button.clicked.connect(self.click_btn_open_editor)

    def todo_start(self):
        """todo线程的启动函数"""

        # 先检测是否已经在启动状态, 如果是, 立刻关闭 然后继续执行
        if self.thread_todo_running:
            self.signal_print_to_ui.emit("[定时任务] 检测到线程已启动, 正在关闭", color="blue")
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
            self.signal_print_to_ui.emit("[定时任务] 本次启动为 定时自启动 不清屏", color="blue")
        else:
            # 清屏并输出(仅限手动)
            self.TextBrowser.clear()
            self.start_print()
        # 设置输出文本
        self.signal_print_to_ui.emit("[任务事项] 链接开始 Todo线程开启", color="blue")

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
        self.thread_todo_1 = ThreadTodo(faa=faa, opt=self.opt, signal_dict=self.signal_dict,todo_id=1)

        self.thread_todo_1.start()

    def todo_end(self):
        """
                  线程已经激活 则从外到内中断,再从内到外销毁
                  thread_todo (QThread)
                      |-- thread_1p (ThreadWithException)
                      |-- thread_2p (ThreadWithException)
                  """
        # 暂停外部线程
        self.thread_todo.pause()

        # 中断[内部战斗线程]
        # Q thread 线程 stop方法需要自己手写
        thread = self.thread_todo.thread_card_manager
        if thread is not None:
            thread.stop()

        # python 默认线程 可用stop线程
        for thread in [self.thread_todo.thread_1p, self.thread_todo.thread_2p]:
            if thread is not None:
                thread.stop()
                thread.join()  # 等待线程确实中断

        # 中断 销毁 [任务线程]
        self.thread_todo.terminate()
        self.thread_todo.wait()  # 等待线程确实中断
        self.thread_todo.deleteLater()

        # 中止[动作处理线程]
        T_ACTION_QUEUE_TIMER.stop()

        """UI处理"""
        # 设置flag
        self.thread_todo_running = False
        # 设置按钮文本
        self.Button_Start.setText("开始任务\nLink Start")
        # 设置输出文本
        self.signal_print_to_ui.emit("[任务事项] 已关闭全部线程", color="blue")

    def todo_click_btn(self):
        """战斗开始函数"""

        # 线程没有激活
        if not self.thread_todo_running:
            self.todo_start()
        else:
            self.todo_end()

    def change_current_todo_plan(self, plan_index):
        # 先更改ui中的当前选中方案
        self.CurrentPlan.setCurrentIndex(plan_index)
        # 再加载ui的设定到程序
        self.ui_to_opt()

    def todo_timer_start(self):
        # 先读取界面上的方案
        self.ui_to_opt()
        # 清屏并输出
        self.TextBrowser.clear()
        self.start_print()
        # 设置按钮文本
        self.Button_StartTimer.setText("关闭定时任务\nTimer Stop")
        # 设置输出文本
        self.signal_print_to_ui.emit("[定时任务] 已启动!", color="blue")
        # 设置Flag
        self.todo_timer_running = True
        # 新设todo timer manager的opt
        self.todo_timer_manager.set_opt(self.opt)
        # 启动线程群
        self.todo_timer_manager.start()

    def todo_timer_stop(self):
        # 设置按钮文本
        self.Button_StartTimer.setText("启动定时任务\nTimer Start")
        # 设置输出文本
        self.signal_print_to_ui.emit("[定时任务] 定时作战已关闭!", color="blue")
        # 设置Flag
        self.todo_timer_running = False
        # 关闭线程群
        self.todo_timer_manager.stop()

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


def main():
    # 实例化 PyQt后台管理
    app = QApplication(sys.argv)

    # 实例化 主窗口
    window = QMainWindowService()

    # 主窗口 实现
    window.show()

    # 运行主循环，必须调用此函数才可以开始事件处理
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
