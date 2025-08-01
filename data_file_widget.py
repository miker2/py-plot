# This Python file uses the following encoding: utf-8

from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QTabWidget, QMessageBox, \
    QCheckBox, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QListWidget, \
    QMenu, QAction, QApplication, QDialog, QPushButton
from filter_box_widget import FilterBoxWidget
from var_list_widget import VarListWidget
from logging_config import get_logger

import csv
import math
import numpy as np
import os
import pandas as pd

import simlog_decode

from imports import install_and_import

pyarrow = install_and_import("pyarrow")

logger = get_logger(__name__)


class DataFileWidget(QWidget):
    countChanged = pyqtSignal()
    tabChanged = pyqtSignal()
    fileOpened = pyqtSignal([int], [str])
    fileClosed = pyqtSignal(str)

    def __init__(self, parent):
        QWidget.__init__(self, parent=parent)

        self.controller = parent

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        # TODO(rose@): Enable this when the filename is embedded in the VarListWidget
        # self.tabs.setTabBarAutoHide(True)
        self.tabs.tabCloseRequested.connect(self.close_file)
        self.tabs.tabBar().customContextMenuRequested.connect(self.on_context_menu_request)
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.currentChanged.connect(lambda x: self.tabChanged.emit())
        layout.addWidget(self.tabs)

        self.filter_box = FilterBoxWidget(self.tabs)
        layout.addWidget(self.filter_box)

        self._fileloader_module = {'.parquet': ParquetLoader,
                                   '.bin': BinaryFileLoader,  # pybullet
                                   '.csv': GenericCSVLoader}

        self.sources = dict()
        self.latest_data_file_name = None

    def _get_var_list_from_tab(self, tab_widget):
        """Helper to extract VarListWidget from tab container"""
        return tab_widget.var_list

    @property
    def open_count(self):
        return self.tabs.count()

    def open_file(self, filepath):
        filepath = os.path.abspath(filepath)
        ext = os.path.splitext(filepath)[-1]
        loader = self._fileloader_module[ext](self, filepath)
        if not loader.success:
            # File didn't finish loading. Nothing else to do.
            return
        var_list = VarListWidget(self, loader)

        if loader.time_offset != 0.0:
            var_list.set_time_offset(loader.time_offset)

        # Create a container widget with checkbox and var_list
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(2, 2, 2, 2)  # Small margins
        tab_layout.setSpacing(2)  # Small spacing

        # Store direct reference to VarListWidget on the container
        tab_widget.var_list = var_list

        # Add checkbox for derived variables toggle
        derived_checkbox = QCheckBox("Show derived variables")
        derived_checkbox.setChecked(var_list.model()._show_derived)
        derived_checkbox.toggled.connect(var_list.model().set_show_derived)

        # Only enable checkbox if there are derived variables
        derived_checkbox.setEnabled(len(var_list.model()._derived_data) > 0)

        # Update checkbox state when derived variables are added/removed
        def update_checkbox_state():
            has_derived = len(var_list.model()._derived_data) > 0
            derived_checkbox.setEnabled(has_derived)
            if not has_derived:
                derived_checkbox.setChecked(False)

        # Connect to model changes (we'll need to call this when derived vars change)
        var_list._derived_checkbox = derived_checkbox  # Store reference for updates
        var_list._update_checkbox = update_checkbox_state

        # Set callback in the model so it can update the checkbox
        var_list.model()._checkbox_update_callback = update_checkbox_state

        tab_layout.addWidget(derived_checkbox)
        tab_layout.addWidget(var_list)

        tab_name = os.path.basename(filepath)
        # Create a new tab and add the container widget to it.
        self.latest_data_file_name = filepath
        self.tabs.addTab(tab_widget, tab_name)
        self.sources[filepath] = var_list  # Store the VarListWidget, not the container
        self.tabs.setCurrentWidget(tab_widget)
        self._update_range_slider()

        var_list.timeChanged.connect(self._update_range_slider)

        self.countChanged.emit()
        self.fileOpened[str].emit(filepath)
        self.fileOpened[int].emit(self.tabs.currentIndex())

    def close_file(self, index):
        # Add function for closing the tab here.
        tab_widget = self.tabs.widget(index)
        var_list = self._get_var_list_from_tab(tab_widget)

        filename = var_list.filename
        var_list.close()

        self.tabs.removeTab(index)
        if self.tabs.count() > 0:
            self._update_range_slider()

        self.countChanged.emit()
        self.fileClosed[str].emit(filename)

    def get_active_data_file(self):
        tab_widget = self.tabs.currentWidget()
        return self._get_var_list_from_tab(tab_widget)

    def get_latest_data_file_name(self):
        return self.latest_data_file_name

    def get_data_file(self, idx):
        tab_widget = self.tabs.widget(idx)
        return self._get_var_list_from_tab(tab_widget)

    def get_data_file_by_name(self, name):
        return self.sources[name]

    def get_sources(self):
        return self.sources

    def get_time(self, idx=0):
        if self.tabs.count() == 0:
            return None
        return self.get_data_file(idx).time

    @pyqtSlot(QPoint)
    def on_context_menu_request(self, pos):
        # We only want to bring up the context menu when an actual tab is right-clicked. Check that
        # the click position is inside the tab bar
        if self.tabs.tabBar().rect().contains(pos):
            # Figure out specifically which tab was right-clicked:
            tab_idx = self.tabs.tabBar().tabAt(pos)

            offset_act = QAction("time offset...")
            offset_act.setStatusTip("Set a fix time offset.")
            offset_act.triggered.connect(lambda: self._set_time_offset(tab_idx))

            menu = QMenu(self.tabs)
            menu.addAction(offset_act)

            menu.addSeparator()

            get_path_act = QAction("Copy path")
            get_path_act.triggered.connect(lambda: self._copy_to_clipboard(tab_idx))
            menu.addAction(get_path_act)

            menu.exec(self.tabs.tabBar().mapToGlobal(pos))

    @pyqtSlot()
    def _update_range_slider(self):
        min_time = math.inf
        max_time = -math.inf

        for idx in range(self.tabs.count()):
            tab_widget = self.tabs.widget(idx)
            var_list = self._get_var_list_from_tab(tab_widget)
            t_range = var_list.time_range
            logger.debug(f"idx: {idx} - Time range: {t_range}")
            min_time = min(min_time, t_range[0])
            max_time = max(max_time, t_range[1])
        logger.debug(f"min_time: {min_time}, max_time: {max_time}")

        # TODO(rose@) replace this with signal/slot logic
        self.controller.plot_manager.update_slider_limits(min_time, max_time)

    def _copy_to_clipboard(self, idx):
        cb = QApplication.clipboard()
        tab_widget = self.tabs.widget(idx)
        var_list = self._get_var_list_from_tab(tab_widget)
        cb.setText(var_list.filename)

    def _set_time_offset(self, idx):
        tab_widget = self.tabs.widget(idx)
        var_list = self._get_var_list_from_tab(tab_widget)

        initial_offset = var_list.time_offset

        # Create a dialog box for getting user input. This can be created on the fly.
        time_offset_dialog = QDialog(tab_widget)
        time_offset_dialog.setModal(False)  # Make it non-modal

        form = QFormLayout(time_offset_dialog)

        # Add manual user input dialog box
        time_offset_spin = QDoubleSpinBox()
        time_offset_spin.setDecimals(3)
        time_offset_spin.setSingleStep(0.001)
        time_offset_spin.setRange(-float("inf"), float("inf"))
        time_offset_spin.setSuffix(" sec")
        time_offset_spin.setValue(initial_offset)
        form.addRow("time offset:", time_offset_spin)

        # Adds an option that allows the user to set the first time value to zero.
        start_zero_check_box = QCheckBox("start at zero")
        form.addRow(start_zero_check_box)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                      Qt.Horizontal, time_offset_dialog)
        form.addRow(button_box)

        # --- Signal Connections for Live Update ---

        def update_offset():
            if start_zero_check_box.isChecked():
                # Disable spin box when checkbox is checked
                time_offset_spin.setEnabled(False)
                t_offset = -var_list.time_range[0]
                # Update spinbox to reflect the change, without emitting a new signal
                time_offset_spin.blockSignals(True)
                time_offset_spin.setValue(t_offset)
                time_offset_spin.blockSignals(False)
                var_list.set_time_offset(t_offset)
            else:
                # Re-enable spin box
                time_offset_spin.setEnabled(True)
                var_list.set_time_offset(time_offset_spin.value())

        # Connect signals
        time_offset_spin.valueChanged.connect(update_offset)
        start_zero_check_box.stateChanged.connect(update_offset)

        def on_accept():
            # Final value is already set by the live updates, just close the dialog.
            time_offset_dialog.accept()

        def on_reject():
            # User cancelled, so restore the original offset.
            var_list.set_time_offset(initial_offset)
            time_offset_dialog.reject()

        button_box.accepted.connect(on_accept)
        button_box.rejected.connect(on_reject)

        # Show the dialog
        time_offset_dialog.show()


