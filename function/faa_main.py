import sys
import multiprocessing

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


def main():
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)

    from function.core.loading_window import LoadingWindow
    loading = LoadingWindow()
    loading.update_progress(0)
    loading.show()

    QTimer.singleShot(100, lambda: delayed_init(app,loading))

    sys.exit(app.exec())


def delayed_init(app,loading):
    from function.core.qmw_3_service import faa_start_main
    faa_start_main(app,loading)


if __name__ == '__main__':
    main()