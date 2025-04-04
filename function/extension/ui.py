# 忽略警告: libpng warning: iCCP: known incorrect sRGB profile
import os
os.environ["PYTHONWARNINGS"] = "ignore::libpng warning"
import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QDoubleSpinBox, QScrollArea, QFileDialog, 
    QMessageBox, QCheckBox, QLabel, QSpinBox, QTextEdit, QDialog,QDialogButtonBox
)
from PyQt6.QtCore import Qt, QSize, QTimer, QEvent, QObject, QTime
from PyQt6.QtGui import QTextOption, QColor, QFont, QIcon
from PyQt6.Qsci import QsciScintilla, QsciLexerPython
import saltedfish_rc
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# 初始化全局调度器
scheduler = BackgroundScheduler()
scheduler.start()

from function_faa import ExecuteThread


class Codecode_editWindow(QDialog):
    def __init__(self, parent=None, code=""):
        super().__init__(parent)
        self.setWindowTitle("代码编辑器")
        self.setMinimumSize(600, 400)
        
        # 设置主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 代码标签
        self.lbl_code = QLabel("代码：")
        layout.addWidget(self.lbl_code)

        # 代码编辑区域
        self.code_edit = self.init_edit(code)
        layout.addWidget(self.code_edit)

        # 添加确认/取消按钮（符合图片简洁风格）
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)  # 点击 OK 触发 Accepted
        btn_box.rejected.connect(self.reject)  # 点击 Cancel 触发 Rejected
        layout.addWidget(btn_box)

    def init_edit(self,code):
        code_edit= QsciScintilla()
        
        font = QFont("Consolas", 12)  # 字体名称和大小
        # code_edit.setFont(font) # 设置默认字体（这种方法不会生效，必须通过 lexer 设置字体）
        
        # 启用行号
        code_edit.setMarginsBackgroundColor(QColor("#f0f0f0"))
        code_edit.setMarginWidth(0, "0000")  # 设置行号栏宽度
        code_edit.setMarginLineNumbers(0, True)  # 显示行号

        # 设置 Python 语法高亮
        lexer = QsciLexerPython()
        lexer.setFont(font)  # 通过 lexer 设置字体
        code_edit.setLexer(lexer)
        

        # 启用代码折叠
        code_edit.setFolding(QsciScintilla.FoldStyle.PlainFoldStyle)

        # 其他配置
        code_edit.setAutoIndent(True)  # 自动缩进
        code_edit.setIndentationWidth(4)
        code_edit.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)  # 括号匹配
        code_edit.setText(code)
        

        return code_edit

    def get_code(self) -> str:
        """获取编辑框中的代码内容"""
        return self.code_edit.text()  
    

    def set_code(self, code: str):
        """设置编辑框中的代码内容"""
        self.code_edit.setText(code)






class ParamGroupWidget(QWidget):
    # valueChanged = pyqtSignal(float)  # 统一信号，方便后续扩展
    
    def __init__(self, 
                label_text, 
                default, 
                decimals, 
                suffix, 
                is_float=True,
                minimum=0,
                maximum=9999,
                label_fixed_width=60,
                spin_fixed_width=100):
        super().__init__()
        
        # 创建水平布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 标签部分
        self.label = QLabel(label_text)
        self.label.setFixedWidth(label_fixed_width)
        layout.addWidget(self.label)

        # 数值输入部分
        if is_float:
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(decimals)
        else:
            self.spin = QSpinBox()
        
        # 设置公共属性
        self.spin.setRange(minimum, maximum)
        self.spin.setValue(default)
        self.spin.setFixedWidth(spin_fixed_width)
        if suffix:
            self.spin.setSuffix(f" {suffix}")

        # 禁用滚轮
        self.spin.installEventFilter(self._create_wheel_filter())
        layout.addWidget(self.spin)

    def _create_wheel_filter(self):
        class WheelFilter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Wheel:
                    return True
                return super().eventFilter(obj, event)
        return WheelFilter(self.spin)

    @property
    def value(self):
        return self.spin.value()
    
    @value.setter
    def value(self, val):
        self.spin.setValue(val)

