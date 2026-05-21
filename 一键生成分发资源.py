import glob
import os
import shutil
import subprocess
from datetime import datetime


class FileMover:
    def __init__(self, src_dir, dest_dir):
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self.to_move = []

    def add_file(self, relative_path):
        """ 添加单个文件到待移动列表 """
        full_path = os.path.join(self.src_dir, relative_path)
        if os.path.isfile(full_path):
            self.to_move.append((full_path, os.path.join(self.dest_dir, relative_path)))

    def add_folder(self, target, exclude_files=None, exclude_paths=None, exclude_types=None, dest_subdir=None):
        """ 
        添加文件夹及其中的所有文件到待移动列表，并支持排除特定文件或类型 
        :param target: 源目录中的目标文件夹路径
        :param exclude_files: 要排除的文件名列表
        :param exclude_paths: 要排除的相对路径列表
        :param exclude_types: 要排除的文件扩展名列表
        :param dest_subdir: 基于 dest_dir 的目标相对路径。如果指定，会将 target 文件夹下的内容（保持子文件夹结构）移动到 dest_dir/dest_subdir 下，不包含 target 文件夹本身
        """
        exclude_files = exclude_files or []
        exclude_paths = exclude_paths or []
        exclude_types = exclude_types or []

        for root, dirs, files in os.walk(os.path.join(self.src_dir, target)):
            # 计算相对于 src_dir/target 的路径（即 target 文件夹内部的相对路径）
            rel_to_target = os.path.relpath(root, os.path.join(self.src_dir, target))
            if dest_subdir is not None:
                if rel_to_target == '.':
                    new_rel_root = dest_subdir if dest_subdir else ''
                else:
                    new_rel_root = os.path.join(dest_subdir, rel_to_target) if dest_subdir else rel_to_target
            else:
                new_rel_root = os.path.relpath(root, self.src_dir)
            
            for file in files:
                if file in exclude_files:
                    continue
                rel_path_for_exclude = os.path.relpath(os.path.join(root, file), self.src_dir)
                if rel_path_for_exclude in exclude_paths:
                    continue
                if os.path.splitext(file)[1] in exclude_types:
                    continue
                if new_rel_root:
                    dest_path = os.path.join(self.dest_dir, new_rel_root, file)
                else:
                    dest_path = os.path.join(self.dest_dir, file)
                
                self.to_move.append((
                    os.path.join(root, file),
                    dest_path
                ))

    def preview(self):
        """ 打印预览信息 """
        for src, dest in self.to_move:
            print(f'Would copy: {src} -> {dest}')

    def run(self):
        """ 执行文件移动操作 """
        for src, dest in self.to_move:
            dest_dir = os.path.dirname(dest)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            shutil.copy2(src, dest)
            print(f'Copied: {src} -> {dest}')


