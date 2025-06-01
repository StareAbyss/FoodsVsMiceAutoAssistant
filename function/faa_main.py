import sys
import multiprocessing
from time import sleep

from PyQt6.QtCore import QTimer, QThread, pyqtSignal
from function.globals.loadings import loading, app
class AnimationThread(QThread):

    def __init__(self):
        super().__init__()
        self._is_running = True  # 线程运行状态标志
    def run(self):
        while self._is_running:
            QThread.msleep(100)  # 控制帧率 (单位：毫秒)
            loading.gif_movie.jumpToNextFrame(),
            loading.repaint()
    def stop(self):
        """安全停止线程的方法"""
        self._is_running = False
        self.wait()  # 等待线程自然退出

def main():
    def delayed_init(app, loading,anim_thread):
        anim_thread.start()
        from function.core.qmw_3_service import faa_start_main
        faa_start_main(app, loading,anim_thread)
    multiprocessing.freeze_support()
    loading.update_progress(0)
    loading.show()
    loading.update_progress(1)
    anim_thread = AnimationThread()
    QTimer.singleShot(100, lambda: delayed_init(app, loading,anim_thread))
    # 创建动画线程

    sys.exit(app.exec())





if __name__ == '__main__':
    main()