class ImageSettingsWidget(QWidget):
    def __init__(self, index: int):
        super().__init__()
        self.index = index  # 直接接收索引参数
        self.code=""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)
        
        
        
        # === 第一行：图片路径 ===
        
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(5)
        
        # 在布局中添加显示索引的标签
        self.index_label = QLabel(f"配置项{self.index + 1}")
        path_layout.addWidget(self.index_label)
        
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

        self.tolerance_group = ParamGroupWidget("精度:", 0.95, 2, "")
        param_layout.addWidget(self.tolerance_group)

        self.interval_group = ParamGroupWidget("间隔:", 0.10, 2, "秒")
        param_layout.addWidget(self.interval_group)

        self.timeout_group = ParamGroupWidget("超时:", 3.0, 2, "秒", maximum=9999)
        param_layout.addWidget(self.timeout_group)

        sleep_container = QHBoxLayout()
        sleep_container.addStretch()
        self.sleep_group = ParamGroupWidget("休眠:", 0.2, 2, "秒", maximum=9999)
        sleep_container.addWidget(self.sleep_group)
        param_layout.addLayout(sleep_container, stretch=1)
        
        main_layout.addLayout(param_layout)

        # === 第三行：功能区域（校验和截图区域） ===
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self.check_need_click = QCheckBox("识图后点击")
        self.check_need_click.setChecked(True)
        action_layout.addWidget(self.check_need_click)

        # 在点击后校验后增加一个选择框“点击后输入”
        self.check_click_input = QCheckBox("点击后输入")
        action_layout.addWidget(self.check_click_input)
        self.check_click_input.toggled.connect(self.on_click_input_toggled)

        # 新增：偏移相关设置
        self.check_offset_enabled = QCheckBox("是否偏移")
        action_layout.addWidget(self.check_offset_enabled)
        self.check_offset_enabled.toggled.connect(self.on_offset_toggled)
        
        # 新增：结束后运行代码
        self.check_run_code=QCheckBox("结束后运行代码")
        action_layout.addWidget(self.check_run_code)



        # 截图区域配置
        action_layout.addWidget(QLabel("截图区域:"))
        self.x1_group = ParamGroupWidget("X1:", 0, 0, "",is_float=False, label_fixed_width=20,spin_fixed_width=60)
        self.y1_group = ParamGroupWidget("Y1:", 0, 0, "",is_float=False, label_fixed_width=20,spin_fixed_width=60)
        self.x2_group = ParamGroupWidget("X2:", 2000, 0, "",is_float=False, label_fixed_width=20,spin_fixed_width=60)
        self.y2_group = ParamGroupWidget("Y2:", 2000, 0, "",is_float=False, label_fixed_width=20,spin_fixed_width=60)
        action_layout.addWidget(self.x1_group)
        action_layout.addWidget(self.y1_group)
        action_layout.addWidget(self.x2_group)
        action_layout.addWidget(self.y2_group)
        
        





        main_layout.addLayout(action_layout)

        


        # === 第四行：点击后输入的编辑框（只有当勾选“点击后输入”时显示） ===
        click_input_layout = QHBoxLayout()
        click_input_layout.setContentsMargins(0, 0, 0, 0)
        click_input_layout.setSpacing(5)
        # 添加一个空白标签作为占位，与前面行对齐
        self.label_input = QLabel("输入内容：")
        self.label_input.setFixedWidth(60)
        self.label_input.setVisible(False)
        click_input_layout.addWidget(self.label_input)

        self.click_input_edit = QLineEdit()
        self.click_input_edit.setPlaceholderText("请输入内容")
        click_input_layout.addWidget(self.click_input_edit)
        
        
        # 偏移x
        self.offset_x_group = ParamGroupWidget("偏移x:", 0, 0, "", is_float=False, minimum=-2000, label_fixed_width=60, spin_fixed_width=60)
        click_input_layout.addWidget(self.offset_x_group)
        self.offset_x_group.setVisible(False)  # 初始状态下隐藏
        
        self.offset_y_group = ParamGroupWidget("偏移y:", 0, 0, "", is_float=False, minimum=-2000, label_fixed_width=60, spin_fixed_width=60)
        click_input_layout.addWidget(self.offset_y_group)
        self.offset_y_group.setVisible(False)  # 初始状态下隐藏
        
        
        main_layout.addLayout(click_input_layout)
        self.click_input_edit.setVisible(False)  # 初始状态下隐藏
        
        
        
        # === 第五行：操作按钮 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_open_code_code_edit=QPushButton("编辑代码")
        self.btn_open_code_code_edit.setFixedWidth(100)
        self.btn_open_code_code_edit.clicked.connect(self.show_code_code_edit)
        btn_layout.addWidget(self.btn_open_code_code_edit)
        
        self.insert_after_btn = QPushButton("向后插入")
        self.insert_after_btn.setFixedWidth(100)
        btn_layout.addWidget(self.insert_after_btn)
        
        self.delete_btn = QPushButton("删除配置项")
        self.delete_btn.setFixedWidth(100)
        btn_layout.addWidget(self.delete_btn)
        
        main_layout.addLayout(btn_layout)

        self.browse_btn.clicked.connect(self.browse_image)
        
        # === 第六行：分割线 ==
        # 创建一个自定义的分割线
        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: gray;")
        main_layout.addWidget(line)

    def show_code_code_edit(self):
        """显示代码编辑器窗口，编辑完后把代码存入code属性"""
        code_edit = Codecode_editWindow(self)
        code_edit.set_code(self.code)  # 可选：设置初始代码
        if code_edit.exec() == QDialog.DialogCode.Accepted:
            code = code_edit.get_code()
            self.code=code
            print("编辑的代码已记录，别忘了保存配置")
            
            

    def update_index(self, new_index: int):
        """更新索引并刷新显示"""
        self.index = new_index
        self.index_label.setText(f"配置项 {self.index + 1}")


    def on_click_input_toggled(self, checked):
        """当“点击后输入”复选框状态改变时，显示或隐藏输入框"""
        self.click_input_edit.setVisible(checked)
        self.label_input.setVisible(checked)

    def on_offset_toggled(self, checked):
        """当“点击后输入”复选框状态改变时，显示或隐藏输入框"""
        self.offset_x_group.setVisible(checked)
        self.offset_y_group.setVisible(checked)
    
    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模板图片", "", "PNG Files (*.png)")
        if path:
            self.image_path_edit.setText(path)

    def get_data(self):
        """从配置项ui中获取配置"""
        return {
            "template_path": self.image_path_edit.text(),
            "tolerance": self.tolerance_group.value,
            "interval": self.interval_group.value,
            "timeout": self.timeout_group.value,
            "after_sleep": self.sleep_group.value,
            
            
            "need_click": self.check_need_click.isChecked(),
            "click_input_enabled": self.check_click_input.isChecked(),
            "click_input": self.click_input_edit.text() if self.check_click_input.isChecked() else "",
            "check_offset_enabled":self.check_offset_enabled.isChecked(),
            "check_run_code":self.check_run_code.isChecked(),
            "offset_x": self.offset_x_group.value if  self.offset_x_group.value else 0,
            "offset_y": self.offset_y_group.value if self.offset_y_group.value else 0,
            
            "source_range": [
                self.x1_group.value,
                self.y1_group.value,
                self.x2_group.value,
                self.y2_group.value
            ],
            "code":self.code
        }

