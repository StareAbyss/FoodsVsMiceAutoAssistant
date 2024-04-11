import random
import sys

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QApplication

from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_channel_name import get_channel_name
from function.script.FAA import FAA
from function.script.QMW_2_log import QMainWindowLog
from function.script.Todo import Todo
from function.tools.editor_of_battle_plan import JsonEditor


class QMainWindowService(QMainWindowLog):
    signal_end = pyqtSignal()

    def __init__(self):
        # 继承父类构造方法
        super().__init__()
        self.thread_todo = None
        self.thread_todo_active = False

        self.reply = None
        self.faa = [None, None, None]

        # 链接中止函数
        self.signal_end.connect(self.todo_end)

        # 编辑器窗口
        self.window_editor = JsonEditor()

        # 注册函数：开始/结束/高级设置按钮
        self.Button_Start.clicked.connect(self.click_btn_start)
        self.Button_Save.clicked.connect(self.click_btn_save)
        self.Button_DeletePlan.clicked.connect(self.delete_current_plan)
        self.Button_RenamePlan.clicked.connect(self.rename_current_plan)
        self.Button_CreatePlan.clicked.connect(self.create_new_plan)
        self.CurrentPlan.currentIndexChanged.connect(self.opt_to_ui_todo_plans)
        self.OpenEditorOfBattlePlan_Button.clicked.connect(self.click_btn_open_editor)

    def todo_end(self):
        # 设置flag
        self.thread_todo_active = False
        # 设置按钮文本
        self.Button_Start.setText("开始\nLink Start")
        # 设置输出文本
        self.signal_print_to_ui.emit("\n>>> 全部完成 线程关闭 <<<\n")
        # 中止点击处理
        T_ACTION_QUEUE_TIMER.stop()

    def todo_start(self):
        # 设置flag
        self.thread_todo_active = True
        # 设置按钮文本
        self.Button_Start.setText("终止\nEnd")
        # 设置输出文本
        self.TextBrowser.clear()
        self.start_print()
        self.signal_print_to_ui.emit("\n>>> 链接开始 线程开启 <<<\n")
        # 启动点击处理
        T_ACTION_QUEUE_TIMER.start()

    def start_all(self):

        # 先读取界面上的方案
        self.ui_to_opt()

        channel_1p, channel_2p = get_channel_name(
            game_name=self.opt["base_settings"]["game_name"],
            name_1p=self.opt["base_settings"]["name_1p"],
            name_2p=self.opt["base_settings"]["name_2p"])
        # 防呆测试 不通过就直接结束弹窗
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

        self.todo_start()

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

        # 创造todo线程
        self.thread_todo = Todo(faa=faa, opt=self.opt, signal_dict=self.signal_dict)

        # 开始线程
        self.thread_todo.start()

    def stop_all(self):
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

        # 结束线程后的ui处理
        self.todo_end()

    def click_btn_start(self):
        """战斗开始函数"""

        # 线程没有激活
        if not self.thread_todo_active:
            self.start_all()
        else:
            self.stop_all()

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
