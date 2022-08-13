import numpy as np

from maths.maths_base import MathSpecBase


class DifferentiateSpec(MathSpecBase):
    def __init__(self, parent):
        MathSpecBase.__init__(self, parent=parent, name="differentiate")

    def button_callback(self, checked):
        self.create_message_box()

    def get_params(self):
        return True

    def do_math(self, data, dt):
        return np.concatenate(([0], np.diff(data.data) / np.diff(data.time)))

    def default_var_name(self, vname):
        return f"Diff({vname})"


class IntegrateSpec(MathSpecBase):
    def __init__(self, parent):
        MathSpecBase.__init__(self, parent=parent, name="integrate")

    def button_callback(self, checked):
        self.create_message_box()

    def get_params(self):
        return True

    def do_math(self, data, dt):
        return np.cumsum(data.data * np.concatenate(([0], np.diff(data.time))))

    def default_var_name(self, vname):
        return f"Int({vname})"
