import datetime
import ctypes
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import psutil
import win32con
import win32gui
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QVBoxLayout, QPushButton, QWidget

from function.common.process_manager import get_path_and_sub_titles
from function.common.startup_manager import *
from function.common.update_backup import backup_summary
from function.common.update_state import detect_local_state
from function.core.faa.faa_mix import FAA
from function.core.my_crypto import encrypt_data
from function.core.performance_analysis import QMWPerformanceAnalysis, run_analysis_in_thread
from function.core.qmw_2_load_settings import CommonHelper, QMainWindowLoadSettings
from function.core.qmw_editor_of_battle_plan import QMWEditorOfBattlePlan
from function.core.qmw_editor_of_stage_plan import QMWEditorOfStagePlan
from function.core.qmw_settings_migrator import QMWSettingsMigrator
from function.core.qmw_task_plan_editor import TaskEditor
from function.core.qmw_tip_accelerate_settings import QMWTipAccelerateSettings
from function.core.qmw_tip_battle import QMWTipBattle
from function.core.qmw_tip_battle_senior import QMWTipBattleSenior
from function.core.qmw_tip_editor_of_battle_plan import QMWTipEditorOfBattlePlan
from function.core.qmw_tip_level2 import QMWTipLevels2
from function.core.qmw_tip_login_settings import QMWTipLoginSettings
from function.core.qmw_tip_misu_logistics import QMWTipMisuLogistics
from function.core.qmw_tip_qqlogin import QMWTipQQlogin
from function.core.qmw_tip_sleep import QMWTipSleep
from function.core.qmw_tip_stage_id import QMWTipStageID
from function.core.qmw_tip_update import QMWTipUpdate
from function.core.qmw_tip_warm_gift import QMWTipWarmGift
from function.core.qmw_update_backup_manager import QMWUpdateBackupManager
from function.core.qmw_useful_tools_widget import UsefulToolsWidget
from function.core.todo import ThreadTodo
from function.globals import EXTRA, SIGNAL
from function.globals import g_resources
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.check_task_sequence import fresh_and_check_all_task_sequence
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_channel_name import get_channel_name
from function.scattered.get_stage_info_online import get_stage_info_online
from function.scattered.resize_360_windows import batch_resize_window
from function.scattered.test_route_connectivity import test_route_connectivity
from function.scattered.todo_timer_manager import TodoTimerManager

from function.core.git_update_manager import prepare_release_update, refresh_dev_manifest, refresh_release_manifest
from function.core.update_apply import launch_update_from_staging


def apply_windows_taskbar_icon(window):
    """将 FAA 图标写入 Windows 原生窗口句柄，修正任务栏仍显示 pythonw 图标的问题。"""
    if sys.platform != "win32":
        return

    icon_path = os.path.join(PATHS["logo"], "\u5706\u89d2-FetDeathWing-256x-AllSize.ico")
    if not os.path.exists(icon_path):
        return

    try:
        hwnd = int(window.winId())
        if not hwnd:
            return

        window.setWindowIcon(QtGui.QIcon(icon_path))

        user32 = ctypes.windll.user32
        user32.LoadImageW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
        user32.SendMessageW.restype = ctypes.c_void_p

        image_icon = 1
        lr_load_from_file = 0x00000010
        wm_set_icon = 0x0080
        icon_small = 0
        icon_big = 1
        gclp_hicon = -14
        gclp_hiconsm = -34

        big_size = user32.GetSystemMetrics(11) or 32
        small_size = user32.GetSystemMetrics(49) or 16
        big_icon = user32.LoadImageW(None, icon_path, image_icon, big_size, big_size, lr_load_from_file)
        small_icon = user32.LoadImageW(None, icon_path, image_icon, small_size, small_size, lr_load_from_file)

        hwnd_ptr = ctypes.c_void_p(hwnd)
        if big_icon:
            user32.SendMessageW(hwnd_ptr, wm_set_icon, icon_big, ctypes.c_void_p(big_icon))
        if small_icon:
            user32.SendMessageW(hwnd_ptr, wm_set_icon, icon_small, ctypes.c_void_p(small_icon))

        set_class_long = getattr(user32, "SetClassLongPtrW", None)
        if set_class_long is not None:
            set_class_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            set_class_long.restype = ctypes.c_void_p
            to_class_icon_arg = ctypes.c_void_p
        else:
            set_class_long = user32.SetClassLongW
            set_class_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
            set_class_long.restype = ctypes.c_long
            to_class_icon_arg = ctypes.c_long
        if big_icon:
            set_class_long(hwnd_ptr, gclp_hicon, to_class_icon_arg(big_icon))
        if small_icon:
            set_class_long(hwnd_ptr, gclp_hiconsm, to_class_icon_arg(small_icon))

        # Windows 任务栏最终读取 HWND 图标；Qt 图标和原生大小图标都设置一次更稳。
        # 原生图标句柄需要和窗口同生命周期保留，避免被回收后任务栏图标丢失。
        window._faa_native_taskbar_icons = (big_icon, small_icon)
    except Exception as e:
        CUS_LOGGER.debug(f"设置主窗口任务栏图标失败: {e}")


