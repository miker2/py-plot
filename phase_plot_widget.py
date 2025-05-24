import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QMenu, QAction, QMessageBox
from PyQt5.QtGui import QPalette, QColor, QKeyEvent # Added QKeyEvent for keyPressEvent
from PyQt5.QtCore import Qt, QVariant, QSettings # Added QSettings
import pickle

# Assuming flow_layout.py is in the same directory or Python path
# from flow_layout import FlowLayout 
# For now, I'll mock FlowLayout if it's not available in the environment.
# If it's a custom class, it needs to be provided.
try:
    from flow_layout import FlowLayout
except ImportError:
    print("Warning: FlowLayout not found. Using QVBoxLayout as a placeholder for legend_layout.")
    class FlowLayout(QVBoxLayout): # Placeholder
        def __init__(self, parent=None):
            super().__init__(parent)
            self.widgets = []

        def addWidget(self, widget):
            super().addWidget(widget)
            self.widgets.append(widget)

        def takeAt(self, index):
            if 0 <= index < len(self.widgets):
                widget = self.widgets.pop(index)
                return self.itemAt(index) # QVBoxLayout specific
            return None
        
        def count(self):
            return len(self.widgets)
        
        def clear(self): # Custom clear for placeholder
            while self.count():
                child = self.takeAt(0)
                if child:
                    widget = child.widget()
                    if widget:
                        widget.deleteLater()
            self.widgets = []


from phase_plot_item import PhasePlotItem, PEN_WIDTH # PEN_WIDTH is from phase_plot_item
import numpy as np

