from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QVariant, Qt, QSortFilterProxyModel, QDateTime
from PyQt5.QtGui import QBrush, QColor

from enum import IntEnum, auto

import text_log_decode as tld


class TextLogEntry(IntEnum):
    Timestamp = 0
    Severity = auto()
    Message = auto()
    Source = auto()
    Tick = auto()


class TextLogItem(object):
    """
        Data structure for storing data items in the list widget
    """

    def __init__(self, log_msg):
        self._log_msg = log_msg

    @property
    def time(self):
        return self._log_msg.time

    @property
    def severity(self):
        return self._log_msg.severity

    @property
    def msg(self):
        return self._log_msg.msg

    @property
    def source(self):
        return self._log_msg.source

    @property
    def tick(self):
        return self._log_msg.step

    def get(self, item):
        if item == TextLogEntry.Timestamp:
            return self.time
        elif item == TextLogEntry.Severity:
            return self.severity
        elif item == TextLogEntry.Message:
            return self.msg
        elif item == TextLogEntry.Source:
            return self.source
        elif item == TextLogEntry.Tick:
            return self.tick

    def __repr__(self):
        return repr(self._log_msg)


_SEVERITY_FG = {
    tld.Severity.Critical: Qt.black,
    tld.Severity.Error: Qt.red,
    # This is supposed to be some sort of yellow, but yellow on a white background is hard.
    tld.Severity.Warn: QColor(230, 172, 0),
    tld.Severity.Note: Qt.darkGreen,
    tld.Severity.Trace: Qt.magenta
}

_SEVERITY_BG = {
    tld.Severity.Critical: Qt.red
}


class TextLogModel(QAbstractTableModel):
    def __init__(self, text_log, parent=None):
        QAbstractTableModel.__init__(self, parent=parent)

        text_log = tld.decode_text_log(text_log)
        self._data, self._time, self._ticks = zip(*[[TextLogItem(msg), msg.time, msg.step] for msg in text_log])

        self._header_labels = [header.name for header in TextLogEntry]

    @property
    def time(self):
        return self._time

    @property
    def ticks(self):
        return self._ticks

    @property
    def tick_max(self):
        return self._time.shape[0]

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return 4

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._header_labels[section]
        return QAbstractTableModel.headerData(self, section, orientation, role)

    def data(self, index, role):
        row = index.row()
        col = index.column()
        item = self._data[index.row()]

        if role == Qt.DisplayRole:
            if col == TextLogEntry.Timestamp:
                datetime = QDateTime.fromMSecsSinceEpoch(int(item.time * 1e3))

                # NOTE: Uncomment this line to show the date as well.
                # fmt_string = "dd-MM-yyyy HH:mm:ss.zzz"
                fmt_string = "HH:mm:ss.zzz"
                return QVariant(datetime.toString(fmt_string))
            elif col == TextLogEntry.Severity:
                return QVariant(item.severity.name)
            elif col == TextLogEntry.Message:
                return QVariant(item.msg)
            elif col == TextLogEntry.Source:
                return QVariant(item.source)

        elif role == Qt.ForegroundRole:
            try:
                color = _SEVERITY_FG[item.severity]
                return QVariant(QBrush(color))
            except KeyError:
                pass
        elif role == Qt.BackgroundRole:
            try:
                color = _SEVERITY_BG[item.severity]
                return QVariant(QBrush(color))
            except KeyError:
                pass

        elif role == Qt.UserRole:
            return item

        return QVariant()


class SeverityFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent):
        QSortFilterProxyModel.__init__(self, parent)

        # foo bar
        self._max_severity_level = tld.Severity.Debug

    def set_max_severity(self, severity):
        self._max_severity_level = severity
        self.invalidateFilter()

    @property
    def max_severity(self):
        return self._max_severity_level

    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(source_row, 0, source_parent)
        severity = self.sourceModel().data(index, Qt.UserRole).severity
        # print(f"{severity} <= {self._max_severity_level} : {severity <= self._max_severity_level}")

        return severity <= self._max_severity_level
