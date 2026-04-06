import math

from PyQt6 import QtGui, QtCore


def create_qt_icon(q_color, mode):
    """
    绘制图表
    :param q_color: Q color
    :param mode: "-" "x" "<-" "->" "magnifier"
    :return:
    """
    pixmap = QtGui.QPixmap(16, 16)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)

    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    match mode:
        case "x":
            painter.setPen(QtGui.QPen(q_color, 2))
            painter.drawLine(3, 3, 13, 13)
            painter.drawLine(3, 13, 13, 3)
        case "-":
            painter.setPen(QtGui.QPen(q_color, 2))
            painter.drawLine(3, 8, 13, 8)
        case "<-":
            painter.setPen(QtGui.QPen(q_color, 2))
            painter.drawLine(2, 8, 14, 8)  # 主线
            painter.drawLine(2, 8, 6, 4)  # 左上角
            painter.drawLine(2, 8, 6, 12)  # 左下角
        case "->":
            painter.setPen(QtGui.QPen(q_color, 2))
            painter.drawLine(2, 8, 14, 8)  # 主线
            painter.drawLine(14, 8, 10, 4)  # 右上角
            painter.drawLine(14, 8, 10, 12)  # 右下角
        case "magnifier":
            painter.setPen(QtGui.QPen(q_color, 1))
            painter.drawEllipse(3, 3, 10, 10)  # 外圆
            painter.drawLine(11, 11, 13, 13)  # 放大镜的把手
            painter.drawLine(11, 12, 13, 14)  # 放大镜的把手
            painter.drawLine(12, 11, 14, 13)  # 放大镜的把手
            painter.drawLine(12, 12, 14, 14)  # 放大镜的把手
        case "v":
            painter.setPen(QtGui.QPen(q_color, 2))
            painter.drawLine(3, 4, 13, 4)  # 顶部横线
            painter.drawLine(3, 1, 13, 1)  # 顶部横线
            painter.drawLine(3, 4, 8, 12)  # 左边线
            painter.drawLine(13, 4, 8, 12)  # 右边线
        case "refresh":
            painter.setPen(QtGui.QPen(q_color, 2))
            import math
            cx, cy = 8.0, 8.0
            Vx, Vy = 12.0, 4.0
            dx, dy = Vx - cx, Vy - cy
            R = math.hypot(dx, dy)
            rect = QtCore.QRectF(cx - R, cy - R, 2 * R, 2 * R)
            start_angle = 15 * 16
            span_angle = -270 * 16
            painter.drawArc(rect, start_angle, span_angle)
            V = QtCore.QPointF(Vx, Vy)
            L = 4.0
            theta1 = math.radians(115)
            theta2 = math.radians(45)
            A = QtCore.QPointF(V.x() + L * math.cos(theta1), V.y() + L * math.sin(theta1))
            B = QtCore.QPointF(V.x() + L * math.cos(theta2), V.y() + L * math.sin(theta2))
            painter.drawLine(V, A)
            painter.drawLine(V, B)
            painter.drawLine(A, B)
        case _:
            pass

    painter.end()

    return QtGui.QIcon(pixmap)