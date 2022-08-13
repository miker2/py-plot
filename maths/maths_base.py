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
        self.button.clicked.connect(self.button_callback)

        self._msg_box = None

    @property
    def name(self):
        return self._name

    @abc.abstractmethod
    def button_callback(self, checked):
        pass

    @abc.abstractmethod
    def get_params(self):
        pass

    @abc.abstractmethod
    def do_math(self, data, dt):
        pass

    @abc.abstractmethod
    def default_var_name(self, vname):
        pass

    def create_message_box(self):
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

            if self.get_params():
                val = self.do_math(selected, vlist.model().avg_dt)

                vname, accept = QInputDialog.getText(self.parent(), "Enter variable name", "Variable name:",
                                                     text=self.default_var_name(selected.var_name))
                if accept:
                    data_item = DataItem(vname, val)
                    data_item._time = selected._time
                    self.parent().add_new_var(data_item, vlist)
                else:
                    print("User cancelled operation!")
            else:
                print("User cancelled operation!")

        return super().eventFilter(obj, event)
