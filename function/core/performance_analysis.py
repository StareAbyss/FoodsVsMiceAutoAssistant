import asyncio
import os
import threading

import psutil
from PyQt6 import QtCore
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout
from function.widget.GaugePanel import GaugePanel


class QMWPerformanceAnalysis(QDialog):
    """性能分析独立窗口。

    该窗口用 Python 代码复现原 UI 文件里的性能分析页，避免主窗口
    FAA_3.0.ui 继续持有不需要展示在顶部标签栏的 Tab 页面。
    """

    def __init__(self, parent=None):
        """
        初始化性能分析弹窗和监控数据占位控件。

        Args:
            parent: 父窗口，通常是主窗口实例。
        """
        super().__init__(parent)
        self.setWindowTitle("性能分析")
        self.resize(760, 360)

        self.read_bytes_label = QLabel("Null")
        self.write_bytes_label = QLabel("Null")
        self.total_memory_rss_label = QLabel("Null")
        self.total_memory_percent_label = QLabel("Null")
        self.total_cpu_percent_label = QLabel("Null")
        self.Io_panel = QLabel("假装出现了一个仪表盘\n未完待续")
        self.Memory_panel = QLabel("假装出现了一个仪表盘\n未完待续")
        self.cpu_panel = QLabel("假装出现了一个仪表盘\n未完待续")

        for panel in (self.Io_panel, self.Memory_panel, self.cpu_panel):
            panel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.IoLayout = self._build_io_layout()
        self.MemoryLayout = self._build_memory_layout()
        self.CpuLayout = self._build_cpu_layout()

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)
        main_layout.addLayout(self.IoLayout)
        main_layout.addLayout(self.MemoryLayout)
        main_layout.addLayout(self.CpuLayout)

    @staticmethod
    def _add_value_row(layout, title, value_label):
        """添加一行“指标名称 + 当前值”的监控文本。"""
        row_layout = QHBoxLayout()
        row_layout.addWidget(QLabel(title))
        row_layout.addWidget(value_label)
        layout.addLayout(row_layout)

    def _build_io_layout(self):
        """构建磁盘读写监控列。"""
        layout = QVBoxLayout()
        layout.addWidget(QLabel("磁盘 IO 读写"))
        self._add_value_row(layout, "总读取字节数", self.read_bytes_label)
        self._add_value_row(layout, "总写入字节数", self.write_bytes_label)
        layout.addStretch(1)
        layout.addWidget(self.Io_panel)
        layout.addStretch(1)
        return layout

    def _build_memory_layout(self):
        """构建内存占用监控列。"""
        layout = QVBoxLayout()
        layout.addWidget(QLabel("内存占用"))
        self._add_value_row(layout, "总内存使用量", self.total_memory_rss_label)
        self._add_value_row(layout, "总内存使用率", self.total_memory_percent_label)
        layout.addStretch(1)
        layout.addWidget(self.Memory_panel)
        layout.addStretch(1)
        return layout

    def _build_cpu_layout(self):
        """构建 CPU 占用监控列。"""
        layout = QVBoxLayout()
        layout.addWidget(QLabel("CPU 占用"))
        self._add_value_row(layout, "总 CPU 使用率", self.total_cpu_percent_label)
        layout.addStretch(1)
        layout.addWidget(self.cpu_panel)
        layout.addStretch(1)
        return layout

def replace_label_with_gauge(layout_name, label, gauge_panel):
    # 从布局中移除标签
    index = layout_name.indexOf(label)
    layout_name.removeWidget(label)
    label.deleteLater()

    # 将仪表盘控件添加到相同的位置
    layout_name.insertWidget(index, gauge_panel)


async def monitor_io(process_ids, stop_event, performance_window):
    while True:
        if not stop_event.is_set():
            total_read_bytes = 0
            total_write_bytes = 0

            for process_id in process_ids:
                try:
                    process = psutil.Process(process_id)
                    io_counters = process.io_counters()
                    total_read_bytes += io_counters.read_bytes
                    total_write_bytes += io_counters.write_bytes
                except psutil.NoSuchProcess:
                    continue
            performance_window.read_bytes_label.setText(f"{total_read_bytes / 1048576:.2f} MB")
            performance_window.write_bytes_label.setText(f"{total_write_bytes / 1048576:.2f} MB")
            performance_window.io_gp.setValue((total_read_bytes + total_write_bytes) / 1048576)
            # print(f"总读取字节数: {total_read_bytes / 1024 / 1024:.2f} MB")
            # print(f"总写入字节数: {total_write_bytes / 1024 / 1024:.2f} MB")
        await asyncio.sleep(1)


