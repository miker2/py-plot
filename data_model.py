# -*- coding: utf-8 -*-

from PyQt5.QtCore import QAbstractListModel, QModelIndex, QVariant, Qt

import numpy as np

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


class DataModel(QAbstractListModel):
    def __init__(self, data_loader, parent=None):
        QAbstractListModel.__init__(self, parent=parent)

        self._raw_data = data_loader.dataFrame
        self._data = []
        for var in sorted(self._raw_data.columns):
            self._data.append(DataItem(var, self._raw_data[var].to_numpy()))

        self._time = data_loader.time
        # The `.item()` is necessary because we want a python type (float), not a numpy.dtype
        self._t_min = min(self._time).item()
        self._t_max = max(self._time).item()
        self._avg_dt = np.mean(np.diff(self._time)).item()
        print(f"Loaded {data_loader.source} which has a dt of {self._avg_dt} sec and a sampling rate of {int(round(1/self._avg_dt))} Hz")

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

    @property
    def tick_max(self):
        return self._time.shape[0]

    @property
    def avg_dt(self):
        return self._avg_dt

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            item = self._data[index.row()]
            return QVariant(item.var_name)
        elif role == Qt.UserRole:
            # print(type(index))
            # print(type(index.row()))
            return self._data[index.row()]
        return QVariant()

    def getDataByName(self, name):
        data = None
        try:
            data = self._raw_data[name]
        except KeyError:
            print(f"Unknown key: {name}")
        return data
