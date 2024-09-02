from PyQt6.QtWidgets import QStyledItemDelegate
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PyQt6.QtGui import QPixmap


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