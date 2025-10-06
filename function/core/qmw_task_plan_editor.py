import json
import re
import shutil
import sys
import os
import sqlite3
from difflib import get_close_matches

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter,
    QListWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QTextEdit, QPushButton,
    QMessageBox, QFormLayout, QFrame, QListWidgetItem, QMenu, QCheckBox,
    QSpinBox,  QSizePolicy, QScrollArea
)
from PyQt6.QtGui import QPixmap, QAction

from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.scattered.get_list_battle_plan import get_list_battle_plan


# 初始化数据库
def init_db(db_path="tasks.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            task_type TEXT NOT NULL,
            image_data BLOB,
            description_image_data BLOB,  
            parameters TEXT,
            stage_param TEXT,  
            remarks TEXT
        )
    """)
    conn.commit()
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN stage_param TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # 如果列已存在则忽略
    return conn


class StageSelector(QWidget):
    on_selected = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.menu_data = {}
        self.current_text = ""

        self.button = QPushButton("请选择关卡")
        self.button.clicked.connect(self.show_menu)

        layout = QHBoxLayout(self)
        layout.addWidget(self.button)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def add_menu(self, data):
        """强制更新菜单数据"""
        self.menu_data = data
        self.button.setText("请选择关卡")
        self.button.update()

    def show_menu(self):
        """显示多级菜单"""
        menu = QMenu(self)
        self._build_menu(menu, self.menu_data)
        pos = self.button.mapToGlobal(self.button.rect().bottomLeft())
        action = menu.exec(pos)

        if action and action.data():
            self.current_text = action.text()
            self.button.setText(self.current_text)
            self.on_selected.emit(self.current_text, action.data())

    def _build_menu(self, parent_menu, data):
        """递归构建菜单"""
        for key, value in data.items():
            if isinstance(value, dict):
                submenu = parent_menu.addMenu(key)
                self._build_menu(submenu, value)
            elif isinstance(value, list):
                for name, code in value:
                    action = QAction(name, self)
                    action.setData(code)
                    parent_menu.addAction(action)


class TaskEditor(QMainWindow):
    def __init__(self, db_conn):
        super().__init__()
        self.setWindowTitle("任务数据编辑器")
        self.setGeometry(100, 100, 1400, 750)
        self.setFixedSize(1400, 750)
        self.db_conn = db_conn
        self.current_task_id = None
        self.image_data = None
        self.description_image_data = None

        self.image_dir = PATHS["image"]["task"]["chaos"]
        self.description_image_dir = PATHS["image"]["task"]["desc"]


        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)


        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)


        self.task_list = QListWidget()
        self.task_list.itemClicked.connect(self.on_task_selected)


        self.image_list = QListWidget()
        self.image_list.itemClicked.connect(self.on_image_selected)


        btn_frame = QWidget()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.update_btn = QPushButton("修改")
        delete_btn = QPushButton("删除")
        self.sort_btn = QPushButton("按名称排序")  # 新增排序按钮
        self.update_btn.clicked.connect(self.save_task)
        delete_btn.clicked.connect(self.delete_task)
        self.sort_btn.clicked.connect(self.sort_tasks_by_name)  # 连接排序功能
        btn_layout.addWidget(self.update_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(self.sort_btn)

        left_layout.addWidget(QLabel("任务列表"))
        left_layout.addWidget(self.task_list)
        left_layout.addWidget(QLabel("图像目录预览"))
        left_layout.addWidget(self.image_list)
        left_layout.addWidget(btn_frame)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        form_frame = QFrame()
        form_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        form_layout = QFormLayout(form_frame)
        self.remarks = QTextEdit()
        self.remarks.setMaximumHeight(60)
        self.task_name = QLineEdit()
        self.task_type = QComboBox()
        self.task_type.addItems(["刷关", "强卡", "情报",  "其它"])
        self.task_type.currentTextChanged.connect(self.update_params)

        self.param_container = QWidget()
        self.param_container_layout = QVBoxLayout(self.param_container)


        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.param_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)


        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setMinimumHeight(300)

        form_layout.addRow("参数设置:", self.scroll_area)
        form_layout.addRow("任务名称:", self.task_name)
        form_layout.addRow("任务类型:", self.task_type)

        btn_panel = QWidget()
        btn_layout = QHBoxLayout(btn_panel)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        save_btn = QPushButton("增加")
        clear_btn = QPushButton("清除")
        save_btn.clicked.connect(self.add_task)
        clear_btn.clicked.connect(self.clear_form)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(clear_btn)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 1300])
        layout.addWidget(splitter)

        self.initialization_tasks()
        self.load_image_directory()


        self.stage_info = self.load_stage_info()
        self.stage_selector = StageSelector()
        self.stage_selector.setVisible(False)
        self.stage_selector.on_selected.connect(self.on_stage_selected)


        form_layout.addRow("关卡:", self.stage_selector)
        form_layout.addRow("备注:", self.remarks)

        main_ocr_splitter = QSplitter(Qt.Orientation.Horizontal)


        main_content = QWidget()
        main_content_layout = QVBoxLayout(main_content)
        main_content_layout.setContentsMargins(0, 0, 0, 0)


        main_content_layout.addWidget(form_frame)

        main_content_layout.addWidget(btn_panel)


        ocr_group = QWidget()
        ocr_group.setFixedWidth(300)
        ocr_layout = QVBoxLayout(ocr_group)
        ocr_layout.setContentsMargins(5, 5, 5, 5)

        self.image_label = QLabel("主图像预览")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(290, 200)
        self.image_label.setStyleSheet("background: #f0f0f0; border: 1px solid #ccc")
        ocr_layout.addWidget(self.image_label)
        

        self.description_image_label = QLabel("描述图像预览")
        self.description_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_image_label.setFixedSize(290, 180)
        self.description_image_label.setStyleSheet("background: #000000; border: 1px solid #ccc")
        ocr_layout.addWidget(self.description_image_label)

        self.ocr_button = QPushButton("执行OCR识别")
        self.ocr_result = QTextEdit()
        self.ocr_result.setReadOnly(True)
        self.ocr_result.setPlaceholderText("OCR识别结果将显示在此处")

        ocr_layout.addWidget(self.ocr_button)
        self.install_ocr_button = QPushButton("安装OCR环境")
        ocr_layout.addWidget(self.install_ocr_button)
        ocr_layout.addWidget(self.ocr_result)

        ocr_layout.addWidget(QLabel("任务描述OCR结果:"))
        self.desc_ocr_result = QTextEdit()
        self.desc_ocr_result.setReadOnly(True)
        self.desc_ocr_result.setFixedHeight(100)
        ocr_layout.addWidget(self.desc_ocr_result)


        main_ocr_splitter.addWidget(main_content)
        main_ocr_splitter.addWidget(ocr_group)
        main_ocr_splitter.setSizes([1000, 300])  # 初始比例分配


        right_layout.addWidget(main_ocr_splitter)


        self.ocr_button.clicked.connect(self.perform_ocr)
        self.install_ocr_button.clicked.connect(self.install_ocr_environment)


        self.update_params()

    def install_ocr_environment(self):
        """安装OCR环境：克隆仓库并复制补丁文件"""
        try:
            plugin_path = PATHS["plugins"] + "//chineseocr_lite_onnx"
            resource_path = PATHS["plugins"] + "//pak//chinese_ocr.py"

            # 1. 创建/清理插件目录
            if os.path.exists(plugin_path):
                shutil.rmtree(plugin_path)
            os.makedirs(plugin_path)

            # 2. 执行git克隆（需要确保git已安装）
            import subprocess
            subprocess.run([
                "git", "clone",
                "https://github.com/DayBreak-u/chineseocr_lite.git",
                plugin_path
            ], check=True)

            # 3. 复制补丁文件
            if os.path.exists(resource_path):
                shutil.copy(resource_path, f"{plugin_path}//chinese_ocr.py")
                QMessageBox.information(self, "成功", "OCR环境安装完成！")
            else:
                raise FileNotFoundError("补丁文件未找到")
            # 4. 兼容性修改
            file_path = plugin_path + r"\dbnet\decode.py"

            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 修改特定行
            modified = False
            for i in range(len(lines)):
                # 修改116-119行附近的np.int替换为int
                if 115 <= i <= 118:  # 文件索引从0开始，所以115对应第116行
                    if 'np.int' in lines[i]:
                        lines[i] = lines[i].replace('np.int', 'int')
                        modified = True

            # 写入修改后的内容
            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                print("文件修改成功！")
            else:
                print("未找到需要修改的内容")

        except Exception as e:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("错误")
            msg.setText(f"安装失败，确保已安装git，并且网络良好：{str(e)}")
            msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            msg.exec()

    def perform_ocr(self):
        """执行OCR识别并自动填充任务名称与关卡"""
        if not hasattr(self, 'current_main_image_path'):
            QMessageBox.warning(self, "警告", "请先选择一张图片！")
            return


        try:
            from plugins.chineseocr_lite_onnx.chinese_ocr import try_ocr_sort, try_ocr
            # 主图像处理
            main_result = try_ocr_sort(self.current_main_image_path)
            self.ocr_result.setPlainText("\n".join(main_result))

            # 主图像清理与自动填充
            cleaned_text = [re.sub(r'^\d+、', '', text).strip() for text in main_result]
            if len(cleaned_text) >= 2:
                self.task_name.setText(cleaned_text[-2])
                # 关卡匹配逻辑保持不变
                if self.stage_selector.menu_data:
                    all_stage_names = []
                    for parent in self.stage_selector.menu_data.values():
                        for sub in parent.values():
                            for name, code in sub:
                                all_stage_names.append((name, code))
                    ocr_stage_name = cleaned_text[-1]
                    matches = get_close_matches(ocr_stage_name, [name for name, code in all_stage_names], n=1,
                                                cutoff=0.5)
                    if matches:
                        matched_name = matches[0]
                        matched_code = next(code for name, code in all_stage_names if name == matched_name)
                        self.select_stage_by_code(matched_code)
                        QMessageBox.information(self, "成功", f"已自动选择关卡：{matched_name}")

            if hasattr(self, 'current_desc_image_path') and os.path.exists(self.current_desc_image_path):
                desc_result = try_ocr(path=self.current_desc_image_path,size=896)
                processed_text = "，".join([re.sub(r'^\d+、', '', text).strip() for box, text, score in desc_result])
                self.desc_ocr_result.setPlainText(processed_text)

                if processed_text:
                    matches = re.findall(r"使用(.*?)卡", processed_text, re.DOTALL)
                    if len(matches)>0 :
                        clean_name = re.sub(r'[^\u4e00-\u9fa5]', '', matches[-1].strip())
                        self.card_name_edit.setText(clean_name)

            else:
                self.desc_ocr_result.setPlainText("未选择描述图像或图像不存在")

        except Exception as e:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("错误")
            msg.setText(f"OCR识别失败：该功能仅限github源码版使用，请先点下方按钮安装环境，安装之后如果提示缺库请自行通过pip安装Shapely,pyclipper,Pillow等库{str(e)}")
            msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            msg.exec()


    def add_task(self):
        """强制新增任务"""
        self.current_task_id = None
        self.save_task()


    def load_stage_info(self):
        """加载关卡配置文件"""
        try:
            with open(PATHS["config"] + "//stage_info.json", "r", encoding="UTF-8") as f:
                return json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"加载关卡配置失败：{str(e)}")
            return {}



    def load_image_directory(self):
        """加载指定目录下的图像文件（按数字顺序排序）"""
        print(f"开始加载目录: {self.image_dir}")
        if not os.path.exists(self.image_dir):
            print("目录不存在")
            self.image_list.addItem("目录不存在")
            return


        image_extensions = (".jpg", ".png", ".bmp")

        # 自然排序辅助函数
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower()
                    for text in re.split('(\d+)', s)]

        self.image_list.clear()

        try:

            files = os.listdir(self.image_dir)


            sorted_files = sorted(files, key=natural_sort_key)

            for filename in sorted_files:
                if filename.lower().endswith(image_extensions):
                    item = QListWidgetItem(filename)
                    item.setData(Qt.ItemDataRole.UserRole,
                                 os.path.join(self.image_dir, filename))
                    item.setData(Qt.ItemDataRole.UserRole + 1,
                                 os.path.join(self.description_image_dir, filename))
                    self.image_list.addItem(item)
        except Exception as e:
            print(f"加载目录失败: {e}")
            QMessageBox.critical(self, "错误", f"加载目录失败：{str(e)}")

    def on_image_selected(self, item):
        """点击图像文件时更新双图像预览"""
        main_image_path = item.data(Qt.ItemDataRole.UserRole)
        desc_image_path = item.data(Qt.ItemDataRole.UserRole + 1)
        self.current_main_image_path = main_image_path
        self.current_desc_image_path = desc_image_path  # 新增：保存描述图像路径

        try:
            with open(main_image_path, "rb") as file:
                self.image_data = file.read()
            self.show_image_from_data(self.image_data)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法加载主图像：{str(e)}")


        try:
            if os.path.exists(desc_image_path):
                with open(desc_image_path, "rb") as file:
                    self.description_image_data = file.read()
                self.show_description_image_from_data(self.description_image_data)
            else:
                self.description_image_label.setText("描述图像未找到")
                self.description_image_data = None
        except Exception as e:
            QMessageBox.warning(self, "警告", f"描述图像加载异常：{str(e)}")
            self.description_image_label.setText("描述图像加载失败")

    def show_description_image_from_data(self, image_data):
        """从二进制数据显示描述图像"""
        try:
            pixmap = QPixmap()
            if not image_data or not pixmap.loadFromData(image_data):
                raise ValueError("描述图像数据无效或加载失败")
            pixmap = pixmap.scaled(
                self.description_image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.description_image_label.setPixmap(pixmap)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"描述图像显示失败：{str(e)}")
            self.description_image_label.setText("描述图像无效")

    def show_image_from_data(self, image_data):
        """从二进制数据显示图像"""
        try:
            pixmap = QPixmap()
            if not pixmap.loadFromData(image_data):
                raise ValueError("无法加载图像数据")
            pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(pixmap)
            self.image_label.setToolTip("当前图像数据")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"图像加载失败：{str(e)}")

    def update_params(self):
        selected_type = self.task_type.currentText()

        if selected_type == "刷关" and not self.stage_selector.menu_data:
            self.build_stage_selector()

        while self.param_container_layout.count():
            child = self.param_container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if selected_type == "刷关":
            self.stage_selector.setVisible(True)
            self.create_shuaguan_params()
        elif selected_type == "强卡":
            self.stage_selector.setVisible(False)
            self.create_qiangka_params()
        else:
            self.stage_selector.setVisible(False)

    def create_shuaguan_params(self):
        """创建刷关扩展参数"""
        while self.param_container_layout.count():
            child = self.param_container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.use_key_checkbox = QCheckBox()
        self.card_name_edit = QLineEdit()
        self.times_spinbox = QSpinBox()
        self.times_spinbox.setRange(1, 99)
        self.disable_stars_combo = QComboBox()
        self.disable_stars_combo.addItems(["无禁用", "1星", "2星", "3星", "4星", "5星","6星", "7星", "8星", "9星", "10星", "11星","12星", "13星", "14星", "15星", "16星"])
        self.player_mode_combo = QCheckBox()
        self.is_single_player_checkbox = QCheckBox()
        self.banned_card_edit = QLineEdit()
        self.banned_card_count_spinbox = QSpinBox()
        self.banned_card_count_spinbox.setRange(0, 22)
        self.disable_pet_checkbox = QCheckBox()
        self.disable_weapon_checkbox = QCheckBox()
        self.global_plan_checkbox = QCheckBox()
        self.deck_selector = QComboBox()
        self.deck_selector.addItems([str(i) for i in range(0,7)])
        self.deck_selector.setCurrentText("0")
        self.battle_plan_1p = QComboBox()
        self.battle_plan_2p = QComboBox()
        self._init_battle_plan_selector()
        self.skip_checkbox = QCheckBox()

        self._add_param_pair("启用全局方案:", self.global_plan_checkbox)
        self._add_param_pair("是否单人:", self.is_single_player_checkbox)
        self._add_param_pair("是否跳过:", self.skip_checkbox)
        self._add_param_pair("1P方案:", self.battle_plan_1p)
        self._add_param_pair("2P方案:", self.battle_plan_2p)
        self._add_param_pair("使用钥匙:", self.use_key_checkbox)
        self._add_param_pair("带卡名称:", self.card_name_edit)
        self._add_param_pair("禁卡名称:", self.banned_card_edit)
        self._add_param_pair("是否双人:", self.player_mode_combo)
        self._add_param_pair("选择卡组:", self.deck_selector)
        self._add_param_pair("次数:", self.times_spinbox)
        self._add_param_pair("禁用星级:", self.disable_stars_combo)
        self._add_param_pair("带卡数量:", self.banned_card_count_spinbox)
        self._add_param_pair("禁用宠物:", self.disable_pet_checkbox)
        self._add_param_pair("禁用武器:", self.disable_weapon_checkbox)

    def _init_battle_plan_selector(self):
        """初始化战斗方案选择器（仿照关卡方案编辑器）"""
        self.battle_plan_name_list = get_list_battle_plan(with_extension=False)
        self.battle_plan_uuid_list = list(EXTRA.BATTLE_PLAN_UUID_TO_PATH.keys())

        for name in self.battle_plan_name_list:
            self.battle_plan_1p.addItem(name)
            self.battle_plan_2p.addItem(name)


    def create_qiangka_params(self):
        """创建强卡扩展参数"""
        while self.param_container_layout.count():
            child = self.param_container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.star_combo = QComboBox()
        self.star_combo.addItems(["0星","1星", "2星", "3星", "4星", "5星","6星","7星", "8星", "9星", "10星", "11星","12星","13星", "14星", "15星", "16星"])
        self.quantity_spinbox = QSpinBox()
        self.quantity_spinbox.setRange(1, 999)
        self.card_name_edit = QLineEdit()

        self._add_param_pair("星级:", self.star_combo)
        self._add_param_pair("数量:", self.quantity_spinbox)
        self._add_param_pair("制卡名称:", self.card_name_edit)

    def _add_param_pair(self, label_text, widget):
        """
        添加参数对（标签+控件）的统一方法
        """
        fixed_height = 30
        label = QLabel(label_text)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setFixedHeight(fixed_height)

        widget.setMinimumHeight(fixed_height)
        widget.setMaximumHeight(fixed_height + 10)

        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)


        h_layout.addWidget(label, 1)
        h_layout.addWidget(widget, 2)

        self.param_container_layout.addWidget(container)

    def build_stage_selector(self):
        """构建多级关卡选择器"""
        stage_dict = {}
        for type_id, stage_info_1 in self.stage_info.items():
            if type_id in ["default", "name", "tooltip", "update_time"]:
                continue

            type_name = stage_info_1["name"]
            stage_dict[type_name] = {}

            for sub_type_id, stage_info_2 in stage_info_1.items():
                if sub_type_id in ["name", "tooltip"]:
                    continue

                sub_type_name = stage_info_2["name"]
                stage_dict[type_name][sub_type_name] = []

                for stage_id, stage_info_3 in stage_info_2.items():
                    if stage_id in ["name", "tooltip"]:
                        continue

                    stage_name = stage_info_3["name"]
                    stage_code = f"{type_id}-{sub_type_id}-{stage_id}"
                    stage_dict[type_name][sub_type_name].append((stage_name, stage_code))

        self.stage_selector.add_menu(data=stage_dict)


    def on_stage_selected(self, text, stage_code):
        """处理关卡选择"""
        self.current_stage_code = stage_code
        self.stage_selector.setToolTip(text)
    def initialization_tasks(self):
        self.task_list.clear()
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id, task_name FROM tasks")
        for index, row in enumerate(cursor.fetchall(), 1):
            self.task_list.addItem(f"{index} - {row[1]}")

    def on_task_selected(self, item):
        task_index = self.task_list.row(item)
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id FROM tasks")
        task_ids = [row[0] for row in cursor.fetchall()]
        if 0 <= task_index < len(task_ids):
            task_id = task_ids[task_index]
            self.load_task(task_id)

    def load_task(self, task_id):
        self.current_task_id = task_id
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        task = cursor.fetchone()

        self.task_name.clear()
        self.remarks.clear()
        self.image_label.clear()
        self.description_image_label.clear()

        self.task_name.setText(task[1])
        self.task_type.setCurrentText(task[2])


        if task[3]:
            with open(PATHS["config"] + "//stage_info.json", "r", encoding="UTF-8") as f:
                self.stage_info = json.load(f)

            self.image_data = task[3]
            self.show_image_from_data(self.image_data)

        if task[4]:
            if isinstance(task[4], bytes):
                self.description_image_data = task[4]
                self.show_description_image_from_data(self.description_image_data)
            else:
                cursor.execute("UPDATE tasks SET description_image_data = NULL WHERE id=?", (task_id,))
                self.db_conn.commit()
                self.description_image_label.setText("描述图像数据已修复")


        if task[2] == "刷关":
            self.build_stage_selector()
            self.stage_selector.setVisible(True)

            if task[7]:
                self.select_stage_by_code(task[7])
            else:
                self.stage_selector.button.setText("请选择关卡")
                self.current_stage_code = None
        else:
            self.stage_selector.setVisible(False)
            self.stage_selector.button.setText("请选择关卡")
            self.current_stage_code = None
        try:
            if task[2] == "刷关" and task[5]:
                params = json.loads(task[5])
                self.use_key_checkbox.setChecked(params.get("use_key", False))
                self.card_name_edit.setText(params.get("card_name", ""))
                self.times_spinbox.setValue(params.get("times", 1))
                self.disable_stars_combo.setCurrentText(params.get("disable_stars", "无禁用"))
                self.player_mode_combo.setChecked(params.get("is_two_players", False))
                self.is_single_player_checkbox.setChecked(params.get("is_single_player", False))
                self.banned_card_edit.setText(params.get("banned_card", ""))
                self.banned_card_count_spinbox.setValue(params.get("banned_card_count", 0))
                self.disable_pet_checkbox.setChecked(params.get("disable_pet", False))
                self.disable_weapon_checkbox.setChecked(params.get("disable_weapon", False))
                self.global_plan_checkbox.setChecked(params.get("use_global_plan", False))
                self.deck_selector.setCurrentText(str(params.get("deck", 0)))
                self.skip_checkbox.setChecked(params.get("skip", False))  # 加载"是否跳过"参数
                if params.get("battle_plan_1p"):
                    self.battle_plan_1p.setCurrentIndex(self.battle_plan_uuid_list.index(params["battle_plan_1p"]))
                if params.get("battle_plan_2p"):
                    self.battle_plan_2p.setCurrentIndex(self.battle_plan_uuid_list.index(params["battle_plan_2p"]))

            elif task[2] == "强卡" and task[5]:
                params = json.loads(task[5])
                self.star_combo.setCurrentText(params.get("star", "0星"))
                self.quantity_spinbox.setValue(params.get("quantity", 1))
                self.card_name_edit.setText(params.get("card_name", ""))
        except json.JSONDecodeError:
            QMessageBox.warning(self, "警告", "参数加载失败：无效的参数格式")

    def select_stage_by_code(self, target_code):
        """强制查找并回显关卡"""
        self.stage_selector.button.setText("请选择关卡")

        for parent, children in self.stage_selector.menu_data.items():
            for sub_parent, items in children.items():
                for name, code in items:
                    if code == target_code:
                        full_path = f"{parent} > {sub_parent} > {name}"
                        self.stage_selector.button.setText(full_path)
                        self.current_stage_code = code
                        return

        self.stage_selector.button.setText("请选择关卡")
        self.current_stage_code = None

    def sort_tasks_by_name(self):
        """按任务名称排序数据库中的任务"""
        reply = QMessageBox.question(self, "确认", "确定要按名称重新排序所有任务吗？")
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cursor = self.db_conn.cursor()

                cursor.execute("SELECT id, task_name, task_type, image_data, description_image_data, parameters, stage_param, remarks FROM tasks ORDER BY task_name")
                sorted_tasks = cursor.fetchall()

                self.db_conn.execute("BEGIN TRANSACTION")

                cursor.execute("DELETE FROM tasks")

                for new_index, task_data in enumerate(sorted_tasks):
                    original_id, task_name, task_type, image_data, description_image_data, parameters, stage_param, remarks = task_data
                    cursor.execute("""INSERT INTO tasks 
                                   (id, task_name, task_type, image_data, description_image_data, parameters, stage_param, remarks)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                                   (new_index + 1, task_name, task_type, image_data, description_image_data, parameters, stage_param, remarks))

                self.db_conn.commit()

                self.initialization_tasks()
                self.clear_form()
                
                QMessageBox.information(self, "成功", "任务已按名称排序！")
            except Exception as e:
                self.db_conn.rollback()
                QMessageBox.critical(self, "错误", f"排序失败：{str(e)}")

    def delete_task(self):
        if not self.current_task_id:
            QMessageBox.warning(self, "警告", "请先选择一个任务！")
            return

        reply = QMessageBox.question(self, "确认", "确定要删除此任务吗？")
        if reply == QMessageBox.StandardButton.Yes:
            cursor = self.db_conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id=?", (self.current_task_id,))
            self.db_conn.commit()
            self.initialization_tasks()
            self.clear_form()
            QMessageBox.information(self, "成功", "任务已删除！")

    def save_task(self):
        sender = self.sender()

        if sender == self.update_btn and not self.current_task_id:
            QMessageBox.warning(self, "警告", "请先选择一个任务！")
            return
        name = self.task_name.text()
        task_type = self.task_type.currentText()

        remarks = self.remarks.toPlainText()

        if not name or not task_type or not self.image_data:
            QMessageBox.warning(self, "警告", "请填写所有必填项！")
            return

        desc_image_bytes = self.description_image_data if isinstance(self.description_image_data, bytes) else None

        cursor = self.db_conn.cursor()
        if self.task_type.currentText() == "刷关":
            params = {
                "use_key": self.use_key_checkbox.isChecked(),
                "card_name": self.card_name_edit.text(),
                "times": self.times_spinbox.value(),
                "disable_stars": self.disable_stars_combo.currentText(),
                "is_two_players": self.player_mode_combo.isChecked(),
                "is_single_player": self.is_single_player_checkbox.isChecked(),
                "banned_card": self.banned_card_edit.text(),
                "banned_card_count": self.banned_card_count_spinbox.value(),
                "disable_pet": self.disable_pet_checkbox.isChecked(),
                "disable_weapon": self.disable_weapon_checkbox.isChecked(),
                "use_global_plan": self.global_plan_checkbox.isChecked(),
                "deck": int(self.deck_selector.currentText()),
                "battle_plan_1p": self.battle_plan_1p.currentData(),
                "battle_plan_2p": self.battle_plan_2p.currentData(),
                "skip": self.skip_checkbox.isChecked()
            }
            stage_param = getattr(self, "current_stage_code", None)
            param = None
        elif self.task_type.currentText() == "强卡":
            params = {
                "star": self.star_combo.currentText(),
                "quantity": self.quantity_spinbox.value(),
                "card_name": self.card_name_edit.text()
            }
            stage_param = None
            param = None
        else:
            params = {}
            stage_param = None

        param_json = json.dumps(params, ensure_ascii=False)

        if self.current_task_id:
            cursor.execute("""UPDATE tasks SET 
                        task_name=?, task_type=?, image_data=?, 
                        description_image_data=?, parameters=?, stage_param=?, remarks=?
                        WHERE id=?""",
                           (name, task_type, self.image_data,
                            desc_image_bytes, param_json, stage_param, remarks, self.current_task_id))
        else:
            cursor.execute("""INSERT INTO tasks (
                        task_name, task_type, image_data, 
                        description_image_data, parameters, stage_param, remarks
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                           (name, task_type, self.image_data,
                            desc_image_bytes, param_json, stage_param, remarks))

        self.db_conn.commit()
        self.initialization_tasks()
        self.clear_form()
        QMessageBox.information(self, "成功", "任务已保存！")
        if not self.current_task_id:
            if hasattr(self, 'current_main_image_path') and hasattr(self, 'current_desc_image_path'):
                for i in range(self.image_list.count()):
                    item = self.image_list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == self.current_main_image_path:
                        self.image_list.takeItem(i)
                        break
                self.clear_form()

    def clear_form(self):
        self.current_task_id = None
        self.task_name.clear()
        self.task_type.setCurrentIndex(0)
        self.remarks.clear()
        self.image_label.clear()
        self.description_image_label.clear()
        self.image_data = None
        self.description_image_data = None




if __name__ == "__main__":
    path=PATHS["db"]+"/tasks.db"
    db_conn = init_db(path)
    app = QApplication(sys.argv)
    window = TaskEditor(db_conn)
    window.show()
    sys.exit(app.exec())
