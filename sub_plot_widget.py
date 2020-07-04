# This Python file uses the following encoding: utf-8

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QMenu, QAction
from PyQt5.QtCore import Qt, QVariant, QRect
import pyqtgraph as pg

import pickle
import numpy as np
from data_model import DataItem
from custom_plot_item import CustomPlotItem

_DEFAULT_FREQ=500.

class SubPlotWidget(QWidget):
    # Plot colors picked from here: https://colorbrewer2.org/#type=qualitative&scheme=Set1&n=8
    # with a slight modification to the "yellow" so it's darker and easier to see.
    COLORS=('#e41a1c','#377eb8','#4daf4a','#984ea3','#ff7f00', '#a65628', '#D4C200', '#f781bf')
    PEN_WIDTH=2
    def __init__(self, parent):
        QWidget.__init__(self, parent=parent)

        vBox = QVBoxLayout(self)

        self._labels = QHBoxLayout()
        self._labels.addStretch()
        vBox.addLayout(self._labels)

        self.pw = pg.PlotWidget()
        vBox.addWidget(self.pw)

        self.pw.setBackground('w')
        self.pw.showGrid(x=True, y=True)

        pi = self.pw.getPlotItem()
        # pi.addLegend()
        # self.clicked.connect(self.on_clicked)

        # print(self.pw.super().ctrlMenu)

        self.setAcceptDrops(True)
        self.pw.setAcceptDrops(True)
        self.pw.enableAutoRange(x=False)
        self.pw.setMouseEnabled(x=False)
        self.pw.setClipToView(True)  # Only draw items in range

        self.cursor = pg.InfiniteLine(pos=0, movable=False, pen='r')
        self.pw.addItem(self.cursor)

        self.cidx = 0

        self._traces = []

        # We can just override the menu of the ViewBox here but I think a better solution
        # is to create a new object that derives from the ViewBox class and set up everything
        # that way.
        self.pw.getPlotItem().setMenuEnabled(enableMenu=False, enableViewBoxMenu=None)
        self.pw.getViewBox().menu = self.contextMenu()

        self.pw.scene().sigMouseClicked.connect(self._onSceneMouseClickEvent)

    def moveCursor(self, tick):
        self.cursor.setValue(tick / _DEFAULT_FREQ)

    def setXLimits(self, xmin, xmax):
        self.setXLimitMin(xmin)
        self.setXLimitMax(xmax)

    def setXLimitMin(self, xmin):
        self.pw.setLimits(xMin=xmin)

    def setXLimitMax(self, xmax):
        self.pw.setLimits(xMax=xmax)

    def contextMenu(self):
        menu = QMenu()
        addAboveAction = QAction("Add plot above", self.pw.getViewBox())
        addAboveAction.triggered.connect(lambda : self.parent().addSubplotAbove(self))
        menu.addAction(addAboveAction)
        addBelowAction = QAction("Add plot below", self.pw.getViewBox())
        addBelowAction.triggered.connect(lambda : self.parent().addSubplotBelow(self))
        menu.addAction(addBelowAction)
        deleteSubplotAction = QAction("Remove Plot", self.pw.getViewBox())
        deleteSubplotAction.triggered.connect(lambda : self.parent().removeSubplot(self))
        menu.addAction(deleteSubplotAction)
        menu.addSeparator()
        clearPlotAction = QAction("Clear plot", self.pw.getViewBox())
        clearPlotAction.triggered.connect(self.clearPlot)
        menu.addAction(clearPlotAction)
        clearPlotAction = QAction("Reset y-range", self.pw.getViewBox())
        clearPlotAction.triggered.connect(self.updatePlotYRange)
        menu.addAction(clearPlotAction)

        return menu

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("application/x-DataItem"):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        data = e.mimeData()
        bstream = data.retrieveData("application/x-DataItem", QVariant.ByteArray)
        selected = pickle.loads(bstream)

        self.plotDataFromSource(selected.var_name, e.source())

        e.accept()

    def _onSceneMouseClickEvent(self, event):
        if event.button() != Qt.LeftButton:
            event.ignore()
            return

        t_click = self.pw.getViewBox().mapSceneToView(event.scenePos()).x()
        self.parent().plotManager().setTickFromTime(t_click)
        event.accept()

    def plotDataFromSource(self, name, source):
        y_data = source.model().getDataByName(name)

        if y_data is None:
            return

        item = self.pw.getPlotItem().plot(x=source.model().time,
                                          y=y_data,
                                          pen=pg.mkPen(color=self._getColor(self.cidx),
                                                       width=SubPlotWidget.PEN_WIDTH),
                                          name=name,
                                          # clipToView=True,
                                          autoDownsample=True,
                                          downsampleMethod='peak')

        label = CustomPlotItem(self, item, source, self.parent().plotManager()._tick)
        self._traces.append(label)
        # Insert just before the end so that the spacer is last - TODO(rose@): fix this.
        self._labels.insertWidget(self._labels.count() - 1, label)
        self.parent().plotManager().tickValueChanged.connect(label.onTickChanged)

        source.onClose.connect(lambda : self.removeItem(item, label))

        self.cidx += 1

        self.updatePlotYRange()

    def removeItem(self, trace, label):
        self.pw.removeItem(trace)
        self._labels.removeWidget(label)
        label.close()

        self.cidx = max(0, self.cidx-1)

        for idx in range(self._labels.count() - 1):
            self._labels.itemAt(idx).widget().updateColor(self._getColor(idx))

    def clearPlot(self):
        # HAX!!! Save the cursor!
        x = self.cursor.value()
        self.pw.clear()
        # Replace the cursor. Such a hack
        self.cursor = pg.InfiniteLine(pos=x, movable=False, pen='r')
        self.pw.addItem(self.cursor)

        # Remove labels also.
        while self._labels.count() > 1:  # This is a hack so the stretch element doesn't disappear (always last)
            lbl = self._labels.takeAt(0).widget()
            lbl.close()

        self.cidx = 0

    def updatePlotYRange(self, val=None):
        self.pw.autoRange()
        # Workaround for autoRange() not respecting the disabled x-axis
        self.parent().updatePlotXRange()

    def setYRange(self, ymin, ymax):
        self.pw.setYRange(ymin, ymax, padding=0)

    def getPlotInfo(self):
        ''' This method should return a dictionary of information required to reproduce this
            plot '''

        plot_info = dict()
        # Is there a more correct way to get the range of the y-axis? Probably safe to assume that
        # the 'left' axis is always the correct one, but the 'range' property of an 'AxisItem'
        # isn't documented in the public API.
        y_range = self.pw.getPlotItem().getAxis('left').range
        plot_info['yrange'] = y_range
        plot_info['traces'] = [trace.getPlotSpec() for trace in self._traces if trace.isVisible()]

        return plot_info

    def _getColor(self, idx):
        return SubPlotWidget.COLORS[idx % len(SubPlotWidget.COLORS)]
