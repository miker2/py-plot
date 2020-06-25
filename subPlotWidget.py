# This Python file uses the following encoding: utf-8
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import QVariant
import pyqtgraph as pg

import pickle
import numpy as np
from dataModel import DataItem


class subPlotWidget(QWidget):
    COLORS=('r','g','b','c','m')
    def __init__(self, plot_manager):
        QtWidgets.QWidget.__init__(self)

        self._plot_manager = plot_manager

        vBox = QVBoxLayout(self)
        vBox.addWidget(QLabel("This is my label"))

        self.pw = pg.PlotWidget()
        vBox.addWidget(self.pw)

        self.pw.setBackground('w')
        self.pw.showGrid(x=True, y=True)

        pi = self.pw.getPlotItem()
        pi.addLegend()
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

        # We can just override the menu of the ViewBox here but I think a better solution
        # is to create a new object that derives from the ViewBox class and set up everything
        # that way.
        self.pw.getPlotItem().setMenuEnabled(enableMenu=False, enableViewBoxMenu=None)
        self.pw.getViewBox().menu = self.contextMenu()

    def setCursor(self, tick):
        self.cursor.setValue(tick / 500.)

    def setXLimitMin(self, xmin):
        self.pw.setLimits(xMin=xmin)

    def setXLimitMax(self, xmax):
        self.pw.setLimits(xMax=xmax)

    def contextMenu(self):
        menu = QtWidgets.QMenu()
        addAboveAction = QtWidgets.QAction("Add plot above", self.pw.getViewBox())
        addAboveAction.triggered.connect(lambda : self._plot_manager.addSubplotAbove(self))
        menu.addAction(addAboveAction)
        addBelowAction = QtWidgets.QAction("Add plot below", self.pw.getViewBox())
        addBelowAction.triggered.connect(lambda : self._plot_manager.addSubplotBelow(self))
        menu.addAction(addBelowAction)
        deleteSubplotAction = QtWidgets.QAction("Remove Plot", self.pw.getViewBox())
        deleteSubplotAction.triggered.connect(lambda : self._plot_manager.removeSubplot(self))
        menu.addAction(deleteSubplotAction)
        menu.addSeparator()
        clearPlotAction = QtWidgets.QAction("Clear plot", self.pw.getViewBox())
        clearPlotAction.triggered.connect(self.clearPlot)
        menu.addAction(clearPlotAction)

        return menu

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("application/x-DataItem"):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        data = e.mimeData()
        bstream = data.retrieveData("application/x-DataItem", QtCore.QVariant.ByteArray)
        selected = pickle.loads(bstream)

        self.pw.getPlotItem().plot(x=selected.time,
                                   y=selected.data,
                                   pen=pg.mkPen(color=subPlotWidget.COLORS[self.cidx],
                                                width=2),
                                   name=selected.var_name)
        #self.pw.autoRange()
        self.cidx = (self.cidx + 1) % len(subPlotWidget.COLORS)
        e.accept()

    def clearPlot(self):
        # HAX!!! Save the cursor!
        x = self.cursor.value()
        self.pw.clear()
        # Replace the cursor. Such a hack
        self.cursor = pg.InfiniteLine(pos=x, movable=False, pen='r')
        self.pw.addItem(self.cursor)

        self.cidx = 0
