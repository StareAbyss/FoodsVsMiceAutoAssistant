import random

from PyQt6.QtGui import QColor, QMovie
from PyQt6.QtWidgets import QWidget, QProgressBar, QLabel, QVBoxLayout, QApplication, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPointF, QPropertyAnimation, QEasingCurve, QPoint, QSize
from function.globals.get_paths import PATHS

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
        self.animation = QPropertyAnimation(self, b"windowOpacity")  # 注意是 b"windowOpacity"
        self.animation.setDuration(500)  # 动画持续时间（毫秒）
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)

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
        self.progress_bar.setFixedSize(240, 20)  # 固定大小便于定位
        self.progress_bar.setValue(0)

        # 添加 GIF 标签（覆盖在进度条上）
        self.gif_label = QLabel(self)
        self.gif_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.gif_label.setFixedSize(77, 96)
        self.gif_label.setScaledContents(True)
        self.gif_movie = QMovie(PATHS["ui"] + "\\progress.gif")
        self.gif_movie.setScaledSize(QSize(77, 96))
        # self.gif_movie.setCacheMode(QMovie.CacheMode.CacheAll)
        self.gif_label.setMovie(self.gif_movie)
        # self.gif_movie.start()
        self.gif_label.hide()

        container_layout.addWidget(self.label)
        container_layout.addWidget(self.progress_bar)
        container.setLayout(container_layout)

        # 主窗口布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(container)
        self.setLayout(main_layout)

        # 将阴影效果应用到容器
        container.setGraphicsEffect(QGraphicsDropShadowEffect(
            blurRadius=40, color=QColor(0, 0, 0, 120),
            offset=QPointF(0, 0)))

        # 居中显示
        screen = self.screen().geometry()
        self.move(int(screen.width() / 2 - 150), int(screen.height() / 2 - 75))
        self.resize(300, 150)
        # 预设加载文本列表
        self.loading_texts_pool = [
            "FAA 自动化协议正在加载...",
            "正在赞美深渊...",
            "正在一键逆天...",
            "正在构建用户界面...",
            "正在揭露提拉米苏的阴谋...",
            "正在强化海星...",
            "即将完成初始化..."
        ]
    def update_progress(self, value,text=None):
        self.progress_bar.setValue(value)
        if value>0:
            self.update_gif_position(value)
        if value >= 100:
            # self.gif_movie.stop()
            self.start_fade_out()
        if text:
            self.label.setText(text)
        else:
            random_text = random.choice(self.loading_texts_pool)
            self.label.setText(random_text)

    def start_fade_out(self):
        self.animation.stop()
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.start()
        self.animation.finished.connect(self.hide)

    def update_gif_position(self, value):
        """根据进度值动态调整 GIF 位置"""
        bar_width = self.progress_bar.width()
        bar_height = self.progress_bar.height()
        gif_size = self.gif_label.width()
        padding_left = 5

        # 计算有效进度宽度（排除 padding）
        effective_width = bar_width - 2 * padding_left
        current_x = int(padding_left + effective_width * (value / 100.0) - gif_size / 2)

        # 获取进度条在主窗口中的位置
        bar_global_pos = self.progress_bar.mapToGlobal(QPoint(0, 0))
        window_global_pos = self.mapToGlobal(QPoint(0, 0))
        bar_in_window_pos = bar_global_pos - window_global_pos

        # 设置 GIF 位置（修正锚点偏移）
        self.gif_label.move(
            bar_in_window_pos.x() + current_x,
            bar_in_window_pos.y() + (bar_height - gif_size) // 2
        )
        self.gif_label.raise_()
        self.gif_label.show()

