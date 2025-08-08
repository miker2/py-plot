from PyQt5.QtWidgets import QTabWidget, QInputDialog, QMenu, QAction
from PyQt5.QtCore import Qt

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

        # Add a default tab since we're not loading from settings anymore
        self.add_phase_plot_tab(name="Default Phase Plot")

    def add_phase_plot_tab(self, name=None, plot_config=None):
        # PhasePlotWidget now takes data_file_widget and plot_manager in its constructor.
        new_phase_plot_widget = PhasePlotWidget(parent=self.tabs, data_file_widget=self.data_file_widget, plot_manager=self.plot_manager)

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
            # Connect marker updates (individual traces connect themselves to value updates)
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


    def update_all_marker_settings(self):
        """Update marker settings for all phase plot widgets in all tabs"""
        for i in range(self.tabs.count()):
            phase_plot_widget = self.tabs.widget(i)
            if hasattr(phase_plot_widget, 'update_marker_settings_from_preferences'):
                phase_plot_widget.update_marker_settings_from_preferences()

    # closeEvent is handled by DockedWidget, which calls _write_settings.
    # Child QWidgets (QTabWidget, PhasePlotWidgets) are managed by Qt's
    # parent-child hierarchy for deletion when DockedPhasePlotWidget is closed.
    # The explicit deleteLater in close_tab handles individual tab closures.