class PhasePlotWidget(QWidget):
    # Copied from a typical SubPlotWidget.COLORS, adjust if different
    COLORS = (
        (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255),
        (255, 0, 255), (200, 100, 0), (100, 200, 0), (0, 200, 100), (0, 100, 200),
        (100, 0, 200), (200, 0, 100)
    )
    # Using PEN_WIDTH from PhasePlotItem

    def __init__(self, parent, data_file_widget): # Modified signature
        super().__init__(parent)
        self.data_file_widget = data_file_widget # Store data_file_widget
        self.main_layout = QVBoxLayout(self)

        self.legend_layout = FlowLayout() # Or QVBoxLayout if FlowLayout is not found
        self.main_layout.addLayout(self.legend_layout)

        # Status label for drag-and-drop
        self.status_label = QLabel("Drop X variable, then Y variable to create a trace.")
        self.main_layout.addWidget(self.status_label)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.getPlotItem().hideButtons()
        self.plot_widget.getPlotItem().setMenuEnabled(enableMenu=False, enableViewBoxMenu=False)
        self.main_layout.addWidget(self.plot_widget)

        self._traces = []
        
        # Marker related attributes
        self.cursor_marker_item = None # For scatter plot markers ('o', 's', etc.)
        self.cursor_crosshair_h = None # For horizontal line of crosshair
        self.cursor_crosshair_v = None # For vertical line of crosshair
        self.last_tick_index = 0       # To store the last known tick index

        # Load default marker settings
        settings = QSettings()
        self.current_marker_type = settings.value("phase_plot/default_marker_type", "Circle")
        self.current_marker_size = int(settings.value("phase_plot/default_marker_size", 10))
        # Default color: Red, semi-transparent. Consider making this configurable later.
        self.current_marker_color_tuple = (255, 0, 0, 120) 

        self.time_signal_connection = None # To store the connection
        self.color_index = 0

        self.pending_x_var_name = None
        self.pending_x_source_id = None # Will store filename of the source for X

        self.setAcceptDrops(True) # Enable drop events for the widget
        self.setFocusPolicy(Qt.StrongFocus) # For keyboard events
        
        self.setLayout(self.main_layout)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_A and event.modifiers() & Qt.ControlModifier:
            self.autoscale_plot()
            event.accept()
        else:
            # Important to call super to allow other key events 
            # to be processed if this widget doesn't handle them.
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-DataItem"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-DataItem"):
            byte_array = event.mimeData().retrieveData("application/x-DataItem", QVariant.ByteArray)
            try:
                # data_item is an instance of DataItem from data_model.py
                data_item = pickle.loads(byte_array)
            except Exception as e:
                print(f"Error unpickling DataItem: {e}")
                self.status_label.setText("Error processing dropped item.")
                event.ignore()
                return

            # Assuming data_item has 'name' (variable name) and 'source' (DataFile object with 'filename')
            if not hasattr(data_item, 'name') or not hasattr(data_item, 'source') or not hasattr(data_item.source, 'filename'):
                print("Error: Dropped DataItem is not structured as expected (missing name, source, or source.filename).")
                self.status_label.setText("Error: Invalid data item dropped.")
                QMessageBox.warning(self, "Drop Error", "The dropped item does not contain the necessary information (variable name or source file).")
                event.ignore()
                return

            current_var_name = data_item.name
            current_source_id = data_item.source.filename # filename of the source DataFile

            if self.pending_x_var_name is None:
                # This is the first drop (X variable)
                self.pending_x_var_name = current_var_name
                self.pending_x_source_id = current_source_id
                self.status_label.setText(f"X: {self.pending_x_var_name} (from {self.pending_x_source_id}). Drop Y variable.")
                event.acceptProposedAction()
            else:
                # This is the second drop (Y variable)
                source_x = self.data_file_widget.get_data_file_by_name(self.pending_x_source_id)
                source_y = self.data_file_widget.get_data_file_by_name(current_source_id)

                if source_x and source_y:
                    self.add_trace(source_x, self.pending_x_var_name, source_y, current_var_name)
                    self.status_label.setText("Trace added. Drop X variable, then Y variable for a new trace.")
                else:
                    error_msg = "Error: Could not find data source(s).\n"
                    if not source_x:
                        error_msg += f" - Source for X ('{self.pending_x_source_id}') not found.\n"
                    if not source_y:
                        error_msg += f" - Source for Y ('{current_source_id}') not found.\n"
                    error_msg += "Cleared pending X variable."
                    
                    self.status_label.setText(error_msg)
                    QMessageBox.warning(self, "Error Adding Trace", error_msg)
                
                # Reset pending X for the next trace
                self.clear_pending_x_variable() 
                event.acceptProposedAction()
        else:
            event.ignore()

    def clear_pending_x_variable(self):
        self.pending_x_var_name = None
        self.pending_x_source_id = None
        self.status_label.setText("Drop X variable, then Y variable to create a trace.")


    def add_trace(self, source_x, var_name_x, source_y, var_name_y, color_str=None, name=None):
        if color_str:
            color = pg.mkColor(color_str)
        else:
            r, g, b = self.COLORS[self.color_index % len(self.COLORS)]
            color = pg.mkColor(r, g, b)
            self.color_index += 1
        
        pen = pg.mkPen(color=color, width=PEN_WIDTH)
        
        # Use provided name or generate default for PhasePlotItem
        trace_name = name if name else f"{var_name_x}_vs_{var_name_y}"
        item = PhasePlotItem(source_x, var_name_x, source_y, var_name_y, pen, name=trace_name)
        
        self.plot_widget.getPlotItem().addItem(item.get_qt_item())
        self._traces.append(item)
        self._update_legend()
        return item # Return the item in case the caller wants to interact with it

    def remove_trace(self, phase_plot_item_instance):
        if phase_plot_item_instance in self._traces:
            self.plot_widget.getPlotItem().removeItem(phase_plot_item_instance.get_qt_item())
            self._traces.remove(phase_plot_item_instance)
            self._update_legend()
            self.update_marker(self.last_tick_index) # Update markers as a trace was removed

    def clear_plot(self):
        for item in self._traces:
            self.plot_widget.getPlotItem().removeItem(item.get_qt_item())
        self._traces = []
        self.color_index = 0 # Reset color index
        self._update_legend()
        
        # Explicitly clear/hide all marker types
        if self.cursor_marker_item:
            self.cursor_marker_item.setData(spots=[])
        if self.cursor_crosshair_h:
            self.cursor_crosshair_h.hide()
        if self.cursor_crosshair_v:
            self.cursor_crosshair_v.hide()
        # Ensure last_tick_index is reset or handled appropriately if needed,
        # but for now, just clearing markers is fine.


    def _update_legend(self):
        # Clear existing legend items
        # Proper way to clear FlowLayout items:
        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for trace_item in self._traces:
            # Use var_name_x and var_name_y from PhasePlotItem for legend text
            legend_text = f"x: {trace_item.var_name_x} - y: {trace_item.var_name_y}"
            label = QLabel(legend_text)
            
            # Set text color to match trace color
            qcolor = trace_item.pen.color() # This is a QColor
            label.setStyleSheet(f"color: {qcolor.name()}")
            
            self.legend_layout.addWidget(label)

    def update_marker(self, tick_index):
        self.last_tick_index = tick_index

        valid_points = []
        if self._traces: # Only proceed if there are traces
            for trace in self._traces:
                point_data = trace.get_data_at_tick(tick_index)
                if point_data is not None:
                    valid_points.append(point_data) # Store as (x,y) tuples

        # Hide all markers initially
        if self.cursor_marker_item:
            self.cursor_marker_item.setData(spots=[]) # Clear data to hide
        if self.cursor_crosshair_h:
            self.cursor_crosshair_h.hide()
        if self.cursor_crosshair_v:
            self.cursor_crosshair_v.hide()

        if not valid_points: # No valid points at this tick_index for any trace
            return

        # Marker Type Handling
        if self.current_marker_type == "Crosshairs":
            if self.cursor_crosshair_h is None or self.cursor_crosshair_v is None:
                # Use only RGB for pen color, alpha is not typically used for InfiniteLine pen
                crosshair_pen = pg.mkPen(color=self.current_marker_color_tuple[:3], width=1)
                self.cursor_crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=crosshair_pen)
                self.cursor_crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=crosshair_pen)
                self.plot_widget.addItem(self.cursor_crosshair_h, ignoreBounds=True)
                self.plot_widget.addItem(self.cursor_crosshair_v, ignoreBounds=True)
            
            # Use the first point in valid_points for crosshair position
            primary_point = valid_points[0] # This is an (x,y) tuple
            self.cursor_crosshair_h.setPos(primary_point[1]) # Horizontal line at Y value
            self.cursor_crosshair_v.setPos(primary_point[0]) # Vertical line at X value
            self.cursor_crosshair_h.show()
            self.cursor_crosshair_v.show()
        else: # Scatter plot markers ("Circle", "Square", etc.)
            symbol_map = {"Circle": "o", "Square": "s"} # Add more if needed (e.g. "Star": "*", "Plus": "+", "Triangle": "t")
            actual_symbol = symbol_map.get(self.current_marker_type, "o") # Default to circle

            if self.cursor_marker_item is None:
                self.cursor_marker_item = pg.ScatterPlotItem(pen=pg.mkPen(None)) # No border pen for markers
                self.plot_widget.addItem(self.cursor_marker_item)
            
            self.cursor_marker_item.setSize(self.current_marker_size)
            self.cursor_marker_item.setBrush(pg.mkBrush(*self.current_marker_color_tuple))
            
            # Prepare spots data with the correct symbol for all points
            spots_data = [{'pos': p, 'symbol': actual_symbol, 'data': 1} for p in valid_points]
            self.cursor_marker_item.setData(spots=spots_data)
            # ScatterPlotItem is automatically shown when data is set.

    def set_marker_style(self, marker_type=None, size=None, color_tuple=None):
        """
        Sets the style for the cursor marker.
        If a parameter is None, the existing or default setting for that aspect is used.
        """
        settings = QSettings()
        if marker_type is not None:
            self.current_marker_type = marker_type
        else: # Re-read from settings if not provided (e.g. if called from preferences update)
            self.current_marker_type = settings.value("phase_plot/default_marker_type", "Circle")

        if size is not None:
            self.current_marker_size = int(size)
        else:
            self.current_marker_size = int(settings.value("phase_plot/default_marker_size", 10))

        if color_tuple is not None:
            self.current_marker_color_tuple = color_tuple
        # else: keep the current_marker_color_tuple (e.g. (255,0,0,120) or allow future setting)

        # Apply changes immediately by refreshing the marker display
        self.update_marker(self.last_tick_index)
    
    def autoscale_plot(self):
        self.plot_widget.getPlotItem().autoRange()

    def _create_context_menu(self):
        menu = QMenu(self)
        autoscale_action = menu.addAction("Autoscale Plot")
        autoscale_action.triggered.connect(self.autoscale_plot)
        
        clear_action = menu.addAction("Clear Plot")
        clear_action.triggered.connect(self.clear_plot)

        menu.addSeparator()

        clear_pending_x_action = menu.addAction("Clear Pending X Variable")
        clear_pending_x_action.triggered.connect(self.clear_pending_x_variable)
        clear_pending_x_action.setEnabled(self.pending_x_var_name is not None)
        
        # TODO: Add action to add new trace? (might be complex here)
        # TODO: Add action to remove specific trace? (needs sub-menu or dialog)
        return menu

    def contextMenuEvent(self, event):
        menu = self._create_context_menu()
        menu.exec_(event.globalPos())

    def connect_to_time_signal(self, time_emitter_signal):
        # Disconnect previous connection if any
        if self.time_signal_connection:
            try:
                time_emitter_signal.disconnect(self.time_signal_connection)
            except TypeError: # Catches "native Qt signal is not connected"
                pass 
        
        self.time_signal_connection = time_emitter_signal.connect(self.update_marker)

    def get_plot_config(self):
        return [item.get_plot_spec() for item in self._traces]

    def load_plot_config(self, config_list): # Removed data_file_widget from args, use self.data_file_widget
        self.clear_plot()
        for spec in config_list:
            source_x_id = spec.get('source_x_id') # Updated key from PhasePlotItem
            source_y_id = spec.get('source_y_id') # Updated key from PhasePlotItem
            var_x = spec.get('x_var')
            var_y = spec.get('y_var')
            color = spec.get('color')
            name = spec.get('name') # Get trace name from spec

            if not all([source_x_id, var_x, source_y_id, var_y]): # Check all essential parts
                print(f"Warning: Incomplete plot specification: {spec}. Skipping.")
                continue
            
            if self.data_file_widget is None:
                print("Error: data_file_widget is not available in PhasePlotWidget. Cannot load plot config.")
                QMessageBox.critical(self, "Load Error", "Data file handler not available. Cannot load traces.")
                return

            try:
                # Use self.data_file_widget.get_data_file_by_name (as it exists in DataFileWidget)
                source_x = self.data_file_widget.get_data_file_by_name(source_x_id)
                source_y = self.data_file_widget.get_data_file_by_name(source_y_id)
            except AttributeError:
                 print(f"Error: self.data_file_widget is missing 'get_data_file_by_name' method.")
                 QMessageBox.critical(self, "Load Error", "Data file handler is missing an expected method.")
                 return # Stop further processing
            except Exception as e: # Catch other errors from get_data_file_by_name
                 print(f"Error retrieving source: {e} for spec {spec}")
                 QMessageBox.warning(self, "Load Error", f"Error retrieving source for trace '{name or f'{var_x}/{var_y}'}': {e}")
                 continue


            if source_x and source_y:
                self.add_trace(source_x, var_x, source_y, var_y, color_str=color, name=name)
            else:
                warning_msg = f"Warning: Could not find sources for plot specification: {spec}.\n"
                if not source_x:
                    warning_msg += f" - Source X ('{source_x_id}') not found.\n"
                if not source_y:
                    warning_msg += f" - Source Y ('{source_y_id}') not found.\n"
                print(warning_msg)
                QMessageBox.warning(self, "Load Warning", warning_msg)

    def get_traces(self):
        """Returns the list of PhasePlotItem instances."""
        return self._traces

    def get_plot_widget(self):
        """Returns the internal pyqtgraph.PlotWidget instance."""
        return self.plot_widget

