import os
import shutil


class FileMover:
    def __init__(self, src_dir, dest_dir):
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self.files_to_move = []
        self.excluded_files = set()
        self.excluded_types = set()

    def add_folder_or_file(self, tar, exclude_files=None, exclude_types=None):
        """
        添加一个文件或文件夹，并可设置排除的文件名和文件类型。

        :param tar: 文件或文件夹的相对路径
        :param exclude_files: 要排除的文件名列表
        :param exclude_types: 要排除的文件类型列表
        """

        src_full_path = os.path.join(self.src_dir, tar)
        dest_full_path = os.path.join(self.dest_dir, tar)

        if exclude_files is not None:
            self.excluded_files.update(exclude_files)
        if exclude_types is not None:
            self.excluded_types.update(exclude_types)

        if os.path.isfile(src_full_path):
            self.files_to_move.append(tar)
            print(f"Added file: {tar}")

        elif os.path.isdir(src_full_path):
            self._add_files_from_folder(src_full_path, tar)
        else:
            print(f"Add failed file: {tar}, not found")

    def _add_files_from_folder(self, src_folder, relative_path):
        """
        递归地添加文件夹下的所有文件，并排除指定的文件和文件类型。

        :param src_folder: 源文件夹的完整路径
        :param relative_path: 相对于源目录的文件夹路径
        """
        for item in os.listdir(src_folder):
            src_item = os.path.join(src_folder, item)
            if os.path.isfile(src_item) and self._should_include(item):
                self.files_to_move.append(os.path.join(relative_path, item))
                print(f"Added file: {os.path.join(relative_path, item)}")
            elif os.path.isdir(src_item):
                self._add_files_from_folder(src_item, os.path.join(relative_path, item))

    def _should_include(self, filename):
        """
        判断文件是否应该被包含。

        :param filename: 文件名
        :return: 如果文件应该被包含，则返回 True；否则返回 False
        """
        if filename in self.excluded_files:
            return False
        if any(filename.endswith(ext) for ext in self.excluded_types):
            return False
        return True

    def _copy_item(self, src, dest, dry_run=False):
        """
        复制单个文件或文件夹。

        :param src: 源路径
        :param dest: 目标路径
        :param dry_run: 是否为预演模式
        """
        if not dry_run:
            if os.path.isfile(src):
                # 确保目标目录存在
                self._ensure_path_exists(dest)
                shutil.copy2(src, dest)
            elif os.path.isdir(src):
                shutil.copytree(src, dest, dirs_exist_ok=True)
            print(f"Copied: {src} -> {dest}")
        else:
            print(f"Would copy: {src} -> {dest}")

    def run(self):
        """
        执行文件和文件夹的复制。
        """
        self._ensure_destination_exists()

        # 复制文件
        for file in self.files_to_move:
            src_file = os.path.join(self.src_dir, file)
            dest_file = os.path.join(self.dest_dir, file)
            self._copy_item(src_file, dest_file)

    def preview(self):
        """
        预览文件和文件夹的复制。
        """
        self._ensure_destination_exists()

        # 预览复制文件
        for file in self.files_to_move:
            src_file = os.path.join(self.src_dir, file)
            dest_file = os.path.join(self.dest_dir, file)
            self._copy_item(src_file, dest_file, dry_run=True)

    def _ensure_destination_exists(self):
        """
        确保目标目录存在。
        """
        if not os.path.exists(self.dest_dir):
            os.makedirs(self.dest_dir)

    def _ensure_path_exists(self, path):
        """
        确保给定路径的父目录存在。

        :param path: 目标路径
        """
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)


def main():
    """因为被pyinstaller的蜜汁机制折磨疯了, 我还是直接复制粘贴就好了"""

    # 初始化 FileMover 实例
    mover = FileMover(
        src_dir=".",
        dest_dir="..\\_ExeWorkSpace\\dist\\FAA"
    )

    # 添加文件夹及其排除列表
    mover.add_folder_or_file(
        tar="config",
        exclude_files=["settings.json", "空间服登录界面_1P.png", "空间服登录界面_2P.png", "跨服远征_1p.png"]
    )
    mover.add_folder_or_file(
        tar="battle_plan"
    )
    mover.add_folder_or_file(
        tar="battle_plan_not_active"
    )
    mover.add_folder_or_file(
        tar="md_img"
    )
    mover.add_folder_or_file(
        tar="task_sequence"
    )
    mover.add_folder_or_file(
        tar="resource",
        exclude_types=[".pyc"]
    )

    # 添加文件或文件夹
    mover.add_folder_or_file("[入门]FAA从入门到神殿.docx")
    mover.add_folder_or_file("[入门]FAA从入门到神殿.pdf")
    mover.add_folder_or_file("LICENSE")
    mover.add_folder_or_file("README.md")
    mover.add_folder_or_file("致谢名单.md")
    mover.add_folder_or_file("致谢名单.png")
    mover.add_folder_or_file("logs/item_ranking_dag_graph.json")

    # 预览移动
    # mover.preview()

    # 实际移动
    mover.run()


main()
