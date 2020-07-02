# This Python file uses the following encoding: utf-8

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QMessageBox, QInputDialog
from filter_box_widget import FilterBoxWidget
from var_list_widget import VarListWidget

import math
import os
import pandas as pd

import simlog_decode

class DataFileWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent=parent)

        self.controller = parent

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        # self.tabs.setTabBarAutoHide(True)  # TODO(rose@): Enable this when the filename is embedded in the VarListWidget
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

    def closeFile(self, index):
        # Add function for closing the tab here.
        self.tabs.widget(index).close()
        self.tabs.removeTab(index)
        if self.tabs.count() > 0:
            self._update_range_slider()

    def getActiveDataFile(self):
        return self.tabs.currentWidget()

    def getDataFile(self, idx):
        return self.tabs.widget(idx)

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

    @property
    def success(self):
        # Only return success if neither the time nor the data is None
        return not self._time is None and not self._df is None

    @property
    def source(self):
        return self._filename

    @property
    def time(self):
        return self._time

    @property
    def dataFrame(self):
        return self._df

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
        except KeyError:
            # Ask the user which column to use for time
            item, ok = QInputDialog.getItem(caller, "Time variable selector", "Select time variable:", self._df.columns, editable=False)
            if ok:
                self._time = self._df[item]
            else:
                QMessageBox.critical(caller, "Unable to load file",
                                    "No time series selected. Unable to finish loading data.")