async def monitor_memory(process_ids, stop_event, performance_window):
    while True:
        if not stop_event.is_set():
            total_memory_rss = 0
            total_memory_percent = 0

            for process_id in process_ids:
                try:
                    process = psutil.Process(process_id)
                    memory_info = process.memory_info()
                    memory_percent = process.memory_percent()
                    total_memory_rss += memory_info.rss
                    total_memory_percent += memory_percent
                except psutil.NoSuchProcess:
                    continue
            performance_window.total_memory_rss_label.setText(f"{total_memory_rss / 1048576:.2f} MB")
            performance_window.total_memory_percent_label.setText(f"{total_memory_percent:.2f}%")
            performance_window.me_gp.setValue(total_memory_percent)
            # print(f"总内存使用量: {total_memory_rss / (1024 * 1024):.2f} MB")
            # print(f"总内存使用率: {total_memory_percent:.2f}%")
        await asyncio.sleep(1)


async def monitor_cpu(process_ids, stop_event, performance_window):
    while True:
        if not stop_event.is_set():
            total_cpu_percent = 0

            for process_id in process_ids:
                try:
                    process = psutil.Process(process_id)
                    cpu_percent = process.cpu_percent(interval=1)
                    total_cpu_percent += cpu_percent
                except psutil.NoSuchProcess:
                    continue
            performance_window.total_cpu_percent_label.setText(f"{total_cpu_percent:.2f}%")
            performance_window.cpu_gp.setValue(total_cpu_percent)
            # print(f"总CPU使用率: {total_cpu_percent:.2f}%")
        await asyncio.sleep(1)


def get_all_process_ids(main_process_id):
    process_ids = [main_process_id]

    def get_child_processes(pid):
        try:
            process = psutil.Process(pid)
            children = process.children(recursive=True)
            for child in children:
                process_ids.append(child.pid)
                get_child_processes(child.pid)
        except psutil.NoSuchProcess:
            pass

    get_child_processes(main_process_id)
    return process_ids


async def analysis(main_window, performance_window):
    stop_event = asyncio.Event()
    current_process_id = os.getpid()

    process_ids = get_all_process_ids(current_process_id)

    def is_performance_window_visible():
        """判断性能采样是否应该运行，优先以独立弹窗可见状态为准。"""
        return performance_window.isVisible()

    async def check_tab_selection():
        while True:
            if is_performance_window_visible():
                stop_event.clear()  # 清除事件标志，允许监控
            else:
                stop_event.set()  # 设置事件标志，停止监控
            await asyncio.sleep(1)  # 检查间隔

    tasks = [
        monitor_io(process_ids, stop_event, performance_window),
        monitor_memory(process_ids, stop_event, performance_window),
        monitor_cpu(process_ids, stop_event, performance_window),
        check_tab_selection()  # 新增任务，用于检测tab选择状态
    ]

    await asyncio.gather(*tasks)


def run_analysis_in_thread(main_window):
    """
    启动性能监控后台线程，并把仪表盘控件替换到性能分析窗口中。

    Args:
        main_window: 主窗口实例，需持有 window_performance_analysis。
    """
    performance_window = main_window.window_performance_analysis

    def target_function():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(analysis(main_window, performance_window))
        loop.close()

    cpu_gp = GaugePanel("CPU占用率")
    io_gp = GaugePanel("磁盘读写量/MB", 1024)
    me_gp = GaugePanel("内存使用率")
    # GaugePanel 绑定到性能分析窗口，主窗口只负责持有入口按钮。
    performance_window.cpu_gp = cpu_gp
    performance_window.io_gp = io_gp
    performance_window.me_gp = me_gp
    replace_label_with_gauge(performance_window.CpuLayout, performance_window.cpu_panel, cpu_gp)
    replace_label_with_gauge(performance_window.MemoryLayout, performance_window.Memory_panel, me_gp)
    replace_label_with_gauge(performance_window.IoLayout, performance_window.Io_panel, io_gp)

    thread = threading.Thread(target=target_function, daemon=True)
    thread.start()
