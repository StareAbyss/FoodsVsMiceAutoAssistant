import os

from function.get_paths import paths

task_card_s = ["酒杯灯-0.png","酒杯灯-1.png","瓜皮护罩-1.png","小火炉-4.png"]

list_all_card_recorded = os.listdir(paths["picture"]["card"])
for task_card_n in task_card_s:
    # 只ban被记录了图片的变种卡
    if not (task_card_n in list_all_card_recorded):
        task_card_s.remove(task_card_n)
print(task_card_s)