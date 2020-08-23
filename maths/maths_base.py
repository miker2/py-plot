# Create a base for all custom math functions

from PyQt5.QtCore import Qt, QObject, QEvent
from PyQt5.QtWidgets import QPushButton, QMessageBox, QApplication, QInputDialog
from PyQt5.QtGui import QMouseEvent, QKeyEvent

import abc

from data_model import DataItem
from var_list_widget import VarListWidget

class MathSpecBase(QObject):
    __metaclass__ = abc.ABCMeta
    def __init__(self, parent, name):
        QObject.__init__(self, parent=parent)

        self._name = name

        self.button = QPushButton(name)
        self.button.clicked.connect(self.buttonCallback)

        self._msg_box = None

    @property
    def name(self):
        return self._name

    @abc.abstractmethod
    def buttonCallback(self, checked):
        pass

    @abc.abstractmethod
    def getParams(self):
        pass

    @abc.abstractmethod
    def doMath(self, data, dt):
        pass

    @abc.abstractmethod
    def defaultVarName(self, vname):
        pass

    def createMessageBox(self):
        self._msg_box = QMessageBox(self.parent())
        self._msg_box.setWindowTitle(self._name)
        self._msg_box.setText("Select a variable")
        self._msg_box.setWindowModality(Qt.NonModal)
        self._msg_box.show()
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        vlist = None
        if type(obj) is VarListWidget:
            vlist = obj
        elif type(obj.parent()) is VarListWidget:
            vlist = obj.parent()

        if type(event) == QKeyEvent and event.key() == Qt.Key_Escape:
            print("User cancelled operation!")
            QApplication.instance().removeEventFilter(self)

        if vlist is not None and event.type() == QEvent.MouseButtonPress:
            QApplication.instance().removeEventFilter(self)
            mouse_idx = vlist.indexAt(event.pos())
            selected = vlist.model().data(mouse_idx, Qt.UserRole)
            selected._time = vlist.model().time
            if self._msg_box:
                self._msg_box.close()
                self._msg_box = None

            if self.getParams():
                val = self.doMath(selected, vlist.model().avg_dt)

                vname, accept = QInputDialog.getText(self.parent(), "Enter variable name", "Variable name:",
                                                     text=self.defaultVarName(selected.var_name))
                if accept:
                   data_item = DataItem(vname, val)
                   data_item._time = selected._time
                   self.parent().addNewVar(data_item, vlist)
                else:
                    print("User cancelled operation!")
            else:
                print("User cancelled operation!")

        return super().eventFilter(obj, event)
