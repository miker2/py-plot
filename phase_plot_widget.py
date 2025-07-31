import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QMenu, QAction, QMessageBox
from PyQt5.QtGui import QPalette, QColor, QKeyEvent, QPixmap, QPainter # Added QKeyEvent for keyPressEvent
from PyQt5.QtCore import Qt, QVariant, QSettings, QRect # Added QSettings
import pickle
import os

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
from custom_plot_item import CustomPlotItem
import numpy as np

class PhasePlotCustomItem(CustomPlotItem):
    """Customized version of CustomPlotItem for phase plots"""

    def __init__(self, parent, phase_plot_item):
        self.phase_plot_item = phase_plot_item
        self.cursor_visible = True  # Track cursor visibility for this trace

        # Create a mock trace object that CustomPlotItem expects
        # We'll override the methods that need different behavior
        mock_plot_data_item = phase_plot_item.get_qt_item()
        mock_source = None  # We'll handle sources differently
        current_tick = 0    # Phase plots don't use time ticks

        super().__init__(parent, mock_plot_data_item, mock_source, current_tick)

    def _generate_label(self):
        """Override to show phase plot format with file prefixes: 'x: F#:var_name_x - y: F#:var_name_y'"""
        # Get source info from the phase plot item
        source_x = self.phase_plot_item.source_x
        source_y = self.phase_plot_item.source_y

        # Create prefixes for X and Y variables
        x_prefix = ""
        y_prefix = ""

        if hasattr(source_x, 'idx') and source_x.idx is not None:
            x_prefix = f"F{source_x.idx}:"
        if hasattr(source_y, 'idx') and source_y.idx is not None:
            y_prefix = f"F{source_y.idx}:"

        base_label = f"x: {x_prefix}{self.phase_plot_item.var_name_x} - y: {y_prefix}{self.phase_plot_item.var_name_y}"

        # Add current values if we have a valid tick
        if hasattr(self, '_tick') and self._tick is not None:
            x_val, y_val = self._get_current_values(self._tick)
            if x_val is not None and y_val is not None:
                # Format values similar to CustomPlotItem
                x_str = self._format_value(x_val)
                y_str = self._format_value(y_val)
                return f"{base_label} ({x_str}, {y_str})"

        return base_label

    def on_time_changed(self, time):
        """Override to update phase plot values at current time"""
        # Convert time to tick index for both X and Y sources
        import graph_utils

        # Get tick indices for both sources (they might be different if sources have different sampling rates)
        try:
            # Use the X source time for tick calculation (similar to CustomPlotItem)
            self._tick = graph_utils.time_to_tick(self.phase_plot_item.source_x.time, time)
        except Exception as e:
            print(f"Error in time_to_tick conversion: {e}")
            self._tick = 0

        # Update the label to show current values
        self.setText(self._generate_label())

    def _get_current_values(self, tick):
        """Get the current X and Y values at the given tick index"""
        try:
            # Get the data point at the current tick from the phase plot item
            point_data = self.phase_plot_item.get_data_at_tick(tick)
            if point_data is not None:
                return point_data  # Returns (x, y) tuple
        except Exception:
            pass
        return None, None

    def _format_value(self, value):
        """Format a value for display, similar to CustomPlotItem"""
        if isinstance(value, (int, np.integer)):
            return f"{value:d}"
        else:
            return f"{value:.6g}"

    def remove_item(self):
        """Override to call phase plot's remove method"""
        self.parent().remove_trace(self.phase_plot_item)

    def toggle_trace(self, is_checked):
        """Override to work with phase plot items"""
        if is_checked:
            # Hide the trace
            self.phase_plot_item.get_qt_item().hide()
        else:
            # Show the trace
            self.phase_plot_item.get_qt_item().show()

        # Update label appearance (call parent method for consistent styling)
        super().toggle_trace(is_checked)

        # Update markers to show/hide cursor based on trace visibility
        self.parent().update_marker(self.parent().last_tick_index)

    def update_color(self, color_str):
        """Override to update both the phase plot item and the label"""
        # Update the phase plot item's pen
        pen = pg.mkPen(color=color_str, width=PEN_WIDTH)
        self.phase_plot_item.pen = pen
        self.phase_plot_item.get_qt_item().setPen(pen)

        # Update the label appearance (call parent method)
        super().update_color(color_str)

    def create_menu(self):
        """Override to add cursor visibility option"""
        menu = super().create_menu()

        # Add separator before cursor options
        menu.addSeparator()

        # Add cursor visibility toggle
        cursor_action = menu.addAction("Hide cursor")
        cursor_action.setCheckable(True)
        cursor_action.setChecked(not self.cursor_visible)
        cursor_action.triggered.connect(self.toggle_cursor_visibility)

        return menu

    def toggle_cursor_visibility(self, is_checked):
        """Toggle cursor visibility for this trace"""
        self.cursor_visible = not is_checked
        # Update the menu text
        action = self.sender()
        action.setText("Show cursor" if is_checked else "Hide cursor")

        # Trigger marker update to show/hide this trace's cursor
        self.parent().update_marker(self.parent().last_tick_index)

