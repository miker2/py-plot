
import numpy as np

from maths.maths_base import MathSpecBase

class DifferentiateSpec(MathSpecBase):
    def __init__(self, parent):
        MathSpecBase.__init__(self, parent=parent, name="differentiate")

    def buttonCallback(self, checked):
        self.createMessageBox()

    def getParams(self):
        return True

    def doMath(self, data, dt):
        return np.concatenate(([0], np.diff(data.data) / np.diff(data.time)))

    def defaultVarName(self, vname):
        return f"Diff({vname})"


class IntegrateSpec(MathSpecBase):
    def __init__(self, parent):
        MathSpecBase.__init__(self, parent=parent, name="integrate")

    def buttonCallback(self, checked):
        self.createMessageBox()

    def getParams(self):
        return True

    def doMath(self, data, dt):
        return np.cumsum(data.data * np.concatenate(([0], np.diff(data.time))))

    def defaultVarName(self, vname):
        return f"Int({vname})"
