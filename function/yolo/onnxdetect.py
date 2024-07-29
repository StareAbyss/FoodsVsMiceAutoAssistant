import argparse
import cv2.dnn
import numpy as np
import datetime
import random
from math import floor
from function.globals.get_paths import PATHS
'''
注意：如果你推理自己的模型，以下类别需要改成你自己的具体类别
'''
# 老许类别
CLASSES = {0: 'shell', 1: 'flypig', 2: 'pope', 3: 'Vali', 4: 'wave', 5: 'GodWind', 6: 'skull' }# 对应6种特殊老鼠与波次
colors = np.random.uniform(0, 255, size=(len(CLASSES), 3))

# 绘制
def draw_bounding_box(img, class_id, confidence, x, y, x_plus_w, y_plus_h):
    label = f'{CLASSES[class_id]} ({confidence:.2f})'
    color = colors[class_id]
    # 绘制矩形框
    cv2.rectangle(img, (x, y), (x_plus_w, y_plus_h), color, 2)
    # 绘制类别
    cv2.putText(img, label, (x - 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def get_mouse_position(input_image):
    # 使用opencv读取onnx文件
    onnx_model = PATHS["model"]+"/mouse.onnx"
    model: cv2.dnn.Net = cv2.dnn.readNetFromONNX(onnx_model)
    # 读取原图
    # original_image: np.ndarray = cv2.imread(input_image)
    original_image = input_image[:, :, :3]#去除阿尔法通道
    [height, width, _] = original_image.shape
    length = max((height, width))
    image = np.zeros((length, length, 3), np.uint8)
    image[0:height, 0:width] = original_image
    scale = length / 640 # 缩放比例
    # 设置模型输入
    blob = cv2.dnn.blobFromImage(image, scalefactor=1 / 255, size=(640, 640), swapRB=True)#通道是匹配的，不用交换红蓝
    model.setInput(blob)
    # 推理
    outputs = model.forward() # output: 1 X 8400 x 84
    outputs = np.array([cv2.transpose(outputs[0])])
    rows = outputs.shape[1]

    boxes = []
    scores = []
    class_ids = []
    # outputs有8400行，遍历每一行，筛选最优检测结果
    for i in range(rows):
        # 找到第i个候选目标在80个类别中，最可能的类别
        classes_scores = outputs[0][i][4:] # classes_scores:80 X 1
        (minScore, maxScore, minClassLoc, (x, maxClassIndex)) = cv2.minMaxLoc(classes_scores)
        if maxScore >= 0.25:
            box = [
                # cx cy w h  -> x y w h
                outputs[0][i][0] - (0.5 * outputs[0][i][2]), outputs[0][i][1] - (0.5 * outputs[0][i][3]),
                outputs[0][i][2], outputs[0][i][3]]
            boxes.append(box) #边界框
            scores.append(maxScore) # 置信度
            class_ids.append(maxClassIndex) # 类别
    # opencv版最极大值抑制
    result_boxes = cv2.dnn.NMSBoxes(boxes, scores, 0.25, 0.45, 0.5)
    if isinstance(result_boxes, np.int64):  # 检查是否为单个整数
        result_boxes = [result_boxes]  # 转换为列表

    # 从NMS结果中提取过滤后的boxes和class_ids
    filtered_boxes = [list(np.array(boxes[i]) * scale) for i in result_boxes]
    filtered_class_ids = [class_ids[i] for i in result_boxes]#非极大值抑制过后产生的框和类别
    # annotated_image = original_image.copy()
    # for i in range(len(result_boxes)):
    #     index = result_boxes[i]
    #     box = boxes[index]
    #     draw_bounding_box(annotated_image, class_ids[index], scores[index], round(box[0] * scale), round(box[1] * scale),
    #                           round((box[0] + box[2]) * scale), round((box[1] + box[3]) * scale))
    # annotated_image=cv2.resize(annotated_image, (960,540))
    # cv_show('test',annotated_image)
    need_write=True#是否保存图片及对应标签，未来将对接前端
    if need_write or len(result_boxes) > 0:
        cv_write(original_image,result_boxes,class_ids,scores,boxes,scale)
    return filtered_boxes,filtered_class_ids#返回边界框及类别用作进一步处理

def cv_write(original_image,result_boxes,class_ids,scores,boxes,scale):#此函数用于保存标签label及对应数据图片
    output_base_path = PATHS["logs"]+"\\yolo_output"
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    rand_num = str(floor(random.random() * 1000000))
    output_img_path = f"{output_base_path}/images/{timestamp}_{rand_num}.png"
    output_txt = f"{output_base_path}/labels/{timestamp}_{rand_num}.txt"
    cv2.imwrite(output_img_path, original_image)
    with open(output_txt, 'a') as f:
        for i in range(len(result_boxes)):
            index = result_boxes[i]
            class_id = class_ids[index]
            box = boxes[index]
            x, y, w, h = voc_to_yolo(original_image.shape,
                                     [box[0] * scale, box[1] * scale, box[2] * scale, box[3] * scale])
            f.write(f"{class_id} {x} {y} {w} {h}\n")



def voc_to_yolo(size, box):#归一化操作
    dw = 1./size[1]
    dh = 1./size[0]
    x = box[0] + (0.5*box[2])
    y = box[1] + (0.5*box[3])
    w = box[2]
    h = box[3]
    x = x*dw
    w = w*dw
    y = y*dh
    h = h*dh
    return (x,y,w,h)

def cv_show(name,img):#图片展示
    cv2.imshow(name, img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()







if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='mouse.onnx', help='Input your onnx model.')
    parser.add_argument('--img', default=str('20240728154824_236031.png'), help='Path to input image.')
    args = parser.parse_args()
    get_mouse_position(args.img)

