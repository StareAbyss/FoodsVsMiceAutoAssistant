import os
from PIL import Image
import sys
script_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_path)
from model import OcrHandle
# 初始化OCR处理器
ocr = OcrHandle()
def try_ocr(path,size=960):
# 加载图片
    img = Image.open(path).convert("RGB")

    # 执行OCR识别
    results = ocr.text_predict(img, short_size=size)  # short_size必须为32的倍数，含义为缩放尺寸
    # 绘制文字框
    # draw_bbox(img, box)

    return results



def try_ocr_sort(path):
    img = Image.open(path).convert("RGB")
    results = ocr.text_predict(img, short_size=256)

    # 按文本框左上角的x坐标排序
    results.sort(key=lambda result: result[0][0][0])  # 取第一个点的x坐标

    recognized_text = []
    for result in results:
        box, text, score = result
        recognized_text.append(text)

    return recognized_text