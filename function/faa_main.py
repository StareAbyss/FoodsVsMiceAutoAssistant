import multiprocessing
import sys
import traceback
from pathlib import Path

from PyQt6 import QtCore
from PyQt6.QtWidgets import QMessageBox

from function.globals.loadings import loading, app


class StartupController(QtCore.QObject):
    """在 Qt 事件循环运行后依次完成同步启动阶段。"""

    def __init__(self, q_app, loading_window):
        super().__init__()
        self.app = q_app
        self.loading = loading_window

    @QtCore.pyqtSlot()
    def start(self):
        try:
            self._begin_stage(5, "正在读取图像资源...")
            import function.globals.g_resources

            self._begin_stage(30, "正在加载FAA业务模块...")
            from function.core.qmw_3_service import faa_start_main

            self._begin_stage(50, "正在检测本地版本状态...")
            from function.common.update_state import detect_local_state
            from function.globals.get_paths import PATHS
            local_state = detect_local_state(Path(PATHS["root"]))

            self._begin_stage(72, "正在读取用户配置和方案...")
            faa_start_main(self.app, self.loading, local_state=local_state)
        except Exception:
            self.loading.stop_animation()
            self.loading.update_progress(0, "FAA 启动失败，请查看错误信息。")
            QMessageBox.critical(None, "FAA 启动失败", traceback.format_exc())
            self.app.quit()

    def _begin_stage(self, value, text):
        """更新同步启动阶段，并只处理绘制等非输入事件。"""
        self.loading.update_progress(value, text)
        self.app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)


def main():
    # 锁定主进程
    multiprocessing.freeze_support()

    # 启动主程序时显式检查并补齐必需目录，避免导入 PATHS 时产生文件系统副作用
    from function.globals.get_paths import check_paths
    check_paths()

    # 展示加载窗口
    loading.show()
    loading.start_animation()

    # 持有控制器强引用，避免启动期间被 Python 回收。
    app.startup_controller = StartupController(app, loading)
    QtCore.QTimer.singleShot(0, app.startup_controller.start)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
