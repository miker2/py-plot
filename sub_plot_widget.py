# This Python file uses the following encoding: utf-8

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMenu, QAction, QApplication, QFrame
from PyQt5.QtCore import Qt, QVariant
import pyqtgraph as pg
from flow_layout import FlowLayout

import pickle
import numpy as np
from data_model import DataItem
from custom_plot_item import CustomPlotItem


class SubPlotWidget(QWidget):
    # Plot colors picked from here: https://colorbrewer2.org/#type=qualitative&scheme=Set1&n=8
    # with a slight modification to the "yellow" so it's darker and easier to see.
    COLORS = ('#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#a65628', '#D4C200', '#f781bf')

    # Class variable for ensuring unique IDs if no override is provided, though it's better if PlotAreaWidget provides one.
    _subplot_local_id_counter = 0

    def __init__(self, parent, object_name_override=None):
        QWidget.__init__(self, parent=parent)

        if object_name_override:
            self.setObjectName(object_name_override)
        else:
            # Fallback to ensure unique object name if not provided
            SubPlotWidget._subplot_local_id_counter += 1
            self.setObjectName(f"SubPlotWidget_fallback_{SubPlotWidget._subplot_local_id_counter}")

        v_box = QVBoxLayout(self)

        self._labels = FlowLayout()
        v_box.addLayout(self._labels)

        self.pw = pg.PlotWidget()
        # Adding stretch below ensures that the plow widget takes up as much space as possible
        # (labels take up only the minimum space possible)
        v_box.addWidget(self.pw, stretch=1)

        self.pw.setBackground('w')
        self.pw.showGrid(x=True, y=True)

        pi = self.pw.getPlotItem()
        pi.hideButtons()
        # pi.addLegend()
        # self.clicked.connect(self.on_clicked)

        # print(self.pw.super().ctrlMenu)

        self.setAcceptDrops(True)
        self.pw.setAcceptDrops(True)
        self.pw.enableAutoRange(x=False)
        self.pw.setMouseEnabled(x=False)
        self.pw.setClipToView(True)  # Only draw items in range

        self.cursor = pg.InfiniteLine(pos=0, movable=False, pen='r')
        self.pw.addItem(self.cursor)

        self.cidx = 0

        self._traces = []

        # We can just override the menu of the ViewBox here but I think a better solution
        # is to create a new object that derives from the ViewBox class and set up everything
        # that way.
        self.pw.getPlotItem().setMenuEnabled(enableMenu=False, enableViewBoxMenu=None)
        self.pw.getViewBox().menu = self.context_menu()

        self.pw.scene().sigMouseClicked.connect(self._on_scene_mouse_click_event)

        # Drop indicator for visual feedback during drag-and-drop of labels
        self._drop_indicator = QFrame(self) 
        self._drop_indicator.setFrameShape(QFrame.VLine)
        self._drop_indicator.setFrameShadow(QFrame.Sunken)
        self._drop_indicator.setStyleSheet("QFrame { background-color: black; border: none; }")
        self._drop_indicator.setFixedWidth(2)
        self._drop_indicator.hide()
        self._drop_indicator.raise_()

    def move_cursor(self, time):
        self.cursor.setValue(time)

    def set_xlimits(self, xmin, xmax):
        self.set_xlimit_min(xmin)
        self.set_xlimit_max(xmax)

    def set_xlimit_min(self, xmin):
        self.pw.setLimits(xMin=xmin)

    def set_xlimit_max(self, xmax):
        self.pw.setLimits(xMax=xmax)

    def context_menu(self):
        menu = QMenu()
        add_above_action = QAction("Add plot above", self.pw.getViewBox())
        add_above_action.triggered.connect(lambda: self.parent().add_subplot_above(self))
        menu.addAction(add_above_action)
        add_below_action = QAction("Add plot below", self.pw.getViewBox())
        add_below_action.triggered.connect(lambda: self.parent().add_subplot_below(self))
        menu.addAction(add_below_action)
        delete_subplot_action = QAction("Remove Plot", self.pw.getViewBox())
        delete_subplot_action.triggered.connect(lambda: self.parent().remove_subplot(self))
        menu.addAction(delete_subplot_action)
        menu.addSeparator()
        clear_plot_action = QAction("Clear plot", self.pw.getViewBox())
        clear_plot_action.triggered.connect(self.clear_plot)
        menu.addAction(clear_plot_action)
        clear_plot_action = QAction("Reset y-range", self.pw.getViewBox())
        clear_plot_action.triggered.connect(self.update_plot_yrange)
        menu.addAction(clear_plot_action)
        menu.addSeparator()
        ss_plot_action = QAction("copy to clipboard", self.pw.getViewBox())
        ss_plot_action.triggered.connect(self._copy_to_clipboard)
        menu.addAction(ss_plot_action)

        return menu

    def dragEnterEvent(self, e):
        print("DEBUG: dragEnterEvent called.") # New debug print
        if e.mimeData():
            print(f"DEBUG: MimeData formats: {e.mimeData().formats()}") # New debug print
            print(f"DEBUG: Has 'application/x-DataItem': {e.mimeData().hasFormat('application/x-DataItem')}") # New
            print(f"DEBUG: Has 'application/x-customplotitem': {e.mimeData().hasFormat('application/x-customplotitem')}") # New
        else:
            print("DEBUG: No MimeData found in event.") # New debug print
        
        # Existing logic:
        if e.mimeData().hasFormat("application/x-customplotitem") or \
           e.mimeData().hasFormat("application/x-DataItem"):
            print("DEBUG: dragEnterEvent: Accepting event.") # New
            e.acceptProposedAction()
        else:
            print("DEBUG: dragEnterEvent: Ignoring event.") # New
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat("application/x-customplotitem"):
            # This is the existing logic for showing/positioning the drop indicator
            # when dragging a custom plot item (a label).
            if e.pos().y() < self.pw.geometry().top(): # Cursor is in the label area
                target_height = 20 # Default/fallback height
                marker_y = 0
                marker_x = 0

                if self._labels.count() > 0:
                    drop_idx = self._get_drop_index(e.pos())
                    
                    # Determine reference widget for Y position and height
                    # Use item at drop_idx, or last item if drop_idx is count (append)
                    ref_idx_for_y = min(drop_idx, self._labels.count() - 1)
                    if ref_idx_for_y < 0 : ref_idx_for_y = 0 # Ensure valid index if count became 0 mid-drag
                    
                    if self._labels.count() > 0 : # Re-check count as it might change due to external factors
                        ref_widget_for_y = self._labels.itemAt(ref_idx_for_y).widget()
                        if ref_widget_for_y:
                             marker_y = ref_widget_for_y.geometry().top()
                             target_height = ref_widget_for_y.geometry().height()
                        else: # Should not happen if _labels is consistent with _traces
                             self._drop_indicator.hide()
                             e.acceptProposedAction()
                             return
                    else: # No labels, position at top of label area
                        content_rect_top = self.contentsRect().top()
                        marker_y = content_rect_top
                        label_area_height = self.pw.geometry().top() - content_rect_top
                        target_height = max(10, label_area_height if label_area_height > 0 else 20)


                    if drop_idx == 0:
                        first_item_widget = self._labels.itemAt(0).widget()
                        if first_item_widget: # Check if widget exists
                            marker_x = first_item_widget.geometry().left()
                        else: # Fallback if no widget at index 0 somehow
                            marker_x = self.contentsRect().left() + 2
                    elif drop_idx == self._labels.count():
                        last_item_widget = self._labels.itemAt(drop_idx - 1).widget()
                        if last_item_widget: # Check if widget exists
                             marker_x = last_item_widget.geometry().right()
                        else: # Fallback if no widget at last index somehow
                            marker_x = self.contentsRect().left() + 2 # Default to start
                    else:
                        prev_item_widget = self._labels.itemAt(drop_idx - 1).widget()
                        next_item_widget = self._labels.itemAt(drop_idx).widget()
                        if prev_item_widget and next_item_widget: # Check if widgets exist
                            marker_x = (prev_item_widget.geometry().right() + next_item_widget.geometry().left()) // 2
                        else: # Fallback if widgets are missing
                            marker_x = self.contentsRect().left() + 2


                    self._drop_indicator.setGeometry(marker_x - self._drop_indicator.width() // 2, 
                                                     marker_y,
                                                     self._drop_indicator.width(), 
                                                     target_height)
                    self._drop_indicator.show()
                    self._drop_indicator.raise_()
                
                else: # Labels area but no labels currently
                    content_rect_top = self.contentsRect().top()
                    label_area_height = self.pw.geometry().top() - content_rect_top
                    
                    self._drop_indicator.setGeometry(self.contentsRect().left() + 2,
                                                     content_rect_top,
                                                     self._drop_indicator.width(),
                                                     max(10, label_area_height if label_area_height > 0 else 20))
                    self._drop_indicator.show()
                    self._drop_indicator.raise_()
            else: # Over plot area or otherwise not in a valid label drop zone for customplotitem
                self._drop_indicator.hide()
            
            e.acceptProposedAction() # Accept for custom plot item

        elif e.mimeData().hasFormat("application/x-DataItem"):
            # For items from VarListWidget, we don't show the drop indicator,
            # but we MUST accept the event to allow dropEvent to be called.
            self._drop_indicator.hide() # Ensure indicator is hidden
            e.acceptProposedAction() # Crucially accept the event
        
        else:
            # Unknown type, hide indicator and ignore.
            self._drop_indicator.hide()
            e.ignore()

    def dragLeaveEvent(self, e):
        self._drop_indicator.hide()
        super().dragLeaveEvent(e)

    def dropEvent(self, e):
        self._drop_indicator.hide() # Hide indicator on drop
        if e.mimeData().hasFormat("application/x-customplotitem"):
            plot_name = e.mimeData().text()
            source_data_bytes = e.mimeData().data("application/x-customplotitem-source")
            source_widget_name_bytes = e.mimeData().data("application/x-customplotitem-sourcewidget")

            try:
                source_object = pickle.loads(source_data_bytes)
            except Exception as err:
                print(f"Error unpickling source_object: {err}")
                e.ignore()
                return

            source_widget_name_from_mime = source_widget_name_bytes.data().decode()

            actual_source_widget = None
            if e.source() and isinstance(e.source(), CustomPlotItem):
                actual_source_widget = e.source()._subplot_widget
                if actual_source_widget is None:
                    print("Error: Dragged CustomPlotItem's _subplot_widget is None.")
                    e.ignore()
                    return
                # Sanity check if objectName from mime matches the direct reference
                if actual_source_widget.objectName() != source_widget_name_from_mime:
                    print(f"Warning: Mismatch between e.source()._subplot_widget.objectName() ('{actual_source_widget.objectName()}') and MIME source widget name ('{source_widget_name_from_mime}'). Prioritizing e.source()._subplot_widget.")

            else: # Fallback to lookup by name if e.source() is not CustomPlotItem (should not happen)
                print("Warning: e.source() is not a CustomPlotItem. Falling back to objectName lookup for source widget.")
                if source_widget_name_from_mime == self.objectName():
                    actual_source_widget = self
                elif hasattr(self.parent(), 'plot_area'): # Assumes PlotAreaWidget is parent
                    for i in range(self.parent().plot_area.count()):
                        widget = self.parent().plot_area.itemAt(i).widget()
                        if isinstance(widget, SubPlotWidget) and widget.objectName() == source_widget_name_from_mime:
                            actual_source_widget = widget
                            break
                if actual_source_widget is None:
                    print(f"Fallback Error: Could not find source widget by name: {source_widget_name_from_mime}")
                    e.ignore()
                    return

            # Determine insertion index based on drop location
            idx_for_insertion: int
            if e.pos().y() < self.pw.geometry().top(): # pw is the pyqtgraph.PlotWidget
                # Drop is likely in the upper region where labels are
                idx_for_insertion = self._get_drop_index(e.pos())
            else:
                # Drop is likely in the lower region (the plot graph itself)
                idx_for_insertion = len(self._traces) # Append
            
            if actual_source_widget == self: # Reordering within the same widget
                dragged_item_widget = None
                original_idx = -1
                for i, trace_item in enumerate(self._traces):
                    # Using trace.name() as CustomPlotItem.name also calls this.
                    if trace_item.trace.name() == plot_name: 
                        dragged_item_widget = trace_item
                        original_idx = i
                        break
                
                if dragged_item_widget is None:
                    print(f"Error: Could not find dragged item '{plot_name}' in self for reordering.")
                    e.ignore()
                    return

                # Use the determined index for reordering
                new_idx = idx_for_insertion

                # Remove from _traces. Note: dragged_item_widget is the object, not pg_trace
                # Popping _traces first.
                self._traces.pop(original_idx)
                
                # Adjust new_idx if original_idx was before it, due to the pop operation
                if new_idx > original_idx:
                    new_idx -= 1
                # FlowLayout does not have insertWidget. Need to rebuild.
                
                # Store all label widgets, remove the dragged one from list
                all_labels = []
                dragged_label_for_reinsert = None
                for i in range(self._labels.count()):
                    lbl_widget = self._labels.itemAt(i).widget()
                    if lbl_widget == dragged_item_widget: # CustomPlotItem is a QLabel
                         dragged_label_for_reinsert = self._labels.takeAt(i).widget() # Take it
                         break # Found and took the one we need to re-insert
                
                # If not found by object equality, try by name (less robust)
                if dragged_label_for_reinsert is None:
                    for i in range(self._labels.count()):
                        lbl_widget = self._labels.itemAt(i).widget()
                        if lbl_widget.name == plot_name : # CustomPlotItem.name
                            dragged_label_for_reinsert = self._labels.takeAt(i).widget()
                            break
                
                if dragged_label_for_reinsert is None:
                    print(f"Error: Could not find label widget for '{plot_name}' to reorder.")
                    # We already modified self._traces, this state is inconsistent.
                    # This path should ideally not be reached if dragged_item_widget was found.
                    # For safety, try to restore _traces or ignore.
                    e.ignore()
                    return

                # Clear remaining items from _labels and store them
                remaining_labels = []
                while self._labels.count() > 0:
                    remaining_labels.append(self._labels.takeAt(0).widget())
                
                # Reconstruct the list of labels in the new order
                # new_idx here is relative to the list *after* removing the item.
                # If new_idx was for appending, it should be len(remaining_labels)
                # For now, let's use the placeholder new_idx for _traces logic,
                # and for labels, we insert at the same conceptual index.
                # This new_idx is for self._traces, which now has one less item.
                # So, if new_idx was len(self._traces) (before pop), it's now len(self._traces)-1 (after pop)
                # Example: [a,b,c,d], pop b (idx 1). traces = [a,c,d]. new_idx=3 (append).
                # labels: [L_a, L_c, L_d]. Insert L_b at new_idx=3. -> [L_a, L_c, L_d, L_b]

                final_label_order = remaining_labels
                final_label_order.insert(new_idx, dragged_label_for_reinsert)

                # Re-populate _labels
                for lbl_widget in final_label_order:
                    self._labels.addWidget(lbl_widget)

                # Insert into _traces at new_idx
                self._traces.insert(new_idx, dragged_item_widget)

                # Update colors
                self._update_all_trace_colors()
                
                e.acceptProposedAction()

            else: # Moving from a different widget
                # Add to current (target) widget. plot_data_from_source needs the name and the source object.
                # The 'source' argument in plot_data_from_source is the original data source (e.g. data file widget)
                # not the CustomPlotItem's source attribute directly.
                # source_object here *is* CustomPlotItem.source.
                
                # Moving from a different widget - implement precise positional insertion.
                # Use the determined index for move-in
                new_idx = idx_for_insertion

                # a. Get Data (source_object is the CustomPlotItem.source from the dragged item)
                #    plot_name is the name of the trace.
                if not hasattr(source_object, 'model') or not callable(source_object.model) or \
                   not hasattr(source_object, 'time'):
                    print(f"Error: source_object for '{plot_name}' lacks model() or time attribute.")
                    e.ignore()
                    return

                y_data = source_object.model().get_data_by_name(plot_name)
                if y_data is None:
                    print(f"Error: Could not retrieve y_data for '{plot_name}' from source_object.")
                    e.ignore()
                    return
                x_data = source_object.time

                # b. Create pyqtgraph.PlotDataItem
                # Use a temporary color; _update_all_trace_colors will finalize it.
                # Using new_idx for temp color, or len if it's an append.
                temp_color_idx = new_idx if new_idx < len(self._traces) else len(self._traces)
                temp_color = self._get_color(temp_color_idx) 
                
                plot_data_item = self.pw.getPlotItem().plot(x=x_data,
                                                            y=y_data,
                                                            pen=pg.mkPen(color=temp_color,
                                                                         width=CustomPlotItem.PEN_WIDTH),
                                                            name=plot_name,
                                                            autoDownsample=True,
                                                            downsampleMethod='peak')

                # c. Create CustomPlotItem (the label)
                # Assuming self.parent() is PlotAreaWidget, and it has plot_manager() method
                # CustomPlotItem expects a tick value (int or float that can be mapped to a tick)
                # self.parent().plot_manager()._tick is an int, _time is float.
                # CustomPlotItem's constructor uses the passed value directly as self._tick
                # For consistency, let's use current _tick from plot_manager.
                current_tick = self.parent().plot_manager()._tick
                label = CustomPlotItem(self, plot_data_item, source_object, current_tick)

                # d. Insert into _traces
                self._traces.insert(new_idx, label)
                self.cidx += 1 # Increment count of items

                # e. Insert Label into _labels (FlowLayout) - Re-populate
                # Clear existing labels from layout
                while self._labels.count() > 0:
                    old_label_layout_item = self._labels.takeAt(0)
                    if old_label_layout_item and old_label_layout_item.widget():
                        # Don't destroy, just remove from layout. They are in self._traces.
                        old_label_layout_item.widget().hide() # Hide temporarily

                # Re-add all labels from self._traces in the new order
                for trace_item_widget in self._traces:
                    self._labels.addWidget(trace_item_widget)
                    trace_item_widget.show() # Ensure it's visible if it was hidden

                # f. Connect Signals for the New Label
                self.parent().plot_manager().timeValueChanged.connect(label.on_time_changed)
                
                # The original plot_data_from_source used: source.onClose.connect(...)
                # Here, 'source_object' is the CustomPlotItem.source from the *dragged* item.
                # This source_object (e.g., DataFileWidget instance) should have onClose.
                if hasattr(source_object, 'onClose') and callable(getattr(source_object, 'onClose', None)):
                    # Ensure we use the correct plot_data_item and label for removal
                    disconnect_slot = lambda item_to_remove=plot_data_item, lbl_to_remove=label: self.remove_item(item_to_remove, lbl_to_remove)
                    source_object.onClose.connect(disconnect_slot)
                    # Store the slot for potential disconnection if needed, though typically not for onClose.
                    label.setProperty("onClose_slot", disconnect_slot) 
                else:
                    print(f"Warning: source_object for {plot_name} does not have a callable onClose signal/attribute.")

                # g. Update Plot Y-Range and Colors
                self.update_plot_yrange() 
                self._update_all_trace_colors() # Finalize colors based on new order

                # Remove from source widget (this part remains the same)
                source_item_widget_to_remove = None
                pg_trace_to_remove = None
                for i, trace_item in enumerate(actual_source_widget._traces):
                    if trace_item.trace.name() == plot_name:
                        source_item_widget_to_remove = trace_item
                        pg_trace_to_remove = trace_item.trace 
                        break # Found the item to remove

                if source_item_widget_to_remove and pg_trace_to_remove:
                    actual_source_widget.remove_item(pg_trace_to_remove, source_item_widget_to_remove)
                else:
                    print(f"Error: Could not find item '{plot_name}' in source widget '{actual_source_widget.objectName()}' to remove after move.")
                    # Item already added to target, so proceed, but log error.

                e.acceptProposedAction()

        elif e.mimeData().hasFormat("application/x-DataItem"):
            print("DEBUG: DropEvent for application/x-DataItem") # New debug print
            data = e.mimeData()
            bstream = data.retrieveData("application/x-DataItem", QVariant.ByteArray)
            try:
                selected = pickle.loads(bstream)
                print(f"DEBUG: Unpickled 'selected': {selected}, var_name: {getattr(selected, 'var_name', 'N/A')}") # New debug print
            except Exception as ex:
                print(f"ERROR: Error unpickling DataItem: {ex}") # Changed to ERROR
                e.ignore()
                return

            print(f"DEBUG: e.source() type: {type(e.source())}") # New debug print
            if not hasattr(e.source(), 'model'):
                print("ERROR: e.source() does not have a model() method.") # New debug print
                e.ignore()
                return

            # Call plot_data_from_source
            try:
                print(f"DEBUG: Calling plot_data_from_source with var_name='{selected.var_name}' and source='{e.source()}'") # New
                self.plot_data_from_source(selected.var_name, e.source())
                print("DEBUG: Returned from plot_data_from_source successfully") # New
                e.accept() 
            except Exception as ex_plot:
                print(f"ERROR: Exception during plot_data_from_source or accept: {ex_plot}") # New
                e.ignore() # Ensure event is ignored on error
        else:
            e.ignore()

    def _get_drop_index(self, drop_pos_in_widget_coords):
        """
        Determines the insertion index for a dropped CustomPlotItem within the
        _labels FlowLayout based on the drop position.
        drop_pos_in_widget_coords is relative to the SubPlotWidget.
        """
        if self._labels.count() == 0:
            return 0

        for i in range(self._labels.count()):
            widget = self._labels.itemAt(i).widget()
            if widget is None: # Should not happen with current setup
                continue

            geom = widget.geometry() # Relative to SubPlotWidget's content area

            # Scenario 1: Drop is on a line above this widget
            if drop_pos_in_widget_coords.y() < geom.top():
                return i

            # Scenario 2: Drop is on the same line as this widget (or a line below but needs checking if it's to the left)
            # Check if Y is within this widget's vertical span (or above its bottom edge)
            if drop_pos_in_widget_coords.y() < geom.bottom():
                # If Y is within this widget's height range AND X is to its left (or in its left half)
                if drop_pos_in_widget_coords.x() < geom.left() + geom.width() / 2:
                    return i
        
        # If drop position is below or to the right of all items on their respective lines
        return self._labels.count()

    def _on_scene_mouse_click_event(self, event):
        if event.button() != Qt.LeftButton:
            event.ignore()
            return

        t_click = self.pw.getViewBox().mapSceneToView(event.scenePos()).x()
        self.parent().plot_manager().set_tick_from_time(t_click)
        event.accept()

    def plot_data_from_source(self, name, source):
        print(f"DEBUG: plot_data_from_source called with name='{name}', source type: {type(source)}") # New

        if not hasattr(source, 'model') or not callable(getattr(source, 'model')):
            print(f"ERROR: plot_data_from_source: 'source' ({type(source).__name__}) has no callable model attribute.") # New
            return # Abort if source is not as expected

        # ...
        y_data = source.model().get_data_by_name(name)
        print(f"DEBUG: y_data is None: {y_data is None}") # New
        if y_data is None:
            print(f"ERROR: y_data for '{name}' is None. Aborting plot.") # New
            return 
        
        item = self.pw.getPlotItem().plot(x=source.time,
                                          y=y_data,
                                          pen=pg.mkPen(color=self._get_color(self.cidx),
                                                       width=CustomPlotItem.PEN_WIDTH),
                                          name=name,
                                          # clipToView=True,
                                          autoDownsample=True,
                                          downsampleMethod='peak')

        label = CustomPlotItem(self, item, source, self.parent().plot_manager()._tick)
        self._traces.append(label)
        self._labels.addWidget(label)
        
        # Connect signals for the new label
        # Time changed connection is fine
        self.parent().plot_manager().timeValueChanged.connect(label.on_time_changed)

        # Conditionally connect onClose for the source
        if hasattr(source, 'onClose') and callable(getattr(source, 'onClose', None)):
            # The source here is e.source() from dropEvent when adding new from VarListWidget,
            # or CustomPlotItem.source (pickled/unpickled) when moving an existing plot.
            # For VarListWidget, this connects to VarListWidget.onClose.
            # For moved items, this connects to the original source's onClose (e.g., the original VarListWidget).
            disconnect_slot = lambda item_to_remove=item, lbl_to_remove=label: self.remove_item(item_to_remove, lbl_to_remove)
            source.onClose.connect(disconnect_slot)
            # Store the slot for potential disconnection if needed (though less common for onClose)
            label.setProperty("onClose_slot_plot_data_from_source", disconnect_slot)
        else:
            print(f"Note: Source object {type(source).__name__} does not have an onClose signal. Signal removal might not be tied to source closure for this item: {name}")
        
        # self.cidx += 1 # cidx will be updated based on len(_traces)
        # self.update_plot_yrange() will be called by _update_all_trace_colors if needed, 
        # or can be called separately. For now, let _update_all_trace_colors handle colors.
        # The original plot_data_from_source call to self.update_plot_yrange() is kept.
        self.update_plot_yrange() 
        self._update_all_trace_colors() # Ensure all colors are correct after adding a new trace
        self.cidx = len(self._traces) # Update cidx based on the actual number of traces

    def remove_item(self, trace, label):
        self.pw.removeItem(trace)
        self._labels.removeWidget(label)
        label.close()

        self.cidx = max(0, self.cidx - 1)
        self._update_all_trace_colors()

    def clear_plot(self):
        # HAX!!! Save the cursor!
        x = self.cursor.value()
        self.pw.clear()
        # Replace the cursor. Such a hack
        self.cursor = pg.InfiniteLine(pos=x, movable=False, pen='r')
        self.pw.addItem(self.cursor)

        # Remove labels also.
        while self._labels.count() > 0:
            lbl = self._labels.takeAt(0).widget()
            lbl.close()

        self.cidx = 0

    def update_plot_yrange(self, val=None):
        self.pw.autoRange()
        # Workaround for autoRange() not respecting the disabled x-axis
        self.parent().update_plot_xrange()

    def set_y_range(self, ymin, ymax):
        self.pw.setYRange(ymin, ymax, padding=0)

    def get_plot_info(self):
        """ This method should return a dictionary of information required to reproduce this
            plot """

        plot_info = dict()
        # Is there a more correct way to get the range of the y-axis? Probably safe to assume that
        # the 'left' axis is always the correct one, but the 'range' property of an 'AxisItem'
        # isn't documented in the public API.
        y_range = self.pw.getPlotItem().getAxis('left').range
        plot_info['yrange'] = y_range
        plot_info['traces'] = [trace.get_plot_spec() for trace in self._traces if trace.isVisible()]

        return plot_info

    @staticmethod
    def _get_color(idx):
        return SubPlotWidget.COLORS[idx % len(SubPlotWidget.COLORS)]

    def _update_all_trace_colors(self):
        """
        Updates the pen color of all traces and the text color of their corresponding
        labels based on their current order in self._traces.
        """
        for i, trace_widget in enumerate(self._traces):
            # trace_widget is a CustomPlotItem instance
            if isinstance(trace_widget, CustomPlotItem): # Defensive check
                trace_widget.update_color(self._get_color(i))
            else:
                # This case should ideally not happen if _traces is managed correctly.
                print(f"Warning: Item at index {i} in self._traces is not a CustomPlotItem.")
        
        # If y-range needs to be updated after color/pen style changes that might affect visibility
        # self.update_plot_yrange() # Consider if this is needed here or if it's handled sufficiently elsewhere.
                                  # For now, let's keep it focused on colors.

    def _copy_to_clipboard(self):
        cb = QApplication.clipboard()
        cb.setPixmap(self.grab())
        print("Plot copied to clipboard.")