def get_latest_excel_file():
    """
    获取最新的图像资源Excel文件
    先执行数据库查询脚本生成最新文件，然后返回文件路径
    """
    excel_script = "card_image_url_get.py"

    print("\n" + "="*60)
    print("正在获取最新的图像资源文件...")
    print("="*60)

    try:
        # 执行数据库查询脚本
        print(f"执行脚本: {excel_script}")
        result = subprocess.run(
            ["python", excel_script],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

        # 输出脚本执行结果
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("警告:", result.stderr)

        if result.returncode != 0:
            print(f"✗ 脚本执行失败，返回码: {result.returncode}")
            return None

        # 查找最新生成的Excel文件（在当前目录）
        today = datetime.now().strftime('%Y-%m-%d')
        pattern = f"点我获取更多图像资源 {today}.xlsx"

        latest_file = None
        file_path = os.path.join(".", pattern)
        if os.path.exists(file_path):
            latest_file = file_path
            print(f"✓ 找到最新文件: {latest_file}")
            return latest_file
        else:
            print(f"✗ 未找到今天生成的文件: {pattern}")
            # 尝试查找最近的Excel文件
            all_excel_files = glob.glob(os.path.join(".", "点我获取更多图像资源 *.xlsx"))

            if all_excel_files:
                # 按修改时间排序，返回最新的
                latest_file = max(all_excel_files, key=os.path.getmtime)
                print(f"✓ 使用最近的文件: {latest_file}")
                return latest_file
            else:
                print("✗ 未找到任何图像资源文件")
                return None

    except Exception as e:
        print(f"✗ 获取图像资源文件时出错: {e}")
        return None


def main():
    """因为被 py installer 的蜜汁机制折磨疯了, 我还是直接复制粘贴就好了"""

    # 第一步：获取最新的图像资源Excel文件
    latest_excel = get_latest_excel_file()

    # 初始化 FileMover 实例
    mover = FileMover(
        src_dir=".",
        dest_dir="..\\dist\\FAA"
    )

    # 添加文件夹及其排除列表
    mover.add_folder(
        target="config",
        exclude_files=[
            "settings.json",
            "空间服登录界面_1P.png",
            "空间服登录界面_2P.png",
            "跨服远征_1p.png"
        ],
        exclude_paths=[
            "config\\cus_images\\背包_装备_需使用的\\任意通用包裹.png",
            "config\\cus_images\\背包_装备_需使用的\\星际酬劳.png",
            "config\\cus_images\\背包_装备_需使用的\\浮空酬劳.png",
            "config\\cus_images\\背包_装备_需使用的\\火山酬劳.png",
            "config\\cus_images\\背包_装备_需使用的\\美味酬劳.png",
        ]
    )

    mover.add_folder(
        target="plugins\\uv",
        dest_subdir="."
    )

    mover.add_folder(
        target="function"
    )
    mover.add_folder(
        target="plugins\\git_plus",
        exclude_files=[
            "dev_config.ini"
        ]
    )
    mover.add_folder(
        target="plugins\\pak"
    )
    mover.add_folder(
        target="battle_plan"
    )
    mover.add_folder(
        target="battle_plan_not_active"
    )
    mover.add_folder(
        target="md_img"
    )
    mover.add_folder(
        target="task_sequence"
    )
    mover.add_folder(
        target="tweak_plan"
    )
    mover.add_folder(
        target="resource",
        exclude_types=[".pyc"]
    )

    # 添加文件或文件夹
    tar_files = [
        "新手入门 看我!!! 看我!!! 看我!!!.txt",
        "FAA支持性检测, 仅限Win10+.bat",
        "LICENSE",
        "README.md",
        "README - 高级放卡.md",
        "致谢名单.md",
        "致谢名单.png",
        "logs/item_ranking_dag_graph.json",
        ".python-version",
        "pyproject.toml",
        "uv.lock",
    ]

    # 添加最新的图像资源Excel文件
    if latest_excel:
        tar_files.append(latest_excel)
        print(f"\n✓ 已添加图像资源文件到打包列表: {latest_excel}")
    else:
        print("\n⚠ 警告: 未找到图像资源文件，将跳过此文件")

    for tar_file in tar_files:
        mover.add_file(tar_file)

    # 预览移动
    mover.preview()

    # 实际移动
    mover.run()


"""
我需要完成一个文件迁移打包器，包含以下功能：
* 输入源目录和目标目录
* 根据源目录的相对路径，设置配置，包括以下
    * add_file 函数 直接根据相对路径加入移动列表
    * add_folder 函数 直接根据相对路径遍历内部所有子文件夹和文件，加入移动列表
        * 该函数需要支持 exclude_paths  exclude_files exclude_types 三个参数 参数为list
        * exclude_paths 根据相对路径排除文件 比如我在"config"路径中 可通过 "config/cus_images/背包_装备_需使用的/任意通用包裹.png"准确排除这个文件
        * exclude_files 根据文件名称 + 文件后缀名排除 比如 "致谢名单.png"
        * exclude_types 根据文件后缀名排除 比如 ".pyc"
* preview 函数 预览移动 输出样例
    Would copy:
    '.\config\cus_images\一些常用的图标\浮空岛酬劳.png' -> '..\_ExeWorkSpace\dist\FAA\config\cus_images\一些常用的图标\浮空岛酬劳.png'
* run 函数 实际移动 输出样例
    Copied:
    '.\LICENSE -> ..\_ExeWorkSpace\dist\FAA\LICENSE'
"""

if __name__ == "__main__":
    main()
