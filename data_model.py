# -*- coding: utf-8 -*-

from PyQt5.QtCore import QAbstractListModel, QModelIndex, QVariant, Qt

import numpy as np
from logging_config import get_logger

logger = get_logger(__name__)


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

        # Add support for derived variables
        self._derived_data = {}  # Dictionary to store derived DataItems by name
        self._show_derived = False  # Flag to control visibility in VarListWidget

        self._time = data_loader.time
        self._avg_dt = np.mean(np.diff(self._time)).item()
        try:
            freq = int(round(1 / self._avg_dt))
        except ZeroDivisionError:
            freq = 0
        logger.info(f"Loaded {data_loader.source} which has a dt of {self._avg_dt:.6f} sec and a sampling rate of {freq} Hz")

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
        # First check derived variables
        if name in self._derived_data:
            return self._derived_data[name].data

        # Then check raw data
        try:
            return self._raw_data[name]
        except KeyError:
            logger.warning(f"Unknown key: {name}")
            return None

    def has_variable(self, name):
        """Check if a variable name already exists (raw or derived)"""
        return name in self._raw_data.columns or name in self._derived_data

    def add_derived_variable(self, name, data):
        """Add a derived variable to this model"""
        if self.has_variable(name):
            raise ValueError(f"Variable name '{name}' already exists in this data model")

        self._derived_data[name] = DataItem(name, data)

        # If we're showing derived variables, update the model
        if self._show_derived:
            self._refresh_data_list()

    def remove_derived_variable(self, name):
        """Remove a derived variable from this model"""
        if name in self._derived_data:
            del self._derived_data[name]
            if self._show_derived:
                self._refresh_data_list()

    def set_show_derived(self, show_derived):
        """Control whether derived variables are shown in the list"""
        if self._show_derived != show_derived:
            self._show_derived = show_derived
            self._refresh_data_list()

    def _refresh_data_list(self):
        """Refresh the _data list to include/exclude derived variables"""
        self.beginResetModel()

        # Start with raw data (sorted)
        self._data = []
        for var in sorted(self._raw_data.columns):
            self._data.append(DataItem(var, self._raw_data[var].to_numpy()))

        # Add derived variables at the end (sorted)
        if self._show_derived:
            for var in sorted(self._derived_data.keys()):
                self._data.append(self._derived_data[var])

        self.endResetModel()
