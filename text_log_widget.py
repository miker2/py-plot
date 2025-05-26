from PyQt5.QtCore import Qt, pyqtSignal, QItemSelection, QItemSelectionModel
from PyQt5.QtWidgets import QDockWidget, QTableView, QVBoxLayout, QHBoxLayout, QComboBox, \
    QCheckBox, QWidget
from PyQt5.QtWidgets import QAbstractItemView, QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt5.QtGui import QPalette, QFont

from text_log_model import TextLogModel, TextLogEntry, SeverityFilterProxyModel
from logging_config import get_logger

import os
import numpy as np

import text_log_decode as tld

logger = get_logger(__name__)

# TODO:
#  [ ] Create text log loader
#  [ ] Create text log model (for storing loaded data)
#  [ ] Fill in the 'update' method so that proper messages are highlighted based on tick
#  [ ] Time sync between text logs and binary logs

class DockedTextLogWidget(QDockWidget):
    onClose = pyqtSignal()

    def __init__(self, parent=None, source=None):
        QDockWidget.__init__(self, "Text Log", parent=parent)

        widget = QWidget()
        layout = QVBoxLayout()

        # Try to get the plot manager object from the parent. The text log widget will use this
        # to update the "tick" when a specific message is selected.
        try:
            pm = parent.plot_manager
        except:
            logger.error(f"Unable to get plot manager from parent (of type {type(parent).__name__})")
            pm = None

        self._text_log = TextLogWidget(parent=self, source=source, plot_manager=pm)
        layout.addWidget(self._text_log)

        # H-box for filter selector & reverse-sync selector
        hbox = QHBoxLayout()

        self._filter_list = QComboBox()
        for severity in tld.Severity:
            self._filter_list.addItem(severity.name)
        # Initialize the dropdown menu to be debug level.
        debug_idx = self._filter_list.findText(tld.Severity.Debug.name)
        self._filter_list.setCurrentIndex(debug_idx)

        self._filter_list.currentIndexChanged.connect(self._set_max_severity)

        hbox.addWidget(self._filter_list)

        self._reverse_sync = QCheckBox("Reverse sync")
        self._reverse_sync.setToolTip("When checked, clicking on an entry in the text log\n" +
                                      "will move the time cursor in the plot area.")
        self._reverse_sync.stateChanged.connect(self._text_log.set_reverse_sync)
        self._reverse_sync.setChecked(True)
        hbox.addWidget(self._reverse_sync)

        layout.addLayout(hbox)
        widget.setLayout(layout)

        self.setWidget(widget)

    @property
    def has_source(self):
        return self._text_log.has_source

    def set_source(self, source):
        self._text_log.set_source(source)

    def closeEvent(self, event):
        self._text_log.close()
        self.onClose.emit()
        event.accept()

    def update(self, tick):
        self._text_log.update(tick)

    def _set_max_severity(self, idx):
        self._text_log.set_max_severity(tld.Severity[self._filter_list.itemText(idx)])


