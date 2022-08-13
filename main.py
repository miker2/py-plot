# This Python file uses the following encoding: utf-8
from PyQt5.QtWidgets import QApplication, QMainWindow, QSplitter, \
    QFileDialog, QAction, QMessageBox, QLabel
from PyQt5.QtGui import QKeyEvent, QIcon
from PyQt5.QtCore import Qt, QCoreApplication, QSettings, QSize, QPoint

import pyqtgraph as pg

from data_file_widget import DataFileWidget
from plot_manager import PlotManager

try:
    from visualizer_3d_widget import DockedVisualizer3DWidget

    _visualizer_available = True
except ImportError:
    DockedVisualizer3DWidget = None
    _visualizer_available = False

from maths_widget import DockedMathsWidget
from text_log_widget import DockedTextLogWidget

import os
import sys
from pathlib import Path
import json
import argparse

from imports import install_and_import

shtab = install_and_import("shtab")

pg.setConfigOptions(antialias=True)

_PLOTLIST_EXT = "plotlist"

__APP_NAME__ = "PyPlot"


def __find_dir(start, dirname):
    for directory, *_ in os.walk(start):
        if os.path.split(directory)[-1] == dirname:
            return directory


def __get_base_path():
    # Fill this in with a possible search path if the base directory should be somewhere other than
    # the user home directory.
    return str(Path.home())


__BASE_DIR__ = __get_base_path()


