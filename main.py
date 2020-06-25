# This Python file uses the following encoding: utf-8
import sys
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QSplitter, QWidget
from PyQt5.QtCore import QSize
from dataFileWidget import dataFileWidget
from subPlotWidget import subPlotWidget
from QRangeSlider import QRangeSlider
from QxtSpanSlider import QxtSpanSlider
from plotManager import plotManager

import pyqtgraph as pg


pg.setConfigOptions(antialias=True)

class PlotTool(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)

        self.setMinimumSize(QSize(640, 480))
        self.setWindowTitle("Data Analyzer")
        self.setObjectName("PlotTool")

        qSplitter = QSplitter(self)
        qSplitter.setObjectName("qSplitter")
        qSplitter.setHandleWidth(10)  # Make the handle a bit bigger
        self.setCentralWidget(qSplitter)

        self.data_file_widget = dataFileWidget(self)
        qSplitter.addWidget(self.data_file_widget)

        self.plot_manager = plotManager(self)
        self.plot_manager.setObjectName("plotManagerWidget")
        qSplitter.addWidget(self.plot_manager)

        # Depends on plot_manager, so needs to be created near the end.
        self.setupMainMenu()

    def setupMainMenu(self):
        openAction = QtWidgets.QAction("&Open ...", self)
        openAction.setShortcut("Ctrl+O")
        openAction.setStatusTip("Open a data file")
        openAction.triggered.connect(self.openFile)

        exitAction = QtWidgets.QAction("&Quit", self)
        exitAction.setShortcut("Ctrl+Q")
        exitAction.setStatusTip('Leave The App')
        exitAction.triggered.connect(self.closeApp)

        self.statusBar()

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(openAction)
        fileMenu.addSeparator()
        fileMenu.addAction(exitAction)

        addPlotAction = QtWidgets.QAction("add subplot", self)
        addPlotAction.setShortcut("Ctrl+n")
        addPlotAction.setStatusTip('Add new subplot')
        addPlotAction.triggered.connect(self.plot_manager.addSubplot)

        plotMenu = mainMenu.addMenu('&Plot')
        plotMenu.addAction(addPlotAction)


    def keyPressEvent(self, event):
        ''' Handle keyboard input here (looking mainly for arrow keys + modifiers '''
        if type(event) == QtGui.QKeyEvent and (\
            event.key() == QtCore.Qt.Key_Left or \
            event.key() == QtCore.Qt.Key_Right or \
            event.key() == QtCore.Qt.Key_Up or \
            event.key() == QtCore.Qt.Key_Down):
                #__import__("ipdb").set_trace()
                self.plot_manager.handleKeyPress(event)
                event.accept()
        else:
            event.ignore()


    def closeApp(self):
        sys.exit()

    def openFile(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open loeg file",
                                                      str(Path.home()),
                                                      "Log files (*.csv)")
        # Try setting the "DontUseNativeDialog" option to supress the GtkDialog warning :(
        if len(fname) > 0:
            self.statusBar().showMessage(f"Opening {fname}", 5000)
            self.data_file_widget.openFile(fname)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = PlotTool()
    window.show()
    sys.exit(app.exec_())
