import asyncio
import os
import threading

import psutil
from function.globals.loadings import loading
loading.update_progress(42,"正在全力性能分析中...")
from function.widget.GaugePanel import GaugePanel


def replace_label_with_gauge(layout_name, label, gauge_panel):
    # 从布局中移除标签
    index = layout_name.indexOf(label)
    layout_name.removeWidget(label)
    label.deleteLater()

    # 将仪表盘控件添加到相同的位置
    layout_name.insertWidget(index, gauge_panel)


async def monitor_io(process_ids, stop_event, main_window):
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
            main_window.read_bytes_label.setText(f"{total_read_bytes / 1048576:.2f} MB")
            main_window.write_bytes_label.setText(f"{total_write_bytes / 1048576:.2f} MB")
            main_window.io_gp.setValue((total_read_bytes + total_write_bytes) / 1048576)
            # print(f"总读取字节数: {total_read_bytes / 1024 / 1024:.2f} MB")
            # print(f"总写入字节数: {total_write_bytes / 1024 / 1024:.2f} MB")
        await asyncio.sleep(1)


async def monitor_memory(process_ids, stop_event, main_window):
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
            main_window.total_memory_rss_label.setText(f"{total_memory_rss / 1048576:.2f} MB")
            main_window.total_memory_percent_label.setText(f"{total_memory_percent:.2f}%")
            main_window.me_gp.setValue(total_memory_percent)
            # print(f"总内存使用量: {total_memory_rss / (1024 * 1024):.2f} MB")
            # print(f"总内存使用率: {total_memory_percent:.2f}%")
        await asyncio.sleep(1)


async def monitor_cpu(process_ids, stop_event, main_window):
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
            main_window.total_cpu_percent_label.setText(f"{total_cpu_percent:.2f}%")
            main_window.cpu_gp.setValue(total_cpu_percent)
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


async def analysis(main_window):
    stop_event = asyncio.Event()
    current_process_id = os.getpid()

    process_ids = get_all_process_ids(current_process_id)

    async def check_tab_selection():
        while True:
            if main_window.tabWidget.currentIndex() == 5:  # 选中了性能分析tab
                stop_event.clear()  # 清除事件标志，允许监控
            else:
                stop_event.set()  # 设置事件标志，停止监控
            await asyncio.sleep(1)  # 检查间隔

    tasks = [
        monitor_io(process_ids, stop_event, main_window),
        monitor_memory(process_ids, stop_event, main_window),
        monitor_cpu(process_ids, stop_event, main_window),
        check_tab_selection()  # 新增任务，用于检测tab选择状态
    ]

    await asyncio.gather(*tasks)


def run_analysis_in_thread(main_window):
    def target_function():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(analysis(main_window))
        loop.close()

    cpu_gp = GaugePanel("CPU占用率")
    io_gp = GaugePanel("磁盘读写量/MB", 1024)
    me_gp = GaugePanel("内存使用率")
    # 将 GaugePanel 绑定到 main_window 对象
    main_window.cpu_gp = cpu_gp
    main_window.io_gp = io_gp
    main_window.me_gp = me_gp
    replace_label_with_gauge(main_window.CpuLayout, main_window.cpu_panel, cpu_gp)
    replace_label_with_gauge(main_window.MemoryLayout, main_window.Memory_panel, me_gp)
    replace_label_with_gauge(main_window.IoLayout, main_window.Io_panel, io_gp)

    thread = threading.Thread(target=target_function, daemon=True)
    thread.start()
