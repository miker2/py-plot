# -*- coding: utf-8 -*-

from PyQt5.QtCore import Qt, pyqtSlot, QRect, QMimeData, QByteArray, QPoint # Added QPoint
from PyQt5.QtWidgets import QLabel, QMenu, QAction, QApplication # QApplication moved here
from PyQt5.QtGui import QPalette, QPixmap, QPainter, QDrag # QDrag was already here
from logging_config import get_logger

# try: # QApplication is now directly imported from QtWidgets
#     from PyQt5.QtGui import QApplication
# except ImportError:
#     from PyQt5.QtWidgets import QApplication

import os
import pickle # Add pickle
import pyqtgraph as pg
import numpy as np

import graph_utils

logger = get_logger(__name__)

class CustomPlotItem(QLabel):
    PEN_WIDTH = 2

    def __init__(self, parent, plot_data_item, source, current_tick):
        QLabel.__init__(self, plot_data_item.name(), parent=parent)

        ''' This item should handle the following things:
              1) Hold a handle to the pyqtgraph.PlotItem that is on the plot
              2) Own a QLabel which is used to display the name of the signal and it's value
              3) connect to the tickValueChanged signal so the value can be updated
              4) Remove the label and trace, etc when this item is destroyed
        '''

        self.trace = plot_data_item
        self._subplot_widget = parent # Store parent reference
        self.drag_start_position = QPoint() # Initialize drag start position, ensure it's QPoint

        self.source = source

        # Keep a copy of the current tick in case we need it later:
        self._tick = current_tick

        if np.issubdtype(self.trace.yData.dtype, np.integer):
            self._fmt_str = "{0:d}"
        else:
            self._fmt_str = "{0:.6g}"
        self.setText(self._generate_label())

        # Make the label text the same color as the trace.
        palette = QPalette()
        color = plot_data_item.opts['pen'].color()
        palette.setColor(QPalette.WindowText, color)
        self.setPalette(palette)

        # For now assume that the resources are in the same directory as
        # this script.
        resource_dir, _ = os.path.split(os.path.realpath(__file__))
        self._close_pxm = QPixmap(resource_dir + '/close_icon.png')
        assert (not self._close_pxm.isNull())

        self._hidden = False

        self._show_close_button = False
        self._close_btn_rect = QRect(0, 0, 16, 16)

        self._menu = self.create_menu()

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_menu)

    def update_color(self, color_str):
        pen = pg.mkPen(color=color_str, width=CustomPlotItem.PEN_WIDTH)
        self.trace.setPen(pen)
        palette = QPalette()
        palette.setColor(QPalette.WindowText, pen.color())
        self.setPalette(palette)
        self.toggle_trace(self._hidden)

    def create_menu(self):
        menu = QMenu()
        hide_trace_action = QAction("Hide trace", self)
        hide_trace_action.triggered.connect(self.toggle_trace)
        hide_trace_action.setCheckable(True)
        copy_label_action = QAction("copy", self)
        copy_label_action.triggered.connect(lambda: QApplication.clipboard().setText(self.text()))
        copy_value_action = QAction("copy value", self)

        def value_txt():
            QApplication.clipboard().setText(str(self._get_value(self._tick)))

        copy_value_action.triggered.connect(value_txt)

        menu.addAction(hide_trace_action)
        menu.addAction(copy_label_action)
        menu.addAction(copy_value_action)
        return menu

    def show_menu(self, point):
        self._menu.exec_(self.mapToGlobal(point))

    def toggle_trace(self, is_checked):
        pen = self.trace.opts['pen']
        mycol = pen.color()

        if is_checked:
            pen.setStyle(Qt.NoPen)
            self.trace.setPen(pen)
            # Set QColor alpha for the label:
            mycol.setAlpha(100)
        else:
            pen.setStyle(Qt.SolidLine)
            self.trace.setPen(pen)
            # Set QColor alpha for the label
            mycol.setAlpha(255)
        palette = QPalette()
        palette.setColor(QPalette.WindowText, mycol)
        self.setPalette(palette)

        self._hidden = is_checked

    @property
    def name(self):
        return self.trace.name()

    def get_plot_spec(self):
        # For now, we'll just get the name of the trace, but this will become more complex in the
        # future when we start supporting derived signals.
        return self.trace.name()

    @pyqtSlot(float)
    def on_time_changed(self, time):
        # We use "time_to_tick" here instead of "time_to_nearest_tick" because if a signal is sampled
        # at a lower frequency than the master signal, we want the sample-and-hold version of the
        # value, not the closest value.
        self._tick = graph_utils.time_to_tick(self.trace.xData, time)
        # print(f"on_time_changed called for {self.trace.name()} with time={time}, " + \
        #      f"corresponding tick={self._tick}")
        self.setText(self._generate_label())

    def enterEvent(self, event):
        super().enterEvent(event)
        self._show_close_button = True
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._show_close_button = False
        self.update()

    def paintEvent(self, event):
        self.setText(self._generate_label())
        super().paintEvent(event)

        # print(event.type())
        if self._show_close_button:
            rect = event.rect()
            size = min(self._close_btn_rect.height(), rect.height())
            rect.setWidth(size)
            rect.setHeight(size)
            painter = QPainter(self)
            painter.drawPixmap(rect, self._close_pxm)

            painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._close_btn_rect.contains(event.pos()):
            self.remove_item()
            event.accept()
        elif event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos() # Use self.drag_start_position
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            # Call super for other mouse move events if necessary, or just return
            super().mouseMoveEvent(event)
            return

        # Check if drag_start_position is initialized and valid
        if not hasattr(self, 'drag_start_position') or self.drag_start_position is None or self.drag_start_position.isNull():
            super().mouseMoveEvent(event)
            return

        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        # Start drag
        # logger.info(f"CustomPlotItem '{self.name}': Initiating QDrag.")
        drag = QDrag(self)
        mime_data = QMimeData()

        # Set text for general purpose (e.g., if dropped on a text editor or for SubPlotWidget's text() check)
        mime_data.setText(self.trace.name())

        # Set specific data for "application/x-customplotitem" format
        # This is what SubPlotWidget's dropEvent will primarily check via hasFormat and then use text().
        # Encoding the trace name as QByteArray for setData.
        mime_data.setData("application/x-customplotitem", self.trace.name().encode())

        # It seems SubPlotWidget.dropEvent for CustomPlotItem reordering/moving
        # also uses e.mimeData().data("application/x-customplotitem-sourcewidget")
        # to get the source widget's object name. This should be preserved if still used.
        # The existing code already has this:
        if self._subplot_widget and self._subplot_widget.objectName():
            mime_data.setData("application/x-customplotitem-sourcewidget",
                              QByteArray(self._subplot_widget.objectName().encode()))
        else:
            # logger.warning("CustomPlotItem.mouseMoveEvent: _subplot_widget or its objectName not set.")
            mime_data.setData("application/x-customplotitem-sourcewidget", QByteArray())


        drag.setMimeData(mime_data)

        # Visual feedback for the drag
        try:
            pixmap = self.grab() # Grab the current appearance of the label
            drag.setPixmap(pixmap)
            # Set the hot spot to be where the mouse click started within the label
            drag.setHotSpot(event.pos() - self.rect().topLeft())
        except Exception as e_pixmap:
            logger.exception(f"CustomPlotItem.mouseMoveEvent: Exception during pixmap creation/setting: {e_pixmap}")

        # logger.info(f"CustomPlotItem '{self.name}': Executing drag.")
        drag.exec_(Qt.MoveAction)
        # logger.info(f"CustomPlotItem '{self.name}': Drag finished.")

        # Reset drag_start_position after drag finishes, though it might be good practice
        # to reset it in mouseReleaseEvent as well, or if the drag is cancelled.
        # For now, this matches the original logic of setting it to None.
        self.drag_start_position = QPoint() # Reset to an invalid/default QPoint

    def remove_item(self):
        self.parent().remove_item(self.trace, self)

    def _get_value(self, tick):
        y = self.trace.yData
        tick = min(tick, len(y) - 1)
        return y[tick]

    def _generate_label(self):
        prefix = ""
        if self.source.idx is not None:
            prefix = f"F{self.source.idx}:"
        return f"{prefix}{self.trace.name()}: " + self._fmt_str.format(self._get_value(self._tick))