def bring_main_window_to_front_once(window):
    """启动完成时短暂置前主窗口，但不保持永久置顶。"""
    window.showNormal()
    window.raise_()
    window.activateWindow()

    if sys.platform != "win32":
        return

    try:
        hwnd = int(window.winId())
        if not hwnd:
            return

        flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)

        # 只在启动时短暂置顶一次，避免 FAA 被其他窗口压住；随后立即解除置顶状态。
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, flags)

        def release_topmost():
            try:
                win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, flags)
                window.raise_()
                window.activateWindow()
            except Exception as e:
                CUS_LOGGER.debug(f"解除主窗口临时置顶失败: {e}")

        QtCore.QTimer.singleShot(500, release_topmost)
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        CUS_LOGGER.debug(f"启动时置前主窗口失败: {e}")


class QMainWindowService(QMainWindowLoadSettings):
    signal_todo_end = QtCore.pyqtSignal()
    signal_todo_start = QtCore.pyqtSignal(object)  # 可通过该信号以某个 方案uuid 开启一趟流程
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

        # 额外窗口 - 关卡方案编辑器
        self.window_editor_of_stage_plan = QMWEditorOfStagePlan()
        self.OpenEditorOfStagePlan_Button.clicked.connect(self.click_btn_open_editor_of_stage_plan)

        # 额外窗口 - 配置迁移器
        self.window_settings_migrator = QMWSettingsMigrator()
        self.OpenSettingsMigrator_Button.clicked.connect(self.click_btn_open_settings_migrator)

        # 额外窗口 - 实用小工具
        self.window_useful_tools = UsefulToolsWidget(self)
        self.OpenUsefulTools_Button.clicked.connect(self.click_btn_open_useful_tools)
        # # 额外窗口 - 其它工具
        self.OpenOtherTools_Button.clicked.connect(self.click_btn_open_other_tools)

        # 额外窗口 - 性能分析
        self.window_performance_analysis = QMWPerformanceAnalysis(parent=self)
        self.OpenPerformanceAnalysis_Button.clicked.connect(self.click_btn_open_performance_analysis)

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
        self.window_tip_qqlogin = QMWTipQQlogin()
        self.QQloginTipButton.clicked.connect(self.click_btn_tip_qqlogin)

        # 额外窗口 - QQ登录额外休眠说明
        self.window_tip_sleep = QMWTipSleep()
        self.SleepTipButton.clicked.connect(self.click_btn_tip_sleep)

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

        # 隐藏(拖动)窗口到屏幕视图外 函数绑定
        self.Button_WindowHide.clicked.connect(self.click_btn_hide_window)
        self.game_window_is_hide = False

        # 调整窗口大小
        self.Button_WindowReSize.clicked.connect(self.click_btn_batch_resize_window)

        # 重置卡片状态自学习记忆
        self.ResetCardStatusMemoryButton.clicked.connect(self.click_btn_reset_card_status_memory)

        # 一键获取路径与窗口名
        self.oneclick_getpath.clicked.connect(self.click_btn_set_360_path)

        # 选择天知强卡器路径
        self.TCE_path_select_btn.clicked.connect(self.click_btn_select_tce_path)

        # 重启应用程序按钮
        self.Button_Refreshed.clicked.connect(self.restart_application)

        # 版本更新相关按钮
        self.CheckUpdateButton.clicked.connect(self.click_btn_check_update)
        self.ForceUpdateButton.clicked.connect(self.click_btn_force_update)
        self.NormalUpdateButton.clicked.connect(self.click_btn_normal_update)
        self.BackupManagerButton.clicked.connect(self.click_btn_manage_update_backups)
        self.UpdateHelpButton.clicked.connect(self.click_btn_tip_update)
        self.CheckUpdateButton.setText("加载正式版更新列表")
        self.NormalUpdateButton.setText("更新至选中的版本")
        self.NormalUpdateButton.setEnabled(False)
        self.ForceUpdateButton.setText("加载开发版更新列表")
        self.DevMoreUpdateButton.setText("加载更多开发者更新内容")
        self.DevMoreUpdateButton.clicked.connect(self.click_btn_load_more_dev_updates)
        self.DevMoreUpdateButton.setEnabled(False)
        self.update_candidates = []
        self.update_target_mode = "release"
        self.dev_manifest_pages = 1
        self.window_update_backup_manager = None
        self.window_tip_update = QMWTipUpdate()
        self.setup_update_state_labels()
        self.refresh_update_state_label()
        self.update_progress_started_at = None
        self.update_progress_step = "空闲"
        self.update_download_progress = None
        self.update_progress_timer = QtCore.QTimer(self)
        self.update_progress_timer.setInterval(1000)
        self.update_progress_timer.timeout.connect(self.refresh_update_progress_label)
        self.refresh_update_progress_label()

        # 线程状态
        self.is_ending = False  # 线程是否正在结束
        self.is_start = False  # 线程是否正在启动

        # 检查并生成任务序列的UUID
        fresh_and_check_all_task_sequence()

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

    @staticmethod
    def _format_file_size(size_bytes):
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} {unit}"
            size /= 1024

    def warn_recording_size_if_needed(self):
        recording_path = os.path.join(PATHS["logs"], "recording")
        if not os.path.isdir(recording_path):
            return

        video_count = 0
        total_size = 0
        for root, _, files in os.walk(recording_path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    total_size += os.path.getsize(file_path)
                    video_count += 1
                except OSError:
                    continue

        if total_size <= 1024 ** 3:
            return

        size_text = self._format_file_size(total_size)
        recording_url = QtCore.QUrl.fromLocalFile(recording_path).toString()
        warning_text = (
            f"FAA已为您录制了{video_count}条视频，大小总计{size_text}，"
            f"<a href='{recording_url}'>点击跳转</a>查看，请注意清理！"
        )
        SIGNAL.PRINT_TO_UI.emit("", time=False)
        SIGNAL.PRINT_TO_UI.emit(warning_text, color_level=1, time=False)

    def warn_update_backups_if_needed(self):
        summary = backup_summary(Path(PATHS["root"]))
        if summary["count"] <= 0:
            return

        if summary["total_size"] <= 512 * 1024 * 1024:
            return

        backups_path = os.path.join(PATHS["root"], "backups")
        backups_url = QtCore.QUrl.fromLocalFile(backups_path).toString()
        warning_text = (
            f"FAA 已保留 {summary['count']} 个更新备份，大小总计 {summary['total_size_text']}，"
            f"<a href='{backups_url}'>点击跳转</a>查看，也可以在更新页使用“管理更新备份”清理。"
        )
        SIGNAL.PRINT_TO_UI.emit("", time=False)
        SIGNAL.PRINT_TO_UI.emit(warning_text, color_level=1, time=False)

    def warn_update_state_if_needed(self):
        local_state = detect_local_state(Path(PATHS["root"]))
        warnings = local_state.get("warnings", [])
        if not warnings:
            return

        SIGNAL.PRINT_TO_UI.emit("", time=False)
        for warning in warnings:
            SIGNAL.PRINT_TO_UI.emit(f"[更新状态] {warning}", color_level=1, time=False)

    def setup_update_state_labels(self):
        """绑定更新页顶部 2x2 状态标签。"""
        self.update_state_labels = {
            "version": self.UpdateVersionInfoLabel,
            "node": self.UpdateNodeInfoLabel,
            "version_type": self.UpdateBranchInfoLabel,
            "source": self.UpdateSourceInfoLabel,
        }
        if hasattr(self, "UpdateStateGridLayout"):
            self.UpdateStateGridLayout.setColumnStretch(0, 1)
            self.UpdateStateGridLayout.setColumnStretch(1, 1)

        for label in self.update_state_labels.values():
            label.setWordWrap(True)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
            label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)

    def refresh_update_state_label(self, local_state: dict | None = None, release_entry: dict | None = None):
        """
        刷新更新页顶部的本地版本状态摘要。

        Args:
            local_state: 已读取的本地版本状态；为空时现场读取。
            release_entry: 当前版本对应的正式版 manifest 条目，用于补充 PR 合并时间。
        """
        local_state = local_state or detect_local_state(Path(PATHS["root"]))
        release_entry = release_entry or {}
        for key, text in self._build_update_state_texts(local_state, release_entry).items():
            self.update_state_labels[key].setText(text)

    def _build_update_state_texts(self, local_state: dict, release_entry: dict) -> dict[str, str]:
        """生成更新页顶部 2x2 状态标签文本。"""
        version = local_state.get("version") or "未知"
        tag = local_state.get("tag") or "未记录"
        pr = local_state.get("pr")
        pr_text = f"#{pr}" if pr else "未记录"
        commit = local_state.get("commit") or ""
        commit_text = commit[:12] if commit else "未记录"
        merged_at = release_entry.get("merged_at") or local_state.get("merged_at") or "未记录"
        return {
            "version": f"当前版本：{version}",
            "node": f"更新节点：PR {pr_text} / {commit_text} / {merged_at}",
            "version_type": f"版本类型：{self._format_version_type(version, tag)}",
            "source": f"版本信息和当前状态来源：{self._format_update_state_source(local_state)}",
        }

    @staticmethod
    def _format_version_type(version: str, tag: str) -> str:
        if version != "未知" and version == tag:
            return "内部版本号与Git Tag一致，为标准发行版"
        return "无GitTag，为中间版本，有可能不稳定的特性"

    @staticmethod
    def _format_update_state_source(local_state: dict) -> str:
        source_key = local_state.get("source")
        if source_key == "git":
            return "Git工作区 - 有本地改动" if local_state.get("dirty") else "Git工作区 - 干净"
        if source_key == "update_state":
            return "用户本地 - 版本状态文件正常运作"
        return "用户本地 - 版本状态文件异常运作，使用项目全局VERSION变量"

    def _ensure_update_allowed_outside_git_worktree(self) -> bool:
        local_state = detect_local_state(Path(PATHS["root"]))
        if local_state.get("source") != "git":
            return True

        self.refresh_update_state_label(local_state=local_state)
        message = (
            "当前运行目录是真实 Git 开发工作区。\n\n"
            "为避免热更新覆盖开发者源码工作区，本功能已被阻止。\n"
            "请先打包为标准发行包，再在打包后的目录中测试热更新。"
        )
        SIGNAL.PRINT_TO_UI.emit("[更新状态] 已阻止在 Git 开发工作区执行热更新。", color_level=1)
        QMessageBox.warning(self, "开发者工作区不允许执行更新", message)
        return False

    def refresh_update_progress_label(self):
        """刷新更新页的当前操作阶段和等待时间。"""
        if self.update_progress_started_at is None:
            self.UpdateProgressLabel.setText(f"更新进度：{self.update_progress_step}")
            return

        elapsed = int((datetime.datetime.now() - self.update_progress_started_at).total_seconds())
        progress_detail = self._format_update_download_progress()
        suffix = f"，{progress_detail}" if progress_detail else ""
        end = "。" if progress_detail else ""
        self.UpdateProgressLabel.setText(f"更新进度：{self.update_progress_step}，已等待 {elapsed} 秒{suffix}{end}")

    @staticmethod
    def _format_update_progress_mb(size_bytes: int | float | None) -> str:
        if size_bytes is None:
            return "未知"
        return f"{float(size_bytes) / 1024 / 1024:.2f}"

    def _format_update_download_progress(self) -> str:
        """生成下载阶段的体积、百分比、速度和预计剩余时间文本。"""
        progress = self.update_download_progress
        if not progress:
            return ""
        if progress.get("phase") != "download":
            return progress.get("message", "")

        downloaded = progress.get("downloaded_bytes") or 0
        total = progress.get("total_bytes")
        speed = progress.get("speed_bytes_per_second") or 0
        speed_text = f"{speed / 1024 / 1024:.2f}MB/s"

        if total:
            percent = progress.get("percent")
            percent_text = f"{percent:.1f}%" if percent is not None else "--%"
            remaining = progress.get("remaining_seconds")
            remaining_text = f"{int(remaining + 0.5)}秒" if remaining is not None else "未知"
            return (
                f"{self._format_update_progress_mb(downloaded)}/"
                f"{self._format_update_progress_mb(total)} MB，"
                f"{percent_text}，{speed_text}，预计还需{remaining_text}"
            )

        return (
            f"已下载 {self._format_update_progress_mb(downloaded)} MB，{speed_text}，"
            "Github正在生成下载文件中大小未知"
        )

    def update_download_progress_detail(self, progress: dict):
        """接收下载 worker 上报的字节级进度，并刷新更新页进度文本。"""
        self.update_download_progress = progress
        self.refresh_update_progress_label()

    def start_update_progress(self, step: str):
        """
        开始展示一个耗时更新阶段。

        Args:
            step: 展示给用户的当前阶段说明，例如正在请求 GitHub 或正在准备 staging。
        """
        self.update_progress_step = step
        self.update_progress_started_at = datetime.datetime.now()
        self.update_download_progress = None
        self.refresh_update_progress_label()
        self.update_progress_timer.start()

    def finish_update_progress(self, step: str):
        """
        结束当前耗时阶段，并保留最后的结果说明。

        Args:
            step: 操作完成后的摘要，通常包含成功、失败或取消原因。
        """
        self.update_progress_timer.stop()
        self.update_progress_started_at = None
        self.update_progress_step = step
        self.update_download_progress = None
        self.refresh_update_progress_label()

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
        username_1p = self.username_edit_1.text()
        password_1p = self.password_edit_1.text()

        password_1p = encrypt_data(password_1p)

        # 2p
        username_2p = self.username_edit_2.text()
        password_2p = self.password_edit_2.text()
        password_2p = encrypt_data(password_2p)

        save_path = self.path_edit.text()
        QQ_account = {
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
        with open(save_path, "w", encoding="utf-8") as json_file:
            json.dump(QQ_account, json_file, ensure_ascii=False, indent=4)
        QMessageBox.information(self, "提示", f"您的登录信息已经保存到{save_path}", QMessageBox.StandardButton.Ok)

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
        guild_manager_file = os.path.join(PATHS["logs"], "guild_manager", "guild_manager_data.json")
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
            name_image_path = os.path.join(PATHS["logs"], "guild_manager", "guild_member_images", f"{member_hash}.png")
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

    def todo_start(self, task_sequence_uuid=None):
        """
        todo线程的启动函数
        task_sequence_uuid为定时启动的uuid
        """
        self.is_start = True
        if task_sequence_uuid is None:
            running_task_sequence_uuid = self.opt["current_plan"]
        else:
            running_task_sequence_uuid = task_sequence_uuid

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
        if running_task_sequence_uuid in list(EXTRA.TASK_SEQUENCE_UUID_TO_PATH.keys()):
            running_task_sequence_path = EXTRA.TASK_SEQUENCE_UUID_TO_PATH[running_task_sequence_uuid]
            running_task_sequence_name = os.path.splitext(os.path.basename(running_task_sequence_path))[0]
            SIGNAL.PRINT_TO_UI.emit(
                f"[任务序列] 链接开始 Todo线程开启 - 执行任务序列: {running_task_sequence_name}",
                color_level=1)
            # 当前正在运行 的 文本 修改
            self.Label_RunningStateTask.setText(
                f"任务序列线程状态: 运行中 ({running_task_sequence_name})")
        else:
            SIGNAL.PRINT_TO_UI.emit(f"[任务序列] 未知(索引错误)", color_level=1)
            self.is_start = False
            self.todo_end()
            return

        SIGNAL.PRINT_TO_UI.emit("", is_line=True, line_type="top", color_level=2)

        """线程处理"""
        # 启动点击处理线程
        T_ACTION_QUEUE_TIMER.start()

        # 生成随机数种子
        random_seed = random.randint(-100, 100)
        the_360_lock = threading.Lock()
        # 开始创建faa
        faa_dict = {
            1: FAA(
                channel=channel_1p,
                player=1,
                opt=self.opt,
                the_360_lock=the_360_lock,
                random_seed=random_seed),
            2: FAA(
                channel=channel_2p,
                player=2,
                opt=self.opt,
                the_360_lock=the_360_lock,
                random_seed=random_seed)
        }

        # 创建新的todo并启动线程
        self.thread_todo_1 = ThreadTodo(
            faa_dict=faa_dict,
            opt=self.opt,
            todo_id=1,
            running_task_sequence_uuid=running_task_sequence_uuid)

        # 多线程作战时的第二线程
        self.thread_todo_2 = ThreadTodo(
            faa_dict=faa_dict,
            opt=self.opt,
            todo_id=2,
            running_task_sequence_uuid=running_task_sequence_uuid)

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
        self.Button_Start.setText("执行序列\nLink Start")
        # 设置输出文本
        SIGNAL.PRINT_TO_UI.emit("", is_line=True, line_type="bottom", color_level=2)
        SIGNAL.PRINT_TO_UI.emit("[任务序列] 已关闭全部线程", color_level=1)
        SIGNAL.PRINT_TO_UI.emit("", is_line=True, line_type="top", color_level=2)
        # 当前正在运行 的 文本 修改
        self.Label_RunningStateTask.setText(f"任务序列线程状态: 未运行")

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
        # 检查时间是否重复，方案是否存在
        time_list = []
        for i in range(1, 6):
            timer_opt = self.opt["timer"][str(i)]
            if timer_opt["active"]:
                h_text = getattr(self, f'Timer{i}_H').text()
                m_text = getattr(self, f'Timer{i}_M').text()
                tar_time = {"h": h_text, "m": m_text}
                plan_identifier = timer_opt["plan"]
                if plan_identifier == "" or plan_identifier == -1:
                    SIGNAL.PRINT_TO_UI.emit(
                        f"[定时任务] {h_text}:{m_text} 的定时任务未选择方案，启动失败!",
                        color_level=1)
                    return
                if tar_time in time_list:
                    SIGNAL.PRINT_TO_UI.emit(f"[定时任务] {h_text}:{m_text} 的定时任务时间重复，启动失败!", color_level=1)
                    return
                time_list.append(tar_time)
        # 清屏并输出
        self.TextBrowser.clear()
        self.start_print()
        # 设置按钮文本
        self.Button_StartTimer.setText("关闭定时任务\nTimer Stop")
        # 设置输出文本
        SIGNAL.PRINT_TO_UI.emit("", time=False)
        SIGNAL.PRINT_TO_UI.emit("[定时任务] 已启动!", color_level=1)
        self.Label_RunningStateTimer.setText(
            f"定时任务线程状态: 运行中")
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
        self.Label_RunningStateTimer.setText(
            f"定时任务线程状态: 未运行")
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
        """
        因为 Flash 在窗口外无法正常渲染画面(Chrome可以), 所以老板键只能做成z轴设为最低级
        """

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
                    title="出错！(╬◣д◢)",
                    text=f"{player}P存在错误的窗口名或游戏名称, 请在基础设定处重新拖拽至游戏窗口后保存."
                )
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

    def click_btn_batch_resize_window(self):

        try:
            # 获取窗口名称
            batch_resize_window(
                game_name=self.opt["base_settings"]["game_name"],
                name_1p=self.opt["base_settings"]["name_1p"],
                name_2p=self.opt["base_settings"]["name_2p"]
            )
        except Exception as e:
            # 报错弹窗
            SIGNAL.DIALOG.emit(
                title="出错！(╬◣д◢)",
                text=f"存在错误的窗口名或游戏名称, 请在基础设定处重新拖拽至游戏窗口后保存."
            )

    """打开其他窗口"""

    def click_btn_open_editor_of_battle_plan(self):
        window = self.window_editor_of_battle_plan
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

    def click_btn_open_performance_analysis(self):
        """打开性能分析独立窗口，并把窗口提升到前台。"""
        window = self.window_performance_analysis
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()
        window.raise_()
        window.activateWindow()

    def click_btn_open_useful_tools(self):
        pass
        window = self.window_useful_tools
        window.resize(300, 200)
        window.setFont(self.font)
        self.set_stylesheet(window)
        # 尝试获取句柄
        if window.try_get_handle():
            window.show()
        else:
            SIGNAL.DIALOG.emit(
                title="出错！(╬◣д◢)",
                text="请打开游戏窗口后再使用小工具！")

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

    def click_btn_tip_sleep(self):
        window = self.window_tip_sleep
        window.setFont(self.font)
        self.set_stylesheet(window)
        window.show()

    def click_btn_tip_update(self):
        """打开更新与备份说明窗口。"""
        window = self.window_tip_update
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
            title="链接成功!" if result_bool else "连接失败...",
            text=result_print
        )

    def click_btn_misu_logistics_get_stage_info_online(self):
        result_print = get_stage_info_online()
        SIGNAL.DIALOG.emit(
            title="尝试完成",
            text=result_print
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
                title="哎呦！(╥﹏╥)",
                text=f"未正确获取路径，请确保已打开360大厅及授予FAA管理员权限"
            )
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

    def click_btn_open_other_tools(self):
        # 创建新窗口
        self.tools_window = QWidget()
        self.tools_window.setWindowTitle("其它工具")
        self.tools_window.resize(300, 200)

        # 创建垂直布局
        layout = QVBoxLayout(self.tools_window)

        # 创建按钮
        self.open_task_btn = QPushButton("任务计划编辑器")
        layout.addWidget(self.open_task_btn)

        # 数据库连接
        db_path = os.path.join(PATHS["db"], 'tasks.db')
        db_conn = sqlite3.connect(db_path)

        # 按钮点击连接
        self.open_task_btn.clicked.connect(lambda: self.open_task_editor(db_conn))

        # 显示窗口
        self.tools_window.show()

    def click_btn_manage_update_backups(self):
        """打开更新备份管理窗口，用于查看、删除和恢复备份。"""
        self.window_update_backup_manager = QMWUpdateBackupManager(self)
        self.window_update_backup_manager.show()

    @staticmethod
    def _git_log_callback(level, msg):
        """Git 日志回调 - 根据等级映射颜色"""
        color_map = {"INFO": 3, "WARNING": 2, "ERROR": 1}
        SIGNAL.PRINT_TO_UI.emit(f"[Git] {msg}", color_level=color_map.get(level, 3))

    def click_btn_check_update(self):
        """加载带版本 tag 的正式版更新列表。"""
        SIGNAL.PRINT_TO_UI.emit("[更新] 正在刷新正式版本列表...", color_level=1)
        self.start_update_progress("正在请求 GitHub 正式版 tag 列表")
        self.CheckUpdateButton.setEnabled(False)
        self.ForceUpdateButton.setEnabled(False)
        self.DevMoreUpdateButton.setEnabled(False)
        self.NormalUpdateButton.setEnabled(False)

        def on_check_result(success, message, payload):
            """接收正式版 manifest worker 结果并更新表格和按钮状态。"""
            if success:
                SIGNAL.PRINT_TO_UI.emit(f"[更新] {message}", color_level=2)
            else:
                SIGNAL.PRINT_TO_UI.emit(f"[更新] {message}", color_level=0)

            if payload and payload.get("state_warning"):
                SIGNAL.PRINT_TO_UI.emit(f"[更新状态] {payload['state_warning']}", color_level=1)

            versions = payload.get("versions", []) if payload else []
            local_state = payload.get("local_state", {}) if payload else {}
            current_release = payload.get("current_release", {}) if payload else {}
            if success:
                self.refresh_update_state_label(local_state=local_state, release_entry=current_release)
            self._fill_update_table(versions, mode="release")
            self.update_candidates = versions
            self.update_target_mode = "release"
            if success and not versions:
                self.finish_update_progress("您已经是最新版本！")
            else:
                self.finish_update_progress(
                    f"正式版列表加载完成，共 {len(versions)} 个候选版本" if success
                    else f"正式版列表加载失败：{message}"
                )
            self.NormalUpdateButton.setText("更新至选中的版本")

            self.CheckUpdateButton.setEnabled(True)
            self.ForceUpdateButton.setEnabled(True)
            self.DevMoreUpdateButton.setEnabled(False)
            self.NormalUpdateButton.setEnabled(bool(versions))

        self.git_worker = refresh_release_manifest()
        self.git_worker.result.connect(on_check_result)

    def _selected_update_target(self):
        """
        获取更新表格中当前选中的目标版本。

        Returns:
            目标版本 dict；没有候选项时返回 None。若用户没有手动选中行，
            默认使用候选列表第一项，避免刷新后必须额外点击一次。
        """
        candidates = getattr(self, "update_candidates", [])
        if not candidates:
            return None

        row = self.GitHistoryView.currentRow()
        if 0 <= row < len(candidates):
            return candidates[row]
        return candidates[0]

    def _fill_update_table(self, entries, mode: str):
        """
        将正式版 tag 或开发版 PR 合并提交渲染到更新表格。

        Args:
            entries: 来自 manifest worker 的版本候选列表。
            mode: release 表示正式版列表，developer 表示开发版 PR 合并提交列表。
        """
        self.GitHistoryView.setColumnCount(5)
        self.GitHistoryView.setHorizontalHeaderLabels(['版本/类型', 'PR', '提交哈希', '时间', '标题'])
        self.GitHistoryView.setRowCount(0)

        for entry in entries:
            row_position = self.GitHistoryView.rowCount()
            self.GitHistoryView.insertRow(row_position)
            values = [
                entry.get("tag", "") if mode == "release" else "开发",
                f"#{entry.get('pr')}" if entry.get("pr") else "",
                entry.get("commit", "")[:12],
                entry.get("merged_at", ""),
                entry.get("title") or entry.get("summary", ""),
            ]
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if column == 4:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
                self.GitHistoryView.setItem(row_position, column, item)

        header = self.GitHistoryView.horizontalHeader()
        header.resizeSection(0, 90)
        header.resizeSection(1, 70)
        header.resizeSection(2, 120)
        header.resizeSection(3, 160)
        self.GitHistoryView.resizeRowsToContents()

    def click_btn_force_update(self):
        """进入开发版更新模式，加载最近的 PR merge commit 列表。"""
        reply = QMessageBox.warning(
            self,
            '开发者更新模式',
            '即将显示 main 分支最近的 PR 合并提交。\n'
            '这些提交未必是正式版本，不保证可以正常运行。\n'
            '请确认你知道自己在做什么。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.dev_manifest_pages = 1
        self._refresh_dev_updates(max_pages=self.dev_manifest_pages, stop_at_cached=True)

    def click_btn_load_more_dev_updates(self):
        """继续向更早的 main 分支 PR 合并提交翻页。"""
        self.dev_manifest_pages = max(getattr(self, "dev_manifest_pages", 1) + 1, 2)
        self._refresh_dev_updates(max_pages=self.dev_manifest_pages, stop_at_cached=False)

    def _refresh_dev_updates(self, max_pages: int, stop_at_cached: bool):
        """
        刷新开发版候选列表。

        Args:
            max_pages: 本次最多读取的 GitHub API 分页数量。
            stop_at_cached: 读取到本地缓存已知提交时是否提前停止，用于降低访问量。
        """
        SIGNAL.PRINT_TO_UI.emit(f"[更新] 正在刷新开发者 PR 合并提交列表，页数={max_pages}...", color_level=1)
        self.start_update_progress(f"正在请求 GitHub 开发版 PR 合并提交列表，第 {max_pages} 页范围")
        self.CheckUpdateButton.setEnabled(False)
        self.ForceUpdateButton.setEnabled(False)
        self.DevMoreUpdateButton.setEnabled(False)
        self.NormalUpdateButton.setEnabled(False)

        def on_dev_result(success, message, payload):
            """接收开发版 manifest worker 结果并刷新 PR 合并提交列表。"""
            if success:
                SIGNAL.PRINT_TO_UI.emit(f"[更新] {message}", color_level=2)
            else:
                SIGNAL.PRINT_TO_UI.emit(f"[更新] {message}", color_level=0)

            dev_commits = payload.get("dev_commits", []) if payload else []
            self._fill_update_table(dev_commits, mode="developer")
            self.update_candidates = dev_commits
            self.update_target_mode = "developer"
            self.finish_update_progress(
                f"开发版列表加载完成，共 {len(dev_commits)} 个 PR 合并提交" if success
                else f"开发版列表加载失败：{message}"
            )
            self.NormalUpdateButton.setText("更新至选中的版本")

            self.CheckUpdateButton.setEnabled(True)
            self.ForceUpdateButton.setEnabled(True)
            self.DevMoreUpdateButton.setEnabled(bool(dev_commits))
            self.NormalUpdateButton.setEnabled(bool(dev_commits))

        self.git_worker = refresh_dev_manifest(max_pages=max_pages, stop_at_cached=stop_at_cached)
        self.git_worker.result.connect(on_dev_result)

    def click_btn_normal_update(self):
        """准备并确认应用用户在表格中选中的更新目标。"""
        if not self._ensure_update_allowed_outside_git_worktree():
            return

        target = self._selected_update_target()
        if not target:
            QMessageBox.information(self, "暂无可用更新", "请先点击“检查更新”刷新正式版本列表。")
            return
        mode = getattr(self, "update_target_mode", "release")
        target_name = target.get("tag") or f"PR #{target.get('pr')} / {target.get('commit', '')[:12]}"

        reply = QMessageBox.question(
            self,
            '准备更新',
            f"即将准备更新至 {target_name}。\n"
            "准备阶段会下载目标源码包并迁移当前配置到 staging，不会立刻替换当前目录。\n"
            "准备完成后会再次确认是否执行替换。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        SIGNAL.PRINT_TO_UI.emit(f"[更新] 正在准备 {target_name}...", color_level=1)
        self.start_update_progress(f"正在下载并准备更新到 {target_name}")
        self.CheckUpdateButton.setEnabled(False)
        self.ForceUpdateButton.setEnabled(False)
        self.DevMoreUpdateButton.setEnabled(False)
        self.NormalUpdateButton.setEnabled(False)

        def on_prepare_result(success, message, payload):
            """接收 staging 准备结果，空间足够且用户确认后启动外部 updater。"""
            self.CheckUpdateButton.setEnabled(True)
            self.ForceUpdateButton.setEnabled(True)
            self.DevMoreUpdateButton.setEnabled(self.update_target_mode == "developer" and bool(self.update_candidates))
            self.NormalUpdateButton.setEnabled(True)
            if not success:
                self.finish_update_progress(f"更新准备失败：{message}")

            if not success:
                SIGNAL.PRINT_TO_UI.emit(f"[更新] {message}", color_level=0)
                SIGNAL.DIALOG.emit("更新准备失败", message)
                return

            space = payload.get("space", {})
            validation = payload.get("target_validation", {})
            if validation.get("status") == "compare_failed":
                SIGNAL.PRINT_TO_UI.emit(f"[更新状态] {validation.get('message')}", color_level=1)

            SIGNAL.PRINT_TO_UI.emit(
                f"[更新] 准备完成。需要空间 {space.get('required_text')}，可用 {space.get('available_text')}",
                color_level=2 if space.get("enough") else 0,
            )

            self.finish_update_progress("更新准备完成，正在等待确认是否执行替换")

            if not space.get("enough", False):
                self.finish_update_progress("更新准备完成，但磁盘空间不足，已停止替换")
                SIGNAL.DIALOG.emit(
                    "磁盘空间不足",
                    f"更新已准备但不会执行替换。\n需要：{space.get('required_text')}\n可用：{space.get('available_text')}"
                )
                return

            staging_path = payload.get("staging", {}).get("path", "")
            reply_apply = QMessageBox.question(
                self,
                '执行更新替换',
                f"更新准备完成，staging 位于：\n{staging_path}\n\n"
                "接下来会启动外部 updater，当前程序退出后替换版本区，并保留更新前备份。\n"
                "是否现在执行？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply_apply != QMessageBox.StandardButton.Yes:
                self.finish_update_progress("更新准备完成，用户取消了本次替换")
                return

            launch_info = launch_update_from_staging(PATHS["root"], staging_path)
            self.finish_update_progress(f"外部 updater 已启动，PID={launch_info['pid']}，主程序即将退出")
            SIGNAL.PRINT_TO_UI.emit(f"[更新] 已启动外部 updater，PID={launch_info['pid']}。主程序即将退出。", color_level=1)
            QtCore.QTimer.singleShot(500, QtWidgets.QApplication.quit)

        self.git_worker = prepare_release_update(target, auto_start=False)
        self.git_worker.progress.connect(self.update_download_progress_detail)
        self.git_worker.result.connect(on_prepare_result)
        self.git_worker.start()

    def restart_application(self):
        """
        重启整个应用程序
        干净地关闭所有线程和进程，然后重新启动一个新的 Python 进程
        """

        # 弹窗确认
        reply = QMessageBox.question(
            self,
            '重启 FAA',
            '确定要重启 FAA 吗？\n'
            '这将关闭所有正在运行的任务和线程，然后重新启动程序。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)

        if reply != QMessageBox.StandardButton.Yes:
            return

        CUS_LOGGER.info("[重启] 用户请求重启应用程序，开始清理流程...")
        if self.thread_todo_running:
            CUS_LOGGER.info("[重启] 正在停止 todo 主线程...")
            self.todo_end()
        if self.todo_timer_running:
            CUS_LOGGER.info("[重启] 正在停止定时任务管理器...")
            self.todo_timer_stop()
        CUS_LOGGER.info("[重启] 所有线程已停止，准备重启...")

        # 启动新进程 - 根据启动方式选择正确的命令
        try:
            CUS_LOGGER.debug(f"[重启] 工作目录：{PATHS['root']}")

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            root_entry = os.path.join(PATHS["root"], "FAA.exe")
            if os.path.isfile(root_entry):
                CUS_LOGGER.debug(f"[重启] 使用根目录固定入口：{root_entry}")
                process = subprocess.Popen(
                    [root_entry],
                    cwd=PATHS["root"],
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    startupinfo=startupinfo
                )
            else:
                python_executable = sys.executable
                main_script = os.path.join(PATHS["root"], "function", "faa_main.py")
                main_script_abs = os.path.abspath(main_script)
                try:
                    parent_process = psutil.Process().parent()
                    parent_cmdline = parent_process.cmdline() if parent_process else []
                    mode = any('-m' in arg for arg in parent_cmdline)
                except Exception:
                    mode = False

                if mode:
                    cmd_args = [python_executable, '-m', 'function.faa_main']
                else:
                    cmd_args = [python_executable, main_script_abs]
                CUS_LOGGER.debug(f"[重启] 启动命令：{' '.join(cmd_args)}")
                CUS_LOGGER.debug(f"[重启] 主脚本路径：{main_script_abs}")
                process = subprocess.Popen(
                    cmd_args,
                    cwd=PATHS["root"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    startupinfo=startupinfo
                )

            CUS_LOGGER.info(f"[重启] 新进程 PID: {process.pid}")
        except Exception as e:
            CUS_LOGGER.error(f"[重启] 启动新进程失败：{e}")
            QMessageBox.critical(
                self,
                '重启失败',
                f'无法启动新进程：{str(e)}',
                QMessageBox.StandardButton.Ok)
            return
        CUS_LOGGER.info("[重启] 关闭当前应用...")
        self.close()
        os._exit(0)

    def open_task_editor(self, db_conn):
        """打开任务计划编辑器"""
        self.task_editor = TaskEditor(db_conn)
        self.task_editor.show()


def faa_start_main(app=None, loading=None):
    loading.update_progress(95)
    # app.setStyle("Windows")
    # app.setStyle("WindowsVista")
    # app.setStyle("Fusion")
    # app.setStyle("Windows11")

    """字体"""

    # 设定 全局字体
    app.setFont(EXTRA.Q_FONT)

    # 实例化 主窗口
    window = QMainWindowService()

    # 设置 窗口字体
    window.font = EXTRA.Q_FONT
    # 先停止播放gif再更新进度到100避免线程安全问题
    loading.anim.stop()
    loading.update_progress(100, "载入完成！！！")
    # 主窗口 实现
    window.show()
    QtCore.QTimer.singleShot(100, lambda: apply_windows_taskbar_icon(window))
    QtCore.QTimer.singleShot(250, lambda: bring_main_window_to_front_once(window))
    # 主窗口淡入动画
    window.fade_in_animation.start()
    QtCore.QTimer.singleShot(0, window.warn_recording_size_if_needed)
    QtCore.QTimer.singleShot(0, window.warn_update_backups_if_needed)
    QtCore.QTimer.singleShot(0, window.warn_update_state_if_needed)

    # 性能分析监控启动
    run_analysis_in_thread(window)

    # 检测启动参数
    start_with_task = "--start_with_task" in sys.argv

    # 使用 QTimer 在事件循环开始后执行任务
    if start_with_task:
        print("检测到启动参数 --start_with_task，将自动开始任务")
        window.todo_click_btn()
    app.setQuitOnLastWindowClosed(False)  # 禁止自动退出


if __name__ == "__main__":
    faa_start_main()
