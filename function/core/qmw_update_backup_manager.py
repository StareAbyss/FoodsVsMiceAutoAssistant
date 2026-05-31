from pathlib import Path

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from function.common.update_backup import delete_backup, list_backups
from function.core.update_apply import launch_restore_from_backup
from function.globals.get_paths import PATHS


class QMWUpdateBackupManager(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("更新备份管理")
        self.resize(900, 460)
        self.backups = []

        self.table = QTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["备份目录", "版本", "Tag", "PR", "提交哈希", "大小", "路径"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.refresh_button = QPushButton("刷新")
        self.restore_button = QPushButton("恢复选中备份")
        self.delete_button = QPushButton("删除选中备份")
        self.close_button = QPushButton("关闭")

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.restore_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.close_button)

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.refresh_button.clicked.connect(self.load_backups)
        self.restore_button.clicked.connect(self.restore_selected_backup)
        self.delete_button.clicked.connect(self.delete_selected_backup)
        self.close_button.clicked.connect(self.close)

        self.load_backups()

    def selected_backup(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.backups):
            return None
        return self.backups[row]

    def load_backups(self):
        self.backups = list_backups(Path(PATHS["root"]))
        self.table.setRowCount(0)

        for backup in self.backups:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                backup.get("name", ""),
                backup.get("version", ""),
                backup.get("tag", ""),
                f"#{backup.get('pr')}" if backup.get("pr") else "",
                backup.get("commit", "")[:12],
                backup.get("size_text", ""),
                backup.get("path", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        has_backups = bool(self.backups)
        self.restore_button.setEnabled(has_backups)
        self.delete_button.setEnabled(has_backups)

    def restore_selected_backup(self):
        backup = self.selected_backup()
        if not backup:
            QMessageBox.information(self, "未选择备份", "请先选择一个备份。")
            return

        reply = QMessageBox.question(
            self,
            "恢复备份",
            f"即将恢复备份：\n{backup['path']}\n\n"
            "当前版本区会先保存为新的备份，然后用选中备份覆盖当前版本区。\n"
            "保留区 .venv、backups、update_cache 不会被覆盖。\n"
            "是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        launch_info = launch_restore_from_backup(Path(PATHS["root"]), Path(backup["path"]))
        QMessageBox.information(
            self,
            "恢复已启动",
            f"外部 updater 已启动，PID={launch_info['pid']}。\n当前程序即将退出，恢复完成后会重新启动。",
        )
        QtCore.QTimer.singleShot(500, QtWidgets.QApplication.quit)

    def delete_selected_backup(self):
        backup = self.selected_backup()
        if not backup:
            QMessageBox.information(self, "未选择备份", "请先选择一个备份。")
            return

        reply = QMessageBox.question(
            self,
            "删除备份",
            f"将永久删除备份：\n{backup['path']}\n\n是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_backup(Path(PATHS["root"]), Path(backup["path"]))
        except Exception as exc:
            QMessageBox.critical(self, "删除失败", str(exc))
            return

        self.load_backups()
