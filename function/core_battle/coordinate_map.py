import math


def parse_positions(coordinate, base_info):
    """

    {0: '贝壳', 1: '飞猪', 2: '教皇', 3: '瓦力', 4: '波次', 5: '神风', 6: '骷髅',7: '暴风雪',8:'障碍',9:'酒瓶与光球',10:'冰块'}

    """

    # 更新边界和分割数量
    x_min, x_max = 303, 839
    y_min, y_max = 110, 560
    x_segments = 9
    y_segments = 7

    # 初始化输出变量
    wave = False
    god_wind = False
    positions = set()
    obstacle=set()
    ice=set()

    for index, base_value in enumerate(base_info):

        if base_value == 4:
            wave = True
            continue

        elif base_value == 5:
            god_wind = True
            continue

        elif base_value in [0, 1, 2, 3, 6, 9]:
            x = coordinate[index][0] + 0.5 * coordinate[index][2]
            if base_value == 1:#飞猪的高度要降低一点
                y = coordinate[index][1] + 0.5 * coordinate[index][3] + 50
            else:
                y = coordinate[index][1] + 0.5 * coordinate[index][3]

            # 将坐标映射到分割后的格子
            if x < x_min:
                x_segment = 1
            else:
                x_segment = min(math.ceil((x - x_min) / ((x_max - x_min) / x_segments)), x_segments)
            if y < y_min:
                y_segment = 1
            else:
                y_segment = min(math.ceil((y - y_min) / ((y_max - y_min) / y_segments)), y_segments)

            # 添加位置到列表
            positions.add(f"{x_segment}-{y_segment}")
        elif base_value ==8:
            x = coordinate[index][0] + 0.5 * coordinate[index][2]
            y = coordinate[index][1] + 0.5 * coordinate[index][3]
            # 将坐标映射到分割后的格子
            if x < x_min:
                x_segment = 1
            else:
                x_segment = min(math.ceil((x - x_min) / ((x_max - x_min) / x_segments)), x_segments)
            if y < y_min:
                y_segment = 1
            else:
                y_segment = min(math.ceil((y - y_min) / ((y_max - y_min) / y_segments)), y_segments)

            # 添加障碍位置到列表
            obstacle.add(f"{x_segment}-{y_segment}")
        elif base_value == 10:
            x = coordinate[index][0] + 0.5 * coordinate[index][2]
            y = coordinate[index][1] + 0.5 * coordinate[index][3]
            # 将坐标映射到分割后的格子
            if x < x_min:
                x_segment = 1
            else:
                x_segment = min(math.ceil((x - x_min) / ((x_max - x_min) / x_segments)), x_segments)
            if y < y_min:
                y_segment = 1
            else:
                y_segment = min(math.ceil((y - y_min) / ((y_max - y_min) / y_segments)), y_segments)
            ice.add(f"{x_segment}-{y_segment}")

    return wave, god_wind, list(positions), list(obstacle), list(ice)     # 返回是否有神风，是否有波次，待爆炸点位, 可消除障碍点位, 冰块点位

# 示例调用
# base_info = [0, 0, 4, 6]
# coordinate = [ [np.float32(1195.9874), np.float32(870.25305), np.float32(104.10489), np.float32(126.19858)], [np.float32(1307.134), np.float32(169.3344), np.float32(104.08145), np.float32(130.58484)], [np.float32(1526.3342), np.float32(637.1599), np.float32(106.510345), np.float32(125.32411)], [np.float32(758.6747), np.float32(769.79004), np.float32(107.91458), np.float32(125.20587)]]
# wave, godwind, positions = parse_positions(coordinate, base_info)
# print("Wave:", wave)
# print("Godwind:", godwind)
# print("Positions:", positions)
