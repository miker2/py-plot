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
from maths.running_window import RunningWindowSpec, WindowTypes # Added WindowTypes import
from maths.running_minmax import RunningMinMaxSpec, MinMaxType # Added MinMaxType import

from data_model import DataItem
from docked_widget import DockedWidget
from plot_spec import PlotSpec # Added import

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
    plot_spec: PlotSpec | None = None # Added plot_spec


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
        setattr(self.var_out, 'startDrag', self.start_drag)
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
        selected = pickle.loads(bstream) # selected is a DataItem
        var_name = selected.var_name

        # Determine file_source_identifier
        file_source_identifier = "unknown_file"
        if hasattr(e.source(), 'filename') and e.source().filename:
            file_source_identifier = e.source().filename
        elif hasattr(e.source(), 'idx') and e.source().idx is not None:
            file_source_identifier = str(e.source().idx)

        # Create PlotSpec for the incoming variable
        ps = PlotSpec(name=var_name,
                              source_type="file",
                              original_name=var_name,
                              file_source_identifier=file_source_identifier)

        vidx = f"x{self.var_in.count()}"
        list_name = f"{vidx}: {var_name}"
        new_item = QListWidgetItem(list_name)
        new_item.setData(Qt.ToolTipRole, vidx)
        var_info = VarInfo(var_name, selected.data, e.source(), plot_spec=ps) # Store PlotSpec
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
        data_item._time = self._vars[e_vars[0]].source.time # This time is of the source model (DataModel)

        # Create PlotSpec for the newly evaluated variable
        input_plot_specs = []
        for v_key in e_vars: # e_vars are like 'x0', 'x1'
            var_info = self._vars[v_key] # This is a VarInfo object
            if var_info.plot_spec:
                input_plot_specs.append(var_info.plot_spec)
            else:
                # Fallback for missing input PlotSpec
                print(f"Warning: Input variable {var_info.var_name} (key: {v_key}) is missing PlotSpec. Creating a fallback.")
                # Try to determine file_source_identifier for fallback
                fallback_file_id = "unknown_source"
                if hasattr(var_info.source, 'filename') and var_info.source.filename:
                    fallback_file_id = var_info.source.filename
                elif hasattr(var_info.source, 'idx') and var_info.source.idx is not None:
                    fallback_file_id = str(var_info.source.idx)

                fallback_ps = PlotSpec(
                    name=var_info.var_name,
                    source_type="file_fallback", # Indicates it was likely a file var but spec was missing
                    original_name=var_info.var_name,
                    file_source_identifier=fallback_file_id
                )
                input_plot_specs.append(fallback_ps)
        
        expression_str = self.math_entry.text()
        output_plot_spec = PlotSpec(
            name=vname, # This is the user-defined name for the new variable
            source_type="math_expr", # Changed source_type
            expression=expression_str, 
            input_plot_specs=input_plot_specs,
            operation_details={'expression': expression_str} # Added operation_details
        )
        # Assign the created PlotSpec to the DataItem that will be stored
        data_item.plot_spec = output_plot_spec

        self.add_new_var(data_item, self._vars[e_vars[0]].source, output_plot_spec)

    def add_new_var(self, data_item: DataItem, source, plot_spec: PlotSpec): # plot_spec is now required
        list_name = f"y{self.var_out.count()}"
        new_item = QListWidgetItem(f"{list_name}: {data_item.var_name}")
        new_item.setData(Qt.UserRole, data_item)
        new_item.setData(Qt.ToolTipRole, list_name)
        self.var_out.addItem(new_item)
        # User can use output vars as inputs also.
        # Store the provided plot_spec in VarInfo
        self._vars[list_name] = VarInfo(data_item.var_name, data_item.data, source, plot_spec=plot_spec)

        # TODO(rose@) - Remove this variable from self._vars also.
        remove_row = lambda: self.var_out.takeItem(self.var_out.row(new_item))
        source.onClose.connect(remove_row)

    def start_drag(self, e):
        index = self.var_out.currentRow()

        selected = self.var_out.item(index).data(Qt.UserRole) # This is a DataItem
        vid = self.var_out.item(index).data(Qt.ToolTipRole)

        # Ensure the DataItem (selected) has its PlotSpec correctly set before pickling.
        # The plot_spec should have been set on the DataItem either when it was created
        # (if it's a result of evaluate_math) or when it was dropped (if it came from var_in).
        # The VarInfo's plot_spec is the authoritative one for var_out items.
        if vid in self._vars and self._vars[vid].plot_spec:
            selected.plot_spec = self._vars[vid].plot_spec
        elif selected.plot_spec is None: # Fallback if DataItem itself doesn't have one
            # This case should ideally not be hit if logic is correct elsewhere.
            # It implies a var_out item whose DataItem didn't get a PlotSpec.
            print(f"Warning: PlotSpec missing for {selected.var_name} in start_drag. Creating a basic one.")
            selected.plot_spec = PlotSpec(name=selected.var_name, source_type="unknown_derived_in_drag")

        bstream = pickle.dumps(selected)

        mime_data = QMimeData()
        mime_data.setData("application/x-DataItem", bstream)

        # vid = self.var_out.item(index).data(Qt.ToolTipRole) # Already got vid
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

    def get_data_by_name(self, name) -> DataItem | None:
        # TODO(rose@): This is a bit of a hack in order to make drag/drop plotting work.
        # If we decide to keep this, the model should be formalized.
        # This method should return a DataItem, similar to DataModel.get_data_by_name

        # self.parent is MathsWidget, self.parent._vars stores VarInfo objects
        for var_info in self.parent._vars.values():
            if var_info.var_name == name:
                # Construct a DataItem on the fly
                # VarInfo contains: var_name, data, source (VarListWidget), plot_spec
                data_item = DataItem(
                    var_name=var_info.var_name,
                    data=var_info.data,
                    plot_spec=var_info.plot_spec
                )
                # Try to set the time attribute for the DataItem
                # The source in VarInfo is typically the VarListWidget from which the data originated
                # or was derived in the context of MathsWidget.
                if hasattr(var_info.source, 'time'):
                    data_item._time = var_info.source.time
                elif hasattr(var_info.source, 'model') and hasattr(var_info.source.model(), 'time'):
                    # If source is a widget, its model might have time
                    data_item._time = var_info.source.model().time
                else:
                    # Fallback or if time is not critical for this DataItem's usage via ThinModelMock
                    # print(f"Warning: Time data not found for {var_info.var_name} in ThinModelMock")
                    pass # _time will remain None
                return data_item
        
        print(f"Unknown key: {name} in ThinModelMock")
        return None

    def execute_operation_from_spec(self, output_spec: PlotSpec, input_data_items: list[DataItem]) -> DataItem | None:
        """
        Executes a mathematical operation defined by output_spec using input_data_items.
        This is used for reproducing signals when loading plots.
        """
        if not input_data_items:
            print(f"Error: No input data items provided for operation: {output_spec.name}")
            return None

        result_array = None
        op_details = output_spec.operation_details if output_spec.operation_details else {}

        # Common setup for DataItem
        new_data_item_name = output_spec.name
        # Time array should be consistent with inputs; use the first input's time.
        # This assumes all inputs to an operation share a compatible time basis.
        time_array = input_data_items[0].time
        # avg_dt might be needed for some operations
        avg_dt = np.mean(np.diff(time_array)).item() if time_array is not None and len(time_array) > 1 else 0.0


        if output_spec.source_type == "math_expr":
            expression_str = output_spec.expression
            if not expression_str:
                print(f"Error: No expression string found in PlotSpec for: {output_spec.name}")
                return None

            e_data = {}
            # The expression uses 'x0', 'x1', ... which correspond to input_data_items
            # Their PlotSpecs are output_spec.input_plot_specs
            # The actual variable names used in the expression ('x0', 'x1') are implicitly mapped by order.
            for i, item in enumerate(input_data_items):
                e_data[f'x{i}'] = item.data
            
            try:
                expr_parsed = self.parser.parse(expression_str)
                result_array = expr_parsed.evaluate(e_data)
            except Exception as e:
                print(f"Error evaluating expression '{expression_str}' for '{output_spec.name}': {e}")
                return None

        # Implementation for specific math operations
        elif output_spec.source_type == "math_filter":
            from scipy import signal as scipy_signal # Avoid conflict with PyQt signal
            input_data = input_data_items[0].data
            if not all(k in op_details for k in ['order', 'type', 'cutoff', 'filtfilt']):
                print(f"Error: Missing parameters in operation_details for filter: {output_spec.name}")
                return None
            fs = 1 / avg_dt if avg_dt > 0 else 1.0 # Avoid division by zero
            Wn = op_details['cutoff'] / (0.5 * fs)
            b, a = scipy_signal.butter(op_details['order'], Wn, btype=op_details['type'])
            if op_details['filtfilt']:
                result_array = scipy_signal.filtfilt(b, a, input_data, method='gust')
            else:
                result_array = scipy_signal.lfilter(b, a, input_data)
            
        elif output_spec.source_type == "math_diff":
            input_data = input_data_items[0].data
            if time_array is not None and len(time_array) == len(input_data) and len(time_array) > 1:
                result_array = np.concatenate(([0], np.diff(input_data) / np.diff(time_array)))
            else:
                print(f"Error: Invalid time_array for differentiation: {output_spec.name}")
                return None

        elif output_spec.source_type == "math_integrate":
            input_data = input_data_items[0].data
            if time_array is not None and len(time_array) == len(input_data) and len(time_array) > 1:
                result_array = np.cumsum(input_data * np.concatenate(([0], np.diff(time_array))))
            else:
                print(f"Error: Invalid time_array for integration: {output_spec.name}")
                return None

        elif output_spec.source_type == "math_running_minmax":
            from scipy.ndimage.filters import maximum_filter1d, minimum_filter1d
            input_data = input_data_items[0].data
            if not all(k in op_details for k in ['type', 'window_sz', 'is_ticks']):
                print(f"Error: Missing parameters for running_minmax: {output_spec.name}")
                return None
            
            window_sz_ticks = op_details['window_sz']
            if not op_details['is_ticks']: # Convert time window to ticks
                if avg_dt <= 0:
                    print(f"Error: avg_dt is <=0, cannot convert time window to ticks for {output_spec.name}")
                    return None
                window_sz_ticks = round(op_details['window_sz'] / avg_dt)
            window_sz_ticks = int(max(1, window_sz_ticks)) # Ensure positive integer

            func = minimum_filter1d if op_details['type'] == MinMaxType.MIN.name.lower() else maximum_filter1d # Requires MinMaxType enum or string comparison
            offset = math.ceil(0.5 * window_sz_ticks) - 1
            result_array = func(input_data, size=window_sz_ticks, mode='nearest', origin=int(offset))


        elif output_spec.source_type == "math_running_window":
            from scipy import signal as scipy_signal # Avoid conflict
            input_data = input_data_items[0].data
            if not all(k in op_details for k in ['type', 'window_sz', 'is_ticks']):
                print(f"Error: Missing parameters for running_window: {output_spec.name}")
                return None

            window_sz_ticks = op_details['window_sz']
            if not op_details['is_ticks']:
                if avg_dt <= 0:
                    print(f"Error: avg_dt is <=0, cannot convert time window to ticks for {output_spec.name}")
                    return None
                window_sz_ticks = round(op_details['window_sz'] / avg_dt)
            window_sz_ticks = int(max(1, window_sz_ticks))

            if op_details['type'] == WindowTypes.MEAN.name.lower(): # Requires WindowTypes enum or string comparison
                result_array = np.convolve(input_data, np.ones(window_sz_ticks) / float(window_sz_ticks), mode='same')
            else: # MEDIAN
                if window_sz_ticks % 2 == 0: window_sz_ticks += 1 # Median filter window must be odd
                result_array = scipy_signal.medfilt(input_data, kernel_size=window_sz_ticks)
            
        else:
            print(f"Error: Unknown math source_type '{output_spec.source_type}' for '{output_spec.name}'")
            return None

        if result_array is None:
            print(f"Error: Math operation did not produce a result_array for '{output_spec.name}'")
            return None
            
        # Create the DataItem
        new_data_item = DataItem(name=new_data_item_name, data=result_array, plot_spec=output_spec)
        new_data_item._time = time_array
        
        # Add to MathsWidget's internal tracking (_vars and var_out list)
        # The 'source' for VarInfo when reproducing is self (MathsWidget), as it's the reproducer.
        self.add_new_var(new_data_item, self, output_spec)
        
        return new_data_item
