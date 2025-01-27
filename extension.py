
# 忽略警告: libpng warning: iCCP: known incorrect sRGB profile
import os
os.environ["PYTHONWARNINGS"] = "ignore::libpng warning"

import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QDoubleSpinBox, QScrollArea, QFileDialog, 
    QMessageBox, QCheckBox, QLabel, QSpinBox
)
from PyQt5.QtCore import Qt, QSize, QTimer

from function_faa import execute

class ImageSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # === 第一行：图片路径 ===
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(5)
        
        self.template_label = QLabel("图片路径:")
        self.template_label.setFixedWidth(60)
        path_layout.addWidget(self.template_label)
        
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setPlaceholderText("图片路径")
        path_layout.addWidget(self.image_path_edit)
        
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setFixedWidth(80)
        path_layout.addWidget(self.browse_btn)
        
        main_layout.addLayout(path_layout)

        # === 第二行：数值参数 ===
        param_layout = QHBoxLayout()
        param_layout.setContentsMargins(0, 0, 0, 0)
        param_layout.setSpacing(15)

        self.tolerance_group = self.create_param_group("精度:", 0.95, 2, "")
        param_layout.addLayout(self.tolerance_group)

        self.interval_group = self.create_param_group("间隔:", 0.10, 2, "秒")
        param_layout.addLayout(self.interval_group)

        self.timeout_group = self.create_param_group("超时:", 10.0, 2, "秒")
        param_layout.addLayout(self.timeout_group)

        sleep_container = QHBoxLayout()
        sleep_container.addStretch()
        self.sleep_group = self.create_param_group("休眠:", 0.50, 2, "秒")
        sleep_container.addLayout(self.sleep_group)
        param_layout.addLayout(sleep_container, stretch=1)
        
        main_layout.addLayout(param_layout)

        # === 第三行：功能区域 ===
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self.check_template_check = QCheckBox("点击后校验")
        action_layout.addWidget(self.check_template_check)

        self.x1_spin = QSpinBox()
        self.y1_spin = QSpinBox()
        self.x2_spin = QSpinBox()
        self.y2_spin = QSpinBox()

        area_layout = QHBoxLayout()
        area_layout.setSpacing(4)
        area_layout.addWidget(QLabel("截图区域:"))
        coordinates = [
            ("X1", self.x1_spin), ("Y1", self.y1_spin),
            ("X2", self.x2_spin), ("Y2", self.y2_spin)
        ]
        for text, spin in coordinates:
            spin.setRange(0, 9999)
            spin.setFixedWidth(60)
            spin.setAlignment(Qt.AlignmentFlag.AlignRight)
            area_layout.addWidget(QLabel(text))
            area_layout.addWidget(spin)
        
        coordinates[2][1].setValue(2000)
        coordinates[3][1].setValue(2000)
        
        action_layout.addLayout(area_layout)
        main_layout.addLayout(action_layout)

        # === 操作按钮 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.insert_after_btn = QPushButton("向后插入")
        self.insert_after_btn.setFixedWidth(100)
        btn_layout.addWidget(self.insert_after_btn)
        
        self.delete_btn = QPushButton("删除配置项")
        self.delete_btn.setFixedWidth(100)
        btn_layout.addWidget(self.delete_btn)
        
        main_layout.addLayout(btn_layout)

        self.browse_btn.clicked.connect(self.browse_image)

    def create_param_group(self, label, default, decimals, suffix):
        group = QHBoxLayout()
        group.setContentsMargins(0, 0, 0, 0)
        group.setSpacing(5)
        
        lbl = QLabel(label)
        lbl.setFixedWidth(60)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        group.addWidget(lbl)
        
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setValue(default)
        spin.setFixedWidth(100)
        if suffix:
            spin.setSuffix(f" {suffix}")
        group.addWidget(spin)
        return group

    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模板图片", "", "PNG Files (*.png)")
        if path:
            self.image_path_edit.setText(path)

    def get_data(self):
        return {
            "template_path": self.image_path_edit.text(),
            "tolerance": self.tolerance_group.itemAt(1).widget().value(),
            "interval": self.interval_group.itemAt(1).widget().value(),
            "timeout": self.timeout_group.itemAt(1).widget().value(),
            "after_sleep": self.sleep_group.itemAt(1).widget().value(),
            "check_enabled": self.check_template_check.isChecked(),
            "source_range": [
                self.x1_spin.value(),
                self.y1_spin.value(),
                self.x2_spin.value(),
                self.y2_spin.value()
            ]
        }

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("点击配置管理器")
        self.setMinimumWidth(800)
        self.initial_height = 200
        self.config_widgets = []
        self.current_config_path = None
        self.temp_config_path = "temp_config.json"

        self.init_ui()
        self.update_max_height()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        # === 当前配置路径显示 ===
        path_display_layout = QHBoxLayout()
        path_display_layout.addWidget(QLabel("当前配置路径:"))
        
        self.current_config_label = QLabel("无")
        self.current_config_label.setStyleSheet("color: #666;")
        self.current_config_label.setWordWrap(True)
        path_display_layout.addWidget(self.current_config_label, stretch=1)
        
        clear_btn = QPushButton("×")
        clear_btn.setFixedSize(20, 20)
        clear_btn.clicked.connect(lambda: self.update_config_path(None))
        path_display_layout.addWidget(clear_btn)
        
        main_layout.addLayout(path_display_layout)

        self.add_btn = QPushButton("添加配置")
        self.add_btn.clicked.connect(lambda: self.add_config())
        main_layout.addWidget(self.add_btn)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(5)
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll)

        # === 底部按钮布局 ===
        bottom_btn_layout = QHBoxLayout()
        
        self.open_btn = QPushButton("打开配置")
        self.open_btn.clicked.connect(self.load_config)
        bottom_btn_layout.addWidget(self.open_btn)

        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.save_config)
        bottom_btn_layout.addWidget(self.save_btn)

        bottom_btn_layout.addStretch()

        hwnd_label = QLabel("窗口名")
        bottom_btn_layout.addWidget(hwnd_label)

        self.window_name_edit = QLineEdit()
        self.window_name_edit.setFixedWidth(150)
        self.window_name_edit.setPlaceholderText("输入窗口名（如：美食大战老鼠 | 小号1）")
        bottom_btn_layout.addWidget(self.window_name_edit)

        self.execute_btn = QPushButton("执行脚本")
        self.execute_btn.setFixedWidth(100)
        self.execute_btn.clicked.connect(self.execute_script)
        bottom_btn_layout.addWidget(self.execute_btn)

        main_layout.addLayout(bottom_btn_layout)
        self.resize(QSize(800, self.initial_height))

    def update_config_path(self, path):
        """ 更新当前配置路径显示 """
        self.current_config_path = path
        display_text = path if path else "无"
        self.current_config_label.setText(display_text)
        self.current_config_label.setToolTip(display_text)

    def execute_script(self):
        """ 执行脚本的核心方法 """
        if not self.current_config_path:
            QMessageBox.warning(self, "警告", "请先保存配置或加载现有配置")
            return

        window_name = self.window_name_edit.text().strip()
        if not window_name:
            QMessageBox.warning(self, "警告", "请输入窗口名")
            return

        try:
            execute(window_name,self.current_config_path)
            QMessageBox.information(self, "成功", "脚本执行已完成")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"执行失败：{str(e)}")

    def update_max_height(self):
        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.max_window_height = int(screen_geo.height() * 0.6)

    def calculate_required_height(self):
        header_height = self.add_btn.sizeHint().height()
        footer_height = self.save_btn.sizeHint().height()
        margins = self.centralWidget().layout().contentsMargins()
        scroll_content_height = self.scroll_content.sizeHint().height()
        return (
            header_height +
            footer_height +
            scroll_content_height +
            margins.top() + margins.bottom() +
            20
        )

    def add_config(self, index=None, scroll=True):
        new_config = ImageSettingsWidget()
        
        if index is None:
            self.scroll_layout.addWidget(new_config)
            self.config_widgets.append(new_config)
        else:
            self.scroll_layout.insertWidget(index, new_config)
            self.config_widgets.insert(index, new_config)
        
        new_config.delete_btn.clicked.connect(
            lambda: self.remove_config(new_config)
        )
        new_config.insert_after_btn.clicked.connect(
            lambda: self.insert_config_after(new_config)
        )

        QApplication.processEvents()
        required_height = self.calculate_required_height()
        new_height = min(required_height, self.max_window_height)
        if new_height > self.height():
            self.resize(self.width(), new_height)
        
        if scroll:
            QTimer.singleShot(10, self.force_scroll_to_bottom)

    def insert_config_after(self, current_widget):
        try:
            index = self.config_widgets.index(current_widget)
            self.add_config(index + 1, scroll=False)
        except ValueError:
            self.add_config()

    def remove_config(self, widget):
        if widget in self.config_widgets:
            self.scroll_layout.removeWidget(widget)
            self.config_widgets.remove(widget)
            widget.deleteLater()
            
            QApplication.processEvents()
            required_height = self.calculate_required_height()
            new_height = min(required_height, self.max_window_height)
            if self.height() > new_height:
                self.resize(self.width(), new_height)
            
            self.update_scrollbar_policy(required_height)

    def force_scroll_to_bottom(self):
        scroll_bar = self.scroll.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())
        QTimer.singleShot(10, lambda: scroll_bar.setValue(scroll_bar.maximum()))

    def update_scrollbar_policy(self, required_height):
        if required_height > self.max_window_height:
            self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def save_config(self):
        config_data = [w.get_data() for w in self.config_widgets]
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存配置文件", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            self.update_config_path(file_path)
            QMessageBox.information(self, "成功", "配置保存成功！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存文件时出错：{str(e)}")

    def load_config(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开配置文件", "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            while self.config_widgets:
                widget = self.config_widgets.pop()
                self.scroll_layout.removeWidget(widget)
                widget.deleteLater()
            
            for item in config_data:
                new_config = ImageSettingsWidget()
                self._apply_config_data(new_config, item)
                self.scroll_layout.addWidget(new_config)
                self.config_widgets.append(new_config)
                
                new_config.delete_btn.clicked.connect(
                    lambda _, w=new_config: self.remove_config(w)
                )
                new_config.insert_after_btn.clicked.connect(
                    lambda _, w=new_config: self.insert_config_after(w)
                )

            self.update_config_path(file_path)
            QApplication.processEvents()
            self.resize(self.width(), min(
                self.calculate_required_height(),
                self.max_window_height
            ))
            self.force_scroll_to_bottom()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载配置文件失败：{str(e)}")

    def _apply_config_data(self, widget, data):
        widget.image_path_edit.setText(data.get("template_path", ""))
        widget.check_template_check.setChecked(data.get("check_enabled", False))
        
        widget.tolerance_group.itemAt(1).widget().setValue(data.get("tolerance", 0.95))
        widget.interval_group.itemAt(1).widget().setValue(data.get("interval", 0.1))
        widget.timeout_group.itemAt(1).widget().setValue(data.get("timeout", 10.0))
        widget.sleep_group.itemAt(1).widget().setValue(data.get("after_sleep", 0.5))
        
        source_range = data.get("source_range", [0, 0, 0, 0])
        widget.x1_spin.setValue(source_range[0])
        widget.y1_spin.setValue(source_range[1])
        widget.x2_spin.setValue(source_range[2])
        widget.y2_spin.setValue(source_range[3])



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
