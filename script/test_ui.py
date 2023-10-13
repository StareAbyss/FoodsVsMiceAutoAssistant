import sys
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QMainWindow, QApplication
import _thread, time
from PyQt5 import QtCore, QtWidgets, QtGui


class mysignal(QObject):  # 定义信号槽基类
    threadsignal = pyqtSignal(str)


class Example(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setGeometry(300, 300, 300, 220)
        self.c = mysignal()
        self.c.threadsignal.connect(self.text_display)  # 连接信号槽
        self.textEdit = QtWidgets.QTextEdit(self)
        self.textEdit.setGeometry(QtCore.QRect(20, 20, 270, 180))
        self.textEdit.setObjectName("textEdit")
        self.textEdit.setText("hello word! 2022-04-27")

        self.show()
        _thread.start_new_thread(self.thread_proc, ())  # 开启子线程

    def text_display(self, cmdstr):  # 这里是接收信号
        print(cmdstr)
        self.textEdit.append(cmdstr + time.strftime(" %H:%M:%S"))
        cursor = self.textEdit.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.textEdit.setTextCursor(cursor)
        # self.close()

    def thread_proc(self):
        print("start thread!")
        i = 0
        while 1:
            hehe = list(range(10))
            self.c.threadsignal.emit("cmd tool_and_test ok!" + str(i))  # 发送信号，修改界面信息
            time.sleep(1)
            i = i + 1


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())