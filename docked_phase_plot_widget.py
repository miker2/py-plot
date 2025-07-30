from PyQt5.QtWidgets import QTabWidget, QInputDialog, QMenu, QAction
from PyQt5.QtCore import Qt, QSettings # QSettings might not be directly used if DockedWidget handles it

from docked_widget import DockedWidget
from phase_plot_widget import PhasePlotWidget

class DockedPhasePlotWidget(DockedWidget):
    def __init__(self, parent, plot_manager_instance, data_file_widget_instance):
        self.plot_manager = plot_manager_instance
        self.data_file_widget = data_file_widget_instance

        self.tabs = QTabWidget()

        super().__init__("Phase Plots", parent)

        self.setWidget(self.tabs) # Sets the main widget for the DockedWidget

        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setTabBarAutoHide(False) # Or True, as per preference

        # Connect signals for tab management
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.tabBar().customContextMenuRequested.connect(self.on_tab_bar_context_menu)
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBarDoubleClicked.connect(self.rename_tab_dialog)

        # _read_settings is called by DockedWidget's constructor after this __init__
        # So, tab loading will happen there.
        # If _read_settings doesn't load any tabs, we add a default one.
        # This check is now moved to the end of _read_settings itself.

    def add_phase_plot_tab(self, name=None, plot_config=None):
        # PhasePlotWidget now takes data_file_widget in its constructor.
        new_phase_plot_widget = PhasePlotWidget(parent=self.tabs, data_file_widget=self.data_file_widget)

        # Connect its time signal. PhasePlotWidget has connect_to_time_signal method.
        # Let's use that for consistency if the signal name might vary or needs internal management.
        # However, direct connection to update_marker is also fine and currently used.
        # For now, keeping the direct connection as it's already in place.
        # Option 1: Direct connection (current approach)
        if hasattr(self.plot_manager, 'tickValueChanged'):
            time_signal = self.plot_manager.tickValueChanged
        elif hasattr(self.plot_manager, 'timeValueChanged'):
            time_signal = self.plot_manager.timeValueChanged
        else:
            time_signal = None
            print("Warning: PlotManager has neither tickValueChanged nor timeValueChanged signal for PhasePlotWidget.")

        if time_signal:
            # If PhasePlotWidget.connect_to_time_signal is preferred:
            # new_phase_plot_widget.connect_to_time_signal(time_signal)
            # For now, direct connection as it was:
            time_signal.connect(new_phase_plot_widget.update_marker)


        tab_name = name if name is not None else f"Phase Plot {self.tabs.count() + 1}"

        index = self.tabs.addTab(new_phase_plot_widget, tab_name)
        self.tabs.setCurrentWidget(new_phase_plot_widget)

        if plot_config is not None:
            # PhasePlotWidget.load_plot_config now uses self.data_file_widget
            new_phase_plot_widget.load_plot_config(plot_config)

        return new_phase_plot_widget

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        if widget:
            # Disconnect signal to avoid issues during deletion
            if hasattr(self.plot_manager, 'tickValueChanged'):
                 try: widget.update_marker.disconnect() # Disconnect all signals to this slot
                 except TypeError: pass # already disconnected or never connected
            elif hasattr(self.plot_manager, 'timeValueChanged'):
                 try: widget.update_marker.disconnect()
                 except TypeError: pass

            self.tabs.removeTab(index)
            widget.deleteLater() # Important for cleanup

    def rename_tab_dialog(self, index):
        if index < 0 or index >= self.tabs.count(): # Check if index is valid
            # Double-clicking on empty tab bar area gives index -1 for some Qt versions
            return

        old_name = self.tabs.tabText(index)
        new_name, ok = QInputDialog.getText(self, "Rename Tab", "Enter new tab name:", text=old_name)

        if ok and new_name:
            self.tabs.setTabText(index, new_name)

    def on_tab_bar_context_menu(self, point):
        menu = QMenu(self)

        add_action = menu.addAction("Add New Phase Plot")
        add_action.triggered.connect(lambda: self.add_phase_plot_tab()) # Lambda to call without args

        tab_index = self.tabs.tabBar().tabAt(point)
        if tab_index != -1: # Check if the click was on an actual tab
            menu.addSeparator()

            rename_action = menu.addAction("Rename Tab")
            rename_action.triggered.connect(lambda checked=False, idx=tab_index: self.rename_tab_dialog(idx))

            close_action = menu.addAction("Close Tab")
            close_action.triggered.connect(lambda checked=False, idx=tab_index: self.close_tab(idx))

        menu.exec_(self.tabs.tabBar().mapToGlobal(point))

    def _write_settings(self):
        # DockedWidget's _write_settings already calls self.settings.beginGroup(self.windowTitle())
        super()._write_settings() # Call parent method first

        # self.settings should already be scoped by DockedWidget to self.windowTitle()
        self.settings.beginWriteArray("tabs")
        for i in range(self.tabs.count()):
            self.settings.setArrayIndex(i)
            tab_widget = self.tabs.widget(i)
            if isinstance(tab_widget, PhasePlotWidget): # Ensure it's the correct widget type
                self.settings.setValue("name", self.tabs.tabText(i))
                self.settings.setValue("plot_config", tab_widget.get_plot_config())
            else:
                # Handle placeholder or unexpected widget type if necessary
                self.settings.setValue("name", self.tabs.tabText(i))
                self.settings.setValue("plot_config", []) # Save empty config for non-PhasePlotWidgets
                print(f"Warning: Tab {i} ('{self.tabs.tabText(i)}') is not a PhasePlotWidget. Saving empty config.")

        self.settings.endArray()
        # DockedWidget's _write_settings calls self.settings.endGroup()

    def _read_settings(self):
        # DockedWidget's _read_settings already calls self.settings.beginGroup(self.windowTitle())
        super()._read_settings() # Call parent method first

        # self.settings should already be scoped
        count = self.settings.beginReadArray("tabs")
        for i in range(count):
            self.settings.setArrayIndex(i)
            name = self.settings.value("name")
            plot_config = self.settings.value("plot_config")
            # Ensure plot_config is a list, QSettings might return single item if array had one element
            if not isinstance(plot_config, list) and plot_config is not None:
                plot_config = [plot_config]
            elif plot_config is None: # Handle case where plot_config might be None
                plot_config = []

            self.add_phase_plot_tab(name=name, plot_config=plot_config)
        self.settings.endArray()

        if self.tabs.count() == 0: # If no tabs were loaded (e.g., first run)
            self.add_phase_plot_tab(name="Default Phase Plot")
        # DockedWidget's _read_settings calls self.settings.endGroup()

    # closeEvent is handled by DockedWidget, which calls _write_settings.
    # Child QWidgets (QTabWidget, PhasePlotWidgets) are managed by Qt's
    # parent-child hierarchy for deletion when DockedPhasePlotWidget is closed.
    # The explicit deleteLater in close_tab handles individual tab closures.

