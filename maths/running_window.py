
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSpinBox, QComboBox, QDoubleSpinBox, QFormLayout, \
    QDialogButtonBox, QRadioButton, QGroupBox, QVBoxLayout, QDialog

from dataclasses import dataclass

from enum import Enum
import math
import numpy as np
from scipy import signal

from maths.maths_base import MathSpecBase

class WindowTypes(Enum):
    MEDIAN = 0
    MEAN = 1

@dataclass
class RunningWindowParams:
    type: WindowTypes
    window_sz: float
    is_ticks: bool

class RunningWindowSpec(MathSpecBase):

    def __init__(self, parent):
        MathSpecBase.__init__(self, parent=parent, name="running mean/median")

    def buttonCallback(self, checked):
        self.createMessageBox()

    def getParams(self):
        # Create a dialog for getting the window parameters.
        # Store results and then use them in the doMath method
        # Items we need:
        #  1. Filter type (QComboBox)
        #  2. Window units (QRadioButton) - time or ticks?
        #  3. Window size (QDoubleSpinBox/QSpinBox)
        param_dialog = QDialog(self.parent())
        form = QFormLayout(param_dialog)

        # Window type
        window_type = QComboBox()
        for e in WindowTypes:
            window_type.addItem(e.name.lower(), e)
        window_type.setEditable(False)
        form.addRow("Type", window_type)

        # Window units
        window_unit_group = QGroupBox("Window size units:")
        window_tick = QRadioButton("ticks")
        window_time = QRadioButton("time")
        window_tick.setChecked(True)
        vbox = QVBoxLayout()
        vbox.addWidget(window_tick)
        vbox.addWidget(window_time)
        window_unit_group.setLayout(vbox)
        form.addRow(window_unit_group)

        # Window size
        window_size = QDoubleSpinBox()
        window_size.setMinimum(0)
        window_size.setSingleStep(1)
        form.addRow("window size", window_size)

        # TODO(rose@): Switch between a QDoubleSpinBox and a QSpinBox when the user changes the
        #              window units between ticks and time.

        # Add some standard buttons (Cancel/Ok) at the bottom of the dialog
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                           Qt.Horizontal, param_dialog);
        form.addRow(button_box);
        button_box.accepted.connect(param_dialog.accept)
        button_box.rejected.connect(param_dialog.reject)

        # Show the dialog as modal
        if param_dialog.exec() == QDialog.Accepted:
            # This is where the various values should be collected and stored.
            self._params = RunningWindowParams(window_type.itemData(window_type.currentIndex()),
                                               window_size.value(), window_tick.isChecked())

            return True

        return False


    def doMath(self, data, dt):
        # First, determine the winodw size. if it's a time, we need to conver to ticks
        window_sz = self._params.window_sz
        if not self._params.is_ticks:
            window_sz = round(self._params.window_sz / dt)
        else:
            self._params.window_sz = int(self._params.window_sz)

        if self._params.type == WindowTypes.MEAN:
            val = np.convolve(data.data, np.ones(int(window_sz)) / float(window_sz), mode='same')
        else:
            if window_sz % 2 == 0:
                window_sz += 1
            val = signal.medfilt(data.data, int(window_sz))

        return val

    def defaultVarName(self, vname):
        return f"RunningWindow({vname},{self._params.type.name.lower()},{self._params.window_sz},{int(self._params.is_ticks)})"
