import os
import shutil


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

    def add_folder(self, target, exclude_files=None, exclude_paths=None, exclude_types=None):
        """ 添加文件夹及其中的所有文件到待移动列表，并支持排除特定文件或类型 """
        exclude_files = exclude_files or []
        exclude_paths = exclude_paths or []
        exclude_types = exclude_types or []

        for root, dirs, files in os.walk(os.path.join(self.src_dir, target)):
            rel_root = os.path.relpath(root, self.src_dir)
            for file in files:
                if file in exclude_files:
                    continue
                if os.path.join(rel_root, file) in exclude_paths:
                    continue
                if os.path.splitext(file)[1] in exclude_types:
                    continue
                self.to_move.append((
                    os.path.join(root, file),
                    os.path.join(self.dest_dir, rel_root, file)
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


def main():
    """因为被 py installer 的蜜汁机制折磨疯了, 我还是直接复制粘贴就好了"""

    # 初始化 FileMover 实例
    mover = FileMover(
        src_dir=".",
        dest_dir="..\\_ExeWorkSpace\\dist\\FAA"
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
            "config\\cus_images\\背包_装备_需使用的\\浮空岛酬劳.png",
            "config\\cus_images\\背包_装备_需使用的\\火山岛酬劳.png",
            "config\\cus_images\\背包_装备_需使用的\\美味岛酬劳.png",
        ]
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
        target="resource",
        exclude_types=[".pyc"]
    )

    # 添加文件或文件夹
    mover.add_file("新手入门 看我!!! 看我!!! 看我!!!.txt")
    mover.add_file("LICENSE")
    mover.add_file("README.md")
    mover.add_file("README - 高级放卡.md")
    mover.add_file("致谢名单.md")
    mover.add_file("致谢名单.png")
    mover.add_file("logs/item_ranking_dag_graph.json")

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
下面是调用样例

def main():

    # 初始化 FileMover 实例
    mover = FileMover(
        src_dir=".",
        dest_dir="..\\_ExeWorkSpace\\dist\\FAA"
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
            "config/cus_images/背包_装备_需使用的/任意通用包裹.png"
        ]
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
        target="resource",
        exclude_types=[".pyc"]
    )

    # 添加文件或文件夹
    mover.add_file("[入门]FAA从入门到神殿.docx")
    mover.add_file("[入门]FAA从入门到神殿.pdf")
    mover.add_file("LICENSE")
    mover.add_file("README.md")
    mover.add_file("高级放卡.md")
    mover.add_file("致谢名单.md")
    mover.add_file("致谢名单.png")
    mover.add_file("logs/item_ranking_dag_graph.json")

    # 预览移动
    mover.preview()

    # 实际移动
    # mover.run()  
"""

if __name__ == "__main__":
    main()
