import datetime
import json
import os
import random
import shutil
import sys

import win32con
import win32gui
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QMessageBox

from function.core.FAA import FAA
from function.core.FAA_extra_readimage import kill_process
from function.core.QMW_2_load_settings import CommonHelper, QMainWindowLoadSettings
from function.core.QMW_EditorOfBattlePlan import QMWEditorOfBattlePlan
from function.core.QMW_EditorOfTaskSequence import QMWEditorOfTaskSequence
from function.core.QMW_SettingsMigrator import QMWSettingsMigrator
from function.core.QMW_TipBattle import QMWTipBattle
from function.core.QMW_TipBattleSenior import QMWTipBattleSenior
from function.core.QMW_TipEditorOfBattlePlan import QMWTipEditorOfBattlePlan
from function.core.QMW_TipLevel2 import QMWTipLevels2
from function.core.QMW_TipMisuLogistics import QMWTipMisuLogistics
from function.core.QMW_TipStageID import QMWTipStageID
from function.core.QMW_TipWarmGift import QMWTipWarmGift
from function.core.Todo import ThreadTodo
from function.core.performance_analysis import run_analysis_in_thread
from function.globals import EXTRA, SIGNAL
from function.globals import g_resources
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.TodoTimerManager import TodoTimerManager
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_channel_name import get_channel_name
from function.scattered.get_stage_info_online import get_stage_info_online
from function.scattered.test_route_connectivity import test_route_connectivity


