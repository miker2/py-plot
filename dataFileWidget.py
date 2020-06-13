# This Python file uses the following encoding: utf-8
# from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QTabWidget
from filterBoxWidget import filterBoxWidget
from varListWidget import varListWidget

# TODO(rose@)(2020/05/09) On file load, the end time of the log needs to be
# collected. The maximum of the end times of all files loaded need to be used
# to set the max value of the range slider so that it accurately reflects
# the time range available.

class dataFileWidget(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)

        self.has_file = False

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_file)
        layout.addWidget(self.tabs)

        # dummy_widget = QtWidgets.QWidget()

        # self.tabs.addTab(dummy_widget, "")

        self.filter_box = filterBoxWidget()
        layout.addWidget(self.filter_box)

    def open_file(self, filepath):
        var_list = varListWidget(self, filepath)
        tab_name = filepath.split('/')[-1]
        # Create a new tab and add the varListWidget to it.
        self.tabs.addTab(var_list, tab_name)
        self.tabs.setCurrentWidget(var_list)

    def close_file(self, index):
        # Add function for closing the tab here.
        self.tabs.removeTab(index)
