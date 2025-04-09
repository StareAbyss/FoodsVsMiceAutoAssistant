import argparse
import datetime
import random
import time
from math import floor

import cv2.dnn
import numpy as np
import onnxruntime

from function.globals.get_paths import PATHS


def initialize_session(is_gpu):
    onnx_model = PATHS["model"] + "/mouseV2.onnx"
    providers = [
        'DmlExecutionProvider',
        'CPUExecutionProvider'
    ] if is_gpu else ['CPUExecutionProvider']
    session = onnxruntime.InferenceSession(onnx_model, providers=providers)
    return session


'''
注意：如果你推理自己的模型，以下类别需要改成你自己的具体类别
'''
# 老许类别
CLASSES = {
    0: 'shell',
    1: 'flypig',
    2: 'pope',
    3: 'Vali',
    4: 'wave',
    5: 'GodWind',
    6: 'skull',
    7: 'snowstorm',
    8: 'obstacle',
    9: 'boss165',
    10: 'icetype'}

# 对应6种特殊老鼠与波次 v2版本新增障碍、暴风雪、魔塔165层boss需炸技能、冰块识别
colors = np.random.uniform(0, 255, size=(len(CLASSES), 3))


# 绘制
def draw_bounding_box(img, class_id, confidence, x, y, x_plus_w, y_plus_h):
    """
    :param img:
    :param class_id:
    :param confidence:
    :param x:
    :param y:
    :param x_plus_w:
    :param y_plus_h:
    :return:
    """
    label = f'{CLASSES[class_id]} ({confidence:.2f})'
    color = colors[class_id]
    # 绘制矩形框
    cv2.rectangle(img, (x, y), (x_plus_w, y_plus_h), color, 2)
    # 绘制类别
    cv2.putText(img, label, (x - 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def get_mouse_position(input_image, is_log, session):
    """
    :param input_image:
    :return:
    """
    cv2.ocl.setUseOpenCL(True)
    cv2.setNumThreads(4)  # 根据CPU核心数调整

    # 读取原图
    # original_image: np.ndarray = cv2.imread(input_image)
    original_image = input_image[:, :, :3]  # 去除阿尔法通道
    [height, width, _] = original_image.shape
    length = max((height, width))
    image = np.zeros((length, length, 3), np.uint8)
    image[0:height, 0:width] = original_image
    scale = length / 640  # 缩放比例
    # 设置模型输入
    blob = cv2.dnn.blobFromImage(image, scalefactor=1 / 255, size=(640, 640), swapRB=True)  # 要交换红蓝
    # 推理
    outputs = session.run(
        output_names=[session.get_outputs()[0].name],
        input_feed={session.get_inputs()[0].name: blob}
    )[0]

    outputs = np.transpose(outputs, (0, 2, 1))
    rows = outputs.shape[1]

    boxes = []
    scores = []
    class_ids = []
    # outputs有8400行，遍历每一行，筛选最优检测结果
    for i in range(rows):
        classes_scores = outputs[0][i][4:]  # classes_scores:80 X 1
        (minScore, maxScore, minClassLoc, (x, maxClassIndex)) = cv2.minMaxLoc(classes_scores)
        if maxScore >= 0.25:
            box = [
                # cx cy w h  -> x y w h
                outputs[0][i][0] - (0.5 * outputs[0][i][2]), outputs[0][i][1] - (0.5 * outputs[0][i][3]),
                outputs[0][i][2], outputs[0][i][3]]
            boxes.append(box)  # 边界框
            scores.append(maxScore)  # 置信度
            class_ids.append(maxClassIndex)  # 类别
    # opencv版最极大值抑制
    result_boxes = cv2.dnn.NMSBoxes(boxes, scores, 0.25, 0.45, 0.5)
    if isinstance(result_boxes, np.int64):  # 检查是否为单个整数
        result_boxes = [result_boxes]  # 转换为列表

    # 从NMS结果中提取过滤后的boxes和class_ids
    filtered_boxes = [list(np.array(boxes[i]) * scale) for i in result_boxes]
    filtered_class_ids = [class_ids[i] for i in result_boxes]  # 非极大值抑制过后产生的框和类别
    test_mode = False  #打开就能看见小框框看效果
    if test_mode:
        annotated_image = original_image.copy()
        for i in range(len(result_boxes)):
            index = result_boxes[i]
            box = boxes[index]
            draw_bounding_box(annotated_image, class_ids[index], scores[index], round(box[0] * scale),
                              round(box[1] * scale),
                              round((box[0] + box[2]) * scale), round((box[1] + box[3]) * scale))
        annotated_image = cv2.resize(annotated_image, (960, 540))
        cv_show('test', annotated_image)
    need_write = is_log  # 是否保存图片及对应标签
    if need_write or len(result_boxes) > 0:
        cv_write(original_image, result_boxes, class_ids, boxes, scale)
    return filtered_boxes, filtered_class_ids  # 返回边界框及类别用作进一步处理


def cv_write(original_image, result_boxes, class_ids, boxes, scale):
    """
    此函数用于保存标签label及对应数据图片
    """
    output_base_path = PATHS["logs"] + "\\yolo_output"
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    rand_num = str(floor(random.random() * 1000000))
    output_img_path = f"{output_base_path}/images/{timestamp}_{rand_num}.png"
    output_txt = f"{output_base_path}/labels/{timestamp}_{rand_num}.txt"
    cv2.imwrite(output_img_path, original_image)
    if len(result_boxes) > 0:
        with open(output_txt, 'a') as f:
            for i in range(len(result_boxes)):
                index = result_boxes[i]
                class_id = class_ids[index]
                box = boxes[index]
                x, y, w, h = voc_to_yolo(
                    original_image.shape,
                    [box[0] * scale, box[1] * scale,
                     box[2] * scale, box[3] * scale])
                f.write(f"{class_id} {x} {y} {w} {h}\n")


def voc_to_yolo(size, box):  # 归一化操作
    dw = 1. / size[1]
    dh = 1. / size[0]
    x = box[0] + (0.5 * box[2])
    y = box[1] + (0.5 * box[3])
    w = box[2]
    h = box[3]
    x = x * dw
    w = w * dw
    y = y * dh
    h = h * dh
    return x, y, w, h


def cv_show(name, img):  # 图片展示
    cv2.imshow(name, img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='mouseV2.onnx', help='将模型放到当前目录')
    parser.add_argument('--img', default=str('0002_81.jpg'), help='将图片放到当前目录')
    print(cv2.__version__)
    args = parser.parse_args()
    original_image: np.ndarray = cv2.imread(args.img)
    session1 = initialize_session(True)
    session2 = initialize_session(False)
    gpu_times = []
    cpu_times = []

    for _ in range(1):  # 每个配置运行5次
        for use_gpu in [True, False]:
            session = session1 if use_gpu else session2
            print(f"\n{'=' * 30} 测试开始 {'=' * 30}")
            start = time.time()
            get_mouse_position(original_image, False, session)
            elapsed = time.time() - start

            # 记录耗时
            if use_gpu:
                gpu_times.append(elapsed)
            else:
                cpu_times.append(elapsed)

            print(f"[本次用时] {elapsed:.3f}s")
            print(f"{'=' * 30} 测试结束 {'=' * 30}\n")
            time.sleep(1)
    print("\n=== 平均耗时统计 ===")
    print(f"GPU 平均耗时: {sum(gpu_times) / len(gpu_times):.3f}s (共 {len(gpu_times)} 次)")
    print(f"CPU 平均耗时: {sum(cpu_times) / len(cpu_times):.3f}s (共 {len(cpu_times)} 次)")
