import math


def parse_positions(coordinates, base_info):
    # 更新边界和分割数量
    x_min, x_max = 303, 839
    y_min, y_max = 110, 560
    x_segments = 9
    y_segments = 7

    # 初始化输出变量
    wave = False
    god_wind = False
    positions = []

    for index, base_value in enumerate(base_info):

        if base_value == 4:
            wave = True
            continue

        elif base_value == 5:
            god_wind = True
            continue

        elif base_value in [0, 1, 2, 3, 6]:
            x = coordinates[index][0] + 0.5 * coordinates[index][2]
            if base_value == 1:
                y = coordinates[index][1] + 0.5 * coordinates[index][3] + 50
            else:
                y = coordinates[index][1] + 0.5 * coordinates[index][3]

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
            positions.append(f"{x_segment}-{y_segment}")

    return wave, god_wind, positions  # 返回是否有神风，是否有波次，待爆炸点位

# 示例调用
# base_info = [0, 0, 1, 6, 2, 2, 1]
# coordinates = [
#     [1000, 1000], [400, 200], [500, 300], [700, 500],
#     [600, 600], [750, 700], [350, 100]
# ]
# wave, godwind, positions = parse_positions(base_info, coordinates)
# print("Wave:", wave)
# print("Godwind:", godwind)
# print("Positions:", positions)
