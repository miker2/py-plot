# This Python file uses the following encoding: utf-8
# from PyQt5 import QtCore
from PyQt5.QtWidgets import QListView, QMessageBox
from PyQt5.QtGui import QDrag, QKeyEvent
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData

import pickle
from data_model import DataModel


class VarListWidget(QListView):

    onClose = pyqtSignal()
    timeChanged = pyqtSignal()

    def __init__(self, parent, data_loader):
        QListView.__init__(self, parent)

        model = DataModel(data_loader)
        # self.clicked.connect(self.item_clicked)
        # self.pressed.connect(self.item_pressed)

        self.setModel(model)

        self.setDragEnabled(True)

        self.filename = data_loader.source

        self._idx = None

        self._supervisor_log = data_loader.is_supervisor_log

        parent.countChanged.connect(self._update_idx)

    @property
    def time(self):
        return self.model().time

    @property
    def time_offset(self):
        return self.model().time_offset

    @property
    def time_range(self):
        return self.model().time_range

    @property
    def idx(self):
        return self._idx

    @property
    def is_supervisor_log(self):
        return self._supervisor_log

    def set_time_offset(self, time_offset):
        self.model().set_time_offset(time_offset)
        self.timeChanged.emit()

    def close(self):
        self.onClose.emit()
        return super().close()

    def _update_idx(self):
        if self.parent().count() == 1:
            self._idx = None
        else:
            self._idx = self.parent().indexOf(self) + 1

    def item_clicked(self, index):
        QMessageBox.information(self, "ListWidget",
                                f"You clicked item {index.row()}: {index.data()}\n"
                                + f"{index.data(varListWidget._PLOT_DATA).data}")

    @staticmethod
    def item_pressed(index):
        print(f"You pressed {index.row()} : {index.data()}")

    def keyPressEvent(self, event):
        # We want to ignore the Up/Down arrow keys in the list here so that the "Zoom" functionality
        # works. All other events will be passed to the base class method.
        if type(event) == QKeyEvent and (event.key() == Qt.Key_Up or event.key() == Qt.Key_Down):
            event.ignore()
        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, e):
        self.startDrag(e)

    def startDrag(self, e):
        # This should work, but for some reason, does not always provide the right data.
        # index = self.indexAt(e.pos())
        # Instead, use the `currentIndex` method
        mouse_idx = self.indexAt(e.pos())
        index = self.currentIndex()
        if mouse_idx != index:
            print(f"Warning!!! index at mouse location {mouse_idx} doesn't match the " +
                  f"'currentIndex' {index}")
        if not index.isValid():
            return

        selected = self.model().data(index, Qt.UserRole)
        selected._time = self.model().time

        bstream = pickle.dumps(selected)
        mime_data = QMimeData()
        mime_data.setData("application/x-DataItem", bstream)

        drag = QDrag(self)
        drag.setMimeData(mime_data)

        result = drag.exec()
