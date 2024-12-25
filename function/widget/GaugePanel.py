from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from math import *
import sys


class GaugePanel(QWidget):
    def __init__(self,name,maxnum=100):
        super().__init__()
        self.setWindowTitle("GaugePanel")
        self.setObjectName(name)
        self.setMinimumWidth(300)
        self.setMinimumHeight(300)

        self.timer = QTimer()  # 窗口重绘定时器
        self.timer.timeout.connect(self.update)
        self.timer.start(100)

        self.testTimer = QTimer()
        self.testTimer.timeout.connect(self.testTimer_timeout_handle)

        self.lcdDisplay = QLCDNumber(self)
        self.lcdDisplay.setDigitCount(4)
        self.lcdDisplay.setMode(QLCDNumber.Mode.Dec)
        self.lcdDisplay.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
        self.lcdDisplay.setStyleSheet('border:2px solid green;color:green;background:silver')

        self._startAngle = 120  # 以QPainter坐标方向为准,建议画个草图看看
        self._endAngle = 60  # 以以QPainter坐标方向为准
        self._scaleMainNum = 10  # 主刻度数
        self._scaleSubNum = 10  # 主刻度被分割份数
        self._minValue = 0
        self._maxValue = maxnum
        self._title = name
        self._value = 0
        self._minRadio = 1  # 缩小比例,用于计算刻度数字
        self._decimals = 0  # 小数位数

    @pyqtSlot()
    def testTimer_timeout_handle(self):
        self._value = self._value + 1
        if self._value > self._maxValue:
            self._value = self._minValue

    def setTestTimer(self, flag):
        if flag is True:
            self.testTimer.start(10)
        else:
            self.testTimer.stop()

    def setMinMaxValue(self, min, max):
        self._minValue = min
        self._maxValue = max

    def setTitle(self, title):
        self._title = title

    def setValue(self, value):
        self._value = value

    def setMinRadio(self, minRadio):
        self._minRadio = minRadio

    def setDecimals(self, decimals):
        self._decimals = decimals

    def paintEvent(self, event):
        side = min(self.width(), self.height())

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)  # painter坐标系原点移至widget中央
        painter.scale(side / 200, side / 200)  # 缩放painterwidget坐标系，使绘制的时钟位于widge中央,即钟表支持缩放

        self.drawPanel(painter)  # 画外框表盘
        self.drawScaleNum(painter)  # 画刻度数字
        self.drawScaleLine(painter)  # 画刻度线
        self.drawTitle(painter)  # 画标题备注
        self.drawValue(painter)  # 画数显
        self.drawIndicator(painter)  # 画指针

    def drawPanel(self, p):
        p.save()
        radius = 100
        lg = QLinearGradient(-radius, -radius, radius, radius)
        lg.setColorAt(0, Qt.GlobalColor.white )
        lg.setColorAt(1, Qt.GlobalColor.black)
        p.setBrush(lg)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(-radius, -radius, radius * 2, radius * 2)

        p.setBrush(Qt.GlobalColor.black)
        p.drawEllipse(-92, -92, 92 * 2, 92 * 2)
        p.restore()

    def drawScaleNum(self, p):
        p.save()
        p.setPen(Qt.GlobalColor.white)
        startRad = self._startAngle * (3.14 / 180)
        stepRad = (360 - (self._startAngle - self._endAngle)) * (3.14 / 180) / self._scaleMainNum

        fm = QFontMetricsF(p.font())
        for i in range(0, self._scaleMainNum + 1):
            sina = sin(startRad + i * stepRad)
            cosa = cos(startRad + i * stepRad)

            tmpVal = i * ((self._maxValue - self._minValue) / self._scaleMainNum) + self._minValue
            tmpVal = tmpVal / self._minRadio
            s = '{:.0f}'.format(tmpVal)
            w = fm.horizontalAdvance(s)
            h = fm.height()
            x = 80 * cosa - w / 2
            y = 80 * sina - h / 2
            p.drawText(QRectF(x, y, w, h), s)

        p.restore()

    def drawScaleLine(self, p):
        p.save()
        p.rotate(self._startAngle)
        scaleNums = self._scaleMainNum * self._scaleSubNum
        angleStep = (360 - (self._startAngle - self._endAngle)) / scaleNums
        p.setPen(Qt.GlobalColor.white)

        pen = QPen(Qt.GlobalColor.white)
        for i in range(0, scaleNums + 1):
            if i >= 0.8 * scaleNums:
                pen.setColor(Qt.GlobalColor.red)

            if i % self._scaleMainNum == 0:
                pen.setWidth(2)
                p.setPen(pen)
                p.drawLine(64, 0, 72, 0)
            else:
                pen.setWidth(1)
                p.setPen(pen)
                p.drawLine(67, 0, 72, 0)
            p.rotate(angleStep)

        p.restore()

    def drawTitle(self, p):
        p.save()
        p.setPen(Qt.GlobalColor.white)
        fm = QFontMetrics(p.font())
        w = fm.horizontalAdvance(self._title)
        rect = QRectF(-w / 2, -45, w, fm.height())
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._title)
        p.restore()

    def drawValue(self, p):
        side = min(self.width(), self.height())
        # w, h = side / 2 * 0.4, side / 2 * 0.2
        # x, y = self.width() / 2 - w / 2, self.height() / 2 + side / 2 * 0.55
        w = int(side / 2 * 0.4)  # 确保宽度是整数
        h = int(side / 2 * 0.2)  # 确保高度是整数
        x = int(self.width() / 2 - w / 2)  # 确保 x 坐标是整数
        y = int(self.height() / 2 + side / 2 * 0.55)  # 确保 y 坐标是整数
        self.lcdDisplay.setGeometry(x, y, w, h)

        ss = '{:.' + str(self._decimals) + 'f}'
        self.lcdDisplay.display(ss.format(self._value))

    def drawIndicator(self, p):
        p.save()
        polygon = QPolygon([QPoint(0, -2), QPoint(0, 2), QPoint(60, 0)])
        degRotate = self._startAngle + (360 - (self._startAngle - self._endAngle)) / (
                    self._maxValue - self._minValue) * (self._value - self._minValue)
        # 画指针
        p.rotate(degRotate)
        halogd = QRadialGradient(0, 0, 60, 0, 0)
        halogd.setColorAt(0, QColor(60, 60, 60))
        halogd.setColorAt(1, QColor(160, 160, 160))
        p.setPen(Qt.GlobalColor.white)
        p.setBrush(halogd)
        p.drawConvexPolygon(polygon)
        p.restore()

        # 画中心点
        p.save()
        radGradient = QRadialGradient(0, 0, 10)
        radGradient = QConicalGradient(0, 0, -90)
        radGradient.setColorAt(0.0, Qt.GlobalColor.darkGray)
        radGradient.setColorAt(0.5, Qt.GlobalColor.white)
        radGradient.setColorAt(1.0, Qt.GlobalColor.darkGray)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(radGradient)
        p.drawEllipse(-5, -5, 10, 10)
        p.restore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gp = GaugePanel('内存')
    gp.show()
    gp.setValue(50)
    # gp.setTestTimer(True)
    sys.exit(app.exec())