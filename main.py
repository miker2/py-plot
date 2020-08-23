# This Python file uses the following encoding: utf-8
from PyQt5.QtWidgets import QApplication, QMainWindow, QSplitter, \
        QFileDialog, QAction, QMessageBox, QLabel, QDockWidget
from PyQt5.QtGui import QKeyEvent, QIcon
from PyQt5.QtCore import Qt, QCoreApplication, QSettings, QSize, QPoint

import pyqtgraph as pg

from data_file_widget import DataFileWidget
from plot_manager import PlotManager
try:
    from visualizer_3d_widget import DockedVisualizer3DWidget
    _visualizer_available = True
except ImportError:
    _visualizer_available = False

from maths_widget import DockedMathsWidget

import os
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
        qSplitter.setHandleWidth(8)  # Make the handle a bit bigger
        self.setCentralWidget(qSplitter)

        self.data_file_widget = DataFileWidget(self)
        qSplitter.addWidget(self.data_file_widget)

        self.plot_manager = PlotManager(self)
        self.plot_manager.setObjectName("plotManagerWidget")
        qSplitter.addWidget(self.plot_manager)

        # When resizing the main window, we want the plots to get bigger, but the variable window
        # to remain the same size (unless the user drags the splitter).
        qSplitter.setStretchFactor(0, 0)
        qSplitter.setStretchFactor(1, 1)

        self.visualizer_3d = None
        self.text_log_widget = None
        self.maths_widget = None

        # Depends on plot_manager, so needs to be created near the end.
        self.setupMenuBar()

        tick_time_indicator = TimeTickWidget()
        self.plot_manager.tickValueChanged.connect(tick_time_indicator.updateTick)
        self.plot_manager.timeValueChanged.connect(tick_time_indicator.updateTime)
        self.statusBar().addPermanentWidget(tick_time_indicator)

        self._readSettings()

    def setupMenuBar(self):
        self.setupFileMenu()
        self.setupPlotMenu()
        self.setupToolMenu()

        self.statusBar()

    def setupFileMenu(self):
        openAction = QAction("&Open ...", self)
        openAction.setShortcut("Ctrl+O")
        openAction.setStatusTip("Open a data file")
        openAction.triggered.connect(self.openFileDialog)

        exitAction = QAction("&Quit", self)
        exitAction.setShortcut("Ctrl+Q")
        exitAction.setStatusTip('Leave The App')
        exitAction.triggered.connect(self.closeApp)

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(openAction)
        fileMenu.addSeparator()
        fileMenu.addAction(exitAction)

    def setupPlotMenu(self):
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

        loadPlotlistNewTabAction = QAction("load configuration in new tab", self)
        loadPlotlistNewTabAction.setStatusTip('Loads a plotlist into a new tab')
        loadPlotlistNewTabAction.triggered.connect(lambda : self.loadPlotlist(all_files=False, append=False, new_tab=True))

        appendPlotlistAction = QAction("append to tab", self)
        appendPlotlistAction.setStatusTip('Append the plotlist contents to the current tab')
        appendPlotlistAction.triggered.connect(lambda : self.loadPlotlist(True))

        mainMenu = self.menuBar()
        plotMenu = mainMenu.addMenu('&Plot')
        plotMenu.addAction(addPlotAction)
        plotMenu.addAction(newTabAction)
        plotMenu.addSeparator()
        plotMenu.addAction(savePlotlistAction)
        plotMenu.addAction(loadPlotlistAction)
        plotMenu.addAction(loadPlotlistForAllAction)
        plotMenu.addAction(loadPlotlistNewTabAction)

    def setupToolMenu(self):
        main_menu = self.menuBar()
        tool_menu = main_menu.addMenu('&Tools')

        if _visualizer_available:
            self.visualizer_3d_action = QAction("Show 3D visualizer", self)
            self.visualizer_3d_action.setStatusTip('Show the 3D visualizer window')
            self.visualizer_3d_action.setCheckable(True)
            self.visualizer_3d_action.triggered.connect(self.createVisualizerWindow)
            tool_menu.addAction(self.visualizer_3d_action)

        self.maths_widget_action = QAction("Show maths widget", self)
        self.maths_widget_action.setStatusTip('Show the math widget')
        self.maths_widget_action.setCheckable(True)
        self.maths_widget_action.triggered.connect(self.createOrDestroyMathsWidget)
        tool_menu.addAction(self.maths_widget_action)

    def createVisualizerWindow(self, is_checked):
        if is_checked:
            if not self.visualizer_3d:
                # Create the window
                source = self.data_file_widget.getFirstSupervisorLog()
                self.visualizer_3d = DockedVisualizer3DWidget(self, source)
                self.addDockWidget(Qt.RightDockWidgetArea, self.visualizer_3d)

                # We can't assign a value to a variable in a lambda, so we'll define a small
                # function here.
                def onClose():
                    self.visualizer_3d_action.setChecked(False)
                    self.visualizer_3d = None

                self.visualizer_3d.onClose.connect(onClose)
                self.data_file_widget.countChanged.connect(self.connectSourceToVisualizerMaybe)
                self.plot_manager.tickValueChanged.connect(self.visualizer_3d.update)
            else:
                self.visualizer_3d.show()
        else:
            self.visualizer_3d.hide()

    def connectSourceToVisualizerMaybe(self):
        if self.visualizer_3d and not self.visualizer_3d.hasSource:
            self.visualizer_3d.setSource(self.data_file_widget.getFirstSupervisorLog())

    def createOrDestroyMathsWidget(self, is_checked):
        if is_checked:
            # Create (or unhide) the widget
            if not self.maths_widget:
                self.maths_widget = DockedMathsWidget(self)
                self.addDockWidget(Qt.BottomDockWidgetArea, self.maths_widget)

                def onClose():
                    self.maths_widget_action.setChecked(False)
                    self.maths_widget = None

                self.maths_widget.onClose.connect(onClose)
            else:
                self.maths_widget.show()
        else:
            # Close (or hide) the widget
            self.maths_widget.hide()


    def createFloatingDockWidget(self, title=None):
        print("Calling 'createFloatingDockWidget'")
        dock_widget = QDockWidget(title, self)
        dock_widget.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_widget)
        dock_widget.setFloating(True)

        return dock_widget

    def _writeSettings(self):
        settings = QSettings()

        settings.beginGroup("MainWindow")
        settings.setValue("size", self.size())
        settings.setValue("position", self.pos())
        settings.setValue("window_state", self.windowState())
        settings.setValue("show_3d_viz", int(not (self.visualizer_3d is None or \
                                                  self.visualizer_3d.isHidden())))
        settings.setValue("show_maths", int(not (self.maths_widget is None or \
                                                 self.maths_widget.isHidden())))
        settings.endGroup()

        settings.sync()

    def _readSettings(self):
        settings = QSettings()

        settings.beginGroup("MainWindow")
        self.resize(settings.value("size", QSize(640, 480)))
        self.move(settings.value("position", QPoint(200, 200)))
        window_state = int(settings.value("window_state", Qt.WindowNoState))
        if window_state & Qt.WindowMaximized:
            print("Setting window to maximized.")
            self.showMaximized()
        elif window_state & Qt.WindowFullScreen:
            print("Setting window to fullscreen.")
            self.showFullScreen()
        show_3d_viz = bool(int(settings.value("show_3d_viz", 0)))
        if show_3d_viz:
            self.visualizer_3d_action.setChecked(True)
            self.createVisualizerWindow(True)
        show_maths = bool(int(settings.value("show_maths", 0)))
        if show_maths:
            self.maths_widget_action.setChecked(True)
            self.createOrDestroyMathsWidget(True)
        settings.endGroup()

    def closeEvent(self, event):
        self._writeSettings()

        if self.visualizer_3d:
            self.visualizer_3d.close()
        if self.maths_widget:
            self.maths_widget.close()

        event.accept()

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
        self.close()

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
                                                    __BASE_LEMO_DIR__+"/data/analysis/default.plotlist",
                                                    "Plotlist files (*.plotlist)",
                                                    "*.plotlist")

        if not fname:
            # User aborted.
            return
        # Get the plot info and convert it to nice looking json so the file produced is more human
        # readable
        plotlist = json.dumps(self.plot_manager.getPlotInfoForActiveTab(), indent=4)
        with open(fname, 'w') as fp:
            print(plotlist, file=fp)

    def loadPlotlist(self, all_files=False, append=False, new_tab=False):
        # Get the data source and ensure that a file is actually open before asking the user to
        # select the desired plotlist file.
        data_source = self.data_file_widget.getActiveDataFile()

        if data_source is None:
            QMessageBox.critical(self, "Error: No open file!",
                                 "You must open a file before loading a plot configuration.")
            return

        fname, _ = QFileDialog.getOpenFileName(self, "Load plotlist",
                                                     __BASE_LEMO_DIR__+"/data/analysis/default.plotlist",
                                                      "Plotlist files (*.plotlist)")

        if not fname:
            # No file opened, so nothing to do.
            return
        with open(fname) as fp:
            plotlist = json.load(fp)

        if new_tab:
            self.plot_manager.addPlotTab()

        if not all_files:
            self.plot_manager.generatePlotsForActiveTab(plotlist, data_source, append)
        else:
            for idx in range(self.data_file_widget.openCount):
                self.plot_manager.generatePlotsForActiveTab(plotlist, self.data_file_widget.getDataFile(idx), idx > 0)

    def loadFromCLI(self, args):
        print(f"Loading {args.f}")
        self.openFile(args.f)

        # todo: This is duplicate from above
        # Wrap in function
        if args.p is None:
            # Nothing else to do.
            return

        # Plot manager creates a tab by default, so we'll only add a new tab if there is more than 1 plotlist
        count = 0
        for pl in args.p:
            if count > 0:
                self.plot_manager.addPlotTab()

            data_source = self.data_file_widget.getActiveDataFile()
            if data_source is None:
                print("Error: No open file! You must open a file before loading a plot configuration.")
            try:
                with open(pl[0].name) as fp:
                    plotlist = json.load(fp)
                    self.plot_manager.generatePlotsForActiveTab(plotlist, data_source, append=False)
                count += 1
            except:
                print("notpassed")


class TimeTickWidget(QLabel):
    def __init__(self):
        QLabel.__init__(self)

        self._time = 0
        self._tick = 0

    def updateTime(self, time):
        self._time = time
        self._updateLabel()

    def updateTick(self, tick):
        self._tick = tick
        self._updateLabel()

    def _updateLabel(self):
        self.setText(f"tick: {self._tick} | time: {self._time:0.3f}")


if __name__ == "__main__":
    MainEventThread = QApplication(sys.argv)
    resource_dir, _ = os.path.split(os.path.realpath(__file__))

    MainApplication = RoboPlot()

    # <Begin> Parse args here
    parser = argparse.ArgumentParser(description="PyPlot")
    parser.add_argument('-f')
    parser.add_argument('-p', type=argparse.FileType('r'), action='append', nargs='+')
    parser.set_defaults(func=MainApplication.loadFromCLI)
    args = parser.parse_args()

    if args.f is None and args.p is not None:
        print("If a plotlist is specified from the command-line, a file must also be specified (via '-f').")
    if args.f is not None:
        args.func(args)
    # <End> Parse args here

    MainApplication.show()

    MainEventThread.exec()
