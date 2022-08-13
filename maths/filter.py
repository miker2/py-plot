from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSpinBox, QComboBox, QDoubleSpinBox, QCheckBox, QFormLayout, \
    QDialogButtonBox

try:
    from PyQt5.QtGui import QDialog
except ImportError:
    from PyQt5.QtWidgets import QDialog

from dataclasses import dataclass
from scipy import signal

from maths.maths_base import MathSpecBase


@dataclass
class FilterParams:
    order: int
    type: str
    cutoff: float
    filtfilt: bool


class FilterSpec(MathSpecBase):
    filter_types = ("low", "high")

    def __init__(self, parent):
        MathSpecBase.__init__(self, parent=parent, name="filter")

    def button_callback(self, checked):
        self.create_message_box()

    def get_params(self):
        # Create a dialog for getting the filter parameters.
        # Store results and then use them in the do_math method
        # Items we need:
        #  1. Filter order (QSpinBox)
        #  2. Type (low pass, high pass, others?) (QComboBox)
        #  3. Cutoff frequency (LineEdit or QDoubleSpinBox)
        #  4. Causal vs acausal (QCheckBox)
        param_dialog = QDialog(self.parent())
        form = QFormLayout(param_dialog)
        filt_order = QSpinBox()
        filt_order.setMinimum(1)
        form.addRow("Filter order", filt_order)
        filt_types = QComboBox()
        filt_types.addItems(FilterSpec.filter_types)
        filt_types.setEditable(False)
        form.addRow("Type", filt_types)
        filt_cutoff = QDoubleSpinBox()
        filt_cutoff.setMinimum(0)
        filt_cutoff.setDecimals(2)
        filt_cutoff.setSingleStep(1)
        form.addRow("cutoff [hz]", filt_cutoff)
        filt_filt = QCheckBox("filt-filt")
        form.addRow(filt_filt)

        # Add some standard buttons (Cancel/Ok) at the bottom of the dialog
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                      Qt.Horizontal, param_dialog)
        form.addRow(button_box)
        button_box.accepted.connect(param_dialog.accept)
        button_box.rejected.connect(param_dialog.reject)

        # Show the dialog as modal
        if param_dialog.exec() == QDialog.Accepted:
            # This is where the various values should be collected and stored.
            self._params = FilterParams(filt_order.value(), filt_types.currentText(),
                                        filt_cutoff.value(), filt_filt.isChecked())

            return True

        return False

    def do_math(self, data, dt):
        fs = 1 / dt
        Wn = self._params.cutoff / (0.5 * fs)
        b, a = signal.butter(self._params.order, Wn, btype=self._params.type)
        if self._params.filtfilt:
            return signal.filtfilt(b, a, data.data, method='gust')
        else:
            return signal.lfilter(b, a, data.data)

    def default_var_name(self, vname):
        return f"Filter({vname},{self._params.order},{self._params.type},{self._params.cutoff})"