class TextLogWidget(QTableView):
    def __init__(self, parent, source, plot_manager=None):
        QTableView.__init__(self, parent)

        # This proxy model is an intermediary between the original model and the view. It
        # creates a new model from the original model based on the filter settings.
        self._source = None
        self._proxy_model = SeverityFilterProxyModel(self)
        # Initialize the proxy model to none. This will get updated when the source is set.
        self._proxy_model.setSourceModel(None)

        self.setModel(self._proxy_model)

        selection_model = QItemSelectionModel(self._proxy_model)
        self.setSelectionModel(selection_model)

        self.set_source(source)

        self.clicked.connect(self.itemClicked)

        self._idx = None

        self._do_reverse_sync = False

        self._plot_manager = plot_manager

        # Setup some formatting of the table.
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().hide()
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)

        self.setItemDelegate(SelectedItemDelegate())

    def set_source(self, source):
        self._source = source
        if self._source:
            logger.info(f"Source is '{self._source.filename}'")
            model = None
            # Try to find a corresponding data file:
            base, ext = os.path.splitext(source.filename)
            txt_log = base + ".txt"
            if os.path.exists(txt_log):
                logger.info(f"Corresponding text log: {txt_log}")
                # Create the model and pass it to the proxy model
                model = TextLogModel(txt_log)
            else:
                logger.warning("No corresponding text log exists.")

            self._proxy_model.setSourceModel(model)

            self.setColumnHidden(TextLogEntry.Severity, True)
            self.resizeColumnsToContents()

            self._source.onClose.connect(self._remove_source)

            if hasattr(self, "_idx") and self._idx:
                self.update(self._idx)

    @property
    def has_source(self):
        return self._source is not None

    def _remove_source(self):
        self._source = None

    def update(self, tick):
        self._idx = tick
        if self._source is None or tick is None:
            return

        # Ensure that the tick isn't out of range (in case multiple files are open)
        tick = min(tick, self._source.model().tick_max)

        if self._proxy_model.rowCount() <= 0:
            return

        # Get the ticks associated with the current model. Maybe there's a better way to do this
        ticks = [0] * self._proxy_model.rowCount()
        for r in range(self._proxy_model.rowCount()):
            idx = self._proxy_model.index(r, 0)
            ticks[r] = self._proxy_model.data(idx, Qt.UserRole).tick

        # We want to find the most recent (message) at or prior to this tick, but never after.
        newest_idx = np.where(np.array(ticks) <= tick)[0][-1]
        # Now find the first message from the same tick:
        first_same_tick_idx = ticks.index(ticks[newest_idx])

        # Use the first column here for convenience. Ultimately, the whole row will be selected
        first_model_idx = self._proxy_model.index(first_same_tick_idx, 0)
        last_model_idx = self._proxy_model.index(newest_idx, 0)

        # Select the applicable rows so the user knows which messages correspond to which data.
        selection = QItemSelection(first_model_idx, last_model_idx)
        self.selectionModel().select(selection,
                                     QItemSelectionModel.Rows | QItemSelectionModel.ClearAndSelect)
        # Scroll to the first item first, in case it isn't in view.
        self.scrollTo(first_model_idx, QAbstractItemView.EnsureVisible)
        # Now scroll to the last item. This will ensure that the newest text log message will
        # appear in view.
        self.scrollTo(last_model_idx, QAbstractItemView.EnsureVisible)

    def itemClicked(self, index):
        # When clicking on an item in the list, jump to the correct tick in the plot.
        tick = index.data(Qt.UserRole).tick
        if self._plot_manager and self._do_reverse_sync:
            self._plot_manager.set_tick(tick)
        else:
            logger.debug(f"Selection is at tick {tick}.")
            self.update(tick)

    def set_max_severity(self, severity):
        self._proxy_model.set_max_severity(severity)

    def set_reverse_sync(self, state):
        self._do_reverse_sync = bool(state)


# This is used to set the style of selected cells in our table
class SelectedItemDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        item_option = QStyleOptionViewItem(option)
        if option.state & QStyle.State_Selected:
            palette = item_option.palette
            # If the model provides a text color, use it.
            text_color = index.data(Qt.ForegroundRole)
            text_weight = QFont.Bold
            if text_color is None:
                # Otherwise, use the default
                text_color = palette.brush(QPalette.Text)
                text_weight = QFont.DemiBold
            item_option.palette.setBrush(QPalette.HighlightedText, text_color)
            # Now make the text bold so that we know which rows are selected.
            item_option.font.setWeight(text_weight)

            # If the model provides a background color, use it.
            bg_color = index.data(Qt.BackgroundRole)
            if bg_color is None:
                # No color provided by the model. Use the base color
                bg_color = palette.brush(QPalette.Base)

            # Apply the background color, but make it a bit darker so there is a difference between
            # highlighted and non-highlighted cells.
            item_option.palette.setColor(QPalette.Highlight, bg_color.color().darker(115))

        super().paint(painter, item_option, index)
