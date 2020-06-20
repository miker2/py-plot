# This Python file uses the following encoding: utf-8
# from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QTabWidget
from filterBoxWidget import filterBoxWidget
from varListWidget import varListWidget

import math

# TODO(rose@)(2020/05/09) On file load, the end time of the log needs to be
# collected. The maximum of the end times of all files loaded need to be used
# to set the max value of the range slider so that it accurately reflects
# the time range available.

class dataFileWidget(QtWidgets.QWidget):
    def __init__(self, parent):
        QtWidgets.QWidget.__init__(self)
        self.parent = parent

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_file)
        layout.addWidget(self.tabs)

        self.filter_box = filterBoxWidget()
        layout.addWidget(self.filter_box)

    def open_file(self, filepath):
        var_list = varListWidget(self, filepath)
        tab_name = filepath.split('/')[-1]
        # Create a new tab and add the varListWidget to it.
        self.tabs.addTab(var_list, tab_name)
        self.tabs.setCurrentWidget(var_list)
        self._update_range_slider()

    def close_file(self, index):
        # Add function for closing the tab here.
        self.tabs.removeTab(index)
        self._update_range_slider()

    def _update_range_slider(self):
        min_time = math.inf
        max_time = -math.inf

        for idx in range(self.tabs.count()):
            t_range = self.tabs.widget(idx).time_range
            # print(f"idx: {idx} - Time range: {t_range}")
            min_time = min(min_time, t_range[0])
            max_time = max(max_time, t_range[1])
        # print(f"min_time: {min_time}, max_time: {max_time}")
        self.parent.update_slider_limits(min_time, max_time)
