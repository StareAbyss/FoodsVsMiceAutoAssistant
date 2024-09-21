import asyncio
import time
import psutil


async def monitor_io(process_ids, duration):
    start_time = time.time()

    while time.time() - start_time < duration:
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


async def monitor_memory(process_ids, duration):
    start_time = time.time()

    while time.time() - start_time < duration:
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


async def monitor_cpu(process_ids, duration):
    start_time = time.time()

    while time.time() - start_time < duration:
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


async def analysis(main_process_id):
    duration = int(input("请输入监控时长（秒）："))

    process_ids = get_all_process_ids(main_process_id)

    tasks = [
        monitor_io(process_ids, duration),
        monitor_memory(process_ids, duration),
        monitor_cpu(process_ids, duration)
    ]

    await asyncio.gather(*tasks)