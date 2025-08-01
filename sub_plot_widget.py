# This Python file uses the following encoding: utf-8

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMenu, QAction, QApplication, QFrame
from PyQt5.QtGui import QPalette # Ensure QPalette is imported
from PyQt5.QtCore import Qt, QVariant
import pyqtgraph as pg
from flow_layout import FlowLayout
from logging_config import get_logger

from typing import List

import pickle
import numpy as np
from data_model import DataItem
from custom_plot_item import CustomPlotItem

logger = get_logger(__name__)

# NOTE: This is here to ensure we aren't going to override the existing method
assert(not hasattr(pg.PlotWidget, 'autoRangeEnabled'))
class PatchedPlotWidget(pg.PlotWidget):

    # Patch the pyqtgraph PlotWidget to resolve an internal exception
    def autoRangeEnabled(self):
        return self.plotItem.getViewBox().autoRangeEnabled()

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

        # NOTE: The line below was pg.PlotWidget(), but there's a bug internal to pyqtgraph. See:
        #  https://github.com/pyqtgraph/pyqtgraph/issues/1854
        self.pw = PatchedPlotWidget()
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

        self._traces: List[CustomPlotItem] = []

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
        # Get the highlight color from the palette
        highlight_color = self.palette().color(QPalette.Highlight)
        # Set the style sheet using this color
        self._drop_indicator.setStyleSheet(f"QFrame {{ background-color: {highlight_color.name()}; border: none; }}")
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

    @property
    def _cidx(self):
        return len(self._traces)

    def dragEnterEvent(self, e):
        logger.debug("dragEnterEvent called.")
        if e.mimeData():
            logger.debug(f"MimeData formats: {e.mimeData().formats()}")
            logger.debug(f"Has 'application/x-DataItem': {e.mimeData().hasFormat('application/x-DataItem')}")
            logger.debug(f"Has 'application/x-customplotitem': {e.mimeData().hasFormat('application/x-customplotitem')}")
        else:
            logger.debug("No MimeData found in event.")

        # Existing logic:
        if e.mimeData().hasFormat("application/x-customplotitem") or \
           e.mimeData().hasFormat("application/x-DataItem"):
            logger.debug("dragEnterEvent: Accepting event.")
            e.acceptProposedAction()
        else:
            logger.debug("dragEnterEvent: Ignoring event.")
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
            plot_name = e.mimeData().text() # Still useful for getting the trace name

            # The 'source_object' (original data source like VarListWidget) will be retrieved differently
            # for move-in operations, directly from the dragged CustomPlotItem.

            actual_source_widget = None
            if e.source() and isinstance(e.source(), CustomPlotItem):
                actual_source_widget = e.source()._subplot_widget
                if actual_source_widget is None:
                    logger.error("Dragged CustomPlotItem's _subplot_widget is None.")
                    e.ignore()
                    return
            else:
                logger.error("e.source() is not a CustomPlotItem. Cannot determine source widget.")
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
                    logger.error(f"Could not find dragged item '{plot_name}' in self for reordering.")
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

                # Find and remove the label widget from the layout
                # Since dragged_item_widget is in _traces, it must be in the layout
                for i in range(self._labels.count()):
                    if self._labels.itemAt(i).widget() == dragged_item_widget:
                        dragged_label_for_reinsert = self._labels.takeAt(i).widget()
                        break
                else:
                    # This should never happen if _traces and _labels are kept in sync
                    logger.error(f"Label widget for '{plot_name}' not found in layout despite being in _traces.")
                    self._traces.insert(original_idx, dragged_item_widget)
                    e.ignore()
                    return

                # Insert the label widget at the new position
                self._labels.insertWidget(new_idx, dragged_label_for_reinsert)

                # Insert into _traces at new_idx
                self._traces.insert(new_idx, dragged_item_widget)

                # Update colors
                self._update_all_trace_colors()

                e.acceptProposedAction()

            else: # Moving from a different widget (actual_source_widget != self)
                logger.debug(f"DROP: Move-In operation for plot '{plot_name}' from '{actual_source_widget.objectName()}' to '{self.objectName()}'.")

                if not isinstance(e.source(), CustomPlotItem):
                    logger.error("DROP: Drag source is not a CustomPlotItem during move operation.")
                    e.ignore(); return
                dragged_label_widget = e.source()
                plot_data_item = dragged_label_widget.trace # The pyqtgraph.PlotDataItem
                # original_data_source = dragged_label_widget.source # Store if needed for creating new CustomPlotItem

                # 1. CRITICAL: Remove from source widget FIRST.
                if actual_source_widget:
                    logger.debug(f"DROP: Instructing source widget '{actual_source_widget.objectName()}' to remove item '{plot_name}' (is_move_operation=True).")
                    actual_source_widget.remove_item(plot_data_item, dragged_label_widget, is_move_operation=True)
                else:
                    logger.error(f"DROP: actual_source_widget is None for plot '{plot_name}'. Cannot remove from source.")
                    e.ignore(); return

                # 2. Now, add to target widget (self)
                logger.debug(f"DROP: Re-parenting label '{dragged_label_widget.text()}' to '{self.objectName()}'.")
                dragged_label_widget.setParent(self)
                dragged_label_widget._subplot_widget = self

                logger.debug(f"DROP: Adding plot_data_item for '{plot_name}' to target plot '{self.objectName()}'.")
                if plot_data_item not in self.pw.getPlotItem().items:
                    self.pw.addItem(plot_data_item) # Add existing PlotDataItem
                else:
                    logger.warning(f"DROP: PlotDataItem for '{plot_name}' was already in target plot '{self.objectName()}' before adding.")

                # Determine insertion index
                # Use idx_for_insertion which was determined earlier based on drop zone (label area vs plot area)
                new_idx = idx_for_insertion # This was determined before the if/else actual_source_widget block
                # The following logic for pos_in_labels_coords was part of the instructions, but idx_for_insertion already covers this.
                # We will rely on idx_for_insertion directly.
                # pos_in_labels_coords = self._labels.mapFromParent(e.pos()) # Map drop pos to FlowLayout's coordinate system
                # if self._labels.rect().contains(pos_in_labels_coords): # Check if drop is within the FlowLayout's bounds
                #     new_idx = self._get_drop_index(e.pos()) # Use original logic if inside labels area
                # else: # Drop is outside labels area (e.g. on plot graph), append
                #     new_idx = len(self._traces)
                logger.debug(f"DROP: Determined new_idx for move-in: {new_idx}")

                self._traces.insert(new_idx, dragged_label_widget)

                # Re-populate FlowLayout
                logger.debug(f"DROP: Labels layout repopulating for '{self.objectName()}'.")
                self._labels.insertWidget(new_idx, dragged_label_widget)
                dragged_label_widget.show()
                logger.debug(f"DROP: Labels layout repopulated for '{self.objectName()}'.")


                # Signal Connections
                if actual_source_widget and hasattr(actual_source_widget.parent(), 'plot_manager'):
                    try:
                        actual_source_widget.parent().plot_manager().timeValueChanged.disconnect(dragged_label_widget.on_time_changed)
                        logger.debug(f"DROP: Disconnected timeValueChanged from old plot manager for '{dragged_label_widget.text()}'.")
                    except TypeError:
                        logger.debug(f"DROP: Signal timeValueChanged not connected/already disconnected for '{dragged_label_widget.text()}' from old plot manager.")

                self.parent().plot_manager().timeValueChanged.connect(dragged_label_widget.on_time_changed)
                logger.debug(f"DROP: Connected timeValueChanged to new plot manager for '{dragged_label_widget.text()}'.")

                self.update_plot_yrange()
                self._update_all_trace_colors()
                logger.debug(f"DROP: Plot y-range and colors updated for '{self.objectName()}'. cidx: {self._cidx}")

                e.acceptProposedAction()
                logger.debug(f"DROP: Move-in for '{plot_name}' completed and event accepted.")

        elif e.mimeData().hasFormat("application/x-DataItem"):
            logger.debug("DropEvent for application/x-DataItem")
            data = e.mimeData()
            bstream = data.retrieveData("application/x-DataItem", QVariant.ByteArray)
            try:
                selected = pickle.loads(bstream)
                logger.debug(f"Unpickled 'selected': {selected}, var_name: {getattr(selected, 'var_name', 'N/A')}")
            except Exception as ex:
                logger.exception(f"Error unpickling DataItem: {ex}")
                e.ignore()
                return

            logger.debug(f"e.source() type: {type(e.source())}")
            if not hasattr(e.source(), 'model'):
                logger.error("e.source() does not have a model() method.")
                e.ignore()
                return

            # Call plot_data_from_source
            try:
                logger.debug(f"Calling plot_data_from_source with var_name='{selected.var_name}' and source='{e.source()}'")
                self.plot_data_from_source(selected.var_name, e.source())
                logger.debug("Returned from plot_data_from_source successfully")
                e.accept()
            except Exception as ex_plot:
                logger.exception(f"Exception during plot_data_from_source or accept: {ex_plot}")
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
        logger.debug(f"plot_data_from_source called with name='{name}', source type: {type(source)}")

        if not hasattr(source, 'model') or not callable(getattr(source, 'model')):
            logger.error(f"plot_data_from_source: 'source' ({type(source).__name__}) has no callable model attribute.")
            return # Abort if source is not as expected

        # ...
        y_data = source.model().get_data_by_name(name)
        if y_data is None:
            logger.error(f"y_data for '{name}' is None. Aborting plot.")
            return

        item = self.pw.getPlotItem().plot(x=source.time,
                                          y=y_data,
                                          pen=pg.mkPen(color=self._get_color(self._cidx),
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
        source.timeChanged.connect(label.on_source_time_changed)

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
            logger.info(f"Source object {type(source).__name__} does not have an onClose signal. Signal removal might not be tied to source closure for this item: {name}")

        # self.update_plot_yrange() will be called by _update_all_trace_colors if needed,
        # or can be called separately. For now, let _update_all_trace_colors handle colors.
        # The original plot_data_from_source call to self.update_plot_yrange() is kept.
        self.update_plot_yrange()
        self._update_all_trace_colors() # Ensure all colors are correct after adding a new trace

    def remove_item(self, trace, label, is_move_operation=False):
        # trace: the pyqtgraph.PlotDataItem
        # label: the CustomPlotItem instance
        # is_move_operation: True if this item is being moved to another plot

        logger.debug(f"remove_item called for label '{label.text()}' in subplot '{self.objectName()}', is_move_operation={is_move_operation}")

        # Disconnect the timeChanged signal
        label.source.timeChanged.disconnect(label.on_source_time_changed)

        # Remove from pyqtgraph plot
        self.pw.removeItem(trace)

        # Remove from FlowLayout
        self._labels.removeWidget(label)
        # Note: removeWidget just takes it from the layout's control.
        # The widget itself is not deleted by this call.

        # Remove from internal list of traces
        if label in self._traces:
            self._traces.remove(label)
            logger.debug(f"Label '{label.text()}' removed from _traces list of {self.objectName()}.")
        else:
            logger.warning(f"Label '{label.text()}' (id: {id(label)}) not found in _traces list of {self.objectName()} during remove_item.")

        # Conditionally delete the label widget itself
        if not is_move_operation:
            # If it's not a move, we are deleting the item permanently.
            # Check parentage for safety, though it should be self or None if already detached by layout.
            if label.parent() == self:
                logger.debug(f"Closing label '{label.text()}' (parent is self).")
                label.close() # Schedules for deletion
            elif label.parent() is None:
                logger.debug(f"Closing label '{label.text()}' (parent is None - likely already detached by layout).")
                label.close() # Schedules for deletion
            else:
                # This case (not a move, but parent is different) is unusual.
                # It implies it was reparented by some other logic before a non-move deletion was requested.
                # For safety, don't close if it has an unexpected new parent.
                logger.warning(f"Not closing label '{label.text()}' during non-move operation as its parent is '{label.parent()}'. Expected self or None.")
        else:
            # This is a move operation. The label widget has been (or will be) re-parented
            # to the target SubPlotWidget. Do not close/delete it.
            # Its parent should ideally be the target SubPlotWidget now, or will be set by it.
            logger.debug(f"Not closing label '{label.text()}' because is_move_operation is True. Current parent: {label.parent()}")
            # Ensure it's no longer visible in this subplot if it wasn't already hidden by removeWidget
            label.hide()


        # Update colors in this subplot
        self._update_all_trace_colors()
        logger.debug(f"remove_item completed for '{label.text()}' in {self.objectName()}. _traces count: {len(self._traces)}")

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
                logger.warning(f"Item at index {i} in self._traces is not a CustomPlotItem.")

        # If y-range needs to be updated after color/pen style changes that might affect visibility
        # self.update_plot_yrange() # Consider if this is needed here or if it's handled sufficiently elsewhere.
                                  # For now, let's keep it focused on colors.

    def _copy_to_clipboard(self):
        cb = QApplication.clipboard()
        cb.setPixmap(self.grab())
        logger.info("Plot copied to clipboard.")

    def update_cursor_settings(self):
        """Update cursor appearance from settings"""
        from PyQt5.QtCore import QSettings
        settings = QSettings()
        cursor_color = settings.value("cursor/color", "black")
        cursor_width = int(settings.value("cursor/width", 2))
        pen = pg.mkPen(color=cursor_color, width=cursor_width)
        self.cursor.setPen(pen)
