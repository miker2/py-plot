# -*- coding: utf-8 -*-


from PyQt5.QtCore import QAbstractListModel, QModelIndex, QVariant, Qt

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


class DataModel(QAbstractListModel):
    def __init__(self, filename, parent=None):
        super().__init__(parent)

        # TODO(rose@): If we want to be able to support multiple data formats, we need
        # to move this out of here and make the dataModel take a pandas dataframe instead
        # of a filename. I don't think we want to complicate the logic of the dataModel
        # with specific file handling logic.
        self._raw_data = pd.read_csv(filename)
        self._data = []
        for var in sorted(self._raw_data.columns):
            self._data.append(DataItem(var, self._raw_data[var]))

        self._time = self._raw_data['time']
        self._t_min = min(self._time)
        self._t_max = max(self._time)

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