class FileLoader:
    def __init__(self, filename):
        self._filename = filename
        self._time = None
        self._df = None
        self._supervisor_log = False
        self.time_offset = 0.0

    @property
    def success(self):
        # Only return success if neither the time nor the data is None
        return self._time is not None and self._df is not None

    @property
    def source(self):
        return self._filename

    @property
    def time(self):
        return self._time.to_numpy()

    @property
    def data_frame(self):
        return self._df

    @property
    def is_supervisor_log(self):
        return self._supervisor_log


def time_selector_dialog(caller, df):
    dialog = QDialog(caller)
    dialog.setWindowTitle("Time variable selector")
    form = QFormLayout(dialog)
    var_selector = QListWidget()
    var_selector.addItems(df.columns)
    var_selector.setCurrentRow(0)
    form.addRow("Select time variable:", var_selector)

    # Add scale factor option
    scale_factor_input = QDoubleSpinBox()
    scale_factor_input.setDecimals(12)  # Allow for very small numbers like 1e-9
    scale_factor_input.setMinimum(1e-15)  # Support very small scale factors
    scale_factor_input.setMaximum(1e15)   # Support very large scale factors
    scale_factor_input.setValue(1.0)      # Default to no scaling
    scale_factor_input.setToolTip("Scale factor to apply to the time variable (e.g., 1e-9 to convert nanoseconds to seconds)")
    scale_factor_input.setSingleStep(0.1)

    scale_hbox = QHBoxLayout()
    scale_hbox.addWidget(scale_factor_input)
    scale_hbox.addWidget(QLabel("(e.g., 1e-9 for ns→s)"))

    # Add preset buttons for common scale factors
    ns_to_s_btn = QPushButton("ns→s")
    ns_to_s_btn.setToolTip("Set scale factor to 1e-9 (nanoseconds to seconds)")
    ns_to_s_btn.clicked.connect(lambda: scale_factor_input.setValue(1e-9))

    us_to_s_btn = QPushButton("μs→s")
    us_to_s_btn.setToolTip("Set scale factor to 1e-6 (microseconds to seconds)")
    us_to_s_btn.clicked.connect(lambda: scale_factor_input.setValue(1e-6))

    ms_to_s_btn = QPushButton("ms→s")
    ms_to_s_btn.setToolTip("Set scale factor to 1e-3 (milliseconds to seconds)")
    ms_to_s_btn.clicked.connect(lambda: scale_factor_input.setValue(1e-3))

    reset_btn = QPushButton("1.0")
    reset_btn.setToolTip("Reset scale factor to 1.0 (no scaling)")
    reset_btn.clicked.connect(lambda: scale_factor_input.setValue(1.0))

    scale_hbox.addWidget(ns_to_s_btn)
    scale_hbox.addWidget(us_to_s_btn)
    scale_hbox.addWidget(ms_to_s_btn)
    scale_hbox.addWidget(reset_btn)
    scale_hbox.addStretch()
    form.addRow("Scale factor:", scale_hbox)

    synthetic_time_tickbox = QCheckBox()
    synthetic_time_tickbox.setToolTip("Check this box if you want to create a synthetic time variable.")
    time_delta_input = QDoubleSpinBox()
    DECIMALS = 3
    STEP_SIZE = 1. / (10 ** DECIMALS)
    time_delta_input.setSingleStep(STEP_SIZE)
    time_delta_input.setMinimum(STEP_SIZE)
    time_delta_input.setMaximum(1.0)
    time_delta_input.setDecimals(DECIMALS)
    time_delta_input.setToolTip("Specify the sampling period of the time vector")
    hbox = QHBoxLayout()
    hbox.addWidget(synthetic_time_tickbox)
    hbox.addWidget(time_delta_input)
    hbox.addWidget(QLabel("sec/tick"))
    hbox.addStretch()
    form.addRow("Create time variable:", hbox)

    start_zero_check_box = QCheckBox("Start time at 0")
    start_zero_check_box.setToolTip("If checked, the time vector will be offset so that it starts at 0.")
    form.addRow(start_zero_check_box)

    # Add some standard buttons (Cancel/Ok) at the bottom of the dialog
    button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                  Qt.Horizontal, dialog)
    form.addRow(button_box)
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)

    # Show the dialog as modal
    if dialog.exec() == QDialog.Accepted:
        scale_factor = scale_factor_input.value()
        if synthetic_time_tickbox.isChecked():
            # User wants a synthetic time variable, so let's create one:
            dt = time_delta_input.value() * scale_factor  # Apply scale factor to synthetic time as well
            # We can safely call this variable "time" because if "time" already existed,
            # this dialog wouldn't appear.
            df['time'] = dt * np.array(range(df.shape[0]), dtype=np.float64)
            time = df['time']
        else:
            item = var_selector.currentItem().text()
            time = df[item].astype(np.float64, copy=True) * scale_factor  # Apply scale factor
            if np.any(np.diff(time) < 0):
                QMessageBox.warning(caller, "Non-monotonic time variable",
                                    f"WARNING: Selected time variable '{item}' (after scaling) is not " +
                                    "monotonically increasing!")
        time_offset = 0.0
        if start_zero_check_box.isChecked():
            time_offset = -time.iloc[0]
        return True, time, time_offset
    else:
        return False, None, 0.0


