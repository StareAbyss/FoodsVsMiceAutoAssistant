import sys

from PyQt5 import QtWidgets
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView

url = "https://my.4399.com/yxmsdzls/"
sys.argv.append('--ppapi-flash-path= ./pepflashplayer.dll')


class Ui_Flash(QWebEngineView):
    def __init__(self, parent=None):
        super(Ui_Flash, self).__init__()

        self.resize(800, 600)  # 设置窗口的大小

        self.load(QUrl(url))
        self.show()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    ui = Ui_Flash()
    ui.show()
    sys.exit(app.exec_())
