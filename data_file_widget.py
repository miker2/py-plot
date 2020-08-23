# This Python file uses the following encoding: utf-8

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QTabWidget, QMessageBox, \
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QListWidget
from filter_box_widget import FilterBoxWidget
from var_list_widget import VarListWidget

import math
import numpy as np
import os
import pandas as pd

import simlog_decode

class DataFileWidget(QWidget):

    countChanged = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent=parent)

        self.controller = parent

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        # TODO(rose@): Enable this when the filename is embedded in the VarListWidget
        # self.tabs.setTabBarAutoHide(True)
        self.tabs.tabCloseRequested.connect(self.closeFile)
        layout.addWidget(self.tabs)

        self.filter_box = FilterBoxWidget(self.tabs)
        layout.addWidget(self.filter_box)

        self._fileloader_module = { '.bin' : BinaryFileLoader,  # pybullet
                                    '.csv' : GenericCSVLoader }

    @property
    def openCount(self):
        return self.tabs.count()

    def openFile(self, filepath):
        ext = os.path.splitext(filepath)[-1]
        loader = self._fileloader_module[ext](self, filepath)
        if not loader.success:
            # File didn't finish loading. Nothing else to do.
            return
        var_list = VarListWidget(self, loader)
        tab_name = filepath.split('/')[-1]
        # Create a new tab and add the varListWidget to it.
        self.tabs.addTab(var_list, tab_name)
        self.tabs.setCurrentWidget(var_list)
        self._update_range_slider()

        self.countChanged.emit()

    def closeFile(self, index):
        # Add function for closing the tab here.
        self.tabs.widget(index).close()
        self.tabs.removeTab(index)
        if self.tabs.count() > 0:
            self._update_range_slider()

        self.countChanged.emit()

    def getActiveDataFile(self):
        return self.tabs.currentWidget()

    def getDataFile(self, idx):
        return self.tabs.widget(idx)

    def getFirstSupervisorLog(self):
        for idx in range(self.tabs.count()):
            if self.getDataFile(idx).isSupervisorLog:
                return self.getDataFile(idx)
        return None

    def getTime(self, idx=0):
        if self.tabs.count() == 0:
            return None
        return self.getDataFile(idx).time

    def _update_range_slider(self):
        min_time = math.inf
        max_time = -math.inf

        for idx in range(self.tabs.count()):
            t_range = self.tabs.widget(idx).time_range
            # print(f"idx: {idx} - Time range: {t_range}")
            min_time = min(min_time, t_range[0])
            max_time = max(max_time, t_range[1])
        # print(f"min_time: {min_time}, max_time: {max_time}")

        # TODO(rose@) replace this with signal/slot logic
        self.controller.plot_manager.updateSliderLimits(min_time, max_time)


class FileLoader:
    def __init__(self, filename):

        self._filename = filename
        self._time = None
        self._df = None
        self._supervisor_log = False

    @property
    def success(self):
        # Only return success if neither the time nor the data is None
        return not self._time is None and not self._df is None

    @property
    def source(self):
        return self._filename

    @property
    def time(self):
        return self._time.to_numpy()

    @property
    def dataFrame(self):
        return self._df

    @property
    def isSupervisorLog(self):
        return self._supervisor_log


def timeSelectorDialog(caller, df):
    dialog = QDialog(caller)
    dialog.setWindowTitle("Time variable selector")
    form = QFormLayout(dialog)
    var_selector = QListWidget()
    var_selector.addItems(df.columns)
    var_selector.setCurrentRow(0)
    form.addRow("Select time variable:", var_selector)
    synthetic_time_tickbox = QCheckBox()
    synthetic_time_tickbox.setToolTip("Check this box if you want to create a synthetic time variable.")
    time_delta_input = QDoubleSpinBox()
    DECIMALS = 3
    STEP_SIZE = 1./ (10**DECIMALS)
    time_delta_input.setSingleStep(STEP_SIZE)
    time_delta_input.setMinimum(STEP_SIZE)
    time_delta_input.setMaximum(1.0)
    time_delta_input.setDecimals(DECIMALS)
    time_delta_input.setToolTip("Specify the sampling period of the time vector")
    hbox = QHBoxLayout()
    hbox.addWidget(synthetic_time_tickbox)
    hbox.addWidget(time_delta_input)
    hbox.addWidget(QLabel("sec/tick"))
    hbox.addStretch()
    form.addRow("Create time variable:", hbox)

    # Add some standard buttons (Cancel/Ok) at the bottom of the dialog
    button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                  Qt.Horizontal, dialog);
    form.addRow(button_box);
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)

    # Show the dialog as modal
    if dialog.exec() == QDialog.Accepted:
        if synthetic_time_tickbox.isChecked():
            # User wants a synthetic time variable, so let's create one:
            dt = time_delta_input.value()
            # We can safely call this variable "time" because if "time already existed,
            # this dialog wouldn't appear.
            df['time'] = dt * np.array(range(df.shape[0]), dtype=np.float64)
            time = df['time']
        else:
            item = var_selector.currentItem().text()
            time = df[item]
            if np.any(np.diff(time) < 0):
                QMessageBox.warning(caller, "Non-monotonic time variable",
                                    f"WARNING: Selected time variable '{item}' is not " +
                                    "monotonically increasing!")
        return True, time
    else:
        return False, None


'''
The ".bin" extension is quite generic, but for now assume this is a log file from pybullet.
'''
class BinaryFileLoader(FileLoader):
    def __init__(self, caller, filename):
        FileLoader.__init__(self, filename)

        self._df = simlog_decode.load_df(filename)
        self._time = self._df['timeStamp']

class GenericCSVLoader(FileLoader):
    def __init__(self, caller, filename):
        FileLoader.__init__(self, filename)

        try:
            self._df = pd.read_csv(filename)
            # Assume there is a 'time' column. If not, we'll ask the user
            self._time = self._df['time']
            # Make time start at zero.
            #self._time -= self._time[0]
        except KeyError:
            # Ask the user which column to use for time
            ok, time = timeSelectorDialog(caller, self._df)
            if ok:
                self._time = time
                # Make time start at zero.
                #self._time -= self._time[0]
            else:
                QMessageBox.critical(caller, "Unable to load file",
                                    "No time series selected. Unable to finish loading data.")
