import os
import shutil


class FileMover:
    def __init__(self, src_dir, dest_dir):
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self.files_to_move = []
        self.folders_to_move = {}

    def add_folder(self, folder_name, exclude_files=None, exclude_types=None):
        """
        添加一个文件夹及其排除的文件名和文件类型。

        :param folder_name: 文件夹名称
        :param exclude_files: 需要排除的文件名列表
        :param exclude_types: 需要排除的文件类型列表 (例如 ['.txt', '.jpg'])
        """
        if exclude_files is None:
            exclude_files = []
        if exclude_types is None:
            exclude_types = []
        self.folders_to_move[folder_name] = {
            'exclude_files': exclude_files,
            'exclude_types': exclude_types
        }

    def add_file(self, file_name):
        """
        添加一个文件。

        :param file_name: 文件名称
        """
        self.files_to_move.append(file_name)

    def _copy_item(self, src, dest, dry_run=False):
        """
        复制单个文件或文件夹。

        :param src: 源路径
        :param dest: 目标路径
        :param dry_run: 是否为预演模式
        """
        if not dry_run:
            if os.path.isfile(src):
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

        # 复制文件夹
        for folder, exclude_info in self.folders_to_move.items():
            src_folder = os.path.join(self.src_dir, folder)
            dest_folder = os.path.join(self.dest_dir, folder)
            self._copy_folder(
                src_folder=src_folder,
                dest_folder=dest_folder,
                exclude_files=exclude_info['exclude_files'],
                exclude_types=exclude_info['exclude_types'])

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

        # 预览复制文件夹
        for folder, exclude_info in self.folders_to_move.items():
            src_folder = os.path.join(self.src_dir, folder)
            dest_folder = os.path.join(self.dest_dir, folder)
            self._copy_folder(
                src_folder=src_folder,
                dest_folder=dest_folder,
                exclude_files=exclude_info['exclude_files'],
                exclude_types=exclude_info['exclude_types'],
                dry_run=True)

    def _copy_folder(self, src_folder, dest_folder, exclude_files, exclude_types, dry_run=False):
        """
        复制整个文件夹及其内容，排除指定的文件或文件类型。

        :param src_folder: 源文件夹路径
        :param dest_folder: 目标文件夹路径
        :param exclude_files: 需要排除的文件名列表
        :param exclude_types: 需要排除的文件类型列表
        :param dry_run: 是否为预演模式
        """
        if not dry_run and not os.path.exists(dest_folder):
            os.makedirs(dest_folder)

        for item in os.listdir(src_folder):
            src_item = os.path.join(src_folder, item)
            dest_item = os.path.join(dest_folder, item)
            if item in exclude_files:
                continue
            if os.path.isfile(src_item) and self._should_exclude_by_type(item, exclude_types):
                continue
            if os.path.isdir(src_item):
                self._copy_folder(src_item, dest_item, exclude_files, exclude_types, dry_run=dry_run)
            else:
                self._copy_item(src_item, dest_item, dry_run=dry_run)

    def _should_exclude_by_type(self, filename, exclude_types):
        """
        判断文件是否应该被排除。

        :param filename: 文件名
        :param exclude_types: 需要排除的文件类型列表
        :return: 如果文件应该被排除，则返回 True；否则返回 False
        """
        _, ext = os.path.splitext(filename)
        return ext.lower() in exclude_types

    def _ensure_destination_exists(self):
        """
        确保目标目录存在。
        """
        if not os.path.exists(self.dest_dir):
            os.makedirs(self.dest_dir)


def main():
    """因为被pyinstaller的蜜汁机制折磨疯了, 我还是直接复制粘贴就好了"""

    # 初始化 FileMover 实例
    mover = FileMover(
        src_dir=".",
        dest_dir="..\\_ExeWorkSpace\\dist\\FAA"
    )

    # 添加文件夹及其排除列表
    mover.add_folder("config", exclude_files=["settings.json"])
    mover.add_folder("battle_plan")
    mover.add_folder("battle_plan_not_active")
    mover.add_folder("md_img")
    mover.add_folder("task_sequence")
    mover.add_folder("resource", exclude_types=[".pyc"])

    # 添加文件
    mover.add_file("[入门]FAA从入门到神殿.docx")
    mover.add_file("[入门]FAA从入门到神殿.pdf")
    mover.add_file("LICENSE")
    mover.add_file("README.md")
    mover.add_file("致谢名单.md")
    mover.add_file("致谢名单.png")

    # 预览移动
    mover.preview()

    # 实际移动
    mover.run()


main()
