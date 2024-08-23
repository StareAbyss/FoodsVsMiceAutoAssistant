# from function.core.FAA import FAA
import time
from multiprocessing import Process, Queue

from function.common.bg_img_screenshot import capture_image_png_all
from function.core_battle.Coordinate_map import parse_positions
from function.globals.log import CUS_LOGGER
from function.yolo import onnxdetect


# 生产者函数
def producer(time_num, handle, read_queue,is_log):
    while True:
        # 获取图像并进行目标检测
        result = onnxdetect.get_mouse_position(
            capture_image_png_all(handle),
            is_log
        )

        # 检查结果是否有效
        if result is not None:
            information = parse_positions(*result)  # 加工信息
            # 将检测结果放入队列
            read_queue.put(information)
            wave, godwind, positions = information
            # 遍历所有检测到的目标
            CUS_LOGGER.debug(f"待加工信息为{result} ")
            CUS_LOGGER.debug(f"识图信息为是否检测到波次 {wave} 是否检测到波神风 {godwind},剩下待炸点位 {positions} ")

        # 暂停一段时间
        time.sleep(time_num)


# 消费者函数
# def consumer(time_num,read_queue):
#     while True:
#         boxes,class_id=read_queue.get()
#             print(f"处理识图结果结束")
#        time.sleep(time_num +random.random())  # 模拟消费时间


def read_and_get_return_information(faa,is_log):
    # 创建并启动生产者进程
    read_queue = Queue()
    CUS_LOGGER.debug("开始多进程识别特殊老鼠及波次信息")

    time_num = 2
    p = Process(target=producer, args=(time_num, faa.handle, read_queue,is_log))
    p.start()

    return p, read_queue


# def start_analysis_process(read_queue):
#     # 创建并启动消费者进程
#     CUS_LOGGER.debug("开始多进程解析特殊老鼠及波次信息")
#     time_num=2
#     p = Process(target=consumer, args=(time_num, read_queue))
#     p.start()
#
#     return p,read_queue

def kill_process(process):
    process.terminate()
    process.join()