from PyQt6.QtCore import pyqtSignal

class TextEditRedirector(QObject):
    """用于将 print 的内容写入到自定义的 text_edit 编辑框，采用信号跨线程发送"""
    append_text_signal = pyqtSignal(str)

    def __init__(self, text_edit: QTextEdit):
        super().__init__()
        self.text_edit = text_edit
        # 保存原始的标准输出，这里最好用 sys.__stdout__ 避免重定向后的影响
        self.original_stdout = sys.__stdout__
        # 将信号连接到 QTextEdit 的 append 方法上（保证在主线程调用）
        self.append_text_signal.connect(self.text_edit.append)

    def write(self, message: str):
        """
        将消息输出到 QTextEdit 和终端
        注意：使用信号保证在主线程中更新 QTextEdit
        """
        # 删除尾部的换行符，避免 QTextEdit 显示多余的空行
        message = message.rstrip('\n')
        # 通过信号发射消息，确保在主线程中调用 text_edit.append(message)
        self.append_text_signal.emit(message)
        
        # 检查是否有终端输出流，有的话就同时将消息输出到原始的 stdout（终端）（不检查的话在打包后运行exe时会报错）
        if self.original_stdout:
            self.original_stdout.write(message + "\n")

    def flush(self):
        """实现 flush 方法，因为 sys.stdout 需要它"""
        pass





