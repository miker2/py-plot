# -*- coding: utf-8 -*-

from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QInputDialog, QLineEdit, QMenu, \
    QAction, QApplication

from QRangeSlider import QRangeSlider
from sub_plot_widget import SubPlotWidget
from plot_spec import PlotSpec
from data_model import DataItem # Added import

from typing import TYPE_CHECKING, Dict, Any # Added imports
if TYPE_CHECKING:
    from maths_widget import MathsWidget
    from data_file_widget import DataFileWidget

import math
import graph_utils


def _disp_layout_contents(layout):
    print(f"There are {layout.count()} items in the layout")
    for i in range(layout.count()):
        print(f"{i} : {layout.itemAt(i)}")
        try:
            print(f"      {layout.itemAt(i).widget()}")
        except:
            pass


_DEFAULT_FREQ = 500.

''' This class is for management of a linked set of subplots
'''


class PlotManager(QWidget):
    tickValueChanged = pyqtSignal(int)
    timeValueChanged = pyqtSignal(float)

    def __init__(self, parent):
        QWidget.__init__(self, parent)

        # The "controller" is the main program. This is how we'll access the data file widget
        self._controller = parent

        # This is the main widget of the app. It contains the range slider and a layout containing
        # all of the subplots.
        central_layout = QVBoxLayout(self)
        central_layout.setObjectName("plotManagerLayout")

        self._tick = 0
        self._time = 0

        self.range_slider = QRangeSlider()
        self.range_slider.show()
        self.range_slider.setMin(0.)
        # large number here is sort of a hack for now so the plot x-axis resizes properly on the
        # first file load.
        self.range_slider.setMax(1.e9)
        self.range_slider.setRange(self.range_slider.min(), self.range_slider.max())

        self.range_slider.startValueChanged.connect(self.update_plot_xrange)
        self.range_slider.endValueChanged.connect(self.update_plot_xrange)
        central_layout.addWidget(self.range_slider)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setTabBarAutoHide(False)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_plot_tab)
        # Attach a context menu directly to the tab bar rather than the tab widget itself
        self.tabs.tabBar().customContextMenuRequested.connect(self.on_context_menu_request)
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBarDoubleClicked.connect(self.rename_tab)
        central_layout.addWidget(self.tabs)

        self.add_plot_tab()

    @property
    def tab_count(self):
        return self.tabs.count()

    def close_plot_tab(self, index):
        self.tabs.widget(index).close()
        self.tabs.removeTab(index)

    def add_plot_tab(self):
        tab_count = self.tabs.count()
        paw = PlotAreaWidget(self)
        self.tabs.addTab(paw, f"plot{tab_count + 1}")
        self.tabs.setCurrentWidget(paw)

    def add_subplot(self):
        self.tabs.currentWidget().add_subplot()

    def handle_key_press(self, event):
        """
        This is the main keypress event handler. It will handle distribution of the various
        functionality.
        """
        key = event.key()
        if key == Qt.Key_Down or key == Qt.Key_Up:
            self.modify_zoom(key == Qt.Key_Up, event.modifiers())
        elif key == Qt.Key_Left or key == Qt.Key_Right:
            self.move_cursor(key == Qt.Key_Right, event.modifiers())
        elif key == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            self.tabs.currentWidget().autoscale_y_axes()

    @pyqtSlot(QPoint)
    def on_context_menu_request(self, pos):
        # We only want to bring up the context menu when an actual tab is right-clicked. Check that
        # the click position is inside the tab bar
        if self.tabs.tabBar().rect().contains(pos):
            # Figure out specifically which tab was right clicked:
            # TODO: This seems to have a bug on macOS - look into it.
            # reproduce by right-clicking
            tab_idx = self.tabs.tabBar().tabAt(pos)
            print(f"Tab idx: {tab_idx}")

            rename_act = QAction("rename...")
            rename_act.setStatusTip("Rename the tab")
            rename_act.triggered.connect(lambda: self.rename_tab(tab_idx))

            menu = QMenu(self.tabs)
            menu.addAction(rename_act)

            menu.addSeparator()

            ss_tab_action = QAction("copy to clipboard")
            ss_tab_action.triggered.connect(self.tabs.widget(tab_idx)._copy_to_clipboard)
            menu.addAction(ss_tab_action)

            menu.exec(self.tabs.tabBar().mapToGlobal(pos))

    @pyqtSlot(int)
    def rename_tab(self, idx):
        current_name = self.tabs.tabText(idx)

        text, ok = QInputDialog().getText(self, "Rename Tab", "Tab name:", QLineEdit.Normal,
                                          current_name)
        if ok and text:
            self.tabs.setTabText(idx, text)

    def move_cursor(self, positive, modifier):
        # print(f"Move cursor {'Right' if positive else 'Left'}")
        mult = 1
        if modifier & Qt.ControlModifier:
            mult *= 5
        if modifier & Qt.ShiftModifier:
            mult *= 20
        self.set_tick(self._tick + mult * (1 if positive else -1))

    def set_tick(self, tick):
        time_series = self._get_time()
        # If there's no file open, it probably doesn't make sense to move the cursor anyway.
        if time_series is not None:
            tick = max(0, min(tick, len(time_series) - 1))
            time = time_series[tick]
            self.set_tick_from_time(time)

    def set_tick_from_time(self, t_cursor):
        self._time = t_cursor
        time_series = self._get_time()
        if time_series is None:
            # Default to a psuedo tick count here
            self._tick = int(round(t_cursor * _DEFAULT_FREQ))
        else:
            self._tick = graph_utils.time_to_nearest_tick(time_series, t_cursor)
            self._time = time_series[self._tick]
        self.tickValueChanged.emit(self._tick)
        self.timeValueChanged.emit(self._time)

    def modify_zoom(self, zoom_in, modifier):
        # Slider is in time units. Here we'll assume the DT, but we can change this later.
        min_range = 10. / _DEFAULT_FREQ
        mult = 5. / _DEFAULT_FREQ
        if modifier & Qt.ControlModifier:
            mult *= 5
        if modifier & Qt.ShiftModifier:
            mult *= 20
        mult = min(mult, 250)
        offset = mult * (1 if zoom_in else -1)
        midpoint = 0.5 * (self.range_slider.start() + self.range_slider.end())
        new_start = self.range_slider.start() + offset
        new_end = self.range_slider.end() - offset
        if new_start > new_end:
            # Too much zoom! Limit it to something reasonable.
            new_start = midpoint - 0.5 * min_range
            new_end = midpoint + 0.5 * min_range
        # Make sure neither value is outside the min/max limits
        new_start = max(new_start, self.range_slider.min())
        new_end = min(new_end, self.range_slider.max())

        self.range_slider.setStart(new_start)
        self.range_slider.setEnd(new_end)

    def update_plot_xrange(self, val):
        for idx in range(self.tabs.count()):
            self.tabs.widget(idx).update_plot_xrange(val)

    # Originally these methods were located in the top level file (main.py)
    # These should probably be cleaned up a bit. We could make the dataFileWidget
    # emit a signal when a file is opened or closed. That might make it better.
    def update_slider_limits(self, t_min, t_max):
        self.range_slider.setMin(t_min)
        self.range_slider.setMax(t_max)
        if self.range_slider.min() > self.range_slider.start():
            self.range_slider.setStart(t_min)
        if self.range_slider.max() < self.range_slider.end():
            self.range_slider.setEnd(t_max)

    def get_plot_info_for_active_tab(self):
        # Inject the name of the current tab into the plot info.
        return {**{"name": self.tabs.tabText(self.tabs.currentIndex())},
                **self.tabs.currentWidget().get_plot_info()}

    def generate_plots_for_active_tab(self, plot_info, data_source, append):
        tab_name = plot_info['name']
        if tab_name and not append:  # Don't rename if appending to a tab
            self.tabs.setTabText(self.tabs.currentIndex(), tab_name)
        self.tabs.currentWidget().generate_plots(plot_info, data_source, clear_existing=not append)

    def _get_time(self, idx=0):
        return self._controller.data_file_widget.get_time(idx)


