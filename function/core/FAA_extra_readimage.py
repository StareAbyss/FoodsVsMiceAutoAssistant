from function.yolo import onnxdetect
from function.common.bg_img_screenshot import capture_image_png_all
from multiprocessing import Process, Queue
from function.globals.log import CUS_LOGGER

# from function.core.FAA import FAA
import time
# import random


# 生产者函数
def producer(time_num, handle,read_queue):
    while True:
        # 获取图像并进行目标检测
        result = onnxdetect.get_mouse_position(capture_image_png_all(handle))

        # 检查结果是否有效
        if result is not None:
            boxes, class_id = result

            # 将检测结果放入队列
            read_queue.put([class_id, boxes])

            # 遍历所有检测到的目标
            for i, box in enumerate(boxes):
                CUS_LOGGER.debug(f"识图信息为 {class_id[i]} 类别位于以 {box[0]}, {box[1]} 为中心，{box[2]}, {box[3]} 大小的方框内")

        # 暂停一段时间
        time.sleep(time_num)

# 消费者函数
# def consumer(time_num):
#     while True:
#         boxes,class_id=read_queue.get()
#             print(f"处理识图结果结束")
#        time.sleep(time_num +random.random())  # 模拟消费时间



def read_and_get_return_information(faa):
    # 创建并启动生产者进程
    read_queue = Queue()
    CUS_LOGGER.debug("开始识别")

    time_num=2
    p = Process(target=producer, args=(time_num,faa.handle, read_queue))
    p.start()

    return p,read_queue

def kill_process(process):
    process.terminate()
    process.join()