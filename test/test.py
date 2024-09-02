import sys
import pandas as pd
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTableView, QCalendarWidget, \
    QStyledItemDelegate
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PyQt6.QtGui import QPixmap

from function.globals.get_paths import PATHS


class PandasModel(QAbstractTableModel):
    def __init__(self, data_frame, parent=None):
        super().__init__(parent)
        self._data_frame = data_frame

    def rowCount(self, parent=QModelIndex()):
        return len(self._data_frame)

    def columnCount(self, parent=QModelIndex()):
        return len(self._data_frame.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and index.isValid():
            row = index.row()
            col = index.column()
            value = self._data_frame.iat[row, col]

            # Return image paths or text
            if col == 0:  # Assuming image path is in the first column
                return value
            return str(value)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return ["成员名", "贡献值"][section]
            elif orientation == Qt.Orientation.Vertical:
                # 动态计算行号以反映排序后的行顺序
                return str(section + 1)
            else:
                return str(self._data_frame.index[section])
        return None

    def sort(self, column, order):
        if column == 1:  # Assuming contribution value is in the first column
            if order == Qt.SortOrder.AscendingOrder:
                self._data_frame = self._data_frame.sort_values(by='Total Contribution', ascending=True)
            elif order == Qt.SortOrder.DescendingOrder:
                self._data_frame = self._data_frame.sort_values(by='Total Contribution', ascending=False)
            self.layoutChanged.emit()


class ImageDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if index.column() == 0:  # Assuming images are in the first column
            image_path = index.data(Qt.ItemDataRole.DisplayRole)
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                painter.drawPixmap(option.rect, pixmap.scaled(option.rect.size(), Qt.AspectRatioMode.KeepAspectRatio))
        else:
            super().paint(painter, option, index)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Load data from CSV
        self.df = pd.read_csv(f"{PATHS["logs"]}\\guild_manager\\guild_members_contributions.csv")
        self.filtered_df = self.df[['Name Image Path', 'Total Contribution']]

        # Set up the UI
        self.setWindowTitle("Guild Member Contributions")
        self.setGeometry(100, 100, 800, 600)

        # Create widgets
        self.table_view = QTableView()
        self.calendar = QCalendarWidget()

        # Set up layout
        layout = QVBoxLayout()
        layout.addWidget(self.table_view)
        layout.addWidget(self.calendar)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Set up table model
        self.model = PandasModel(self.filtered_df)
        self.table_view.setModel(self.model)

        # Use custom delegate for images
        self.image_delegate = ImageDelegate(self.table_view)
        self.table_view.setItemDelegateForColumn(0, self.image_delegate)  # Apply delegate to image column

        # Adjust row height
        self.table_view.verticalHeader().setDefaultSectionSize(40)  # Set row height to 100 pixels

        # Connect calendar selection change to filter
        self.calendar.selectionChanged.connect(self.update_table_view)

        # Set up sorting behavior
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().sectionClicked.connect(self.on_header_clicked)

    def update_table_view(self):
        selected_date = self.calendar.selectedDate().toString('yyyy-MM-dd')
        if selected_date:
            self.filtered_df = self.df[self.df['Date'] == selected_date][['Name Image Path', 'Total Contribution']]
            self.model = PandasModel(self.filtered_df)
            self.table_view.setModel(self.model)

    def on_header_clicked(self, logical_index):
        if logical_index == 1:  # Only sort by the contribution column
            sort_order = self.table_view.horizontalHeader().sortIndicatorOrder()
            self.model.sort(logical_index, sort_order)
            self.table_view.update()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
