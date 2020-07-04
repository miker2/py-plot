# This Python file uses the following encoding: utf-8
from PyQt5.QtWidgets import QApplication, QMainWindow, QSplitter, \
        QFileDialog, QAction, QMessageBox, QLabel
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtCore import QSize, Qt

import pyqtgraph as pg

from data_file_widget import DataFileWidget
from plot_manager import PlotManager

import sys
from pathlib import Path
import pprint
import json
import argparse

pg.setConfigOptions(antialias=True)


class RoboPlot(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)

        self.setMinimumSize(QSize(640, 480))
        self.setWindowTitle("Data Analyzer")
        self.setObjectName("PyPlot")

        qSplitter = QSplitter(self)
        qSplitter.setObjectName("qSplitter")
        qSplitter.setHandleWidth(10)  # Make the handle a bit bigger
        self.setCentralWidget(qSplitter)

        self.data_file_widget = DataFileWidget(self)
        qSplitter.addWidget(self.data_file_widget)

        self.plot_manager = PlotManager(self)
        self.plot_manager.setObjectName("plotManagerWidget")
        qSplitter.addWidget(self.plot_manager)

        # Depends on plot_manager, so needs to be created near the end.
        self.setupMainMenu()

        tick_time_indicator = TimeTickWidget()
        self.plot_manager.tickValueChanged.connect(tick_time_indicator.updateTimeTick)
        self.statusBar().addPermanentWidget(tick_time_indicator)

    def setupMainMenu(self):
        openAction = QAction("&Open ...", self)
        openAction.setShortcut("Ctrl+O")
        openAction.setStatusTip("Open a data file")
        openAction.triggered.connect(self.openFileDialog)

        exitAction = QAction("&Quit", self)
        exitAction.setShortcut("Ctrl+Q")
        exitAction.setStatusTip('Leave The App')
        exitAction.triggered.connect(self.closeApp)

        self.statusBar()

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(openAction)
        fileMenu.addSeparator()
        fileMenu.addAction(exitAction)

        addPlotAction = QAction("add subplot", self)
        addPlotAction.setShortcut("Ctrl+n")
        addPlotAction.setStatusTip('Add new subplot')
        addPlotAction.triggered.connect(self.plot_manager.addSubplot)

        newTabAction = QAction("add plot tab", self)
        newTabAction.setShortcut("Ctrl+t")
        newTabAction.setStatusTip('Add a new plot tab')
        newTabAction.triggered.connect(self.plot_manager.addPlotTab)

        savePlotlistAction = QAction("save tab configuration", self)
        savePlotlistAction.setShortcut("Ctrl+s")
        savePlotlistAction.setStatusTip('Save tab configuration to file')
        savePlotlistAction.triggered.connect(self.savePlotlist)

        loadPlotlistAction = QAction("load tab configuration", self)
        loadPlotlistAction.setShortcut("Ctrl+Shift+o")
        loadPlotlistAction.setStatusTip('Load tab configuration from plotlist')
        loadPlotlistAction.triggered.connect(self.loadPlotlist)

        loadPlotlistForAllAction = QAction("load plotlist for all files", self)
        loadPlotlistForAllAction.setStatusTip('Load the plotlist for all open datafiles')
        loadPlotlistForAllAction.triggered.connect(lambda : self.loadPlotlist(all_files=True, append=True))

        appendPlotlistAction = QAction("append to tab", self)
        appendPlotlistAction.setStatusTip('Append the plotlist contents to the current tab')
        appendPlotlistAction.triggered.connect(lambda : self.loadPlotlist(True))

        plotMenu = mainMenu.addMenu('&Plot')
        plotMenu.addAction(addPlotAction)
        plotMenu.addAction(newTabAction)
        plotMenu.addSeparator()
        plotMenu.addAction(savePlotlistAction)
        plotMenu.addAction(loadPlotlistAction)
        plotMenu.addAction(loadPlotlistForAllAction)


    def keyPressEvent(self, event):
        ''' Handle keyboard input here (looking mainly for arrow keys + modifiers '''
        if type(event) == QKeyEvent and (\
            event.key() == Qt.Key_Left or \
            event.key() == Qt.Key_Right or \
            event.key() == Qt.Key_Up or \
            event.key() == Qt.Key_Down) or \
            (event.key() == Qt.Key_A and event.modifiers() & Qt.ControlModifier):
                #__import__("ipdb").set_trace()
                self.plot_manager.handleKeyPress(event)
                event.accept()
        else:
            event.ignore()


    def closeApp(self):
        sys.exit()

    def openFileDialog(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open log file",
                                                      str(Path.home()),
                                                      "Log files (*.bin *.csv)")
        # Try setting the "DontUseNativeDialog" option to supress the GtkDialog warning :(
        self.openFile(fname)

    def openFile(self, filename):
        if len(filename) > 0:
            self.statusBar().showMessage(f"Opening {filename}", 5000)
            self.data_file_widget.openFile(filename)

    def savePlotlist(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save plotlist",
                                                    str(Path.home()) + "/default.plotlist",
                                                    "Plotlist files (*.plotlist)",
                                                    "*.plotlist")

        if fname is None:
            # User aborted.
            return
        # Get the plot info and convert it to nice looking json so the file produced is more human
        # readable
        plotlist = json.dumps(self.plot_manager.getPlotInfoForActiveTab(), indent=4)
        with open(fname, 'w') as fp:
            print(plotlist, file=fp)

    def loadPlotlist(self, all_files=False, append=False):
        # Get the data source and ensure that a file is actually open before asking the user to
        # select the desired plotlist file.
        data_source = self.data_file_widget.getActiveDataFile()

        if data_source is None:
            QMessageBox.critical(self, "Error: No open file!",
                                 "You must open a file before loading a plot configuration.")
            return

        fname, _ = QFileDialog.getOpenFileName(self, "Load plotlist",
                                                      str(Path.home()),
                                                      "Plotlist files (*.plotlist)")

        if fname is None:
            # No file opened, so nothing to do.
            return
        with open(fname) as fp:
            plotlist = json.load(fp)

        if not all_files:
            self.plot_manager.generatePlotsForActiveTab(plotlist, data_source, append)
        else:
            for idx in range(self.data_file_widget.openCount):
                self.plot_manager.generatePlotsForActiveTab(plotlist, self.data_file_widget.getDataFile(idx), idx > 0)

    def loadFromCLI(self, args):
        print(f"Loading {args.filename}...")
        self.openFile(args.filename)

        if not args.p is None:
            # Load plotlist here. Code above needs a bit of refactoring
            pass


class TimeTickWidget(QLabel):
    def __init__(self):
        QLabel.__init__(self)

    def updateTimeTick(self, val):
        self.setText(f"tick: {val} | time: {val / 500.:0.3f}")


if __name__ == "__main__":
    MainEventThread = QApplication([])

    MainApplication = RoboPlot()

    # Parse args here
    parser = argparse.ArgumentParser(description='PyPlot')
    subparser = parser.add_subparsers(help="sub-command help")

    # gui_parser = subparser.add_parser('gui')

    cli_parser = subparser.add_parser('load')
    cli_parser.add_argument('filename')
    cli_parser.add_argument('-p')
    cli_parser.set_defaults(func=MainApplication.loadFromCLI)
    args = parser.parse_args()

    print(args)
    try:
        args.func(args)
    except:
        pass

    MainApplication.show()

    MainEventThread.exec()

