# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from QRangeSlider import QRangeSlider
from subPlotWidget import subPlotWidget

import math



''' This class is for management of a linked set of subplots
'''
class plotManager(QtWidgets.QWidget):

    tickValueChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent):
        QtWidgets.QWidget.__init__(self, parent)

        # This is the main widget of the app. It contains the range slider and a layout containing all of the subplots.
        central_layout = QVBoxLayout(self)
        central_layout.setObjectName("plotManagerLayout")

        self.range_slider = QRangeSlider()
        self.range_slider.show()
        self.range_slider.setMin(0.)
        self.range_slider.setMax(1000.)  # large number here is sort of a hack for now so the plot x-axis resizes properly on the first file load.
        self.range_slider.setRange(self.range_slider.min(), self.range_slider.max())

        self.range_slider.startValueChanged.connect(self.updatePlotXRange)
        self.range_slider.endValueChanged.connect(self.updatePlotXRange)
        central_layout.addWidget(self.range_slider)

        self.plot_area = QVBoxLayout()
        central_layout.addLayout(self.plot_area)

        self._tick = 0

        # Start off with two subplots
        self.addSubplot()
        self.addSubplot()

    def addSubplot(self, idx=None):
        if not idx:
            idx = self.plot_area.count()
        subplot = subPlotWidget(self)
        subplot.setCursor(self._tick)
        self.tickValueChanged.connect(subplot.setCursor)
        self.range_slider.minValueChanged.connect(subplot.setXLimitMin)
        self.range_slider.maxValueChanged.connect(subplot.setXLimitMax)
        self.plot_area.insertWidget(idx, subplot)

        self._linkAxes()

        #self._dispLayoutContents()

    def addSubplotAbove(self, subplot):
        idx = self._getIndex(subplot)
        self.addSubplot(idx)

    def addSubplotBelow(self, subplot):
        idx = self._getIndex(subplot)
        self.addSubplot(idx+1)

    def removeSubplot(self, subplot):
        if self.plot_area.count() <= 1:
            # Don't allow the only remaining plot to be removed
            return
        item = self.plot_area.takeAt(self.plot_area.indexOf(subplot))
        subplot.deleteLater()

        #self._dispLayoutContents()

        if self.plot_area.count() <= 1:
            # Nothing else to do here
            return

        # We need to handle the special case of the first subplot being removed!
        # Re-link all axes to the first plot in the list
        self._linkAxes()

    def handleKeyPress(self, event):
        ''' This is the main keypress event handler. It will handle distrubution of the various functionality. '''
        key = event.key()
        if key == QtCore.Qt.Key_Down or key == QtCore.Qt.Key_Up:
            self.modifyZoom(key == QtCore.Qt.Key_Up, event.modifiers())
        elif key == QtCore.Qt.Key_Left or key == QtCore.Qt.Key_Right:
            self.moveCursor(key == QtCore.Qt.Key_Right, event.modifiers())


    def moveCursor(self, positive, modifier):
        # print(f"Move cursor {'Right' if positive else 'Left'}")
        mult = 1
        if modifier & QtCore.Qt.ControlModifier:
            mult *= 5
        if modifier & QtCore.Qt.ShiftModifier:
            mult *= 20
        self._tick += mult * (1 if positive else -1)
        self._tick = max(0, min(self._tick, math.inf))

        self.tickValueChanged.emit(self._tick)

    def modifyZoom(self, zoom_in, modifier):
        # Slider is in time units. Here we'll assume the DT, but we can change this later.
        default_freq = 500.
        min_range = 10. / default_freq
        mult = 5. / default_freq
        if modifier & QtCore.Qt.ControlModifier:
            mult *= 5
        if modifier & QtCore.Qt.ShiftModifier:
            mult *= 20
        mult = min(mult, 250)
        offset = mult * (1 if zoom_in else -1)
        midpoint = 0.5 * (self.range_slider.start() + self.range_slider.end())
        new_start = self.range_slider.start() + offset
        new_end = self.range_slider.end() - offset
        if new_start > new_end:
            # Too much zoom! Limit it to something reasonable.
            new_start = midpoint - 0.5 * min_range
            new_end = midpoint + 0.5 * min_range
        # Make sure neither value is outside the min/max limits
        new_start = max(new_start, self.range_slider.min())
        new_end = min(new_end, self.range_slider.max())

        self.range_slider.setStart(new_start)
        self.range_slider.setEnd(new_end)

    def updatePlotXRange(self, val):
        #print(f"Value: {val}, start: start: {self.range_slider.start()}, end: {self.range_slider.end()}")
        # Because plots are linked we only need to do this for the first plot. Others will follow suite.
        self._getPlot(0).pw.setXRange(min=self.range_slider.start(),
                                                       max=self.range_slider.end(),
                                                       padding=0)

    def _linkAxes(self):
        # TODO: Make this use signal/slot mechanism
        pw = self._getPlot(0).pw
        for idx in range(1, self.plot_area.count()):
            self._getPlot(idx).pw.setXLink(pw)

    def _getIndex(self, subplot):
        ''' This method returns the index of the subplot (both from the layout and the list) '''
        return self.plot_area.indexOf(subplot)

    def _getPlot(self, idx):
        return self.plot_area.itemAt(idx).widget()

    def _dispLayoutContents(self):
        print(f"There are {self.plot_area.count()} items in the layout")
        for i in range(self.plot_area.count()):
            print(f"{i} : {self.plot_area.itemAt(i)}")
            try:
                print(f"      {self._getPlot(i)}")
            except:
                pass

    # Originally these methods were located in the top level file (main.py)
    # These should probably be cleaned up a bit. We could make the dataFileWidget
    # emit a signal when a file is opened or closed. That might make it better.
    def updateSliderLimits(self, t_min, t_max):
        self.range_slider.setMin(t_min)
        self.range_slider.setMax(t_max)
        if self.range_slider.min() > self.range_slider.start():
            self.range_slider.setStart(t_min)
        if self.range_slider.max() < self.range_slider.end():
            self.range_slider.setEnd(t_max)

        #print(f"slider - min: {self.range_slider.min()}, start: {self.range_slider.start()}, " +
        #      f"max: {self.range_slider.max()}, end: {self.range_slider.end()}")