class PhasePlotWidget(QWidget):
    # Use the exact same colors as SubPlotWidget for consistency
    COLORS = ('#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#a65628', '#D4C200', '#f781bf')
    # Using PEN_WIDTH from PhasePlotItem

    def __init__(self, parent, data_file_widget, plot_manager=None): # Modified signature
        super().__init__(parent)
        self.data_file_widget = data_file_widget # Store data_file_widget
        self.plot_manager = plot_manager # Store plot_manager
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

        # Marker related attributes - now stored per trace
        self.trace_markers = {}  # Dictionary to store markers per trace: trace_id -> marker_items
        self.last_tick_index = 0  # To store the last known tick index

        # Load default marker settings
        settings = QSettings()
        self.current_marker_type = settings.value("phase_plot/default_marker_type", "Circle")
        self.current_marker_size = int(settings.value("phase_plot/default_marker_size", 10))
        # Default color: Black, more opaque for better visibility
        default_color = settings.value("phase_plot/marker_color", "0,0,0,200")  # "R,G,B,A" format
        color_parts = [int(x) for x in default_color.split(',')]
        self.current_marker_color_tuple = tuple(color_parts)

        self.time_signal_connection = None # To store the connection
        self.cidx = 0  # Color index, same as SubPlotWidget

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

            # Get variable name from DataItem and source info from the drag source
            if not hasattr(data_item, 'var_name'):
                print("Error: Dropped DataItem is missing var_name property.")
                self.status_label.setText("Error: Invalid data item dropped.")
                QMessageBox.warning(self, "Drop Error", "The dropped item does not contain the necessary information (variable name or source file).")
                event.ignore()
                return

            current_var_name = data_item.var_name
            drag_source = event.source()

            # Get the filename from the drag source (the widget that initiated the drag)
            if not hasattr(drag_source, 'filename'):
                print("Error: Drag source does not have filename attribute.")
                self.status_label.setText("Error: Cannot identify data source.")
                QMessageBox.warning(self, "Drop Error", "The dropped item does not contain the necessary information (variable name or source file).")
                event.ignore()
                return

            current_source_id = drag_source.filename

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
            color = pg.mkColor(self._get_color(self.cidx))
            self.cidx += 1

        pen = pg.mkPen(color=color, width=PEN_WIDTH)

        # Use provided name or generate default for PhasePlotItem
        trace_name = name if name else f"{var_name_x}_vs_{var_name_y}"
        item = PhasePlotItem(source_x, var_name_x, source_y, var_name_y, pen, name=trace_name)

        self.plot_widget.getPlotItem().addItem(item.get_qt_item())

        # Create the legend label (following SubPlotWidget pattern)
        label = PhasePlotCustomItem(self, item)
        self._traces.append(label)  # Store the legend item, like SubPlotWidget does
        self.legend_layout.addWidget(label)

        # Connect to time signal directly using stored plot_manager (similar to SubPlotWidget)
        if self.plot_manager and hasattr(self.plot_manager, 'timeValueChanged'):
            self.plot_manager.timeValueChanged.connect(label.on_time_changed)
            print(f"Connected phase plot label to timeValueChanged signal")
        elif self.plot_manager and hasattr(self.plot_manager, 'tickValueChanged'):
            self.plot_manager.tickValueChanged.connect(label.on_time_changed)
            print(f"Connected phase plot label to tickValueChanged signal")
        else:
            print(f"Warning: No plot_manager available for time signal connection")

        # Connect to source onClose signals to automatically remove trace when files are closed
        if hasattr(source_x, 'onClose'):
            source_x.onClose.connect(lambda label=label: self.remove_trace(label.phase_plot_item))
        if hasattr(source_y, 'onClose') and source_y != source_x:
            source_y.onClose.connect(lambda label=label: self.remove_trace(label.phase_plot_item))

        return item # Return the item in case the caller wants to interact with it

    def remove_trace(self, phase_plot_item_instance):
        # Find the legend label that corresponds to this phase plot item
        label_to_remove = None
        for label in self._traces:
            if label.phase_plot_item == phase_plot_item_instance:
                label_to_remove = label
                break

        if label_to_remove:
            # Clean up markers for this trace
            trace_id = id(label_to_remove)
            if trace_id in self.trace_markers:
                marker_items = self.trace_markers[trace_id]
                # Remove all marker items from the plot
                for marker_item in marker_items.values():
                    self.plot_widget.removeItem(marker_item)
                # Remove from our marker tracking
                del self.trace_markers[trace_id]

            # Remove the plot item from the plot
            self.plot_widget.getPlotItem().removeItem(phase_plot_item_instance.get_qt_item())
            # Remove the label from the layout and close it
            self.legend_layout.removeWidget(label_to_remove)
            label_to_remove.close()
            # Remove from our traces list
            self._traces.remove(label_to_remove)

            # Decrement color index (same as SubPlotWidget)
            self.cidx = max(0, self.cidx - 1)

            # Recolor all remaining traces to maintain proper color sequence
            for idx in range(self.legend_layout.count()):
                widget_item = self.legend_layout.itemAt(idx)
                if widget_item:
                    label = widget_item.widget()
                    if hasattr(label, 'update_color'):
                        label.update_color(self._get_color(idx))

            # Update markers since trace was removed
            self.update_marker(self.last_tick_index)

    def clear_plot(self):
        for label in self._traces:
            # Remove the plot item from the plot
            self.plot_widget.getPlotItem().removeItem(label.phase_plot_item.get_qt_item())
            # Remove the label from the layout and close it
            self.legend_layout.removeWidget(label)
            label.close()

        # Clean up all markers
        for trace_id, marker_items in self.trace_markers.items():
            for marker_item in marker_items.values():
                self.plot_widget.removeItem(marker_item)
        self.trace_markers.clear()

        self._traces = []
        self.cidx = 0 # Reset color index


    def _update_legend(self):
        # This method is no longer needed since we manage legend items directly in add_trace()
        # Keeping it for compatibility but it's now a no-op
        pass

    def update_marker(self, tick_index):
        self.last_tick_index = tick_index

        # Hide all existing markers first
        for trace_id, marker_items in self.trace_markers.items():
            if self.current_marker_type == "Crosshairs":
                if 'crosshair_h' in marker_items:
                    marker_items['crosshair_h'].hide()
                if 'crosshair_v' in marker_items:
                    marker_items['crosshair_v'].hide()
            else:
                if 'scatter' in marker_items:
                    marker_items['scatter'].setData(spots=[])

        if not self._traces:
            return

        # Process each trace individually
        for trace_idx, label in enumerate(self._traces):
            # Check if trace is hidden (uses the _hidden attribute from CustomPlotItem)
            trace_is_hidden = getattr(label, '_hidden', False)

            # Skip if cursor should be hidden (either trace is hidden OR cursor is explicitly hidden)
            if trace_is_hidden or not label.cursor_visible:
                continue

            point_data = label.phase_plot_item.get_data_at_tick(tick_index)
            if point_data is None:
                continue

            trace_id = id(label)  # Use object id as unique trace identifier

            # Initialize marker items for this trace if needed
            if trace_id not in self.trace_markers:
                self.trace_markers[trace_id] = {}

            # Handle different marker types
            if self.current_marker_type == "Crosshairs":
                self._update_crosshair_marker(trace_id, point_data)
            else:
                self._update_scatter_marker(trace_id, point_data)

    def _update_crosshair_marker(self, trace_id, point_data):
        """Update crosshair marker for a specific trace"""
        marker_items = self.trace_markers[trace_id]
        crosshair_pen = pg.mkPen(color=self.current_marker_color_tuple[:3], width=1)

        # Create or update horizontal crosshair
        if 'crosshair_h' not in marker_items:
            marker_items['crosshair_h'] = pg.InfiniteLine(angle=0, movable=False, pen=crosshair_pen)
            self.plot_widget.addItem(marker_items['crosshair_h'], ignoreBounds=True)
        else:
            marker_items['crosshair_h'].setPen(crosshair_pen)
            # Remove and re-add to ensure it's on top
            self.plot_widget.removeItem(marker_items['crosshair_h'])
            self.plot_widget.addItem(marker_items['crosshair_h'], ignoreBounds=True)

        # Create or update vertical crosshair
        if 'crosshair_v' not in marker_items:
            marker_items['crosshair_v'] = pg.InfiniteLine(angle=90, movable=False, pen=crosshair_pen)
            self.plot_widget.addItem(marker_items['crosshair_v'], ignoreBounds=True)
        else:
            marker_items['crosshair_v'].setPen(crosshair_pen)
            # Remove and re-add to ensure it's on top
            self.plot_widget.removeItem(marker_items['crosshair_v'])
            self.plot_widget.addItem(marker_items['crosshair_v'], ignoreBounds=True)

        # Position crosshairs
        marker_items['crosshair_h'].setPos(point_data[1])  # Horizontal line at Y value
        marker_items['crosshair_v'].setPos(point_data[0])  # Vertical line at X value
        marker_items['crosshair_h'].show()
        marker_items['crosshair_v'].show()

    def _update_scatter_marker(self, trace_id, point_data):
        """Update scatter marker for a specific trace"""
        marker_items = self.trace_markers[trace_id]
        symbol_map = {"Circle": "o", "Square": "s"}
        actual_symbol = symbol_map.get(self.current_marker_type, "o")

        # Create or update scatter plot item
        if 'scatter' not in marker_items:
            marker_items['scatter'] = pg.ScatterPlotItem(pen=pg.mkPen(None))
            self.plot_widget.addItem(marker_items['scatter'])
        else:
            # Remove and re-add to ensure it's on top
            self.plot_widget.removeItem(marker_items['scatter'])
            self.plot_widget.addItem(marker_items['scatter'])

        marker_items['scatter'].setSize(self.current_marker_size)
        marker_items['scatter'].setBrush(pg.mkBrush(*self.current_marker_color_tuple))

        # Set the single point data
        spots_data = [{'pos': point_data, 'symbol': actual_symbol, 'data': 1}]
        marker_items['scatter'].setData(spots=spots_data)

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

    def update_marker_settings_from_preferences(self):
        """Update marker settings from QSettings and refresh display"""
        settings = QSettings()

        # Clear all existing markers before applying new settings
        self._clear_all_markers()

        # Update marker type
        self.current_marker_type = settings.value("phase_plot/default_marker_type", "Circle")

        # Update marker size
        self.current_marker_size = int(settings.value("phase_plot/default_marker_size", 10))

        # Update marker color
        default_color = settings.value("phase_plot/marker_color", "0,0,0,200")
        color_parts = [int(x) for x in default_color.split(',')]
        self.current_marker_color_tuple = tuple(color_parts)

        # Refresh the marker display with new settings
        self.update_marker(self.last_tick_index)

    def _clear_all_markers(self):
        """Remove all existing markers from the plot and clear tracking"""
        for trace_id, marker_items in self.trace_markers.items():
            for marker_item in marker_items.values():
                self.plot_widget.removeItem(marker_item)
        self.trace_markers.clear()

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
        return [label.phase_plot_item.get_plot_spec() for label in self._traces]

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
        return [label.phase_plot_item for label in self._traces]

    def get_plot_widget(self):
        """Returns the internal pyqtgraph.PlotWidget instance."""
        return self.plot_widget

    def connect_labels_to_time_signal(self, time_signal):
        """Connect all legend labels to the time signal for value updates"""
        self._time_signal = time_signal  # Store reference for future traces
        for label in self._traces:
            time_signal.connect(label.on_time_changed)

    @staticmethod
    def _get_color(idx):
        """Get color by index, same as SubPlotWidget"""
        return PhasePlotWidget.COLORS[idx % len(PhasePlotWidget.COLORS)]

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
    main_window = PhasePlotWidget(parent=None, data_file_widget=mock_dfw_for_init, plot_manager=None)

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