def _is_supervisor_log(filename, df):
    # We need to determine if this is a "supervisor" log so that the 3D visualizer
    # works properly. Start with the obvious and see if "supervisor" is in the name.

    return "time" in df.columns and \
           (filename.find("supervisor") >= 0 or "control_elapsed_dt" in df.columns)


class BinaryFileLoader(FileLoader):
    def __init__(self, caller, filename):
        FileLoader.__init__(self, filename)

        try:
            # This is a pybullet simulation log.
            self._df = simlog_decode.load_df(filename)
            self._time = self._df['timeStamp']

        except KeyError:
            # Log file doesn't have one of the expected time variables, so ask the user to pick one.
            ok, time, offset = time_selector_dialog(caller, self._df)
            if ok:
                self._time = time
                self.time_offset = offset
            else:
                QMessageBox.critical(caller, "Unable to load .bin file",
                                     "No time series selected. Unable to finish loading data.")


class GenericCSVLoader(FileLoader):
    def __init__(self, caller, filename):
        FileLoader.__init__(self, filename)

        # Ensure the csv file is not malformed. Oddly, pandas does not do a good job of this.
        with open(filename, 'r') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            header = reader.__next__()
            expected_cols = len(header)
            for i, row in enumerate(reader):
                if len(row) != expected_cols:
                    QMessageBox.critical(caller, "Unable to load file",
                                         f"Malformed CSV file at line {i + 2}. Expected {expected_cols} columns, found {len(row)}")
                    return

        try:
            self._df = pd.read_csv(filename, on_bad_lines='error', na_filter=True)

            if 'time' in self._df.columns:
                # Assume there is a 'time' column. If not, we'll ask the user
                self._time = self._df['time'].astype(np.float64, copy=True)
            else:
                # Try reading a time in nanoseconds and convert to seconds
                self._time = self._df['time_ns'].astype(np.float64, copy=True) * 1e-9
        except KeyError:
            # Ask the user which column to use for time
            ok, time, offset = time_selector_dialog(caller, self._df)
            if ok:
                self._time = time
                self.time_offset = offset
            else:
                QMessageBox.critical(caller, "Unable to load file",
                                     "No time series selected. Unable to finish loading data.")


class ParquetLoader(FileLoader):
    def __init__(self, caller, filename):
        FileLoader.__init__(self, filename)

        try:
            self._df = pd.read_parquet(filename, engine='pyarrow')

            try:
                self._supervisor_log = _is_supervisor_log(filename, self._df)
                self._time = self._df['time']
            except KeyError:
                # Parquet log doesn't have one of the expected time variables, so ask the user for one.
                ok, time, offset = time_selector_dialog(caller, self._df)
                if ok:
                    self._time = time
                    self.time_offset = offset
                else:
                    QMessageBox.critical(caller, "Unable to load parquet file",
                                                 "No time series selected. Unable to finish loading data.")

        except Exception as ex:
            # If we've gotten here, this likely isn't a parquet file.
            logger.error(f"Error loading parquet file: {ex}")
            QMessageBox.critical(caller, "Unable to load parquet file", f"Unable to load {filename}. Does not appear to be a valid parquet file.")
