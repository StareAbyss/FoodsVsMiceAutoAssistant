import asyncio
import os
import psutil

async def monitor_io(process_ids, stop_event):
    while not stop_event.is_set():
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

        print(f"总读取字节数: {total_read_bytes / 1024 / 1024:.2f} MB")
        print(f"总写入字节数: {total_write_bytes / 1024 / 1024:.2f} MB")
        await asyncio.sleep(1)


async def monitor_memory(process_ids, stop_event):
    while not stop_event.is_set():
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

        print(f"总内存使用量: {total_memory_rss / (1024 * 1024):.2f} MB")
        print(f"总内存使用率: {total_memory_percent:.2f}%")
        await asyncio.sleep(1)


async def monitor_cpu(process_ids, stop_event):
    while not stop_event.is_set():
        total_cpu_percent = 0

        for process_id in process_ids:
            try:
                process = psutil.Process(process_id)
                cpu_percent = process.cpu_percent(interval=1)
                total_cpu_percent += cpu_percent
            except psutil.NoSuchProcess:
                continue

        print(f"总CPU使用率: {total_cpu_percent:.2f}%")
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
            if main_window.tabWidget.currentIndex() == 0:#选中了性能分析tab
                stop_event.clear()  # 清除事件标志，允许监控
            else:
                stop_event.set()  # 设置事件标志，停止监控
            await asyncio.sleep(1)  # 检查间隔

    tasks = [
        monitor_io(process_ids, stop_event),
        monitor_memory(process_ids, stop_event),
        monitor_cpu(process_ids, stop_event),
        check_tab_selection()  # 新增任务，用于检测tab选择状态
    ]

    await asyncio.gather(*tasks)