# -*- coding: utf-8 -*-

from PyQt5.QtCore import QAbstractListModel, QModelIndex, QVariant, Qt

import numpy as np

from plot_spec import PlotSpec # Added import


class DataItem(object):
    """
        Data structure for storing data items in the list widget
    """

    def __init__(self, var_name, data, plot_spec: PlotSpec | None = None): # Added plot_spec
        self._var_name = var_name
        self._data = data
        self._plot_spec = plot_spec # Added plot_spec
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

    @property
    def plot_spec(self): # Added plot_spec property
        return self._plot_spec

    @plot_spec.setter
    def plot_spec(self, value: PlotSpec | None): # Added plot_spec setter
        self._plot_spec = value

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

    def get_data_by_name(self, name) -> DataItem | None:
        # Iterates self._data (which is list[DataItem]) and finds the DataItem with the matching var_name.
        for item in self._data:
            if item.var_name == name:
                # Ensure the PlotSpec is created if it's missing for a file-loaded item
                if item.plot_spec is None:
                    # Attempt to get a file_source_identifier
                    # This DataModel instance itself doesn't store the filename directly in a way
                    # that's easily accessible per item here. We'll assume a generic one or improve later if needed.
                    # For now, we know it's from this model, which is usually file-based.
                    file_id = "unknown_data_model_source"
                    # A better approach would be if data_loader.source (filename) was stored in DataModel
                    # and accessible here, or if DataItem was initialized with it.
                    # Let's assume self.filename could exist if DataModel was enhanced.
                    # if hasattr(self, 'filename') and self.filename:
                    #     file_id = self.filename
                    
                    item.plot_spec = PlotSpec(
                        name=item.var_name,
                        source_type="file",
                        original_name=item.var_name,
                        file_source_identifier=file_id # Placeholder, actual file ID needs better handling
                    )
                return item
        print(f"Unknown key: {name} in DataModel")
        return None
