# -*- coding: utf-8 -*-

from PyQt5.QtCore import Qt, pyqtSlot, QRect
from PyQt5.QtWidgets import QLabel, QMenu, QAction
from PyQt5.QtGui import QPalette, QPixmap, QPainter

try:
    from PyQt5.QtGui import QApplication
except ImportError:
    from PyQt5.QtWidgets import QApplication

import os
import pyqtgraph as pg
import numpy as np

import graph_utils
from plot_spec import PlotSpec
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from var_list_widget import VarListWidget
    from maths_widget import MathsWidget
    # PlotSpec is already imported above, no need to re-import under TYPE_CHECKING unless it was causing issues


class CustomPlotItem(QLabel):
    PEN_WIDTH = 2

    def __init__(self, parent, plot_data_item, source, current_tick, plot_spec_from_source: 'PlotSpec | None' = None): # Added plot_spec_from_source
        QLabel.__init__(self, plot_data_item.name(), parent=parent)

        ''' This item should handle the following things:
              1) Hold a handle to the pyqtgraph.PlotItem that is on the plot
              2) Own a QLabel which is used to display the name of the signal and it's value
              3) connect to the tickValueChanged signal so the value can be updated
              4) Remove the label and trace, etc when this item is destroyed
        '''

        self.trace = plot_data_item

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

        # Initialize self.plot_spec based on plot_spec_from_source
        if plot_spec_from_source:
            self.plot_spec = plot_spec_from_source
        else:
            # Create a default "file" PlotSpec if none is provided
            name = plot_data_item.name() # Use the name from the plot_data_item
            file_id = "unknown_source_widget" # Default file identifier
            
            # Attempt to get a more specific file_id from the source
            # source is typically VarListWidget or MathsWidget (or their models)
            if hasattr(source, 'filename') and source.filename: # Check for direct filename (e.g. VarListWidget)
                file_id = source.filename
            elif hasattr(source, 'idx') and source.idx is not None: # Check for direct idx (e.g. VarListWidget)
                file_id = str(source.idx)
            # If source is MathsWidget, it's more complex as it doesn't have a single 'filename' or 'idx'
            # However, if plot_spec_from_source is None, it implies the data isn't from a known math operation.
            # This logic assumes that if data comes from MathsWidget, plot_spec_from_source should be set.

            self.plot_spec = PlotSpec(
                name=name,
                source_type="file", # Default to "file" if not otherwise specified
                original_name=name, # Assume original_name is same as current name if not specified
                file_source_identifier=file_id
            )

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
        # This method should now return the full PlotSpec object.
        return self.plot_spec

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
        else:
            super().mousePressEvent(event)

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