# Example Usage (for testing purposes, if run directly)
if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    import sys
    import time

    # Mock Data Source for testing
    class MockDataSource:
        def __init__(self, name, data_map):
            self._name = name
            self.data = data_map # e.g., {'rpm': np.array([...]), 'torque': np.array([...])}
        
        def model(self): # To mimic the structure PhasePlotItem expects
            return self
        
        def get_data_by_name(self, var_name):
            return self.data.get(var_name)

        def name(self): # For get_plot_spec and load_plot_config
            return self._name

    # Mock DataFileWidget for testing load_plot_config
    class MockDataFileWidget:
        def __init__(self):
            self.sources = {} # filename: MockDataSource

        def add_source(self, source):
            # In actual DataFileWidget, sources are likely stored by filename
            self.sources[source.filename] = source # Assuming source has .filename
        
        def get_data_file_by_name(self, source_id): # Matching method name in DataFileWidget
            return self.sources.get(source_id)
        
        # Mock DataItem for drag-drop testing
        class MockDataItem:
            def __init__(self, name, source_obj):
                self.name = name # var_name
                self.source = source_obj # MockDataSource which has .filename

    # Mock time emitter signal
    class TimeEmitter:
        def __init__(self):
            self.tickValueChanged = pg.SignalProxy(None, slot=self.emit_tick, PUSH_MODE="Weakref") # Mocking a signal
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)
            return callback # Return something to "disconnect"

        def disconnect(self, callback_ref):
            if callback_ref in self._callbacks:
                self._callbacks.remove(callback_ref)
        
        def emit_tick(self, tick):
            for cb in self._callbacks:
                cb(tick)

    app = QApplication(sys.argv)
    
    # Create mock data
    t = np.linspace(0, 10, 500)
    source1_data_x = np.sin(t)
    source1_data_y = np.cos(t)
    source2_data_x = 0.5 * np.sin(t + np.pi/2)
    source2_data_y = 0.5 * np.cos(t - np.pi/2)

    # For MockDataSource, add filename attribute
    MockDataSource.__init__ = lambda self, filename, data_map: (setattr(self, 'filename', filename), setattr(self, 'data', data_map))
    mock_source1 = MockDataSource("EngineData.csv", {'rpm': source1_data_x, 'load': source1_data_y})
    mock_source2 = MockDataSource("TransmissionData.log", {'speed': source2_data_x, 'torque': source2_data_y})
    
    mock_dfw_for_init = MockDataFileWidget() # For PhasePlotWidget constructor
    mock_dfw_for_init.add_source(mock_source1)
    mock_dfw_for_init.add_source(mock_source2)


    # Setup widget
    main_window = PhasePlotWidget(parent=None, data_file_widget=mock_dfw_for_init)
    
    # Add traces
    trace1 = main_window.add_trace(mock_source1, 'rpm', mock_source1, 'load', name="Engine RPM vs Load")
    trace2 = main_window.add_trace(mock_source2, 'speed', mock_source2, 'torque', name="Trans Speed vs Torque")

    # Test remove trace
    # main_window.remove_trace(trace1)

    # Test clear plot
    # main_window.clear_plot()
    # main_window.add_trace(mock_source1, 'rpm', mock_source1, 'load') # Re-add one

    main_window.show()
    main_window.autoscale_plot()

    # Test marker
    mock_time_emitter = TimeEmitter()
    main_window.connect_to_time_signal(mock_time_emitter)

    # Test get_plot_config
    config = main_window.get_plot_config()
    print("Plot Config:", config)

    # Test load_plot_config (uses self.data_file_widget passed in constructor)
    # To test load, clear current traces and load them back from config
    # print("Plot Config before save:", config)
    # main_window.clear_plot() 
    # print("Loading config...")
    # main_window.load_plot_config(config) # No longer needs mock_dfw as arg
    # print("Config loaded.")
    # main_window.autoscale_plot()


    # --- Test Drag and Drop ---
    # Simulate a drop event
    def simulate_drop(var_name, source_obj):
        data_item_instance = MockDataItem(var_name, source_obj)
        pickled_data = pickle.dumps(data_item_instance)
        
        # Create a mock MimeData
        class MockMimeData:
            def __init__(self):
                self._data = {}
            def hasFormat(self, mime_type):
                return mime_type in self._data
            def retrieveData(self, mime_type, type_):
                return self._data.get(mime_type)
            def setData(self, mime_type, data):
                self._data[mime_type] = data
        
        mime = MockMimeData()
        mime.setData("application/x-DataItem", pickled_data)

        # Create a mock DropEvent
        class MockDropEvent:
            def __init__(self, mime_data, source_widget):
                self._mimeData = mime_data
                self._source_widget = source_widget # Mock the source of the drag
            def mimeData(self):
                return self._mimeData
            def source(self): # To mimic event.source()
                return self._source_widget
            def acceptProposedAction(self):
                print("Drop event accepted.")
            def ignore(self):
                print("Drop event ignored.")

        # Mock the VarListWidget as the source of the drag event
        mock_var_list_widget = QWidget() # Placeholder

        drop_event = MockDropEvent(mime, mock_var_list_widget)
        main_window.dropEvent(drop_event)

    # Simulate dropping variable for X axis
    print("\nSimulating drop for X axis (rpm from EngineData.csv)...")
    simulate_drop('rpm', mock_source1) 
    print(f"Pending X: {main_window.pending_x_var_name} from {main_window.pending_x_source_id}")

    # Simulate dropping variable for Y axis
    print("\nSimulating drop for Y axis (load from EngineData.csv)...")
    simulate_drop('load', mock_source1)
    print(f"Pending X after Y drop: {main_window.pending_x_var_name} from {main_window.pending_x_source_id}")
    print(f"Number of traces: {len(main_window.get_traces())}")
    if main_window.get_traces():
        print(f"Trace 1 spec: {main_window.get_traces()[0].get_plot_spec()}")

    # Simulate dropping another X
    print("\nSimulating drop for X axis (speed from TransmissionData.log)...")
    simulate_drop('speed', mock_source2)
    print(f"Pending X: {main_window.pending_x_var_name} from {main_window.pending_x_source_id}")
    
    # Test clear pending X via context menu action (if possible to simulate menu click easily)
    # Alternatively, call the method directly
    # main_window.clear_pending_x_variable()
    # print(f"Pending X after clear: {main_window.pending_x_var_name}")


    # Simulate dropping another Y
    print("\nSimulating drop for Y axis (torque from TransmissionData.log)...")
    simulate_drop('torque', mock_source2)
    print(f"Pending X after Y drop: {main_window.pending_x_var_name} from {main_window.pending_x_source_id}")
    print(f"Number of traces: {len(main_window.get_traces())}")
    if len(main_window.get_traces()) > 1:
        print(f"Trace 2 spec: {main_window.get_traces()[1].get_plot_spec()}")
    
    main_window.autoscale_plot()


    # Simulate time ticks for marker update
    def time_updater():
        for i in range(len(t)):
            mock_time_emitter.emit_tick(i)
            QApplication.processEvents() # Allow GUI to update
            time.sleep(0.02) # 20 ms delay
        print("Finished time simulation.")

    # Create a simple button to start the time simulation
    button = QPushButton("Start Time Simulation")
    main_window.main_layout.addWidget(button) # Add button to layout
    button.clicked.connect(time_updater)


    sys.exit(app.exec_())
