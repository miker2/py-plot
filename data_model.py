# -*- coding: utf-8 -*-

from PyQt5.QtCore import QAbstractListModel, QModelIndex, QVariant, Qt

import numpy as np


class DataItem(object):
    """
        Data structure for storing data items in the list widget
    """

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

        self._raw_data = data_loader.data_frame
        self._data = []
        for var in sorted(self._raw_data.columns):
            self._data.append(DataItem(var, self._raw_data[var].to_numpy()))

        self._time = data_loader.time
        self._avg_dt = np.mean(np.diff(self._time)).item()
        try:
            freq = int(round(1 / self._avg_dt))
        except ZeroDivisionError:
            freq = 0
        print(f"Loaded {data_loader.source} which has a dt of {self._avg_dt} sec and a sampling rate of {freq} Hz")

        self._time_offset = 0

    @property
    def time(self):
        return self._time + self._time_offset

    @property
    def t_min(self):
        # The `.item()` is necessary because we want a python type (float), not a numpy.dtype
        return min(self.time).item()

    @property
    def t_max(self):
        # The `.item()` is necessary because we want a python type (float), not a numpy.dtype
        return max(self.time).item()

    @property
    def time_offset(self):
        return self._time_offset

    @property
    def time_range(self):
        return self.t_min, self.t_max

    @property
    def tick_max(self):
        return self._time.shape[0] - 1

    @property
    def avg_dt(self):
        return self._avg_dt

    def set_time_offset(self, time_offset):
        self._time_offset = time_offset

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

    def has_key(self, name):
        return name in self._raw_data.index

    def get_data_by_name(self, name):
        data = None
        try:
            data = self._raw_data[name]
        except KeyError:
            print(f"Unknown key: {name}")
        return data
