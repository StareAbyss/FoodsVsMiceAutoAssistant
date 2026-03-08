"""
Git 更新管理界面模块
提供 Git 配置修改、检查更新、普通更新、强制更新等功能
"""

import os
import configparser
import threading
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QCheckBox, QPushButton, QLabel, QMessageBox,
    QSpinBox, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from plugins.git_plus.GitSDK import git_by_ini


class GitConfigDialog(QDialog):
    """Git 配置修改对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Git 配置")
        self.setModal(True)
        self.resize(500, 400)
        
        # 配置文件路径
        self.config_file = os.path.join(
            PATHS["root"], 
            "plugins", 
            "git_plus", 
            "config.ini"
        )
        
        self.init_ui()
        self.load_config()
    
    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Git 配置组
        git_group = QGroupBox("Git 仓库配置")
        git_layout = QFormLayout()
        
        self.repo_edit = QLineEdit()
        self.repo_edit.setPlaceholderText("https://github.com/user/repo.git")
        git_layout.addRow("仓库地址:", self.repo_edit)
        
        self.branch_edit = QLineEdit()
        self.branch_edit.setText("main")
        git_layout.addRow("分支名称:", self.branch_edit)
        
        self.git_path_edit = QLineEdit()
        self.git_path_edit.setPlaceholderText("depend/MinGit-2.53.0-64-bit/mingw64/bin/git.exe")
        git_layout.addRow("Git 路径:", self.git_path_edit)
        
        git_group.setLayout(git_layout)
        layout.addWidget(git_group)
        
        # 更新配置组
        update_group = QGroupBox("更新配置")
        update_layout = QFormLayout()
        
        self.update_check = QCheckBox("启用自动更新")
        self.update_check.setChecked(True)
        update_layout.addRow(self.update_check)
        
        self.keep_changes_check = QCheckBox("保留本地修改 (Stash)")
        update_layout.addRow(self.keep_changes_check)
        
        self.mirror_check = QCheckBox("使用 Mirror 加速")
        self.mirror_check.stateChanged.connect(self.toggle_mirror_url)
        update_layout.addRow(self.mirror_check)
        
        self.mirror_url_edit = QLineEdit()
        self.mirror_url_edit.setPlaceholderText("https://gitclone.com/")
        self.mirror_url_edit.setEnabled(False)
        update_layout.addRow("Mirror 地址:", self.mirror_url_edit)
        
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(0, 999)  # 0 表示完整克隆
        self.depth_spin.setValue(1)
        self.depth_spin.setSpecialValueText("完整克隆")
        update_layout.addRow("浅克隆深度:", self.depth_spin)
        
        update_group.setLayout(update_layout)
        layout.addWidget(update_group)
        
        # 网络配置组
        network_group = QGroupBox("网络配置")
        network_layout = QFormLayout()
        
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("端口号，如：7890")
        network_layout.addRow("代理端口:", self.proxy_edit)
        
        self.ssl_check = QCheckBox("验证 SSL 证书")
        self.ssl_check.setChecked(True)
        network_layout.addRow(self.ssl_check)
        
        network_group.setLayout(network_layout)
        layout.addWidget(network_group)
        
        # 按钮组
        btn_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(self.save_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def toggle_mirror_url(self, state):
        """切换 Mirror 地址输入框的启用状态"""
        self.mirror_url_edit.setEnabled(state == Qt.CheckState.Checked.value)
    
    def load_config(self):
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            QMessageBox.warning(
                self, 
                "警告", 
                f"配置文件不存在:\n{self.config_file}"
            )
            return
        
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        # Git 配置
        self.repo_edit.setText(config.get('git', 'repository', fallback=''))
        self.branch_edit.setText(config.get('git', 'branch', fallback='main'))
        self.git_path_edit.setText(config.get('git', 'git_path', fallback=''))
        
        # 更新配置
        self.update_check.setChecked(config.getboolean('update', 'update', fallback=True))
        self.keep_changes_check.setChecked(config.getboolean('update', 'keep_changes', fallback=False))
        self.mirror_check.setChecked(config.getboolean('update', 'mirror', fallback=False))
        self.mirror_url_edit.setText(config.get('update', 'mirror_url', fallback=''))
        # 根据勾选状态启用/禁用 Mirror 地址输入框
        if self.mirror_check.isChecked():
            self.mirror_url_edit.setEnabled(True)
        else:
            self.mirror_url_edit.setEnabled(False)
        
        depth_str = config.get('update', 'depth', fallback='1')
        try:
            self.depth_spin.setValue(int(depth_str) if depth_str else 1)
        except ValueError:
            self.depth_spin.setValue(1)
        
        # 网络配置
        proxy = config.get('network', 'proxy', fallback='')
        # 如果是完整的代理地址格式，提取端口号
        if proxy and proxy.startswith('http://127.0.0.1:'):
            port = proxy.split(':')[-1]
            self.proxy_edit.setText(port)
        else:
            self.proxy_edit.setText(proxy)
        self.ssl_check.setChecked(config.getboolean('network', 'ssl', fallback=True))
    
    def save_config(self):
        """保存配置文件"""
        try:
            config = configparser.ConfigParser()
                
            # Git配置
            config['git'] = {
                'repository': self.repo_edit.text().strip(),
                'branch': self.branch_edit.text().strip(),
                'git_path': self.git_path_edit.text().strip()
            }
                
            # 更新配置
            config['update'] = {
                'update': str(self.update_check.isChecked()),
                'keep_changes': str(self.keep_changes_check.isChecked()),
                'mirror': str(self.mirror_check.isChecked()),
                'mirror_url': self.mirror_url_edit.text().strip(),
                # 关键修复：如果深度为 0（完整克隆），写入空字符串；否则写入实际数值
                'depth': '' if self.depth_spin.value() == 0 else str(self.depth_spin.value())
            }
            
            # 网络配置 - 只保存端口号
            proxy_text = self.proxy_edit.text().strip()
            # 如果输入的是完整代理地址，提取端口号；否则直接保存
            if proxy_text and proxy_text.startswith('http://127.0.0.1:'):
                port = proxy_text.split(':')[-1]
                proxy_value = port
            elif proxy_text and proxy_text.isdigit():
                proxy_value = proxy_text
            else:
                proxy_value = proxy_text
            
            config['network'] = {
                'proxy': proxy_value,
                'ssl': str(self.ssl_check.isChecked())
            }
            
            # 路径配置 - 保留原有的 project_folder 值
            existing_config = configparser.ConfigParser()
            if os.path.exists(self.config_file):
                existing_config.read(self.config_file, encoding='utf-8')
                project_folder = existing_config.get('paths', 'project_folder', fallback='.')
            else:
                project_folder = '.'
            
            config['paths'] = {
                'project_folder': project_folder
            }
            
            # 写入文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                config.write(f)
            
            CUS_LOGGER.info(f"Git 配置已保存到：{self.config_file}")
            QMessageBox.information(
                self, 
                "成功", 
                "Git 配置已保存！"
            )
            self.accept()
            
        except Exception as e:
            CUS_LOGGER.error(f"保存 Git 配置失败：{e}")
            QMessageBox.critical(
                self, 
                "错误", 
                f"保存配置失败:\n{str(e)}"
            )




class GitUpdateManager(QThread):
    """Git 更新管理器（每次调用创建新实例）"""
    
    # 信号定义
    result = pyqtSignal(bool, str)  # success/has_update, message
    
    def __init__(self, operation='check', log_callback=None, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.log_callback = log_callback
    
    def run(self):
        """在线程中执行 Git 操作"""
        try:
            # 映射操作类型
            op_map = {
                'check': ('check_update', "检测到新版本！", "已是最新版本", None),  # keep_changes=None（不使用）
                'normal': ('update', "更新成功！", "更新可能失败，部分文件未同步，请查看日志", True),  # keep_changes=True
                'force': ('update', "强制更新成功！", "强制更新可能失败，部分文件未同步，请查看日志", False),  # keep_changes=False
            }
            
            if self.operation not in op_map:
                raise ValueError(f"未知操作：{self.operation}")
            
            git_op, success_msg, fail_msg, keep_changes = op_map[self.operation]
            
            # 使用 git_by_ini 执行操作（传递外部传入的日志回调到前端 UI）
            # use_dev=None 表示根据配置文件中的 use_dev_config 选项自动决定
            result = git_by_ini(async_mode=False, operation=git_op, log_callback=self.log_callback, keep_changes_override=keep_changes)
            
            if result:
                self.result.emit(True, success_msg)
            else:
                self.result.emit(False, fail_msg)
                
        except Exception as e:
            CUS_LOGGER.error(f"Git 操作异常：{e}")
            error_msg = f"{'检查' if self.operation == 'check' else '更新'}失败:\n{str(e)}"
            self.result.emit(False, error_msg)


# 模块级统一接口函数
def git_operation(operation: str, log_callback=None):
    """统一的 Git 操作接口
    
    Args:
        operation: 操作类型，'check' | 'normal' | 'force'
        log_callback: 日志回调函数，直接处理日志输出到前端 UI
        
    Returns:
        GitUpdateManager: 工作线程对象，用于连接信号
    """
    worker = GitUpdateManager(operation=operation, log_callback=log_callback)
    worker.start()
    return worker

