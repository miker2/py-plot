from PyQt5.QtCore import Qt, pyqtSignal, QSettings, QSize, QPoint
from PyQt5.QtWidgets import QDockWidget


class DockedWidget(QDockWidget):
    onClose = pyqtSignal()

    def __init__(self, name, parent):
        QDockWidget.__init__(self, name, parent=parent)

        self._docked_size = None
        self._undocked_size = None
        self._undocked_pos = None
        self._settings_read = False  # a hack until I can sort out the sizing logic
        self.topLevelChanged.connect(self._on_dock_state_change)

        self._read_settings()

        # Docked widget starts as docked always, so we need to set sizes appropriately
        if not self.isFloating():
            self.resize(self._docked_size)

    def closeEvent(self, event):
        self._write_settings()
        self.widget().close()
        self.onClose.emit()
        event.accept()

    def sizeHint(self):
        size_hint = self._docked_size
        if self.isFloating():
            size_hint = self._undocked_size

        return size_hint

    def _read_settings(self):
        if not self._settings_read:
            settings = QSettings()

            settings.beginGroup(self.windowTitle())
            self._undocked_size = settings.value("size", QSize(640, 480))
            self._docked_size = settings.value("docked_size", QSize(320, 500))
            self._undocked_pos = settings.value("position", QPoint(10, 10))

            is_floating = bool(int(settings.value("floating", 1)))
            self.setFloating(is_floating)
            settings.endGroup()
            self._settings_read = True

    def _write_settings(self):
        settings = QSettings()

        settings.beginGroup(self.windowTitle())
        # Convert to an int because it's easier to parse when reading
        settings.setValue("floating", int(self.isFloating()))
        settings.setValue("size", self._undocked_size)
        settings.setValue("docked_size", self._docked_size)
        if self.isFloating():
            settings.setValue("position", self.pos())
        settings.endGroup()

    def _on_dock_state_change(self, is_floating):
        if is_floating:
            self.move(self._undocked_pos)
            self.resize(self._undocked_size)
        else:
            self.resize(self._docked_size)

    def moveEvent(self, event):
        if self._settings_read:
            # Capture the position of the widget when it changes so that we can restore
            # the proper position on dock/undock events
            if self.isFloating():
                # print(f"{self.windowTitle()} Capturing new position: {event.pos()}, {self.pos()}")
                self._undocked_pos = event.pos()

        super().moveEvent(event)

    def resizeEvent(self, event):
        if self._settings_read:
            # Capture the size of the widget when it changes so that we can restore
            # the proper size on dock/undock events
            if self.isFloating():
                self._undocked_size = self.widget().size()
                self._undocked_pos = self.pos()
            else:
                self._docked_size = self.widget().size()
        super().resizeEvent(event)
