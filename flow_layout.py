# Ported from the C++ implementation found here:
#  https://doc.qt.io/qt-5/qtwidgets-layouts-flowlayout-example.html

from PyQt5.QtWidgets import QLayout, QStyle, QSizePolicy, QWidgetItem, QWidget
from PyQt5.QtCore import Qt, QPoint, QRect, QSize


class FlowLayout(QLayout):

    def __init__(self, parent=None, margin=-1, h_spacing=-1, v_spacing=-1):
        QLayout.__init__(self, parent)

        self._h_space = h_spacing
        self._v_space = v_spacing

        self._item_list = []

        self.setContentsMargins(margin, margin, margin, margin)

    # Do we need to delete the items in the widget on deletion?
    # C++ implementation walks the list of items by calling:
    #  while(item = takeAt(0)) {
    #    delete item;
    #  }
    # Python should garbage collect automatically

    def addItem(self, item):
        self._item_list.append(item)

    def insertWidget(self, index: int, item: QWidget):
        self._item_list.insert(index, QWidgetItem(item))

    def horizontal_spacing(self):
        if self._h_space >= 0:
            return self._h_space
        else:
            return self._smart_spacing(QStyle.PM_LayoutHorizontalSpacing)

    def vertical_spacing(self):
        if self._v_space >= 0:
            return self._v_space
        else:
            return self._smart_spacing(QStyle.PM_LayoutVerticalSpacing)

    def expandingDirections(self):
        return Qt.Horizontal | Qt.Vertical

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        try:
            return self._item_list[index]
        except IndexError:
            return None

    def minimum_size(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())

        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimum_size()

    def takeAt(self, idx):
        if 0 <= idx < self.count():
            return self._item_list.pop(idx)
        return None

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._item_list:
            widget = item.widget()
            space_x = self.horizontal_spacing()
            if space_x == -1:
                space_x = widget.style().layoutSpacing(QSizePolicy.Label,
                                                       QSizePolicy.Label,
                                                       Qt.Horizontal)
            space_y = self.vertical_spacing()
            if space_y == -1:
                space_y = widget.style().layoutSpacing(QSizePolicy.Label,
                                                       QSizePolicy.Label,
                                                       Qt.Vertical)
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + bottom

    def _smart_spacing(self, pm):
        if not self.parent():
            return -1
        elif self.parent().isWidgetType():
            return self.parent().style().pixelMetric(pm, None, self.parent())
        else:
            return self.parent().spacing()
