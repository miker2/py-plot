# -*- coding: utf-8 -*-

# from PyQt5 import QtGui
from PyQt5.QtGui import QDrag
from PyQt5.QtCore import QAbstractListModel, QModelIndex, QVariant, Qt, pyqtSignal, QMimeData
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QListView

import numpy as np
import pandas as pd
import pickle
import random


class DataItem(object):
    """
        Data structure for storing data items in the list widget
    """

    def __init__(self, var_name, data):
        self._var_name = var_name
        self._data = data
        self._time = None
        self.file = None

    @property
    def var_name(self):
        return self._var_name

    @property
    def data(self):
        return self._data

    @property
    def time(self):
        return self._time


class DataModel(QAbstractListModel):
    def __init__(self, filename, parent=None):
        super().__init__(parent)

        # Produce random data:
        data = pd.read_csv(filename)
        self._data = []
        for var in sorted(data.columns):
            self._data.append(DataItem(var, data[var]))
        self._time = data['time']

    @property
    def time(self):
        return self._time

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            item = self._data[index.row()]
            return QVariant(item.var_name)
        elif role == Qt.UserRole:
            return self._data[index.row()]
        return QVariant()


class DataFileWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self)
        self.parent = parent

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_file)
        layout.addWidget(self.tabs)

    def open_file(self, filename):
        var_list = VarListWidget(self, filename)
        # Create a new tab and add the varListWidget to it.
        self.tabs.addTab(var_list, filename)
        self.tabs.setCurrentWidget(var_list)

    def close_file(self, index):
        # Add function for closing the tab here.
        self.tabs.widget(index).close()
        self.tabs.removeTab(index)


class VarListWidget(QListView):
    onClose = pyqtSignal()

    def __init__(self, parent, filename):
        super().__init__(parent)

        model = DataModel(filename)

        self.setModel(model)

        self.setDragEnabled(True)

        self.filename = filename

    def close(self):
        print(f"Emitting 'onClose' signal for {self.filename}")
        self.onClose.emit()

    def mouseMoveEvent(self, e):
        self.startDrag(e)

    def startDrag(self, e):
        index = self.indexAt(e.pos())
        if not index.isValid():
            return

        selected = self.model().data(index, Qt.UserRole)
        selected._time = self.model().time
        # selected.file = self;

        bstream = pickle.dumps(selected)
        mime_data = QMimeData()
        mime_data.setData("application/x-DataItem", bstream)

        drag = QDrag(self)
        drag.setMimeData(mime_data)

        result = drag.exec()
