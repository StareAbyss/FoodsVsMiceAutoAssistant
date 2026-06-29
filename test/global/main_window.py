# main_window.py
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget

from change_global import change
import value


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Increment Global Variable")
        self.setGeometry(100, 100, 300, 200)

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.increment_button = QPushButton("Increment")
        self.increment_button.clicked.connect(self.increment_global_var)

        layout.addWidget(self.increment_button)

    def increment_global_var(self):
        change()
        print(value.global_var)


def main():
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
