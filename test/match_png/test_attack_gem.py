"""
测试攻击宝石的图像匹配功能
"""
from function.common.bg_img_match import match_p_in_w
from function.globals.g_resources import RESOURCE_P
from function.scattered.gat_handle import faa_get_handle


def test_attack_gem():
    """
    测试能否找到攻击宝石

    步骤:
    1. 获取游戏窗口句柄
    2. 加载攻击宝石模板
    3. 在指定区域内进行图像匹配
    4. 输出匹配结果
    """

    print("=" * 60)
    print("开始测试攻击宝石匹配")
    print("=" * 60)

    # 第一步：获取游戏窗口句柄
    print("\n[1/4] 正在获取游戏窗口句柄...")
    source_handle = faa_get_handle(channel="锑食", mode="flash")

    if source_handle is None:
        print("✗ 错误：无法获取游戏窗口句柄，请确保游戏已启动")
        return

    print(f"✓ 成功获取窗口句柄: {source_handle}")

    # 第二步：设置搜索区域
    print("\n[2/4] 设置搜索区域...")
    source_range = [558, 89, 903, 532]  # [左上x, 左上y, 右下x, 右下y]
    print(f"  搜索区域: {source_range}")

    # 第三步：加载攻击宝石模板
    print("\n[3/4] 加载攻击宝石模板...")
    template = RESOURCE_P["synthesis"]["可分解宝石"]["攻击宝石.png"]
    print(f"  模板类型: {type(template)}")
    print(f"  模板形状: {template.shape if hasattr(template, 'shape') else 'N/A'}")

    # 第四步：执行图像匹配
    print("\n[4/4] 执行图像匹配...")
    match_status_code, match_result = match_p_in_w(
        source_handle=source_handle,
        source_range=source_range,
        template=template,
        match_tolerance=0.7,
        test_print=True,   # 打印详细日志
        test_show=True     # 显示匹配结果可视化
    )

    # 输出结果
    print("\n" + "=" * 60)
    print("匹配结果:")
    print(f"  状态码: {match_status_code}")

    if match_status_code == 0:
        print("  ✗ 匹配失败：发生致命错误")
    elif match_status_code == 1:
        print("  ✗ 匹配失败：未找到目标（匹配度低于阈值）")
    elif match_status_code == 2:
        print(f"  ✓ 匹配成功！")
        print(f"  位置坐标: {match_result}")
        print(f"    - X: {match_result[0]}")
        print(f"    - Y: {match_result[1]}")

    print("=" * 60)

    return match_status_code, match_result


if __name__ == "__main__":
    test_attack_gem()