# Example usage (requires DockedWidget, PhasePlotWidget, and mock plot_manager, data_file_widget):
if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication, QMainWindow
    import sys

    # --- Mockups for testing ---
    class MockPlotManager:
        def __init__(self):
            # Mock a signal like tickValueChanged or timeValueChanged
            self.tickValueChanged = pg.SignalProxy(None, slot=self.emit_tick, PUSH_MODE="Weakref") # Example, requires pyqtgraph for SignalProxy
            self._callbacks = []

        def connect_tick_value_changed(self, func): # Actual connection mechanism might vary
            # self.tickValueChanged.connect(func)
            self._callbacks.append(func)
            return func

        def disconnect_tick_value_changed(self, func_ref):
            # self.tickValueChanged.disconnect(func_ref)
            if func_ref in self._callbacks:
                self._callbacks.remove(func_ref)

        def emit_tick(self, tick_value): # Simulate emitting the signal
            # self.tickValueChanged.emit(tick_value) # If using actual pg.SignalProxy
            for cb in self._callbacks:
                cb(tick_value)

    class MockDataFileWidget:
        def __init__(self):
            self.sources = {} # Assuming it stores by filename now for consistency with PhasePlotWidget needs

        def add_source(self, source): # Assuming source has a 'filename' attribute
            if hasattr(source, 'filename'):
                self.sources[source.filename] = source
            else: # Fallback for older mock source structure if any
                self.sources[source.name()] = source

        # This method is used by PhasePlotWidget.load_plot_config
        def get_data_file_by_name(self, source_id):
            return self.sources.get(source_id)

        # Keep get_source_by_id if it's used by other parts of the test setup,
        # but ensure get_data_file_by_name is what PhasePlotWidget expects.
        def get_source_by_id(self, source_id): # Potentially an alias or different lookup
            return self.sources.get(source_id)


    # Need pyqtgraph for SignalProxy if used in MockPlotManager
    import pyqtgraph as pg

    # --- Main Application Setup ---
    app = QApplication(sys.argv)
    # Required for QSettings to work without specifying org/app name
    app.setOrganizationName("TestOrg")
    app.setApplicationName("TestApp")

    main_window = QMainWindow()
    main_window.setCentralWidget(QLabel("Main Window Area")) # Placeholder

    # Instantiate mock dependencies
    mock_plot_mgr = MockPlotManager()
    mock_df_widget = MockDataFileWidget()

    # Create and add the docked widget
    docked_phase_plot = DockedPhasePlotWidget(main_window, mock_plot_mgr, mock_df_widget)
    main_window.addDockWidget(Qt.RightDockWidgetArea, docked_phase_plot)

    # Example: Add some mock data sources to data_file_widget for testing config load
    import numpy as np
    class MockDataSource:
        def __init__(self, filename, data_map): # Changed 'name' to 'filename' for clarity
            self.filename = filename # Ensure filename attribute exists
            self._name = filename # Keep _name if other parts of mock rely on it
            self.data = data_map
        def model(self): return self
        def get_data_by_name(self, var_name): return self.data.get(var_name)
        def name(self): return self._name # For compatibility if .name() is still used by some mock parts

    source1 = MockDataSource("Engine.csv", {"rpm": np.array([1,2,3]), "torque": np.array([10,20,30])})
    mock_df_widget.add_source(source1)

    main_window.show()
    sys.exit(app.exec_())
