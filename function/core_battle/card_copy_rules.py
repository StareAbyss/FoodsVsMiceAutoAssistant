def get_creator_god_safe_locations(locations: list[str]) -> list[str]:
    """
    返回周围完整 3×3 都属于原卡摆放范围的中心格。

    结果保留战斗方案中的原始位置顺序，供非遍历模式选取首项，也供遍历
    模式依次放置。棋盘坐标为左上 ``1-1``、右下 ``9-7``。
    """
    parsed_locations = set()
    for location in locations:
        try:
            column_text, row_text = location.split("-", maxsplit=1)
            column = int(column_text)
            row = int(row_text)
        except (AttributeError, TypeError, ValueError):
            continue
        if 1 <= column <= 9 and 1 <= row <= 7:
            parsed_locations.add((column, row))

    safe_locations = []
    for location in locations:
        try:
            column_text, row_text = location.split("-", maxsplit=1)
            column = int(column_text)
            row = int(row_text)
        except (AttributeError, TypeError, ValueError):
            continue
        surrounding = {
            (column + column_offset, row + row_offset)
            for column_offset in (-1, 0, 1)
            for row_offset in (-1, 0, 1)
        }
        if surrounding.issubset(parsed_locations):
            safe_locations.append(location)
    return safe_locations
