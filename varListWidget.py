# This Python file uses the following encoding: utf-8
# from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5 import QtCore

import pandas
import pickle
from dataModel import *


class varListWidget(QtWidgets.QListView):
    _PLOT_DATA = QtCore.Qt.UserRole
    def __init__(self, parent, filename):
        super().__init__(parent)

        model = dataModel(filename)
        # self.clicked.connect(self.itemClicked)
        self.pressed.connect(self.itemPressed)

        self.setModel(model)

        self.setDragEnabled(True)

        self.filename = filename

    @property
    def time_range(self):
        return self.model().time_range

    def itemClicked(self, index):
        QtGui.QMessageBox.information(self, "ListWidget",
                                      f"You clicked item {index.row()}: {index.data()}\n"
                                      + f"{index.data(varListWidget._PLOT_DATA).data}")
    def itemPressed(self, index):
        print(f"You pressed {index.row()} : {index.data()}")

    def get_data(self, filename):
        return pandas.read_csv(filename)

    def mouseMoveEvent(self, e):
        self.startDrag(e)

    def startDrag(self, e):
        index = self.indexAt(e.pos())
        if not index.isValid():
            return

        selected = self.model().data(index, QtCore.Qt.UserRole)
        selected._time = self.model().time
        bstream = pickle.dumps(selected)
        mimeData = QtCore.QMimeData()
        mimeData.setData("application/x-DataItem", bstream)

        drag = QtGui.QDrag(self)
        drag.setMimeData(mimeData)

        result = drag.exec()
