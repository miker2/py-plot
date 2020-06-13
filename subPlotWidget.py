# This Python file uses the following encoding: utf-8
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import QVariant
import pyqtgraph as pg

import pickle
import numpy as np
from dataItem import *

COLORS=('r','g','b','c','m')

class subPlotWidget(QWidget):
    def __init__(self, scale=1):
        QtWidgets.QWidget.__init__(self)

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

        self.cidx = 0

    def context_menu(self):
        pass

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("application/x-dataItem"):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        data = e.mimeData()
        bstream = data.retrieveData("application/x-dataItem", QtCore.QVariant.ByteArray)
        selected = pickle.loads(bstream)

        self.pw.getPlotItem().plot(y=selected.data,
                                   pen=pg.mkPen(color=COLORS[self.cidx],
                                                width=2),
                                   name=selected.var_name)
        self.cidx = (self.cidx + 1) % len(COLORS)
        e.accept()
