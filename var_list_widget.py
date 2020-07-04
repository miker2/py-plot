# This Python file uses the following encoding: utf-8
# from PyQt5 import QtCore
from PyQt5.QtWidgets import QListView, QMessageBox
from PyQt5.QtGui import QDrag, QKeyEvent
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData

import pickle
from data_model import DataModel


class VarListWidget(QListView):

    onClose = pyqtSignal()

    def __init__(self, parent, data_loader):
        QListView.__init__(self, parent)

        model = DataModel(data_loader)
        # self.clicked.connect(self.itemClicked)
        # self.pressed.connect(self.itemPressed)

        self.setModel(model)

        self.setDragEnabled(True)

        self.filename = data_loader.source

        self._idx = None

        parent.countChanged.connect(self._updateIdx)

    @property
    def time_range(self):
        return self.model().time_range

    @property
    def idx(self):
        return self._idx

    def close(self):
        self.onClose.emit()
        return super().close()

    def _updateIdx(self):
        if self.parent().count() == 1:
            self._idx = None
        else:
            self._idx = self.parent().indexOf(self) + 1

    def itemClicked(self, index):
        QMessageBox.information(self, "ListWidget",
                                f"You clicked item {index.row()}: {index.data()}\n"
                                + f"{index.data(varListWidget._PLOT_DATA).data}")
    def itemPressed(self, index):
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
        mimeData = QMimeData()
        mimeData.setData("application/x-DataItem", bstream)

        drag = QDrag(self)
        drag.setMimeData(mimeData)

        result = drag.exec()