from typing import Optional
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FAA - 自定义识图插件")
        self.setWindowIcon(QIcon(":/icons/saltedfish.ico"))
        self.setMinimumWidth(900)
        self.initial_height = 200
        self.config_widgets:Optional[list[ImageSettingsWidget]] = []
        self.current_config_path = None
        self.temp_config_path = "temp_config.json"

        self.execute_thread:Optional[ExecuteThread]=None
        
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

        config_btn_layout = QHBoxLayout()
        self.open_btn = QPushButton("打开配置")
        self.open_btn.clicked.connect(self.load_config)
        config_btn_layout.addWidget(self.open_btn)

        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.save_config)
        config_btn_layout.addWidget(self.save_btn)

        self.save_as_btn = QPushButton("将配置另存为")
        self.save_as_btn.clicked.connect(self.save_as_config)
        config_btn_layout.addWidget(self.save_as_btn)
        main_layout.addLayout(config_btn_layout)

        self.add_btn = QPushButton("添加配置项")
        self.add_btn.clicked.connect(lambda: self.add_config())
        main_layout.addWidget(self.add_btn)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(250)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(5)
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll)

        # === 底部按钮布局 ===
        bottom_btn_layout = QHBoxLayout()
        


        # 循环执行次数
        self.loop_group = ParamGroupWidget("循环执行次数", 1, 0, "次", is_float=False, maximum=9999,label_fixed_width=100,spin_fixed_width=60)
        bottom_btn_layout.addWidget(self.loop_group)
        # 在循环执行次数的右边增加一个选择框“显示识图效果”
        self.show_detection_effect_checkbox = QCheckBox("显示识图效果")
        bottom_btn_layout.addWidget(self.show_detection_effect_checkbox)

        bottom_btn_layout.addStretch()

        hwnd_label = QLabel("窗口名")
        bottom_btn_layout.addWidget(hwnd_label)

        self.window_name_edit = QLineEdit()
        self.window_name_edit.setFixedWidth(150)
        self.window_name_edit.setPlaceholderText("输入窗口名（如：美食大战老鼠）")
        self.window_name_edit.setText("美食大战老鼠")
        bottom_btn_layout.addWidget(self.window_name_edit)

        self.execute_btn = QPushButton("执行脚本")
        self.execute_btn.setFixedWidth(100)
        self.execute_btn.clicked.connect(self.execute_script)
        bottom_btn_layout.addWidget(self.execute_btn)

        main_layout.addLayout(bottom_btn_layout)
        self.resize(QSize(800, self.initial_height))
        
        # === 定时任务区域 ===
        timer_layout = QHBoxLayout()
        timer_layout.setContentsMargins(0, 0, 0, 0)
        timer_layout.setSpacing(5)

        # 标签“定时运行时间：”
        timer_label = QLabel("定时运行时间：")
        timer_label.setFixedWidth(100)
        timer_layout.addWidget(timer_label)

        # 编辑框
        self.timer_edit = QLineEdit()
        self.timer_edit.setPlaceholderText("输入时间点（如 08:00:00）")
        timer_layout.addWidget(self.timer_edit)

        # 按钮“启动定时任务”
        self.start_timer_btn = QPushButton("启动定时任务")
        self.start_timer_btn.setFixedWidth(120)
        self.start_timer_btn.clicked.connect(self.start_timer_task)
        timer_layout.addWidget(self.start_timer_btn)

        # 将定时任务区域添加到主布局
        main_layout.addLayout(timer_layout)
        
        # === 底部日志区域 ===
        # “日志输出”标签
        self.log_label = QLabel("日志输出:")
        self.log_label.setStyleSheet("color: #333; font-weight: bold;")
        main_layout.addWidget(self.log_label)

        # 创建 QTextEdit 用于显示长文本
        self.log_output = QTextEdit()
        self.log_output.setText("欢迎使用自定义识图插件。\n你可以在网站：https://stareabyss.github.io/FAA-WebSite/guide/start/自定义识图脚本教程.html 中查看使用教程。\n\n注意：当你使用别人发给你的配置文件时，记得修改配置中的图片路径，保证其与你的电脑一致\n")
        self.log_output.setWordWrapMode(QTextOption.WrapMode.WordWrap)   # 启用自动换行
        self.log_output.setMinimumHeight(100)  # 设置最小高度
        self.log_output.setReadOnly(True)  # 设置为只读，防止编辑
        # 使用新的 TextEditRedirector 重定向标准输出到 QTextEdit
        # 注意：保存实例到 self.stdout_redirector 以防被垃圾回收
        self.stdout_redirector = TextEditRedirector(self.log_output)
        sys.stdout = self.stdout_redirector
        
        # 将底部日志区域添加到主布局
        main_layout.addWidget(self.log_output)
        

    
    

    
    
    def start_timer_task(self):
        """启动定时任务"""
        try:
            # 获取用户输入的时间
            time_input = self.timer_edit.text().strip()
            task_time = QTime.fromString(time_input, "hh:mm:ss")

            if not task_time.isValid():
                QMessageBox.warning(None, "警告", "请输入有效的时间点（格式如 08:00:00）")
                return

            # 提取小时、分钟、秒
            hour = task_time.hour()
            minute = task_time.minute()
            second = task_time.second()

            # 添加定时任务到调度器
            scheduler.add_job(
                self.execute_script,  # 定时执行的函数
                CronTrigger(hour=hour, minute=minute, second=second),
                id="daily_task",  # 任务 ID
                replace_existing=True  # 如果有同名任务则替换
            )

            print(f"定时任务已启动，将在每天 {time_input} 执行一次\n注意：请确保配置完成，建议先使用“执行脚本”进行测试，确保无误后再使用定时功能")

        except Exception as e:
            QMessageBox.warning(None, "错误", f"启动定时任务时出错：{str(e)}")

    def update_config_path(self, path):
        """ 更新当前配置路径显示 """
        self.current_config_path = path
        display_text = path if path else "无"
        self.current_config_label.setText(display_text)
        self.current_config_label.setToolTip(display_text)

    def execute_script(self):
        """ 执行脚本的核心方法，用来连接按钮 """
        
        # 结束执行
        if self.execute_btn.text() == "结束脚本":
            self.execute_btn.setText("结束中……")
            self.execute_btn.setEnabled(False)  # 禁用按钮
            QApplication.processEvents() # 刷新ui
            
            self.execute_thread.stop()  # 调用自己写的方法，让线程自己安全退出
            self.execute_thread.join()  # 等待线程退出
            self.execute_thread = None
            self.execute_btn.setText("执行脚本")
            self.execute_btn.setEnabled(True)  # 启动按钮
            
            
            return 
        
        # 启动执行
        if not self.current_config_path:
            QMessageBox.warning(self, "警告", "请先保存配置或加载现有配置")
            return

        window_name = self.window_name_edit.text().strip()
        if not window_name:
            QMessageBox.warning(self, "警告", "请输入窗口名")
            return

        loop_times = self.loop_group.value
        
        # 获取“显示识图效果”复选框的状态
        need_test = self.show_detection_effect_checkbox.isChecked()
        
        self.execute_btn.setText("结束脚本")
        QApplication.processEvents()
        # 创建执行线程，并将是否显示识图效果的状态赋值给线程的一个属性
        
        self.execute_thread = ExecuteThread(window_name, self.current_config_path, loop_times, need_test)
        self.execute_thread.start()
        
        def show_message(title, text):
            # 在主线程中显示消息框
            QMessageBox.information(self, title, text)
            self.execute_btn.setText("执行脚本")
        # 连接信号到槽函数
        self.execute_thread.message_signal.connect(show_message)

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
        # 计算新配置项的索引
        
        if index is None: # 在末尾插入（python为检查index和数组长度是否相等，因此不会比append慢很多）
            index = len(self.config_widgets)
        
        new_config = ImageSettingsWidget(index=index)
        
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
            # 获取被删除项的索引
            index = self.config_widgets.index(widget)
            # 删除控件
            self.scroll_layout.removeWidget(widget)
            self.config_widgets.remove(widget)
            widget.deleteLater()
            # 更新后续所有配置项的索引
            for i in range(index, len(self.config_widgets)):
                self.config_widgets[i].update_index(i)
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
        if not self.current_config_path:
            self.save_as_config()
        else:
            config_data = [w.get_data() for w in self.config_widgets]
            
            try:
                with open(self.current_config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                print("保存配置成功")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存文件时出错：{str(e)}")

    def save_as_config(self):
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
            print("保存配置成功")
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
            
            for i,item in enumerate(config_data):
                new_config = ImageSettingsWidget(i)
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
            print("打开配置成功")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载配置文件失败：{str(e)}")
    def _apply_config_data(self, widget:ImageSettingsWidget, data:dict):
        """将配置数据应用到指定的 ImageSettingsWidget 实例中"""
        # 图片路径
        widget.image_path_edit.setText(data.get("template_path", ""))
        
        # 复选框状态
        widget.check_need_click.setChecked(data.get("need_click", True))
        
        # 数值参数组
        widget.tolerance_group.value = data.get("tolerance", 0.95)
        widget.interval_group.value = data.get("interval", 0.1)
        widget.timeout_group.value = data.get("timeout", 10.0)
        widget.sleep_group.value = data.get("after_sleep", 0.5)
        
        # 截图区域
        source_range = data.get("source_range", [0, 0, 0, 0])
        widget.x1_group.value = source_range[0]
        widget.y1_group.value = source_range[1]
        widget.x2_group.value = source_range[2]
        widget.y2_group.value = source_range[3]
        
        # 点击后输入相关配置
        widget.check_click_input.setChecked(data.get("click_input_enabled", False))
        widget.click_input_edit.setText(data.get("click_input", ""))
        widget.click_input_edit.setVisible(widget.check_click_input.isChecked())
        
        # 点击位置偏移相关配置
        widget.check_offset_enabled.setChecked(data.get("check_offset_enabled", False))
        widget.check_run_code.setChecked(data.get("check_run_code",False))
        widget.offset_x_group.value = data.get("offset_x", 0)
        widget.offset_x_group.setVisible(widget.check_offset_enabled.isChecked())
        widget.offset_y_group.value = data.get("offset_y", 0)
        widget.offset_y_group.setVisible(widget.check_offset_enabled.isChecked())
        
        # 代码相关
        widget.code=data.get("code", "")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
