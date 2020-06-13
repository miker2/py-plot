# This Python file uses the following encoding: utf-8
# from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QCheckBox


class filterBoxWidget(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)

        layout = QHBoxLayout(self)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText('Search for variables here...')

        self.search_button = QPushButton("Search")

        clear_button = QPushButton("clear")
        clear_button.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                   QtWidgets.QSizePolicy.Fixed)

        clear_button.clicked.connect(self.clear_text)


        # self.filter_box = QCheckBox("filter")
        # self.filter_box.stateChanged.connect(self.filter_list)

        layout.addWidget(self.search_box)
        layout.addWidget(self.search_button)
        layout.addWidget(clear_button)
        # layout.addWidget(self.filter_box)


        print(f"search button size: {self.search_button.size()}")
        print(f"search button min size: {self.search_button.minimumSizeHint()}")

    def clear_text(self):
        self.search_box.clear()

    def filter_list(self):
        print(f"Filter button state: {self.filter_box.isChecked()}")

    # Need to connect the "search" button to the list that will be passed
    # into this guy.
