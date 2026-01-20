import sys

from PyQt6.QtCore import Qt, QLineF
from PyQt6.QtGui import QPainter, QPen, QTransform
from PyQt6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QVBoxLayout, QMainWindow, QWidget,
    QGraphicsLineItem, QGraphicsTextItem, QPushButton, QHBoxLayout
)


class TaskItem(QGraphicsRectItem):
    def __init__(self, x, y, width, height, grid_size):
        super().__init__(x, y, width, height)
        self.grid_size = grid_size  # Grid size for snapping
        self.setBrush(Qt.GlobalColor.blue)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsFocusable, True)

    def mousePressEvent(self, event):
        self.setBrush(Qt.GlobalColor.red)  # Change color when selected
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setBrush(Qt.GlobalColor.blue)  # Revert color when deselected
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        # Snap to grid
        new_x = round(self.x() / self.grid_size) * self.grid_size
        self.setX(new_x)


class TimelineView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.grid_size = 100
        self.track_height = 60
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0

        # Dictionary to store timeline state
        self.timeline_data = {
            "tasks": [],  # List to store tasks
            "scene_width": 2000,
            "scene_height": 300,
            "track_count": 5
        }

        self.setSceneRect(0, 0, self.timeline_data["scene_width"], self.timeline_data["scene_height"])

        # Draw initial time grid and labels
        self.draw_time_grid()

        # Add some task items
        self.add_task(100, 20, 200, 40)  # Task in the first track
        self.add_task(400, 80, 300, 40)  # Task in the second track

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

    def draw_time_grid(self):
        self.scene().clear()  # Clear the scene before redrawing
        grid_color = Qt.GlobalColor.lightGray
        pen = QPen(grid_color, 0.5)

        # Draw vertical time markers and labels
        for i in range(0, int(self.timeline_data["scene_width"]), self.grid_size):
            line = QGraphicsLineItem(QLineF(i, 0, i, self.timeline_data["scene_height"]))
            line.setPen(pen)
            self.scene().addItem(line)

            # Add time label
            label = QGraphicsTextItem(f"{i // self.grid_size}s")
            label.setPos(i, 0)
            self.scene().addItem(label)

        # Draw horizontal grid lines to represent different tracks
        for j in range(0, self.timeline_data["scene_height"], self.track_height):
            line = QGraphicsLineItem(QLineF(0, j, self.timeline_data["scene_width"], j))
            line.setPen(pen)
            self.scene().addItem(line)

    def add_task(self, x, y, width, height):
        task = TaskItem(x, y, width, height, self.grid_size)
        self.scene().addItem(task)
        self.timeline_data["tasks"].append((x, y, width, height))  # Store task in timeline_data

    def add_track(self):
        self.timeline_data["scene_height"] += self.track_height
        self.timeline_data["track_count"] += 1
        self.setSceneRect(0, 0, self.timeline_data["scene_width"], self.timeline_data["scene_height"])
        self.refresh_ui()

    def remove_track(self):
        if self.timeline_data["scene_height"] > self.track_height:
            self.timeline_data["scene_height"] -= self.track_height
            self.timeline_data["track_count"] -= 1
            self.setSceneRect(0, 0, self.timeline_data["scene_width"], self.timeline_data["scene_height"])
            self.refresh_ui()

    def refresh_ui(self):
        self.draw_time_grid()
        for task in self.timeline_data["tasks"]:
            x, y, width, height = task
            self.add_task(x, y, width, height)

    def wheelEvent(self, event):
        # Zoom in/out with mouse wheel
        zoom_in_factor = 1.1
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        new_zoom_factor = self.zoom_factor * zoom_factor
        if self.min_zoom <= new_zoom_factor <= self.max_zoom:
            self.zoom_factor = new_zoom_factor
            transform = QTransform().scale(self.zoom_factor, 1.0)
            self.setTransform(transform)

            # Redraw the time grid and refresh tasks
            # self.refresh_ui()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timeline Editor")
        self.setGeometry(100, 100, 1000, 500)

        layout = QVBoxLayout()
        timeline_view = TimelineView()
        layout.addWidget(timeline_view)

        button_layout = QHBoxLayout()

        add_track_btn = QPushButton("Add Track")
        add_track_btn.clicked.connect(timeline_view.add_track)
        button_layout.addWidget(add_track_btn)

        remove_track_btn = QPushButton("Remove Track")
        remove_track_btn.clicked.connect(timeline_view.remove_track)
        button_layout.addWidget(remove_track_btn)

        layout.addLayout(button_layout)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
