# This Python file uses the following encoding: utf-8

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton
from PyQt5.QtWidgets import QCheckBox, QSizePolicy

class FilterBoxWidget(QWidget):
    def __init__(self, df_widget):
        QWidget.__init__(self)

        self.df_widget = df_widget

        layout = QVBoxLayout(self)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText('Search for variables here (eg. *FL*)')
        self.search_box.returnPressed.connect(self.searchList)
        layout.addWidget(self.search_box)

        hlayout = QHBoxLayout()

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.searchList)

        clear_button = QPushButton("clear")
        clear_button.setSizePolicy(QSizePolicy.Minimum,
                                   QSizePolicy.Fixed)

        clear_button.clicked.connect(self.clearText)

        self.filter_box = QCheckBox("RegExp")

        hlayout.addWidget(self.search_button)
        hlayout.addWidget(clear_button)
        hlayout.addWidget(self.filter_box)

        layout.addLayout(hlayout)

        # print(f"search button size: {self.search_button.size()}")
        # print(f"search button min size: {self.search_button.minimumSizeHint()}")

    def searchList(self):
        if self.df_widget.count() > 0 and self.search_box.text():
            #print(f"Active tab is {self.df_widget.currentWidget().filename}")

            list_view = self.df_widget.currentWidget()
            model = list_view.model()

            selected = list_view.currentIndex()
            if not selected.isValid():
                # start at the beginning of the list
                selected = model.index(0)
            flags = Qt.MatchWrap
            if self.filter_box.isChecked() :
                flags = flags | Qt.MatchRegExp
            else:
                flags = flags | Qt.MatchWildcard

            # Probably a bit more of an elegant way to do this, but because "match" might return
            # the "currentIndex" (if it matches) then we request 2 hits. If the first hit is the
            # current index, we skip it and take the 2nd one.
            matches = model.match(selected, Qt.DisplayRole,
                self.search_box.text(), hits=2, flags=flags)
            if matches:
                for m in matches:
                    if m != list_view.currentIndex():
                        self.df_widget.currentWidget().setCurrentIndex(m)
                        break

    def clearText(self):
        self.search_box.clear()