class PlotAreaWidget(QWidget):
    def __init__(self, plot_manager):
        QWidget.__init__(self)

        self._plot_manager = plot_manager

        self.plot_area = QVBoxLayout(self)

        self.add_subplot()
        self.add_subplot()

        self.update_plot_xrange()

    def plot_manager(self):
        return self._plot_manager

    def add_subplot(self, idx=None):
        # Default to the bottom of the list
        if idx is None:
            idx = self.plot_area.count()
        subplot = SubPlotWidget(self)
        subplot.move_cursor(self._plot_manager._time)
        subplot.set_xlimits(self._plot_manager.range_slider.min(), self._plot_manager.range_slider.max())
        self._plot_manager.timeValueChanged.connect(subplot.move_cursor)
        self._plot_manager.range_slider.minValueChanged.connect(subplot.set_xlimit_min)
        self._plot_manager.range_slider.maxValueChanged.connect(subplot.set_xlimit_max)
        self.plot_area.insertWidget(idx, subplot)

        self._link_axes()

        # _disp_layout_contents(self.plot_area)

    def add_subplot_above(self, subplot):
        idx = self._get_index(subplot)
        self.add_subplot(idx)

    def add_subplot_below(self, subplot):
        idx = self._get_index(subplot)
        self.add_subplot(idx + 1)

    def remove_subplot(self, subplot):
        if self.plot_area.count() <= 1:
            # Don't allow the only remaining plot to be removed
            return
        item = self.plot_area.takeAt(self.plot_area.indexOf(subplot))
        subplot.close()

        # _disp_layout_contents(self.plot_area)

        if self.plot_area.count() <= 1:
            # Nothing else to do here
            return

        # We need to handle the special case of the first subplot being removed!
        # Re-link all axes to the first plot in the list
        self._link_axes()

    def update_plot_xrange(self, val=None):
        # print(f"Value: {val}, start: start: {self.range_slider.start()}, end: {self.range_slider.end()}")
        # Because plots are linked we only need to do this for the first plot. Others will follow suite.
        self._get_plot(0).pw.setXRange(min=self._plot_manager.range_slider.start(),
                                       max=self._plot_manager.range_slider.end(),
                                       padding=0)

    def autoscale_y_axes(self):
        for idx in range(self.plot_area.count()):
            self._get_plot(idx).update_plot_yrange()

    def _link_axes(self):
        # TODO: Make this use signal/slot mechanism
        pw = self._get_plot(0).pw
        for idx in range(1, self.plot_area.count()):
            self._get_plot(idx).pw.setXLink(pw)

    def _get_index(self, subplot):
        """ This method returns the index of the subplot (both from the layout and the list) """
        return self.plot_area.indexOf(subplot)

    def _get_plot(self, idx):
        return self.plot_area.itemAt(idx).widget()

    def _reproduce_signal(self, plot_spec_dict: Dict[str, Any], 
                          data_file_widget_ref: 'DataFileWidget', 
                          maths_widget_ref: 'MathsWidget', 
                          loaded_signals_cache: Dict[str, DataItem]) -> DataItem | None:
        """
        Recursively reproduces a signal based on its PlotSpec dictionary.
        Uses a cache to avoid reprocessing the same signal.
        """
        if not plot_spec_dict:
            print("Error: Received empty plot_spec_dict.")
            return None

        try:
            plot_spec = PlotSpec.from_dict(plot_spec_dict)
        except Exception as e:
            print(f"Error converting dict to PlotSpec: {e}. Dict: {plot_spec_dict}")
            return None

        if plot_spec.unique_id in loaded_signals_cache:
            return loaded_signals_cache[plot_spec.unique_id]

        data_item: DataItem | None = None

        if plot_spec.source_type == "file":
            if plot_spec.file_source_identifier and plot_spec.original_name:
                # Assume DataFileWidget has a method to get a DataItem by some identifier and original name
                # This method would need to find the correct VarListWidget/DataModel and get the DataItem
                # For now, this is a conceptual call.
                # data_item = data_file_widget_ref.get_data_item_by_file_id_and_name(
                #     plot_spec.file_source_identifier, 
                #     plot_spec.original_name
                # )
                
                # Placeholder for DataFileWidget interaction:
                # We need a way to map file_source_identifier to a specific DataModel/VarListWidget
                # and then retrieve the DataItem.
                # Let's assume data_file_widget_ref can provide access to its models/var_lists
                found_model = None
                if hasattr(data_file_widget_ref, 'var_lists'): # Assuming var_lists is a list of VarListWidget
                    for vl in data_file_widget_ref.var_lists:
                        # This matching logic for file_source_identifier needs to be robust.
                        # It could be a filename, an index, or a unique ID assigned to the source.
                        current_model_identifier = vl.filename if hasattr(vl, 'filename') else str(vl.idx)
                        if current_model_identifier == plot_spec.file_source_identifier:
                            found_model = vl.model() # DataModel
                            break
                
                if found_model:
                    data_item = found_model.get_data_by_name(plot_spec.original_name) # This returns DataItem
                    if data_item and data_item.plot_spec is None:
                        # If the original DataItem didn't have a PlotSpec (e.g. from older save),
                        # assign the one we just loaded/recreated.
                        data_item.plot_spec = plot_spec
                    elif data_item and data_item.plot_spec and data_item.plot_spec.unique_id != plot_spec.unique_id:
                        # This might happen if the file was reloaded and IDs changed.
                        # The loaded plot_spec should be preferred for consistency of the loaded plot.
                        print(f"Info: Replacing PlotSpec on DataItem {data_item.var_name} with loaded PlotSpec.")
                        data_item.plot_spec = plot_spec

                if data_item is None:
                    print(f"Error: Could not find 'file' signal '{plot_spec.original_name}' from source '{plot_spec.file_source_identifier}'.")

            else:
                print(f"Error: 'file' source_type missing file_source_identifier or original_name for PlotSpec: {plot_spec.name}")
        
        elif plot_spec.source_type.startswith("math_"):
            input_data_items: list[DataItem] = []
            valid_inputs = True
            for input_spec_dict in plot_spec_dict.get('input_plot_specs', []): # Use dict for recursion
                input_data_item = self._reproduce_signal(
                    input_spec_dict, 
                    data_file_widget_ref, 
                    maths_widget_ref, 
                    loaded_signals_cache
                )
                if input_data_item:
                    input_data_items.append(input_data_item)
                else:
                    print(f"Error: Could not reproduce input signal for {plot_spec.name}. Input spec dict: {input_spec_dict}")
                    valid_inputs = False
                    break # Stop if any input fails
            
            if valid_inputs:
                # Pass the PlotSpec object, not the dict
                data_item = maths_widget_ref.execute_operation_from_spec(plot_spec, input_data_items)
                if data_item and data_item.plot_spec is None:
                    # Ensure the reproduced DataItem has its plot_spec set (execute_operation_from_spec should ideally do this)
                    print(f"Warning: PlotSpec was not set by execute_operation_from_spec for {data_item.var_name}. Setting it now.")
                    data_item.plot_spec = plot_spec
                elif data_item and data_item.plot_spec and data_item.plot_spec.unique_id != plot_spec.unique_id:
                    # If execute_operation_from_spec set a different PlotSpec (e.g. a new one with a new ID),
                    # prefer the one that guided the reproduction to maintain consistency with the saved plot.
                    print(f"Info: Overwriting PlotSpec on DataItem {data_item.var_name} from math operation with the loaded PlotSpec for consistency.")
                    data_item.plot_spec = plot_spec

            else:
                print(f"Error: Failed to reproduce one or more input signals for math operation: {plot_spec.name}")

        else:
            print(f"Error: Unknown or unsupported source_type: {plot_spec.source_type} for PlotSpec: {plot_spec.name}")


        if data_item:
            loaded_signals_cache[plot_spec.unique_id] = data_item
        
        return data_item

    def get_plot_info(self):
        n_plots = self.plot_area.count()
        plotlist = dict()
        # Not entirely certain this is necesary, but maybe it is if we use a different format or
        # for error checking?
        plotlist['count'] = n_plots
        plots = [self._get_plot(i).get_plot_info() for i in range(n_plots)]
        plotlist['plots'] = plots

        return plotlist

    def generate_plots(self, plot_info, data_source, clear_existing=True):
        # First, we ensure that there are the correct number of plots available.
        requested_count = plot_info['count']
        while self.plot_area.count() < requested_count:
            self.add_subplot()

        if clear_existing:
            while self.plot_area.count() > requested_count:
                idx = self.plot_area.count() - 1
                print("Plot at idx {idx} : {self._get_plot(idx)}")
                self.remove_subplot(self._get_plot(self.plot_area.count() - 1))

        # Walk the list of traces and produce the plots.
        loaded_signals_cache: Dict[str, DataItem] = {}
        # Assuming controller and its widgets are accessible. Adjust paths if necessary.
        # These refs might be better passed in or accessed via a more stable interface.
        maths_widget_ref = self.plot_manager()._controller.maths_widget if hasattr(self.plot_manager()._controller, 'maths_widget') else None
        data_file_widget_ref = self.plot_manager()._controller.data_file_widget if hasattr(self.plot_manager()._controller, 'data_file_widget') else None

        if not maths_widget_ref or not data_file_widget_ref:
            print("Error: MathsWidget or DataFileWidget reference not found. Cannot reproduce signals.")
            return

        for i in range(requested_count):
            plot_dict = plot_info["plots"][i] # Renamed 'plot' to 'plot_dict' to avoid confusion
            subplot = self._get_plot(i)

            if clear_existing:
                subplot.clear_plot()

            for trace_spec_dict in plot_dict["traces"]: # trace_spec_dict is a PlotSpec dictionary
                # The 'data_source' argument in the original plot_data_from_source was a single
                # VarListWidget. This is not suitable for reproduced signals which can come from
                # various files or be math-generated.
                # We now use _reproduce_signal to get the DataItem.
                
                data_item_to_plot = self._reproduce_signal(
                    trace_spec_dict, # This is the plot_spec_dict for the trace
                    data_file_widget_ref,
                    maths_widget_ref,
                    loaded_signals_cache
                )

                if data_item_to_plot:
                    # The SubPlotWidget.plot_data_from_source method will need to be adapted
                    # to accept a DataItem directly, or a new method like plot_reproduced_data_item
                    # needs to be created. For now, we assume plot_data_from_source can handle this.
                    # The 'source' argument here is tricky. For file items, it was the VarListWidget.
                    # For math items, it was MathsWidget.
                    # We pass a reference that CustomPlotItem might use (e.g. for onClose).
                    # This will be refined when SubPlotWidget is modified.
                    
                    # Tentative call, assuming plot_data_from_source is modified:
                    # The first argument to plot_data_from_source was 'name'. Now we pass DataItem.
                    # The second argument was 'source'.
                    # Let's assume a modification to plot_data_from_source like:
                    # plot_data_from_source(self, name_or_data_item, source_for_connections_if_any=None, is_reproduced_item=False)
                    
                    # Determine a 'source' for connection purposes (e.g. onClose).
                    # If it's a file item, its original VarListWidget source is complex to get here.
                    # If it's a math item, MathsWidget is the source.
                    # For now, pass maths_widget_ref as a general source for potential connections.
                    # This part (source_for_connections) needs careful handling in SubPlotWidget.
                    subplot.plot_data_from_source(
                        name_or_data_item=data_item_to_plot, 
                        source_or_none=maths_widget_ref, # Placeholder for source context
                        is_reproduced_item=True # New flag
                    ) 
                else:
                    print(f"Warning: Could not reproduce signal for spec: {trace_spec_dict.get('name', 'Unknown name')}")

            # Handle the case where the "yrange" key is missing.
            if clear_existing and "yrange" in plot_dict.keys(): # Use plot_dict
                # Don't mess up the y-range if plots are being appended.
                subplot.set_y_range(*plot["yrange"])

    def _copy_to_clipboard(self):
        cb = QApplication.clipboard()
        cb.setPixmap(self.grab())
        print("Plot copied to clipboard.")
