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

    def get_operation_details(self):
        # Differentiation is straightforward, parameters could be added if different methods are implemented
        return {'method': 'finite_difference', 'order': 1}

    def get_source_type(self):
        return "math_diff"


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

    def get_operation_details(self):
        # Integration is also straightforward for this implementation
        return {'method': 'cumulative_sum'}

    def get_source_type(self):
        return "math_integrate"
