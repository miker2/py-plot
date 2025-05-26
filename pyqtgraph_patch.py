import pyqtgraph as pg
from pyqtgraph.widgets.PlotWidget import PlotWidget

# Add autoRangeEnabled to PlotWidget
def autoRangeEnabled(self):
    return self.plotItem.getViewBox().autoRangeEnabled()

# Add the method to PlotWidget class
PlotWidget.autoRangeEnabled = autoRangeEnabled
