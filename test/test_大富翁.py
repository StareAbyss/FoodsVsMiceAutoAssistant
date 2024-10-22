import random


def roll_dice():
    """模拟掷骰子，返回1到6之间的随机数"""
    return random.randint(1, 6)


def simulate_round(location):
    """模拟一轮游戏，返回完成一圈所需的骰子数"""
    location = location  # 初始位置
    dice_rolls = 0
    bonus_counter = 0  # 奖励计数器
    add_one_round = False  # 是否额外加一圈

    while True:

        # 如果超过38，调整位置
        if location >= 38:
            location -= 38
            break

        # 检查特殊格子并应用效果 然后中止本次计算
        if location == 4:  # 前进1格
            location += 1
            continue
        elif location == 34:  # 前进4格
            location += 4
            continue
        elif location in [9, 19, 28]:  # 前进1-6格
            location += roll_dice()
            continue
        elif location in [8, 12, 17, 29]:  # 后退1-6格
            location -= roll_dice()
            continue

        dice_roll = roll_dice()
        dice_rolls += 1
        location += dice_roll

        if location in [2, 15, 26, 37]:  # 骰子+1
            dice_rolls -= 1
        elif location == 33:  # 圈数+1，完成一圈
            add_one_round = True
        elif location in [5, 13, 18, 22, 24, 31, 35]:  # 获得奖励
            bonus_counter += 1

    return dice_rolls, bonus_counter, add_one_round, location


# 模拟多轮，计算平均骰子数和平均奖励数
total_rounds = 10000
total_rounds_count = 10000
total_dice_rolls = 0
total_bonus_counter = 0

position = 0
for _ in range(total_rounds):
    dice_rolls, bonus_counter, add_one_round, position = simulate_round(position)
    total_dice_rolls += dice_rolls
    total_bonus_counter += bonus_counter
    if add_one_round:
        total_rounds_count += 1

average_dice_rolls = total_dice_rolls / total_rounds_count
average_bonus_counter = total_bonus_counter / total_dice_rolls

print(f"平均需要 {average_dice_rolls:.2f} 个骰子完成一圈(计数器)")
print(f"平均获得 {average_bonus_counter:.2f} 奖励次/骰")
