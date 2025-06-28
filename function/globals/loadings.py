import sys
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
from function.core.loading_window import LoadingWindow
loading = LoadingWindow()