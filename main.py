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

import pyqtgraph as pg


pg.setConfigOptions(antialias=True)

class PlotTool(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)

        self.setMinimumSize(QSize(640, 480))
        self.setWindowTitle("Data Analyzer")
        self.setObjectName("PlotTool")

        self.setup_menu()

        qSplitter = QSplitter(self)
        qSplitter.setObjectName("qSplitter")
        qSplitter.setHandleWidth(10)  # Make the handle a bit bigger
        self.setCentralWidget(qSplitter)

        self.data_file_widget = dataFileWidget()
        qSplitter.addWidget(self.data_file_widget)

        plotAreaWidget = QWidget(self)
        plotAreaWidget.setObjectName("plotAreaWidget")
        qSplitter.addWidget(plotAreaWidget)

        self.plotAreaLayout = QVBoxLayout(plotAreaWidget)
        self.plotAreaLayout.setObjectName("plotAreaLayout")
        # plotAreaWidget.setLayout(plotAreaLayout)

        rs = QRangeSlider()
        rs.show()
        rs.setMin(0)
        rs.setMax(2**10)
        rs.setRange(rs.min(), rs.max())
        #rs.setBackgroundStyle('background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #222, stop:1 #333);')
        #rs.handle.setStyleSheet('background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #282, stop:1 #393);')
        self.plotAreaLayout.addWidget(rs)

        #qxtss = QxtSpanSlider()
        #qxtss.setRange(0, 100)
        #qxtss.setSpan(10, 70)
        #plotAreaLayout.addWidget(qxtss)

        self.subplots = []
        subPlot1 = subPlotWidget()
        self.plotAreaLayout.addWidget(subPlot1)
        self.subplots.append(subPlot1)

        subPlot2 = subPlotWidget(500000)
        self.plotAreaLayout.addWidget(subPlot2)
        self.subplots.append(subPlot2)

    def setup_menu(self):
        openAction = QtWidgets.QAction("&Open ...", self)
        openAction.setShortcut("Ctrl+O")
        openAction.setStatusTip("Open a data file")
        openAction.triggered.connect(self.open_file)

        exitAction = QtWidgets.QAction("&Quit", self)
        exitAction.setShortcut("Ctrl+Q")
        exitAction.setStatusTip('Leave The App')
        exitAction.triggered.connect(self.close_app)

        self.statusBar()

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(openAction)
        fileMenu.addSeparator()
        fileMenu.addAction(exitAction)

        addPlotAction = QtWidgets.QAction("add subplot", self)
        addPlotAction.setShortcut("Ctrl+n")
        addPlotAction.setStatusTip('Add new subplot')
        addPlotAction.triggered.connect(self.add_subplot)

        plotMenu = mainMenu.addMenu('&Plot')
        plotMenu.addAction(addPlotAction)

    def close_app(self):
        print("You closed me brah!")
        sys.exit()

    def open_file(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open loeg file",
                                                      str(Path.home()),
                                                      "Log files (*.csv)")
        # Try setting the "DontUseNativeDialog" option to supress the GtkDialog warning :(
        if len(fname) > 0:
            self.statusBar().showMessage(f"Opening {fname}", 5000)
            self.data_file_widget.open_file(fname)

    def add_subplot(self):
        subPlot = subPlotWidget(500000)
        self.plotAreaLayout.addWidget(subPlot)
        self.subplots.append(subPlot)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = PlotTool()
    window.show()
    sys.exit(app.exec_())
