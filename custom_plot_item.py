# -*- coding: utf-8 -*-

from PyQt5.QtCore import Qt, pyqtSlot, QEvent, QRect
from PyQt5.QtWidgets import QLabel, QSizePolicy
from PyQt5.QtGui import QPalette, QPixmap, QPainter, QPaintEvent

import pyqtgraph as pg
import numpy as np

class CustomPlotItem(QLabel):
    def __init__(self, parent, plot_data_item, current_tick):
        QLabel.__init__(self, plot_data_item.name(), parent=parent)

        ''' This item should handle the following things:
              1) Hold a handle to the pyqtgraph.PlotItem that is on the plot
              2) Own a QLabel which is used to display the name of the signal and it's value
              3) connect to the tickValueChanged signal so the value can be updated
              4) Remove the label and trace, etc when this item is destroyed
        '''

        self.trace = plot_data_item

        if np.issubdtype(self.trace.yData.dtype, np.integer):
            self._fmt_str = "{0:d}"
        else:
            self._fmt_str = "{0:.6g}"
        self.setText(self._generateLabel(current_tick))
        # __import__("ipdb").set_trace()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum))
        self.setWordWrap(True)

        # Make the label text the same color as the trace.
        palette = QPalette()
        color = plot_data_item.opts['pen'].color()
        palette.setColor(QPalette.WindowText, color)
        self.setPalette(palette)

        self._close_pxm = QPixmap('close_icon.png')
        assert(not self._close_pxm.isNull())


        self._show_close_button = False
        self._close_btn_rect = QRect(0, 0, 16, 16)

    def updateColor(self, color_str):
        pen = pg.mkPen(color=color_str, width=self.parent().PEN_WIDTH)
        self.trace.setPen(pen)
        palette = QPalette()
        palette.setColor(QPalette.WindowText, pen.color())
        self.setPalette(palette)

    @property
    def name(self):
        return self.trace.name()

    def getPlotSpec(self):
        # For now, we'll just get the name of the trace, but this will become more complex in the
        # future when we start supporting derived signals.
        return self.trace.name()

    @pyqtSlot(int)
    def onTickChanged(self, tick):
        # print(f"onTickChanged called with tick={tick}")
        self.setText(self._generateLabel(tick))

    def enterEvent(self, event):
        super().enterEvent(event)
        self._show_close_button = True
        self.update()


    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._show_close_button = False
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        #print(event.type())
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
            self.removeItem()
            event.accept()
        else:
            super().mousePressEvent(event)

    def removeItem(self):
        self.parent().removeItem(self.trace, self)

    def _getValue(self, tick):
        y = self.trace.yData
        tick = min(tick, len(y)-1)

        return y[tick]

    def _generateLabel(self, tick):
        return f"{self.trace.name()}: " + self._fmt_str.format(self._getValue(tick))
