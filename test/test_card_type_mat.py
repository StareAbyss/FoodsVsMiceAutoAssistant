import os
"""
测试卡片材质类型配置文件读取功能
"""
import json
from function.globals.get_paths import PATHS


def test_load_card_type_mat():
    """测试加载 card_type_mat.json 配置文件"""

    config_path = os.path.join(PATHS["config"], 'card_type_mat.json')

    print(f"配置文件路径: {config_path}")
    print("-" * 50)

    try:
        with open(file=config_path, mode="r", encoding="UTF-8") as file:
            config = json.load(file)

        print("✓ 配置文件加载成功")
        print(f"✓ 共找到 {len(config)} 种卡片材质类型")
        print("-" * 50)

        # 遍历所有类型并显示
        for mat_type, cards in config.items():
            print(f"\n类型: {mat_type}")
            print(f"  卡片数量: {len(cards)}")
            print(f"  卡片列表: {cards}")

        print("\n" + "=" * 50)
        print("✓ 测试通过 - 配置文件格式正确")

    except FileNotFoundError:
        print("✗ 测试失败 - 配置文件不存在")

    except json.JSONDecodeError as e:
        print(f"✗ 测试失败 - JSON格式错误: {e}")


if __name__ == "__main__":
    test_load_card_type_mat()