class PyPlot(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)

        QCoreApplication.setApplicationName(__APP_NAME__)

        self.setMinimumSize(QSize(640, 480))
        self.setWindowTitle(QCoreApplication.applicationName())
        self.setObjectName(QCoreApplication.applicationName())

        self.show_text_logs_action = None
        self.maths_widget_action = None
        self.visualizer_3d_action = None

        q_splitter = QSplitter(self)
        q_splitter.setObjectName("qSplitter")
        q_splitter.setHandleWidth(8)  # Make the handle a bit bigger
        self.setCentralWidget(q_splitter)

        self.data_file_widget = DataFileWidget(self)
        q_splitter.addWidget(self.data_file_widget)

        self.plot_manager = PlotManager(self)
        self.plot_manager.setObjectName("plotManagerWidget")
        q_splitter.addWidget(self.plot_manager)

        # When resizing the main window, we want the plots to get bigger, but the variable window
        # to remain the same size (unless the user drags the splitter).
        q_splitter.setStretchFactor(0, 0)
        q_splitter.setStretchFactor(1, 1)

        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        self.visualizer_3d = None
        self.text_log_widget = None
        self.maths_widget = None

        # Depends on plot_manager, so needs to be created near the end.
        self.setup_menu_bar()

        tick_time_indicator = TimeTickWidget()
        self.plot_manager.tickValueChanged.connect(tick_time_indicator.update_tick)
        self.plot_manager.timeValueChanged.connect(tick_time_indicator.update_time)
        self.statusBar().addPermanentWidget(tick_time_indicator)

        self._read_settings()

    def setup_menu_bar(self):
        self.setup_file_menu()
        self.setup_plot_menu()
        self.setup_tool_menu()

        self.statusBar()

    def setup_file_menu(self):
        open_action = QAction("&Open ...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.setStatusTip("Open a data file")
        open_action.triggered.connect(self.open_file_dialog)

        exit_action = QAction("&Quit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip('Leave The App')
        exit_action.triggered.connect(self.close_app)

        main_menu = self.menuBar()
        file_menu = main_menu.addMenu('&File')
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

    def setup_plot_menu(self):
        add_plot_action = QAction("add subplot", self)
        add_plot_action.setShortcut("Ctrl+n")
        add_plot_action.setStatusTip('Add new subplot')
        add_plot_action.triggered.connect(self.plot_manager.add_subplot)

        new_tab_action = QAction("add plot tab", self)
        new_tab_action.setShortcut("Ctrl+t")
        new_tab_action.setStatusTip('Add a new plot tab')
        new_tab_action.triggered.connect(self.plot_manager.add_plot_tab)

        save_plotlist_action = QAction("save plotlist for current tab", self)
        save_plotlist_action.setShortcut("Ctrl+s")
        save_plotlist_action.setStatusTip('Save tab configuration to plotlist')
        save_plotlist_action.triggered.connect(self.save_plotlist)

        load_plotlist_action = QAction("load plotlist for current tab", self)
        load_plotlist_action.setShortcut("Ctrl+Shift+o")
        load_plotlist_action.setStatusTip('Load tab configuration from plotlist')
        load_plotlist_action.triggered.connect(self.load_plotlist)

        load_plotlist_for_all_action = QAction("load plotlist for all files", self)
        load_plotlist_for_all_action.setStatusTip('Load the plotlist for all open datafiles')
        load_plotlist_for_all_action.triggered.connect(lambda: self.load_plotlist(all_files=True, append=True))

        load_plotlist_new_tab_action = QAction("load plotlist in new tab", self)
        load_plotlist_new_tab_action.setStatusTip('Loads a plotlist into a new tab')
        load_plotlist_new_tab_action.triggered.connect(
            lambda: self.load_plotlist(all_files=False, append=False, new_tab=True))

        append_plotlist_action = QAction("append to tab", self)
        append_plotlist_action.setStatusTip('Append the plotlist contents to the current tab')
        append_plotlist_action.triggered.connect(lambda: self.load_plotlist(True))

        main_menu = self.menuBar()
        plot_menu = main_menu.addMenu('&Plot')
        plot_menu.addAction(add_plot_action)
        plot_menu.addAction(new_tab_action)
        plot_menu.addSeparator()
        plot_menu.addAction(save_plotlist_action)
        plot_menu.addAction(load_plotlist_action)
        plot_menu.addAction(load_plotlist_for_all_action)
        plot_menu.addAction(load_plotlist_new_tab_action)

    def setup_tool_menu(self):
        main_menu = self.menuBar()
        tool_menu = main_menu.addMenu('&Tools')

        if _visualizer_available:
            self.visualizer_3d_action = QAction("Show 3D visualizer", self)
            self.visualizer_3d_action.setStatusTip('Show the 3D visualizer window')
            self.visualizer_3d_action.setCheckable(True)
            self.visualizer_3d_action.triggered.connect(self.create_visualizer_window)
            tool_menu.addAction(self.visualizer_3d_action)

        self.maths_widget_action = QAction("Show maths widget", self)
        self.maths_widget_action.setStatusTip('Show the math widget')
        self.maths_widget_action.setCheckable(True)
        self.maths_widget_action.triggered.connect(self.create_or_destroy_math_widget)
        tool_menu.addAction(self.maths_widget_action)

        self.show_text_logs_action = QAction("Show text logs", self)
        self.show_text_logs_action.setStatusTip('Display the text log window')
        self.show_text_logs_action.setCheckable(True)
        self.show_text_logs_action.triggered.connect(self.create_or_destroy_text_log_widget)
        tool_menu.addAction(self.show_text_logs_action)

    def create_visualizer_window(self, is_checked):
        if is_checked:
            if not self.visualizer_3d:
                # Create the window
                source = self.data_file_widget.get_first_supervisor_log()
                self.visualizer_3d = DockedVisualizer3DWidget(self, source)
                self.addDockWidget(Qt.RightDockWidgetArea, self.visualizer_3d)

                # We can't assign a value to a variable in a lambda, so we'll define a small
                # function here.
                def on_close():
                    self.visualizer_3d_action.setChecked(False)
                    self.visualizer_3d = None

                self.visualizer_3d.onClose.connect(on_close)
                self.data_file_widget.countChanged.connect(self.connect_source_to_widget_maybe)
                self.plot_manager.tickValueChanged.connect(self.visualizer_3d.update)
            else:
                self.visualizer_3d.show()
        else:
            self.visualizer_3d.hide()

    def connect_source_to_widget_maybe(self):
        # Below code is called by every widget and modifies every widget
        # TODO: make more efficient
        if self.visualizer_3d and not self.visualizer_3d.has_source:
            self.visualizer_3d.set_source(self.data_file_widget.get_first_supervisor_log())
        # if self.text_log_widget and not self.text_log_widget.has_source:
        #    self.text_log_widget.set_source(self.data_file_widget.get_active_data_file())

    def create_or_destroy_math_widget(self, is_checked):
        if is_checked:
            # Create (or unhide) the widget
            if not self.maths_widget:
                self.maths_widget = DockedMathsWidget(self)
                self.addDockWidget(Qt.BottomDockWidgetArea, self.maths_widget)

                def on_close():
                    self.maths_widget_action.setChecked(False)
                    self.maths_widget = None

                self.maths_widget.onClose.connect(on_close)
            else:
                self.maths_widget.show()
        else:
            # Close (or hide) the widget
            self.maths_widget.hide()

    def create_or_destroy_text_log_widget(self, is_checked):
        if is_checked:
            # Create (or unhide) the widget
            if not self.text_log_widget:
                source = self.data_file_widget.get_active_data_file()
                print(f"Source: {source}")
                self.text_log_widget = DockedTextLogWidget(self, source)
                self.addDockWidget(Qt.RightDockWidgetArea, self.text_log_widget)

                def on_close():
                    self.show_text_logs_action.setChecked(False)
                    self.text_log_widget = None

                self.text_log_widget.onClose.connect(on_close)

                def set_source():
                    self.text_log_widget.set_source(self.data_file_widget.get_active_data_file())

                self.data_file_widget.countChanged.connect(set_source)
                self.data_file_widget.tabChanged.connect(set_source)
                self.plot_manager.tickValueChanged.connect(self.text_log_widget.update)
            else:
                self.text_log_widget.show()

        else:
            # Close (or hide) the widget
            self.text_log_widget.hide()

    def _write_settings(self):
        settings = QSettings()

        settings.beginGroup("MainWindow")
        settings.setValue("size", self.size())
        settings.setValue("position", self.pos())
        settings.setValue("window_state", self.windowState())
        settings.setValue("show_3d_viz", int(not (self.visualizer_3d is None or
                                                  self.visualizer_3d.isHidden())))
        settings.setValue("show_maths", int(not (self.maths_widget is None or
                                                 self.maths_widget.isHidden())))
        settings.setValue("show_text_log", int(not (self.text_log_widget is None or
                                                    self.text_log_widget.isHidden())))
        settings.endGroup()

        settings.sync()

    def _read_settings(self):
        settings = QSettings()

        settings.beginGroup("MainWindow")
        self.resize(settings.value("size", QSize(640, 480)))
        self.move(settings.value("position", QPoint(200, 200)))
        window_state = int(settings.value("window_state", Qt.WindowNoState))
        if window_state & Qt.WindowMaximized:
            print("Setting window to maximized.")
            self.showMaximized()
        elif window_state & Qt.WindowFullScreen:
            print("Setting window to full-screen.")
            self.showFullScreen()
        show_3d_viz = bool(int(settings.value("show_3d_viz", 0)))
        if show_3d_viz:
            self.visualizer_3d_action.setChecked(True)
            self.create_visualizer_window(True)
        show_maths = bool(int(settings.value("show_maths", 0)))
        if show_maths:
            self.maths_widget_action.setChecked(True)
            self.create_or_destroy_math_widget(True)
        show_text_log = bool(int(settings.value("show_text_log", 0)))
        if show_text_log:
            self.show_text_logs_action.setChecked(True)
            self.create_or_destroy_text_log_widget(True)

        settings.endGroup()

    def closeEvent(self, event):
        self._write_settings()

        if self.visualizer_3d:
            self.visualizer_3d.close()
        if self.maths_widget:
            self.maths_widget.close()
        if self.text_log_widget:
            self.text_log_widget.close()

        event.accept()

    def keyPressEvent(self, event):
        """ Handle keyboard input here (looking mainly for arrow keys + modifiers """
        if type(event) == QKeyEvent and (
                event.key() == Qt.Key_Left or
                event.key() == Qt.Key_Right or
                event.key() == Qt.Key_Up or
                event.key() == Qt.Key_Down) or \
                (event.key() == Qt.Key_A and event.modifiers() & Qt.ControlModifier):
            # __import__("ipdb").set_trace()
            self.plot_manager.handle_key_press(event)
            event.accept()
        else:
            event.ignore()

    def close_app(self):
        self.close()

    def open_file_dialog(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open log file",
                                               __BASE_DIR__ + "/..",
                                               "Log files (*.bin *.txt *.csv *.parquet)")
        # Try setting the "DontUseNativeDialog" option to suppress the GtkDialog warning :(
        self.open_file(fname)

    def open_file(self, filename):
        if len(filename) > 0:
            self.statusBar().showMessage(f"Opening {filename}", 5000)
            self.data_file_widget.open_file(filename)

    def save_plotlist(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save plotlist",
                                               __BASE_DIR__ + "/analysis/default.plotlist",
                                               f"Plotlist files (*.{_PLOTLIST_EXT} *.{_PLOTLIST_EXT.upper()})",
                                               f"*.{_PLOTLIST_EXT}")

        if not fname:
            # User aborted.
            return
        # Get the plot info and convert it to nice looking json so the file produced is more
        # human-readable
        plotlist = json.dumps(self.plot_manager.get_plot_info_for_active_tab(), indent=4)
        _, ext = os.path.splitext(fname)
        if ext.lower() != os.path.extsep + _PLOTLIST_EXT:
            fname += os.path.extsep + _PLOTLIST_EXT
        with open(fname, 'w') as fp:
            print(plotlist, file=fp)

    def load_plotlist(self, all_files=False, append=False, new_tab=False):
        # Get the data source and ensure that a file is actually open before asking the user to
        # select the desired plotlist file.
        data_source = self.data_file_widget.get_active_data_file()

        if data_source is None:
            QMessageBox.critical(self, "Error: No open file!",
                                 "You must open a file before loading a plotlist.")
            return

        fname, _ = QFileDialog.getOpenFileName(self, "Load plotlist",
                                               __BASE_DIR__ + f"/analysis/default.{_PLOTLIST_EXT}",
                                               f"Plotlist files (*.{_PLOTLIST_EXT} *.{_PLOTLIST_EXT.upper()})")

        if not fname:
            # No file opened, so nothing to do.
            return
        with open(fname) as fp:
            plotlist = json.load(fp)

        if new_tab:
            self.plot_manager.add_plot_tab()

        if not all_files:
            self.plot_manager.generate_plots_for_active_tab(plotlist, data_source, append)
        else:
            for idx in range(self.data_file_widget.open_count):
                self.plot_manager.generate_plots_for_active_tab(plotlist, self.data_file_widget.get_data_file(idx), idx > 0)

    def load_from_cli(self, cli_args):
        print(f"Loading {cli_args.logfile}")
        self.open_file(cli_args.logfile)

        if cli_args.plotlist is None:
            cli_args.plotlist = []

        if cli_args.analysis is not None:
            try:
                for af in cli_args.analysis:
                    content = af.read()
                    analysis_list = content.split("\n")
                    # NOTE: Assume that the plotlists in the analysis file are in the same directory
                    # as the analysis file.
                    plotlist_dir = os.path.dirname(af.name)
                    for pl in analysis_list:
                        if not pl:
                            # Empty line in the file. Skip.
                            continue

                        _, ext = os.path.splitext(pl)
                        if ext.lower() != f".{_PLOTLIST_EXT}":
                            print(f"!!! {pl} does not appear to be a valid plotlist.")
                            continue
                        cli_args.plotlist.append(open(os.path.join(plotlist_dir, pl), af.mode))
            except Exception as e:
                print(f"Exception when loading {af.name}: {repr(e)}")

        # Plot manager creates a tab by default, so we'll only add a new tab if there is more than 1 plotlist
        count = 0
        for pl in cli_args.plotlist:
            if count > 0:
                self.plot_manager.add_plot_tab()

            data_source = self.data_file_widget.get_active_data_file()
            if data_source is None:
                print("Error: No open file! You must open a file before loading a plotlist.")
            try:
                plotlist = json.load(pl)
                self.plot_manager.generate_plots_for_active_tab(plotlist, data_source, append=False)
                count += 1
            except Exception as e:
                print(f"{pl.name} does not appear to be a valid plotlist!")
                print(f"Exception: {repr(e)}")


class TimeTickWidget(QLabel):
    def __init__(self):
        QLabel.__init__(self)

        self._time = 0
        self._tick = 0

    def update_time(self, time):
        self._time = time
        self._update_label()

    def update_tick(self, tick):
        self._tick = tick
        self._update_label()

    def _update_label(self):
        self.setText(f"tick: {self._tick} | time: {self._time:0.3f}")


LOG_FILES = {
    "bash": "_shtab_greeter_compgen_LOGFiles", "zsh": "_files -g '(*.bin|*.BIN|*.csv|*.CSV|*.parquet)'",
    "tcsh": "f:*.bin"}
PREAMBLE = {
    "bash": """
# $1=COMP_WORDS[1]
_shtab_greeter_compgen_LOGFiles() {
  compgen -d -- $1  # recurse into subdirs
  compgen -f -X '!*?.bin' -- $1
  compgen -f -X '!*?.BIN' -- $1
  compgen -f -X '!*?.csv' -- $1
  compgen -f -X '!*?.CSV' -- $1
  compgen -f -X '!*?.parquet' -- $1
}
""", "zsh": "", "tcsh": ""}


# See https://github.com/iterative/shtab for tab-completion setup
def get_main_parser():
    main_parser = argparse.ArgumentParser(description=__APP_NAME__)
    shtab.add_argument_to(main_parser, ["-s", "--print-completion"], preamble=PREAMBLE)  # magic!
    main_parser.add_argument('-f', '--logfile').complete = LOG_FILES
    main_parser.add_argument('-p', '--plotlist', type=argparse.FileType('r'), action='append').complete = shtab.FILE
    main_parser.add_argument('-a', '--analysis', type=argparse.FileType('r'), action='append').complete = shtab.FILE
    return main_parser


if __name__ == "__main__":
    MainEventThread = QApplication(sys.argv)
    resource_dir, _ = os.path.split(os.path.realpath(__file__))
    MainEventThread.setWindowIcon(QIcon(resource_dir + "/logo.png"))

    MainApplication = PyPlot()

    # <Begin> Parse args here
    parser = get_main_parser()
    parser.set_defaults(func=MainApplication.load_from_cli)
    args = parser.parse_args()

    if args.logfile is None and (args.plotlist is not None or args.analysis is not None):
        print("If a plotlist (or set of plotlists) is specified from the command-line, a file must "
              + "also be specified (via '-f').")
    if args.logfile is not None:
        args.func(args)
    # <End> Parse args here

    MainApplication.show()

    MainEventThread.exec()
