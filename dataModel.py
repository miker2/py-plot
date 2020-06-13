# -*- coding: utf-8 -*-

try:
    from PySide import QtCore
    from PySide import QtWidgets
except:
    from PyQt5.QtCore import pyqtSlot as Slot
    from PyQt5 import QtCore
    from PyQt5 import QtWidgets

import pandas as pd
    
from dataItem import *

class dataModel(QtCore.QAbstractListModel):
    def __init__(self, filename, parent=None):
        super().__init__(parent)

        data = pd.read_csv(filename)
        self._data = []
        for var in sorted(data.columns):
            self._data.append(dataItem(var, data[var]))

        #self.setSupportedDragActions(QtCore.Qt.CopyAction)

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._data)

    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:
            item = self._data[index.row()]
            return QtCore.QVariant(item.var_name)
        elif role == QtCore.Qt.UserRole:
            # print(type(index))
            # print(type(index.row()))
            return self._data[index.row()]
        return QtCore.QVariant()