class QMainWindowService(QMainWindowLoadSettings):
    signal_todo_end = QtCore.pyqtSignal()
    signal_todo_start = QtCore.pyqtSignal(int)  # 可通过该信号以某个 方案id 开启一趟流程
    signal_guild_manager_fresh = QtCore.pyqtSignal()  # 刷新公会管理器数据, 于扫描后

    def __init__(self):
        # 继承父类构造方法
        super().__init__()

        # 添加一些信号到列表中方便调用
        SIGNAL.GUILD_MANAGER_FRESH = self.signal_guild_manager_fresh
        SIGNAL.END = self.signal_todo_end

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
        self.window_tip_editor_of_battle_plan = QMWTipEditorOfBattlePlan()
        self.window_editor_of_battle_plan = QMWEditorOfBattlePlan(
            func_open_tip=self.click_btn_tip_editor_of_battle_plan)
        self.OpenEditorOfBattlePlan_Button.clicked.connect(self.click_btn_open_editor_of_battle_plan)

        # 额外窗口 - 任务序列编辑器
        self.window_editor_of_task_sequence = QMWEditorOfTaskSequence()
        self.OpenEditorOfTaskSequence_Button.clicked.connect(self.click_btn_open_editor_of_task_sequence)

        # 额外窗口 - 配置迁移器
        self.window_settings_migrator = QMWSettingsMigrator()
        self.OpenSettingsMigrator_Button.clicked.connect(self.click_btn_open_settings_migrator)

        # 额外窗口 - 温馨礼包提示
        self.window_tip_warm_gift = QMWTipWarmGift()
        self.GetWarmGift_Button.clicked.connect(self.click_btn_tip_warm_gift)

        # 额外窗口 - 关卡代号提示
        self.window_tip_stage_id = QMWTipStageID()
        self.TipStageID_Button.clicked.connect(self.click_btn_tip_stage_id)

        # 额外窗口 - 战斗模式介绍
        self.window_tip_battle = QMWTipBattle()
        self.TipBattle_Button.clicked.connect(self.click_btn_tip_battle)

        # 额外窗口 - 二级说明书
        self.window_tip_level2 = QMWTipLevels2()
        self.Level2_Tip.clicked.connect(self.click_btn_tip_level2)

        # 额外窗口 - 高级战斗说明
        self.window_tip_battle_senior = QMWTipBattleSenior()
        self.Battle_senior_Tip.clicked.connect(self.click_btn_tip_battle_senior)

        # 米苏物流 - tip窗口
        self.window_tip_misu_logistics = QMWTipMisuLogistics()
        self.MisuLogistics_Tip.clicked.connect(self.click_btn_tip_misu_logistics)

        # 米苏物流 - 测试链接
        self.MisuLogistics_LinkTest.clicked.connect(self.click_btn_misu_logistics_link_test)
        # 米苏物流 - 获取线上关卡信息
        self.MisuLogistics_GetStageInfoOnline.clicked.connect(self.click_btn_misu_logistics_get_stage_info_online)
        # 米苏物流 - 设定默认
        self.MisuLogistics_Link_SetDefault.clicked.connect(self.click_btn_misu_logistics_set_default)

        # 启动按钮 函数绑定
        self.Button_Start.clicked.connect(self.todo_click_btn)
        self.Button_StartTimer.clicked.connect(self.todo_timer_click_btn)

        # 保存方案按钮 函数绑定
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

        # 重置卡片状态自学习记忆
        self.Btn_ResetCardStatusMemory.clicked.connect(self.click_btn_reset_card_status_memory)

        # 线程状态
        self.is_ending = False  # 线程是否正在结束
        self.is_start = False  # 线程是否正在启动

        """公会管理器相关"""
        # 初始化工会管理器数据和表格视图
        self.guild_manager_table_init()
        self.guild_manager_data = []
        self.guild_manager_table_load_data()

        # 绑定信号和槽函数, 在更新数据文件后更新内部数据表
        SIGNAL.GUILD_MANAGER_FRESH.connect(self.guild_manager_table_load_data)

        # 根据日历日期，调整表格视图
        self.DateSelector.selectionChanged.connect(self.guild_manager_table_update)

        # 连接自定义信号到槽函数，从而修改编辑框内容
        self.Label_drag.windowNameChanged1.connect(self.updateEditBox1)
        self.Label_drag.windowNameChanged2.connect(self.updateEditBox2)

    """工会管理器页面"""

    def guild_manager_table_init(self):
        """
        初始化公会管理器数据，主要是表头和第一列的图片，其他部分占位
        """

        # 设置表格基础属性
        self.GuildMemberInfoTable.setColumnCount(7)
        self.GuildMemberInfoTable.setHorizontalHeaderLabels(['成员', '贡献', '天', '周', '月', '年', '上次更新'])

        # 调整行高
        self.GuildMemberInfoTable.verticalHeader().setDefaultSectionSize(40)

        # 调整列宽
        header = self.GuildMemberInfoTable.horizontalHeader()
        header.resizeSection(0, 98)  # 设置第一列宽度
        for i in range(1, self.GuildMemberInfoTable.columnCount()):
            header.resizeSection(i, 70)  # 设置其余列宽度

        # 启用表头排序功能
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        self.GuildMemberInfoTable.setSortingEnabled(True)

    def guild_manager_table_load_data(self):
        # guild manager 相关
        guild_manager_file = f"{PATHS['logs']}\\guild_manager\\guild_manager_data.json"
        # 额外窗口，公会管理器
        if os.path.exists(guild_manager_file):
            with EXTRA.FILE_LOCK:
                with open(file=guild_manager_file, mode='r', encoding='utf-8') as file:
                    self.guild_manager_data = json.load(file)

        # 根据目前选择的日期刷新一下数据
        self.guild_manager_table_update()

    def guild_manager_table_update(self):
        """
        根据日期，改变表格显示内容, 绑定触发器 - 日历切换日期
        """

        # 先清空排序状态
        self.GuildMemberInfoTable.sortByColumn(-1, QtCore.Qt.SortOrder.AscendingOrder)

        # 清空表格内容
        self.GuildMemberInfoTable.setRowCount(0)

        # 添加图片
        for member in self.guild_manager_data:
            row_position = self.GuildMemberInfoTable.rowCount()
            self.GuildMemberInfoTable.insertRow(row_position)

            # 添加成员图片
            member_hash = member['name_image_hash']
            name_image_path = f"{PATHS['logs']}\\guild_manager\\guild_member_images\\{member_hash}.png"
            pixmap = QtGui.QPixmap(name_image_path)
            qtw_item = QtWidgets.QTableWidgetItem()

            # 设置单元格图片
            qtw_item.setData(QtCore.Qt.ItemDataRole.DecorationRole, pixmap)

            # 设置单元格不可编辑
            qtw_item.setFlags(qtw_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

            self.GuildMemberInfoTable.setItem(row_position, 0, qtw_item)

        def add_data_widget_into_table(value, row, col):
            """
            根据输入 是否小于0 以不同形式录入 以 支持排序
            :param value: 如果小于0 代表其实是未知数
            :param row:
            :param col:
            :return:
            """
            qtw_item = QtWidgets.QTableWidgetItem()
            # 将整数类型的贡献值填充到表格中
            if value < 0:
                qtw_item.setData(
                    QtCore.Qt.ItemDataRole.DisplayRole,
                    "Unknown")
            else:
                qtw_item.setData(
                    QtCore.Qt.ItemDataRole.DisplayRole,
                    int(value))

            # 设置单元格不可编辑
            qtw_item.setFlags(qtw_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

            self.GuildMemberInfoTable.setItem(row, col, qtw_item)

        selected_date = self.DateSelector.selectedDate()

        # 遍历成员数据 因为图片也是按照guild_manager_data顺序来的, 所以可以直接无脑遍历
        row_position = 0

        for member in self.guild_manager_data:

            # 获取成员数据
            member_data = member.get('data', {})
            member_data_week = member.get('data_week', {})

            # 刷新第二列数据（当天贡献）
            today_contribution = member_data.get(selected_date.toString('yyyy-MM-dd'), -1)
            add_data_widget_into_table(value=today_contribution, row=row_position, col=1)

            # 刷新第三列数据（昨天到今天的变化值）
            yesterday = selected_date.addDays(-1)
            yesterday_contribution = member_data.get(yesterday.toString('yyyy-MM-dd'), -1)
            if today_contribution > 0 and yesterday_contribution > 0:
                value = today_contribution - yesterday_contribution
            else:
                value = -1
            add_data_widget_into_table(value=value, row=row_position, col=2)

            # 刷新第四列数据（尝试读取周贡献）
            today_contribution_week = member_data_week.get(selected_date.toString('yyyy-MM-dd'), -1)
            add_data_widget_into_table(value=today_contribution_week, row=row_position, col=3)

            # 刷新第五列数据（上个月最后一天到今天的变化值）
            last_month = selected_date.addMonths(-1)
            last_day_of_last_month = QtCore.QDate(last_month.year(), last_month.month(), last_month.daysInMonth())
            last_day_of_last_month_str = last_day_of_last_month.toString('yyyy-MM-dd')
            last_day_of_last_month_contribution = member_data.get(last_day_of_last_month_str, -1)
            if today_contribution > 0 and last_day_of_last_month_contribution > 0:
                value = today_contribution - last_day_of_last_month_contribution
            else:
                value = -1
            add_data_widget_into_table(value=value, row=row_position, col=4)

            # 刷新第六列数据（去年最后一天到今天的变化值）
            last_year = selected_date.addYears(-1)
            last_day_of_last_year = QtCore.QDate(last_year.year(), last_year.month(), last_year.daysInMonth())
            last_day_of_last_year_str = last_day_of_last_year.toString('yyyy-MM-dd')
            last_day_of_last_year_contribution = member_data.get(last_day_of_last_year_str, -1)
            if today_contribution > 0 and last_day_of_last_year_contribution > 0:
                value = today_contribution - last_day_of_last_year_contribution
            else:
                value = -1
            add_data_widget_into_table(value=value, row=row_position, col=5)

            # 刷新第七列数据（上次更新）
            today_str = datetime.date.today().strftime('%Y-%m-%d')
            last_update_date_str = max(member_data.keys(), default="Never")
            if last_update_date_str == "Never":
                value = "从未"
            elif last_update_date_str == today_str:
                value = "今天"
            else:
                today_q_date = QtCore.QDate.fromString(today_str, 'yyyy-MM-dd').toPyDate()
                last_q_date = QtCore.QDate.fromString(last_update_date_str, 'yyyy-MM-dd').toPyDate()
                days_since_last_update = (today_q_date - last_q_date).days
                value = f"{days_since_last_update}天前"
            qtw_item = QtWidgets.QTableWidgetItem()
            qtw_item.setData(QtCore.Qt.ItemDataRole.DisplayRole, value)
            self.GuildMemberInfoTable.setItem(row_position, 6, qtw_item)

            row_position += 1

        self.GuildMemberInfoTable.sortByColumn(1, QtCore.Qt.SortOrder.DescendingOrder)  # 降序排序

    def updateEditBox1(self, window_name: str):

        """更新1P编辑框内容的槽函数"""
        if '|' in window_name:
            names = window_name.split('|')
            self.Name1P_Input.setText(names[0].strip())
            self.GameName_Input.setText(names[1].strip())
        else:
            self.Name1P_Input.setText("")
            self.GameName_Input.setText(window_name)

    def updateEditBox2(self, window_name):
        """更新2P编辑框内容的槽函数"""
        if '|' in window_name:
            names = window_name.split('|')
            self.Name2P_Input.setText(names[0].strip())
            self.GameName_Input.setText(names[1].strip())
        else:
            self.Name2P_Input.setText("")
            self.GameName_Input.setText(window_name)

    """主线程管理"""

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
            SIGNAL.PRINT_TO_UI.emit("[定时任务] 检测到线程已启动, 正在关闭", color_level=1)
            self.todo_end()

        # 先读取界面上的方案
        # self.ui_to_opt()

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
                SIGNAL.DIALOG.emit(
                    "出错！(╬◣д◢)",
                    f"{player}P存在错误的窗口名或游戏名称, 请参考 [使用前看我!.pdf] 或 [README.md]")
                self.Button_Start.setText("开始任务\nLink Start")
                self.is_start = False
                return

        """UI处理"""
        # 设置flag
        self.thread_todo_running = True
        # 设置按钮文本
        self.Button_Start.setText("终止任务\nStop")
        if self.todo_timer_running:
            SIGNAL.PRINT_TO_UI.emit("", time=False)
            SIGNAL.PRINT_TO_UI.emit("[定时任务] 本次启动为 定时自启动 不清屏", color_level=1)
        else:
            # 清屏并输出(仅限手动)
            self.TextBrowser.clear()
            self.start_print()
        # 设置输出文本
        SIGNAL.PRINT_TO_UI.emit("", time=False)
        SIGNAL.PRINT_TO_UI.emit("[任务事项] 链接开始 Todo线程开启", color_level=1)
        # 当前正在运行 的 文本 修改
        running_todo_plan_name = self.opt["todo_plans"][running_todo_plan_index]["name"]
        self.Label_RunningState.setText(f"任务事项线程状态: 正在运行       运行方案: {running_todo_plan_name}")

        """线程处理"""
        # 启动点击处理线程
        T_ACTION_QUEUE_TIMER.start()

        # 生成随机数种子
        random_seed = random.randint(-100, 100)

        # 开始创建faa
        faa_dict = {
            1: FAA(
                channel=channel_1p,
                player=1,
                character_level=self.opt["base_settings"]["level_1p"],
                is_auto_battle=self.opt["advanced_settings"]["auto_use_card"],
                is_auto_pickup=self.opt["advanced_settings"]["auto_pickup_1p"],
                random_seed=random_seed),
            2: FAA(
                channel=channel_2p,
                player=2,
                character_level=self.opt["base_settings"]["level_2p"],
                is_auto_battle=self.opt["advanced_settings"]["auto_use_card"],
                is_auto_pickup=self.opt["advanced_settings"]["auto_pickup_2p"],
                random_seed=random_seed)
        }

        # 创建新的todo并启动线程
        self.thread_todo_1 = ThreadTodo(
            faa_dict=faa_dict,
            opt=self.opt,
            running_todo_plan_index=running_todo_plan_index,
            todo_id=1)

        # 用于双人多线程的todo
        self.thread_todo_2 = ThreadTodo(
            faa_dict=faa_dict,
            opt=self.opt,
            running_todo_plan_index=running_todo_plan_index,
            todo_id=2)

        # 链接信号以进行多线程单人
        self.thread_todo_1.signal_start_todo_2_battle.connect(self.thread_todo_2.set_extra_opt_and_start)
        self.thread_todo_2.signal_todo_lock.connect(self.thread_todo_1.change_lock)
        self.thread_todo_1.signal_todo_lock.connect(self.thread_todo_2.change_lock)

        # 启动线程
        self.thread_todo_1.start()

        self.is_start = False  # 完成完整启动

    def todo_end(self):
        """
            线程已经激活 则从外到内中断,再从内到外销毁
            thread_todo (QThread)
               |- thread_1p (ThreadWithException)
               |- thread_2p (ThreadWithException)
        """

        """线程处理"""
        self.is_ending = True
        for thread_0 in [self.thread_todo_1, self.thread_todo_2]:
            if thread_0 is not None:
                # 暂停外部线程
                # thread_0.pause()
                #
                # # 中断[内部战斗线程]
                # # Q thread 线程 stop方法需要自己手写
                # python 默认线程 可用stop线程
                for thread in [thread_0.thread_1p, thread_0.thread_2p]:
                    if thread is not None:
                        thread.stop()
                        # thread.join()  # <-罪魁祸首在此

                process = thread_0.process
                if process is not None:
                    kill_process(process)  # 杀死识图进程

                manager = thread_0.thread_card_manager
                if manager is not None:
                    manager.stop()

                # 释放战斗锁
                if thread_0.faa_dict:
                    for faa in thread_0.faa_dict.values():
                        if faa:
                            lock = faa.battle_lock
                            if lock.locked():
                                lock.release()

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
        SIGNAL.PRINT_TO_UI.emit("[任务事项] 已关闭全部线程", color_level=1)
        # 当前正在运行 的 文本 修改
        self.Label_RunningState.setText(f"任务事项线程状态: 未运行")
        self.is_ending = False  # 完成完整的线程结束

    def todo_click_btn(self):
        """战斗开始函数"""

        # 线程没有激活
        if not (self.thread_todo_running or self.is_ending or self.is_start):
            self.todo_start()
        elif not self.is_ending:  # 加强鲁棒性，用于防熊
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
        SIGNAL.PRINT_TO_UI.emit("", time=False)
        SIGNAL.PRINT_TO_UI.emit("[定时任务] 已启动!", color_level=1)
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
        SIGNAL.PRINT_TO_UI.emit("", time=False)
        SIGNAL.PRINT_TO_UI.emit("[定时任务] 定时作战已关闭!", color_level=1)
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

    """其他"""

    def set_stylesheet(self, widget):
        # 定义一个字典，将复选框对象映射到对应的值
        skin_dict = {
            self.skin1: 1,
            self.skin2: 2,
            self.skin3: 3,
            self.skin4: 4,
            self.skin5: 5,
            self.skin6: 6,
            self.skin7: 7,
            self.skin8: 8,
            self.skin9: 9,
            self.skin10: 10,
            self.skin11: 11
        }

        # 遍历字典，找到第一个被选中的复选框
        for skin, option in skin_dict.items():
            if skin.isChecked():
                my_opt = option
                break

        styleFile = self.getstylefile(my_opt)
        if styleFile is not None:
            qssStyle = CommonHelper.readQss(styleFile)
            widget.setStyleSheet(qssStyle)
        else:
            widget.setStyleSheet("")

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
                SIGNAL.DIALOG.emit(
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

    """打开其他窗口"""

    def click_btn_open_editor_of_battle_plan(self):
        window = self.window_editor_of_battle_plan
        window.set_my_font(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_open_editor_of_task_sequence(self):
        window = self.window_editor_of_task_sequence
        window.set_my_font(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_open_settings_migrator(self):
        window = self.window_settings_migrator
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_tip_warm_gift(self):
        window = self.window_tip_warm_gift
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_tip_stage_id(self):
        window = self.window_tip_stage_id
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_tip_battle(self):
        window = self.window_tip_battle
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_tip_level2(self):
        window = self.window_tip_level2
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_tip_battle_senior(self):
        window = self.window_tip_battle_senior
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_tip_editor_of_battle_plan(self):
        window = self.window_tip_editor_of_battle_plan
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_tip_misu_logistics(self):
        window = self.window_tip_misu_logistics
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()

    """测试网络"""

    def click_btn_misu_logistics_link_test(self):

        url = self.MisuLogistics_Link.text()
        if not url:
            url = None  # 判空

        result_bool, result_print = test_route_connectivity(url=url)
        SIGNAL.DIALOG.emit(
            "链接成功!" if result_bool else "连接失败...",
            result_print
        )

    def click_btn_misu_logistics_get_stage_info_online(self):
        result_print = get_stage_info_online()
        SIGNAL.DIALOG.emit(
            "尝试完成",
            result_print
        )

    def click_btn_misu_logistics_set_default(self):
        self.MisuLogistics_Link.setText("")

    def click_btn_reset_card_status_memory(self):
        # 弹出是或否选项
        reply = QMessageBox.question(
            self,
            '重置FAA卡片状态自学习记忆',
            '确定要进行此操作吗?\n'
            '在严重卡顿下, FAA可能学习错误的卡片状态, 导致放卡异常\n'
            '进行此操作, 可以尝试修复问题, 让放卡回归正常.\n'
            '请不要在FAA运行中使用此功能, 这会造成未知错误.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)

        if reply != QMessageBox.StandardButton.Yes:
            return

        CUS_LOGGER.warning("重置卡片状态自学习记忆, 开始")

        # 初始化清理计数器
        cleaned_count = 0

        # 删除名称为3和以上的
        card_status_folder = os.path.join(PATHS["image"]["card"], "状态判定")
        for folder_name in os.listdir(card_status_folder):
            if folder_name.isdigit() and int(folder_name) >= 3:
                # 从文件中清理
                folder_path = os.path.join(card_status_folder, folder_name)
                shutil.rmtree(folder_path)
                # 从内存读取的资源文件中, 清空对应部分
                del g_resources.RESOURCE_P["card"]["状态判定"][folder_name]
                cleaned_count += 1

        if cleaned_count == 0:
            QMessageBox.information(
                self,
                '重置FAA卡片状态自学习记忆',
                '您的状态已是最新，无需清理。',
                QMessageBox.StandardButton.Ok
            )
        else:
            QMessageBox.information(
                self,
                '重置FAA卡片状态自学习记忆',
                f'成功释放大失忆术! 遗忘状态: {cleaned_count}项.\n'
                '该操作不需要重启FAA. 再启动试试吧!',
                QMessageBox.StandardButton.Ok
            )

        CUS_LOGGER.warning("重置卡片状态自学习记忆, 结束")


def faa_start_main():
    # 实例化 PyQt后台管理
    app = QtWidgets.QApplication(sys.argv)

    """字体"""
    # 读取字体文件
    font_id = QtGui.QFontDatabase.addApplicationFont(PATHS["font"] + "\\SmileySans-Oblique.ttf")
    QtGui.QFontDatabase.addApplicationFont(PATHS["font"] + "\\手书体.ttf")

    # 获取字体家族名称
    font_families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
    if not font_families:
        raise ValueError("Failed to load font file.")

    font_family = font_families[0]

    # 创建 QFont 对象并设置大小
    font = QtGui.QFont(font_family, 11)
    # print(font_family)

    app.setFont(font)

    # 实例化 主窗口
    window = QMainWindowService()

    # 设置全局字体
    window.font = font

    # 主窗口 实现
    window.show()
    # 性能分析监控启动
    run_analysis_in_thread(window)

    # 运行主循环，必须调用此函数才可以开始事件处理
    app.exec()

    # 退出程序
    sys.exit()


if __name__ == "__main__":
    faa_start_main()
