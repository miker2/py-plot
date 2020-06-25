# This Python file uses the following encoding: utf-8
# from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QTabWidget
from filterBoxWidget import filterBoxWidget
from varListWidget import varListWidget

import math

class dataFileWidget(QtWidgets.QWidget):
    def __init__(self, parent):
        QtWidgets.QWidget.__init__(self)
        self.parent = parent

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.closeFile)
        layout.addWidget(self.tabs)

        self.filter_box = filterBoxWidget(self.tabs)
        layout.addWidget(self.filter_box)

    def openFile(self, filepath):
        var_list = varListWidget(self, filepath)
        tab_name = filepath.split('/')[-1]
        # Create a new tab and add the varListWidget to it.
        self.tabs.addTab(var_list, tab_name)
        self.tabs.setCurrentWidget(var_list)
        self._update_range_slider()

    def closeFile(self, index):
        # Add function for closing the tab here.
        self.tabs.widget(index).deleteLater()
        self.tabs.removeTab(index)
        if self.tabs.count() > 0:
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

        # TODO(rose@) replace this with signal/slot logic
        self.parent.plot_manager.updateSliderLimits(min_time, max_time)
