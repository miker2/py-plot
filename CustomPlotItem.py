# -*- coding: utf-8 -*-

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QLabel, QSizePolicy
from PyQt5.QtGui import QPalette

import pyqtgraph as pg

class CustomPlotItem(QLabel):
    def __init__(self, plot_data_item, current_tick):
        QLabel.__init__(self, plot_data_item.name())

        ''' This item should handle the following things:
              1) Hold a handle to the pyqtgraph.PlotItem that is on the plot
              2) Own a QLabel which is used to display the name of the signal and it's value
              3) connect to the tickValueChanged signal so the value can be updated
              4) Remove the label and trace, etc when this item is destroyed
        '''

        self.trace = plot_data_item

        self._fmt_str = self.trace.name()+": {0:.6f}"
        self.setText(self._generateLabel(current_tick))
        # __import__("ipdb").set_trace()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum))
        self.setWordWrap(True)

        # Make the label text the same color as the trace.
        palette = QPalette()
        color = plot_data_item.opts['pen'].color()
        palette.setColor(QPalette.WindowText, color)
        self.setPalette(palette)

    @property
    def name(self):
        return self.trace.name()

    @pyqtSlot(int)
    def onTickChanged(self, tick):
        # print(f"onTickChanged called with tick={tick}")
        self.setText(self._generateLabel(tick))

    def _getValue(self, tick):
        y = self.trace.yData
        tick = min(tick, len(y)-1)

        return y[tick]

    def _generateLabel(self, tick):
        return self._fmt_str.format(self._getValue(tick))

