# -*- coding: utf-8 -*-
from PyQt5.QtCore import Qt, QVariant, QMimeData, QObject, QEvent
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, \
    QListWidget, QListWidgetItem, QLineEdit, QPushButton, QInputDialog
from PyQt5.QtGui import QDrag, QMouseEvent

from PyQt5.QtWidgets import QMessageBox, QApplication

from dataclasses import dataclass
import math
import numpy as np
import pickle
import time

from var_list_widget import VarListWidget

from maths.filter import FilterSpec
from maths.diff_int import DifferentiateSpec, IntegrateSpec
from maths.running_window import RunningWindowSpec
from maths.running_minmax import RunningMinMaxSpec

from data_model import DataItem
from docked_widget import DockedWidget

try:
    from py_expression_eval import Parser
except ModuleNotFoundError:
    import subprocess
    import sys

    subprocess.check_call([sys.executable, "-m", "pip", "install", "py_expression_eval"])
    from py_expression_eval import Parser


class DockedMathsWidget(DockedWidget):

    def __init__(self, parent=None):
        DockedWidget.__init__(self, "Maths", parent=parent)

        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)

        self.setWidget(MathsWidget(parent=self))


class ThinModelMock:
    # TODO(rose@): Once the plotting stuff is unified, this can be removed, but for now it's
    # required for plotting math-derived variables.
    def __init__(self, parent):
        self.parent = parent

    def get_data_by_name(self, name):
        return self.parent.get_data_by_name(name)


# Convenience method for storing info about math-derived variables. This could be incorporated
# into an actual data model.
@dataclass
class VarInfo:
    var_name: str
    data: np.ndarray
    source: int


class MathsWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.setMinimumWidth(320)
        self.resize(640, 480)

        main_layout = QHBoxLayout()

        math_layout = QVBoxLayout()
        button_layout = self.create_buttons()

        main_layout.addLayout(math_layout)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # This probably needs to be a model so we can store additional info here. At
        # the very least, we need to know which list it came from so we can get the
        # variables eventually.
        self.var_in = QListWidget()
        self.var_in.setAcceptDrops(True)
        self.setAcceptDrops(True)

        self.var_out = QListWidget()
        self.var_out.setDragEnabled(True)
        setattr(self.var_out, 'start_drag', self.start_drag)
        io_layout = QHBoxLayout()
        io_layout.addWidget(self.var_in)
        io_layout.addWidget(self.var_out)

        entry_layout = QHBoxLayout()
        self.math_entry = QLineEdit()
        self.math_entry.setPlaceholderText("enter math here... e.g 'x0 + 3 * x1'")
        self.math_entry.returnPressed.connect(self.evaluate_math)
        entry_layout.addWidget(self.math_entry)

        evaluate_button = QPushButton("enter")
        evaluate_button.clicked.connect(self.evaluate_math)

        entry_layout.addWidget(evaluate_button)

        math_layout.addLayout(io_layout)
        math_layout.addLayout(entry_layout)

        # We'll be lazy for now and store data in this dictionary. We'll fix this later.
        self._vars = {}

        self._silly_model = ThinModelMock(self)

        self.parser = Parser()
        # We need to overwrite some of the functionality so that it works for our numpy arrays:
        # TODO(rose@): Make this more complex so we can use scalars and arrays interchangeably
        self.parser.ops1['sin'] = np.sin
        self.parser.ops1['cos'] = np.cos
        self.parser.ops1['tan'] = np.tan
        self.parser.ops1['asin'] = np.arcsin
        self.parser.ops1['acos'] = np.arccos
        self.parser.ops1['atan'] = np.arctan
        self.parser.ops1['sqrt'] = np.sqrt
        self.parser.ops1['ceil'] = np.ceil
        self.parser.ops1['floor'] = np.floor
        self.parser.ops1['round'] = np.round
        # Here is where we would add additional functions to the list. Probably the best thing
        # would be if we had some object that would provide the additional functions so they are
        # accessible to plotlists as well.

        self._current_cb = None

    def sizeHint(self):
        return self.parentWidget().sizeHint()

    def create_buttons(self):

        math_funcs = (("differentiate", DifferentiateSpec(self)),
                      ("integrate", IntegrateSpec(self)),
                      ("filter", FilterSpec(self)),
                      ("running min/max", RunningMinMaxSpec(self)),
                      ("running mean/median", RunningWindowSpec(self)))

        n_rows = math.ceil(math.sqrt(len(math_funcs)))
        n_cols = math.ceil(len(math_funcs) / n_rows)

        button_layout = QGridLayout()

        for i in range(len(math_funcs)):
            r, c = math.floor(i / n_cols), i % n_cols
            mf, cb = math_funcs[i]
            math_button = QPushButton(mf)
            math_button.clicked.connect(cb.button_callback)
            button_layout.addWidget(math_button, r, c)
        button_layout.setRowStretch(0, 600)
        return button_layout

    def eventFilter(self, obj, event):
        vlist = None
        if type(obj) is VarListWidget:
            vlist = obj
        elif type(obj.parent()) is VarListWidget:
            vlist = obj.parent()

        if vlist is not None and event.type() == QEvent.MouseButtonPress:
            QApplication.instance().removeEventFilter(self)
            mouse_idx = vlist.indexAt(event.pos())
            selected = vlist.model().data(mouse_idx, Qt.UserRole)
            selected._time = vlist.model().time
            self.msgBox.close()

        return super().eventFilter(obj, event)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("application/x-DataItem"):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        data = e.mimeData()
        bstream = data.retrieveData("application/x-DataItem", QVariant.ByteArray)
        selected = pickle.loads(bstream)
        var_name = selected.var_name

        vidx = f"x{self.var_in.count()}"
        list_name = f"{vidx}: {var_name}"
        new_item = QListWidgetItem(list_name)
        new_item.setData(Qt.ToolTipRole, vidx)
        # self._vars[f"x{self.var_in.count()}"] = e.source().model().get_data_by_name(var_name)
        var_info = VarInfo(var_name, selected.data, e.source())
        self._vars[vidx] = var_info
        # Add this to the list of input variables.
        self.var_in.addItem(new_item)

        # TODO(rose@) - Remove this variable from self._vars also.
        remove_row = lambda: self.var_in.takeItem(self.var_in.row(new_item))
        e.source().onClose.connect(remove_row)
        e.accept()

    def evaluate_math(self):
        expr = self.parser.parse(self.math_entry.text())
        e_vars = expr.variables()

        # Ensure all variables in the expression are available in the variable list.
        vars_from_list = set(self._vars.keys()).intersection(e_vars)
        has_all_vars = vars_from_list == set(e_vars)

        if not has_all_vars:
            print("Expression uses unknown variables: " +
                  f"{set(e_vars).difference(vars_from_list)}")
            return

        # Ensure that all variables in the expression are also from the same file:
        f_idx = [self._vars[v].source.idx for v in e_vars]
        if len(set(f_idx)) > 1:
            print("All variables in the expression must be from the same file.")
            print(f"Variables are from the following files: {set(f_idx)}.")
            return

        try:
            # Collect the required variables:
            e_data = {v: self._vars[v].data for v in e_vars}
            val = expr.evaluate(e_data)
        except Exception as ex:
            print(f"Some sort of error! -- {ex}")
            return

        vname = self.math_entry.text()
        for v in e_vars:
            vname = vname.replace(v, self._vars[v].var_name)
        vname = vname.replace(' ', '')
        vname, accept = QInputDialog.getText(self, "Enter variable name", "Variable name:",
                                             text=vname)
        if not accept:
            return

        # Clear the math entry box when the formula is evaluated successfully.
        self.math_entry.clear()

        data_item = DataItem(vname, val)
        # NOTE(rose@): If all of the variables are from the same file, then picking the time for
        #              the first file is sufficient.
        data_item._time = self._vars[e_vars[0]].source.time

        self.add_new_var(data_item, self._vars[e_vars[0]].source)

    def add_new_var(self, data_item, source):
        list_name = f"y{self.var_out.count()}"
        new_item = QListWidgetItem(f"{list_name}: {data_item.var_name}")
        new_item.setData(Qt.UserRole, data_item)
        new_item.setData(Qt.ToolTipRole, list_name)
        self.var_out.addItem(new_item)
        # User can use output vars as inputs also.
        self._vars[list_name] = VarInfo(data_item.var_name, data_item.data, source)

        # TODO(rose@) - Remove this variable from self._vars also.
        remove_row = lambda: self.var_out.takeItem(self.var_out.row(new_item))
        source.onClose.connect(remove_row)

    def start_drag(self, e):
        index = self.var_out.currentRow()

        selected = self.var_out.item(index).data(Qt.UserRole)
        bstream = pickle.dumps(selected)

        mime_data = QMimeData()
        mime_data.setData("application/x-DataItem", bstream)

        vid = self.var_out.item(index).data(Qt.ToolTipRole)
        # NOTE(rose@) These feel like dirty little hacks, but they do work (for now).
        setattr(self, 'onClose', self._vars[vid].source.onClose)
        setattr(self, 'time', self._vars[vid].source.time)
        setattr(self, 'idx', self._vars[vid].source.idx)
        drag = QDrag(self)
        drag.setMimeData(mime_data)

        result = drag.exec()

    ######################### THE CODE BELOW THIS LINE SHOULDN'T EXIST!!! ####################
    def model(self):
        # TODO(rose@): Fix this hack! For now, redirect the model to our mocked model.
        return self._silly_model

    def get_data_by_name(self, name):
        # TODO(rose@): This is a bit of a hack in order to make drag/drop plotting work.
        # If we decide to keep this, the model should be formalized.
        data = None
        # Make a lookup of the variable names... oi vey
        v_lookup = {v.var_name: k for k, v in self._vars.items()}
        try:
            vid = v_lookup[name]
            data = self._vars[vid].data
        except KeyError:
            print(f"Unknown key: {name}")
        return data
