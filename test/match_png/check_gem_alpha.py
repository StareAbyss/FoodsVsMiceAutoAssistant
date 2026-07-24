"""
检查攻击宝石图片的Alpha通道问题
"""
import cv2
import numpy as np
from function.globals.g_resources import RESOURCE_P
from test.output_paths import get_test_output_dir


def check_alpha_channel():
    """
    检查攻击宝石图片的alpha通道值
    """

    print("=" * 60)
    print("检查攻击宝石图片的Alpha通道")
    print("=" * 60)

    # 加载图片
    template = RESOURCE_P["synthesis"]["可分解宝石"]["攻击宝石.png"]

    print(f"\n图片信息:")
    print(f"  形状: {template.shape}")
    print(f"  数据类型: {template.dtype}")
    print(f"  通道数: {template.shape[2] if len(template.shape) == 3 else 'N/A'}")

    # 检查是否有alpha通道（4通道）
    if len(template.shape) == 3 and template.shape[2] == 4:
        print("\n✓ 图片包含Alpha通道（BGRA格式）")

        # 分离通道
        b, g, r, alpha = cv2.split(template)

        print(f"\nAlpha通道统计:")
        print(f"  最小值: {np.min(alpha)}")
        print(f"  最大值: {np.max(alpha)}")
        print(f"  平均值: {np.mean(alpha):.2f}")
        print(f"  标准差: {np.std(alpha):.2f}")

        # 检查透明区域（alpha接近0的像素）
        transparent_mask = alpha < 10  # alpha值小于10的认为是透明
        transparent_count = np.sum(transparent_mask)
        total_pixels = alpha.shape[0] * alpha.shape[1]
        transparent_ratio = transparent_count / total_pixels * 100

        print(f"\n透明区域分析 (alpha < 10):")
        print(f"  透明像素数: {transparent_count}")
        print(f"  总像素数: {total_pixels}")
        print(f"  透明比例: {transparent_ratio:.2f}%")

        # 检查半透明区域（alpha在10-250之间）
        semi_transparent_mask = (alpha >= 10) & (alpha <= 250)
        semi_transparent_count = np.sum(semi_transparent_mask)
        semi_transparent_ratio = semi_transparent_count / total_pixels * 100

        print(f"\n半透明区域分析 (10 <= alpha <= 250):")
        print(f"  半透明像素数: {semi_transparent_count}")
        print(f"  半透明比例: {semi_transparent_ratio:.2f}%")

        # 显示alpha通道的唯一值
        unique_alpha = np.unique(alpha)
        print(f"\nAlpha通道的唯一值数量: {len(unique_alpha)}")
        if len(unique_alpha) <= 20:
            print(f"  唯一值列表: {unique_alpha}")
        else:
            print(f"  最小10个值: {unique_alpha[:10]}")
            print(f"  最大10个值: {unique_alpha[-10:]}")

        # 检查透明区域的RGB值
        if transparent_count > 0:
            print(f"\n透明区域的RGB值示例（前5个）:")
            transparent_positions = np.where(transparent_mask)
            for i in range(min(5, len(transparent_positions[0]))):
                y, x = transparent_positions[0][i], transparent_positions[1][i]
                print(f"  位置({x}, {y}): B={b[y,x]}, G={g[y,x]}, R={r[y,x]}, Alpha={alpha[y,x]}")

        # 保存alpha通道图像以便可视化
        output_dir = get_test_output_dir("match_png")
        alpha_path = output_dir / "alpha_channel_debug.png"
        cv2.imwrite(str(alpha_path), alpha)
        print(f"\n✓ 已保存Alpha通道图像到: {alpha_path}")

        # 创建掩模（将非完全透明的区域设为255，完全透明设为0）
        mask = np.where(alpha > 10, 255, 0).astype(np.uint8)
        mask_path = output_dir / "mask_debug.png"
        cv2.imwrite(str(mask_path), mask)
        print(f"✓ 已保存二值化掩模到: {mask_path}")

        print("\n" + "=" * 60)
        print("结论:")
        if semi_transparent_ratio > 1:
            print(f"⚠ 警告：存在{semi_transparent_ratio:.2f}%的半透明像素！")
            print("  这会导致模板匹配时匹配度降低。")
            print("  建议：使用掩模或预处理图片去除半透明边缘。")
        else:
            print("✓ Alpha通道看起来正常，没有明显的半透明问题。")
        print("=" * 60)

    else:
        print("\n✗ 图片不包含Alpha通道（不是BGRA格式）")
        print(f"  当前格式: {'BGR' if len(template.shape) == 3 and template.shape[2] == 3 else 'GrayScale'}")


if __name__ == "__main__":
    check_alpha_channel()
