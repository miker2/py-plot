# -*- coding: utf-8 -*-

from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QInputDialog, QLineEdit, QMenu, \
    QAction, QApplication

from QRangeSlider import QRangeSlider
from sub_plot_widget import SubPlotWidget
from logging_config import get_logger

import math
import graph_utils

logger = get_logger(__name__)

def _disp_layout_contents(layout):
    logger.debug(f"There are {layout.count()} items in the layout")
    for i in range(layout.count()):
        logger.debug(f"{i} : {layout.itemAt(i)}")
        try:
            logger.debug(f"      {layout.itemAt(i).widget()}")
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
            logger.debug(f"Tab idx: {tab_idx}")

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
        logger.debug(f"Move cursor {'Right' if positive else 'Left'}")
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
        self._next_subplot_idx = 0 # Add subplot index counter

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

        # Generate unique object name for the SubPlotWidget
        subplot_object_name = f"subplot_tab{self._plot_manager.tabs.currentIndex()}_area{self._next_subplot_idx}"
        self._next_subplot_idx += 1
        
        subplot = SubPlotWidget(self, object_name_override=subplot_object_name) # Pass unique name
        subplot.move_cursor(self._plot_manager._time)
        subplot.set_xlimits(self._plot_manager.range_slider.min(), self._plot_manager.range_slider.max())
        self._plot_manager.timeValueChanged.connect(subplot.move_cursor)
        self._plot_manager.range_slider.minValueChanged.connect(subplot.set_xlimit_min)
        self._plot_manager.range_slider.maxValueChanged.connect(subplot.set_xlimit_max)
        self.plot_area.insertWidget(idx, subplot)

        self._link_axes()

        _disp_layout_contents(self.plot_area)

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

        _disp_layout_contents(self.plot_area)

        if self.plot_area.count() <= 1:
            # Nothing else to do here
            return

        # We need to handle the special case of the first subplot being removed!
        # Re-link all axes to the first plot in the list
        self._link_axes()

    def update_plot_xrange(self, val=None):
        logger.debug(f"Value: {val}, start: {self._plot_manager.range_slider.start()}, end: {self._plot_manager.range_slider.end()}")
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
                logger.debug(f"Plot at idx {idx} : {self._get_plot(idx)}")
                self.remove_subplot(self._get_plot(self.plot_area.count() - 1))

        # Walk the list of traces and produce the plots.
        for i in range(requested_count):
            plot = plot_info["plots"][i]

            subplot = self._get_plot(i)

            if clear_existing:
                subplot.clear_plot()

            for trace in plot["traces"]:
                subplot.plot_data_from_source(trace, data_source)

            # Handle the case where the "yrange" key is missing.
            if clear_existing and "yrange" in plot.keys():
                # Don't mess up the y-range if plots are being appended.
                subplot.set_y_range(*plot["yrange"])

    def _copy_to_clipboard(self):
        cb = QApplication.clipboard()
        cb.setPixmap(self.grab())
        logger.info("Plot copied to clipboard.")
