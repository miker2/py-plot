# This Python file uses the following encoding: utf-8

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMenu, QAction, QApplication
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
        if e.mimeData().hasFormat("application/x-customplotitem") or \
           e.mimeData().hasFormat("application/x-DataItem"): # Keep existing functionality
            e.acceptProposedAction() # Use acceptProposedAction for move/copy distinction
        else:
            e.ignore()

    def dropEvent(self, e):
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

                # Determine the new index based on drop position
                new_idx = self._get_drop_index(e.pos())

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
                for i, item_widget in enumerate(self._traces):
                    item_widget.update_color(self._get_color(i))
                
                e.acceptProposedAction()

            else: # Moving from a different widget
                # Add to current (target) widget. plot_data_from_source needs the name and the source object.
                # The 'source' argument in plot_data_from_source is the original data source (e.g. data file widget)
                # not the CustomPlotItem's source attribute directly.
                # source_object here *is* CustomPlotItem.source.
                self.plot_data_from_source(plot_name, source_object) 

                # Remove from source widget
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

        elif e.mimeData().hasFormat("application/x-DataItem"): # Existing functionality
            data = e.mimeData()
            bstream = data.retrieveData("application/x-DataItem", QVariant.ByteArray)
            selected = pickle.loads(bstream) # This is a DataItem

            # e.source() for "application/x-DataItem" is the VarListWidget
            # The 'source' argument for plot_data_from_source should be this VarListWidget
            self.plot_data_from_source(selected.var_name, e.source())
            e.accept()
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
        y_data = source.model().get_data_by_name(name)

        if y_data is None:
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
        self.parent().plot_manager().timeValueChanged.connect(label.on_time_changed)

        source.onClose.connect(lambda: self.remove_item(item, label))
        self.cidx += 1

        self.update_plot_yrange()

    def remove_item(self, trace, label):
        self.pw.removeItem(trace)
        self._labels.removeWidget(label)
        label.close()

        self.cidx = max(0, self.cidx - 1)

        for idx in range(self._labels.count()):
            self._labels.itemAt(idx).widget().update_color(self._get_color(idx))

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

    def _copy_to_clipboard(self):
        cb = QApplication.clipboard()
        cb.setPixmap(self.grab())
        print("Plot copied to clipboard.")
