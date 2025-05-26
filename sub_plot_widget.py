# This Python file uses the following encoding: utf-8

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMenu, QAction, QApplication
from PyQt5.QtCore import Qt, QVariant
import pyqtgraph as pg
from flow_layout import FlowLayout
from logging_config import get_logger

import pickle
import numpy as np
from data_model import DataItem
from custom_plot_item import CustomPlotItem

logger = get_logger(__name__)

class SubPlotWidget(QWidget):
    # Plot colors picked from here: https://colorbrewer2.org/#type=qualitative&scheme=Set1&n=8
    # with a slight modification to the "yellow" so it's darker and easier to see.
    COLORS = ('#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#a65628', '#D4C200', '#f781bf')

    def __init__(self, parent):
        QWidget.__init__(self, parent=parent)

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
        if e.mimeData().hasFormat("application/x-DataItem"):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        data = e.mimeData()
        bstream = data.retrieveData("application/x-DataItem", QVariant.ByteArray)
        selected = pickle.loads(bstream)

        self.plot_data_from_source(selected.var_name, e.source())

        e.accept()

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
        logger.info("Plot copied to clipboard.")
