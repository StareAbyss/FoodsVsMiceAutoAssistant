from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QProgressBar, QLabel, QVBoxLayout, QApplication, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPointF


class LoadingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setStyleSheet("""
            #container {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2b2b2b, stop:1 #1a1a1a);
                border-radius: 8px;
            }
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2b2b2b, stop:1 #1a1a1a);
                border-radius: 8px;
                color: #ffffff;
            }
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                height: 20px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ff88, stop:1 #00ccff);
                border-radius: 4px;
            }
            QLabel {
                font-size: 16px;
                font-weight: 500;
                color: #ffffff;
                text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.3);
            }
        """)

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.SplashScreen |
                            Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 启用半透明

        # 创建主容器
        container = QWidget()
        container.setObjectName("container")
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(30, 40, 30, 40)
        container_layout.setSpacing(25)

        # 将控件添加到容器
        self.label = QLabel("FAA 自动化协议正在加载...")
        self.progress_bar = QProgressBar()
        container_layout.addWidget(self.label)
        container_layout.addWidget(self.progress_bar)
        container.setLayout(container_layout)

        # 主窗口布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(container)
        self.setLayout(main_layout)

        # 将阴影效果应用到容器
        container.setGraphicsEffect(QGraphicsDropShadowEffect(
            blurRadius=15, color=QColor(0, 0, 0, 80),
            offset=QPointF(3, 3)))

        # 居中显示
        screen = self.screen().geometry()
        self.move(int(screen.width() / 2 - 150), int(screen.height() / 2 - 75))
        self.resize(300, 150)
    def update_progress(self, value):
        self.progress_bar.setValue(value)
        QApplication.processEvents()
