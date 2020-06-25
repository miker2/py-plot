# -*- coding: utf-8 -*-

try:
    from PySide import QtCore
    from PySide import QtWidgets
except:
    from PyQt5.QtCore import pyqtSlot as Slot
    from PyQt5 import QtCore
    from PyQt5 import QtWidgets

import pandas as pd

class DataItem(object):
    '''
        Data structure for storing data items in the list widget
    '''
    def __init__(self, var_name, data):
        self._var_name = var_name
        self._data = data
        self._time = None

    @property
    def var_name(self):
        return self._var_name

    @property
    def data(self):
        return self._data

    @property
    def time(self):
        return self._time

    def __repr__(self):
        return self._var_name


class dataModel(QtCore.QAbstractListModel):
    def __init__(self, filename, parent=None):
        super().__init__(parent)

        # TODO(rose@): If we want to be able to support multiple data formats, we need
        # to move this out of here and make the dataModel take a pandas dataframe instead
        # of a filename. I don't think we want to complicate the logic of the dataModel
        # with specific file handling logic.
        data = pd.read_csv(filename)
        self._data = []
        for var in sorted(data.columns):
            self._data.append(DataItem(var, data[var]))

        self._time = data['time']
        self._t_min = min(data['time'])
        self._t_max = max(data['time'])

    @property
    def time(self):
        return self._time

    @property
    def t_min(self):
        return self._t_min

    @property
    def t_max(self):
        return self._t_max

    @property
    def time_range(self):
        return (self.t_min, self.t_max)

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
