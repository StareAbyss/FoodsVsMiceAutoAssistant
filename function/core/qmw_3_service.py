import datetime
import json
import random
import shutil
import webbrowser

import win32con
import win32gui
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QMessageBox, QFileDialog

from function.common.process_and_window_manager import get_path_and_sub_titles
from function.common.startup import *
from function.core.faa import FAA
from function.core.performance_analysis import run_analysis_in_thread
from function.core.qmw_2_load_settings import CommonHelper, QMainWindowLoadSettings
from function.core.qmw_editor_of_battle_plan import QMWEditorOfBattlePlan
from function.core.qmw_editor_of_stage_plan import QMWEditorOfStagePlan
from function.core.qmw_editor_of_task_sequence import QMWEditorOfTaskSequence
from function.core.qmw_settings_migrator import QMWSettingsMigrator
from function.core.qmw_tip_accelerate_settings import QMWTipAccelerateSettings
from function.core.qmw_tip_battle import QMWTipBattle
from function.core.qmw_tip_battle_senior import QMWTipBattleSenior
from function.core.qmw_tip_editor_of_battle_plan import QMWTipEditorOfBattlePlan
from function.core.qmw_tip_level2 import QMWTipLevels2
from function.core.qmw_tip_login_settings import QMWTipLoginSettings
from function.core.qmw_tip_misu_logistics import QMWTipMisuLogistics
from function.core.qmw_tip_stage_id import QMWTipStageID
from function.core.qmw_tip_warm_gift import QMWTipWarmGift
from function.core.qmw_useful_tools_widget import UsefulToolsWidget
from function.core.todo import ThreadTodo
from function.core.my_crypto import encrypt_data
from function.core.qmw_tip_qqlogin import QMWTipQQlogin
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
        self.thread_todo_1: ThreadTodo | None = None
        self.thread_todo_2: ThreadTodo | None = None  # 仅用于单人多线程时, 运行2P任务
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

        # 额外窗口 - 关卡方案编辑器
        self.window_editor_of_stage_plan = QMWEditorOfStagePlan()
        self.OpenEditorOfStagePlan_Button.clicked.connect(self.click_btn_open_editor_of_stage_plan)

        # 额外窗口 - 配置迁移器
        self.window_settings_migrator = QMWSettingsMigrator()
        self.OpenSettingsMigrator_Button.clicked.connect(self.click_btn_open_settings_migrator)

        # 额外窗口 - 实用小工具
        self.window_useful_tools = UsefulToolsWidget(self)
        self.OpenUsefulTools_Button.clicked.connect(self.click_btn_open_useful_tools)

        # 额外窗口 - 日氪链接
        self.TopUpMoneyTipButton.clicked.connect(
            lambda: webbrowser.open("https://stareabyss.top/FAA-WebSite/guide/advanced/pay_to_win_star.html"))
        if EXTRA.ETHICAL_MODE:
            self.TopUpMoneyLabel.setText(
                "!!! 经FAA伦理核心审查, 日氪模块违反*能量限流*协议, 已被临时性*抑制*以符合最高伦理标准 !!!")
            self.TopUpMoneyLabel.setStyleSheet("color: red;")  # 红色文本
        else:
            self.TopUpMoneyLabel.setText("!!! FAA伦理核心已强制卸除, 日氪模块已通过授权, 感谢您对FAA的支持与信任 !!!")
            self.TopUpMoneyLabel.setStyleSheet("color: green;")  # 绿色文本

        # 额外窗口 - 温馨礼包提示
        self.window_tip_warm_gift = QMWTipWarmGift()
        self.GetWarmGiftTipButton.clicked.connect(self.click_btn_tip_warm_gift)

        # 额外窗口 - 关卡代号提示
        self.window_tip_stage_id = QMWTipStageID()
        self.StageIDTipButton.clicked.connect(self.click_btn_tip_stage_id)

        # 额外窗口 - 战斗模式介绍
        self.window_tip_battle = QMWTipBattle()
        self.BattleTipButton.clicked.connect(self.click_btn_tip_battle)

        # 额外窗口 - 二级说明书
        self.window_tip_level2 = QMWTipLevels2()
        self.Level2TipButton.clicked.connect(self.click_btn_tip_level2)

        # 额外窗口 - 高级战斗说明
        self.window_tip_battle_senior = QMWTipBattleSenior()
        self.BattleSeniorTipButton.clicked.connect(self.click_btn_tip_battle_senior)

        # 额外窗口 - 登录选项说明
        self.window_tip_login_settings = QMWTipLoginSettings()
        self.LoginSettingsTipButton.clicked.connect(self.click_btn_tip_login_settings)

        # 额外窗口 - 加速说明
        self.window_tip_accelerate_settings = QMWTipAccelerateSettings()
        self.AccelerateTipButton.clicked.connect(self.click_btn_tip_accelerate_settings)

        # 额外窗口 - QQ密码登录说明
        self.window_tip_qqlogin=QMWTipQQlogin()
        self.QQloginTipButton.clicked.connect(self.click_btn_tip_qqlogin)

        # 额外窗口 - QQ登录额外休眠说明
        self.window_tip_qqlogin=QMWTipQQlogin()
        self.QQloginTipButton.clicked.connect(self.click_btn_tip_qqlogin)

        # 米苏物流 - tip窗口
        self.window_tip_misu_logistics = QMWTipMisuLogistics()
        self.MisuLogisticsTipButton.clicked.connect(self.click_btn_tip_misu_logistics)

        # 米苏物流 - 测试链接
        self.MisuLogistics_LinkTest.clicked.connect(self.click_btn_misu_logistics_link_test)
        # 米苏物流 - 获取线上关卡信息
        self.MisuLogistics_GetStageInfoOnline.clicked.connect(self.click_btn_misu_logistics_get_stage_info_online)
        # 米苏物流 - 设定默认
        self.MisuLogistics_Link_SetDefault.clicked.connect(self.click_btn_misu_logistics_set_default)

        # 自启动
        self.check_startup_status()
        self.Startup.stateChanged.connect(toggle_startup)

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
        self.ResetCardStatusMemoryButton.clicked.connect(self.click_btn_reset_card_status_memory)

        # 一键获取路径与窗口名
        self.oneclick_getpath.clicked.connect(self.click_btn_set_360_path)

        # 选择天知强卡器路径
        self.TCE_path_select_btn.clicked.connect(self.click_btn_select_tce_path)

        # 线程状态
        self.is_ending = False  # 线程是否正在结束
        self.is_start = False  # 线程是否正在启动

        """公会管理器相关"""
        # 初始化公会管理器数据和表格视图
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
        """QQ密码登录模块"""

        self.SavePasswordButton.clicked.connect(self.save_password_button_on_clicked)
        self.ChoosePathButton.clicked.connect(self.choose_path_button_on_clicked)

    def choose_path_button_on_clicked(self):
        """"用于连接ChoosePathButton的函数，选择存储路径"""
        # 弹出一个文件夹选择对话框
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")

        # 如果用户选择了文件夹，保存路径到编辑框
        if folder_path:
            self.path_edit.setText(folder_path)
            
            
    def save_password_button_on_clicked(self):
        """"用于连接SavePasswordButton的函数，保存QQ密码信息"""
        # 1p
        username_1p=self.username_edit_1.text()
        password_1p=self.password_edit_1.text()
        
        password_1p=encrypt_data(password_1p)
        
        # 2p
        username_2p=self.username_edit_2.text()
        password_2p=self.password_edit_2.text()
        password_2p=encrypt_data(password_2p)
        
        save_path=self.path_edit.text()
        QQ_account= {
            "1p": {
                "username": username_1p,
                "password": password_1p
            },
            "2p": {
                "username": username_2p,
                "password": password_2p
            }
        }
        
        save_path = os.path.join(save_path, "QQ_account.json")
        with open(save_path,"w",encoding="utf-8") as json_file:
            json.dump(QQ_account, json_file,ensure_ascii=False, indent=4)
        QMessageBox.information(self, "提示",f"您的登录信息已经保存到{save_path}",QMessageBox.StandardButton.Ok)

    """公会管理器页面"""

    def guild_manager_table_init(self):
        """
        初始化公会管理器数据，主要是表头和第一列的图片，其他部分占位
        """

        # 设置表格基础属性
        header_list = ['成员', '上次更新', '总-贡献', '周-贡献', '总-功勋', '周-功勋']
        self.GuildMemberInfoTable.setColumnCount(len(header_list))
        self.GuildMemberInfoTable.setHorizontalHeaderLabels(header_list)

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
                    "Ø")  # 找不到的默认值
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

            column_position = -1

            # 获取成员数据
            member_contribution = member.get('data', {})
            member_contribution_week = member.get('data_week', {})
            member_merit = member.get('merit', {})
            member_merit_week = member.get('merit_week', {})

            # 获取 当天扫描到的贡献总值
            today_contribution = member_contribution.get(selected_date.toString('yyyy-MM-dd'), -1)
            if today_contribution < 0:
                # 不展示今天压根不存在的数据的行
                continue

            # 初始化列
            self.GuildMemberInfoTable.insertRow(row_position)

            """添加列 - 成员图片"""

            # 添加成员图片
            member_hash = member['name_image_hash']
            name_image_path = f"{PATHS['logs']}\\guild_manager\\guild_member_images\\{member_hash}.png"
            pixmap = QtGui.QPixmap(name_image_path)
            qtw_item = QtWidgets.QTableWidgetItem()

            # 设置单元格图片
            qtw_item.setData(QtCore.Qt.ItemDataRole.DecorationRole, pixmap)

            # 设置单元格不可编辑
            qtw_item.setFlags(qtw_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

            column_position += 1
            self.GuildMemberInfoTable.setItem(row_position, column_position, qtw_item)

            """添加列 - 上次更新时间"""

            today_str = datetime.date.today().strftime('%Y-%m-%d')
            last_update_date_str = max(member_contribution.keys(), default="Never")
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

            column_position += 1
            self.GuildMemberInfoTable.setItem(row_position, column_position, qtw_item)

            """添加列 - 总贡献"""

            column_position += 1
            add_data_widget_into_table(value=today_contribution, row=row_position, col=column_position)

            """添加列 - 周贡献"""

            today_contribution_week = member_contribution_week.get(selected_date.toString('yyyy-MM-dd'), -1)

            column_position += 1
            add_data_widget_into_table(value=today_contribution_week, row=row_position, col=column_position)

            """添加列 - 总功勋"""

            today_merit = member_merit.get(selected_date.toString('yyyy-MM-dd'), -1)

            column_position += 1
            add_data_widget_into_table(value=today_merit, row=row_position, col=column_position)

            """添加列 - 周功勋"""

            today_merit_week = member_merit_week.get(selected_date.toString('yyyy-MM-dd'), -1)

            column_position += 1
            add_data_widget_into_table(value=today_merit_week, row=row_position, col=column_position)

            """昨天到今天的变化值"""

            # yesterday = selected_date.addDays(-1)
            # yesterday_contribution = member_data.get(yesterday.toString('yyyy-MM-dd'), -1)
            # if today_contribution > 0 and yesterday_contribution > 0:
            #     value = today_contribution - yesterday_contribution
            # else:
            #     value = -1
            #
            # column_position += 1
            # add_data_widget_into_table(value=value, row=row_position, col=column_position)

            """上个月最后一天到今天的变化值"""

            # last_month = selected_date.addMonths(-1)
            # last_day_of_last_month = QtCore.QDate(last_month.year(), last_month.month(), last_month.daysInMonth())
            # last_day_of_last_month_str = last_day_of_last_month.toString('yyyy-MM-dd')
            # last_day_of_last_month_contribution = member_data.get(last_day_of_last_month_str, -1)
            # if today_contribution > 0 and last_day_of_last_month_contribution > 0:
            #     value = today_contribution - last_day_of_last_month_contribution
            # else:
            #     value = -1
            #
            # column_position += 1
            # add_data_widget_into_table(value=value, row=row_position, col=column_position)

            """去年最后一天到今天的变化值"""

            # last_year = selected_date.addYears(-1)
            # last_day_of_last_year = QtCore.QDate(last_year.year(), last_year.month(), last_year.daysInMonth())
            # last_day_of_last_year_str = last_day_of_last_year.toString('yyyy-MM-dd')
            # last_day_of_last_year_contribution = member_data.get(last_day_of_last_year_str, -1)
            # if today_contribution > 0 and last_day_of_last_year_contribution > 0:
            #     value = today_contribution - last_day_of_last_year_contribution
            # else:
            #     value = -1
            # column_position += 1
            # add_data_widget_into_table(value=value, row=row_position, col=column_position)

            row_position += 1

        # 默认按照第3列(总贡)降序排序
        self.GuildMemberInfoTable.sortByColumn(2, QtCore.Qt.SortOrder.DescendingOrder)

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

    def check_startup_status(self) -> None:
        """
        检测自启动状态，并在复选框中显示
        """
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
                                 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            self.Startup.setChecked(True)
            winreg.CloseKey(key)
        except FileNotFoundError:
            self.Startup.setChecked(False)

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
        SIGNAL.PRINT_TO_UI.emit("", is_line=True, line_type="bottom", color_level=2)
        SIGNAL.PRINT_TO_UI.emit("[任务序列] 链接开始 Todo线程开启", color_level=1)
        SIGNAL.PRINT_TO_UI.emit("", is_line=True, line_type="top", color_level=2)
        # 当前正在运行 的 文本 修改
        running_todo_plan_name = self.opt["todo_plans"][running_todo_plan_index]["name"]
        self.Label_RunningState.setText(f"任务序列线程状态: 运行中       运行方案: {running_todo_plan_name}")

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
                QQ_login_info=self.opt["QQ_login_info"],
                extra_sleep=self.opt["extra_sleep"],
                random_seed=random_seed),
            2: FAA(
                channel=channel_2p,
                player=2,
                character_level=self.opt["base_settings"]["level_2p"],
                is_auto_battle=self.opt["advanced_settings"]["auto_use_card"],
                is_auto_pickup=self.opt["advanced_settings"]["auto_pickup_2p"],
                QQ_login_info=self.opt["QQ_login_info"],
                extra_sleep=self.opt["extra_sleep"],
                random_seed=random_seed)
        }

        # 创建新的todo并启动线程
        self.thread_todo_1 = ThreadTodo(
            faa_dict=faa_dict,
            opt=self.opt,
            running_todo_plan_index=running_todo_plan_index,
            todo_id=1)

        # 多线程作战时的第二线程
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
        CUS_LOGGER.info("[任务序列] 开始关闭全部任务执行线程")

        self.is_ending = True  # 终止操作正在进行中 放用户疯狂操作

        if self.thread_todo_1 is not None:
            CUS_LOGGER.debug("[任务序列] todo 主线程 - 中止流程 - 开始")
            self.thread_todo_1.stop()
            CUS_LOGGER.debug("[任务序列] todo 主线程 - 中止流程 - 结束")

        if self.thread_todo_2 is not None:
            CUS_LOGGER.debug("[任务序列] todo 副线程 - 中止流程 - 开始")
            self.thread_todo_2.stop()
            CUS_LOGGER.debug("[任务序列] todo 副线程 - 中止流程 - 结束")

        CUS_LOGGER.debug("[任务序列] 动作处理线程 - 中止流程 - 开始")
        T_ACTION_QUEUE_TIMER.stop()
        CUS_LOGGER.debug("[任务序列] 动作处理线程 - 中止流程 - 结束")

        """UI处理"""
        # 设置flag
        self.thread_todo_running = False
        # 设置按钮文本
        self.Button_Start.setText("开始任务\nLink Start")
        # 设置输出文本
        SIGNAL.PRINT_TO_UI.emit("", is_line=True, line_type="bottom", color_level=2)
        SIGNAL.PRINT_TO_UI.emit("[任务序列] 已关闭全部线程", color_level=1)
        SIGNAL.PRINT_TO_UI.emit("", is_line=True, line_type="top", color_level=2)
        # 当前正在运行 的 文本 修改
        self.Label_RunningState.setText(f"任务序列线程状态: 未运行")

        # 调试打印 确定所有内部线程的状态 是否还是运行激活状态
        q_threads = {
            "todo主线程": self.thread_todo_1,
            "todo副线程": self.thread_todo_2,
            "窗口动作处理线程": T_ACTION_QUEUE_TIMER,
        }
        CUS_LOGGER.debug(f"[任务序列] 结束后线程状态检查")
        for q_thread_name, q_thread_obj in q_threads.items():
            CUS_LOGGER.debug(f"[任务序列] {q_thread_name} 正在运行: {q_thread_obj.isRunning()}")

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

    def click_btn_open_editor_of_stage_plan(self):
        window = self.window_editor_of_stage_plan
        window.setFont(self.font)
        self.set_stylesheet(window)
        # 刷新一次战斗方案
        window.refresh_battle_plan_selector()
        window.show()

    def click_btn_open_settings_migrator(self):
        window = self.window_settings_migrator
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_open_useful_tools(self):
        window = self.window_useful_tools
        window.resize(300, 200)
        window.setFont(self.font)
        self.set_stylesheet(window)
        # 尝试获取句柄
        if window.try_get_handle():
            window.show()
        else:
            SIGNAL.DIALOG.emit(
                "出错！(╬◣д◢)",
                "请打开游戏窗口后再使用小工具！")

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

    def click_btn_tip_login_settings(self):
        window = self.window_tip_login_settings
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_tip_accelerate_settings(self):
        window = self.window_tip_accelerate_settings
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

    def click_btn_tip_qqlogin(self):
        window = self.window_tip_qqlogin
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

    def click_btn_set_360_path(self):
        # 弹出是或否选项
        reply = QMessageBox.question(
            self,
            '一键逆天（bushi',
            '使用该功能前, 要打开360大厅的对应的小号\n'
            '本功能会自动填写360大厅的路径\n'
            '记得要保存哦！\n'
            '确定要进行此操作吗?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)

        if reply != QMessageBox.StandardButton.Yes:
            return
        path, title = get_path_and_sub_titles()
        if not path:
            SIGNAL.DIALOG.emit(
                "哎呦！(╥﹏╥)",
                f"未正确获取路径，请确保已打开360大厅及授予FAA管理员权限")
            return
        self.LoginSettings360PathInput.setText(path)

        # if len(title) < 1:
        #     SIGNAL.DIALOG.emit(
        #         "哎呦！(╥﹏╥)",
        #         f"你确定打开了对应的帐号了吗？")
        #     return
        #
        # if len(title) < self.login_first.value():
        #     SIGNAL.DIALOG.emit(
        #         "哎呦！(╥﹏╥)",
        #         f"1p账号序号超过当前打开账号数目")
        #     return
        #
        # self.GameName_Input.setText("")
        # self.Name1P_Input.setText("")
        # self.Name2P_Input.setText("")
        # if len(title) < self.login_second.value():
        #     SIGNAL.DIALOG.emit(
        #         "哎呦！(╥﹏╥)",
        #         f"2p账号序号超过当前打开账号数目,如果单号无视此报错")
        #     name_1p, game_name = get_reverse_channel_name(title[self.login_first.value() - 1])
        #
        # else:
        #     name_1p, name_2p, game_name = get_reverse_channel_name(
        #         title[self.login_first.value() - 1],
        #         title[self.login_second.value() - 1]
        #     )
        #
        # self.GameName_Input.setText(game_name)
        # self.Name1P_Input.setText(name_1p)
        # if name_2p:
        #     self.Name2P_Input.setText(name_2p)

    def click_btn_select_tce_path(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)  # 选择已存在的文件
        file_dialog.setNameFilter("Executable Files (*.exe)")  # 过滤文件类型

        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                file_path = selected_files[0]
                if file_path.lower().endswith("天知强卡器.exe") or file_path.lower().endswith(
                        r"\天知强卡器.exe"):  # 增加了对文件名的判断，做了兼容
                    self.TCE_path_input.setText(file_path)
                else:
                    QMessageBox.warning(self, "警告", "请选择名为 '天知强卡器.exe' 的文件！")
                    self.TCE_path_input.clear()

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

    # app.setStyle("Windows")
    # app.setStyle("WindowsVista")
    # app.setStyle("Fusion")
    # app.setStyle("Windows11")

    """字体"""

    font = EXTRA.Q_FONT

    # 设定 全局字体
    app.setFont(font)

    # 实例化 主窗口
    window = QMainWindowService()

    # 设置 窗口字体
    window.font = font

    # 主窗口 实现
    window.show()

    # 性能分析监控启动
    run_analysis_in_thread(window)

    # 检测启动参数
    start_with_task = "--start_with_task" in sys.argv

    # 使用 QTimer 在事件循环开始后执行任务
    if start_with_task:
        print("检测到启动参数 --start_with_task，将自动开始任务")
        window.todo_click_btn()

    # 运行主循环，必须调用此函数才可以开始事件处理
    app.exec()

    # 退出程序
    sys.exit()


if __name__ == "__main__":
    faa_start_main()
