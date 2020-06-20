# -*- coding: utf-8 -*-

try:
    from PySide import QtWidgets
except:
    from PyQt5 import QtWidgets

from subPlotWidget import subPlotWidget

''' This class is for management of a linked set of subplots
'''
class plotManager:
    def __init__(self, layout):

        # This is the layout containing the subplots
        self._layout = layout

        # We could probably get the list of subplots from the layout, but right now the layout
        # contains more than just plots, so keep a separate list here:
        self._subplots = []

    def addSubplot(self, idx=None):
        if not idx:
            idx = (self._layout.count(), len(self._subplots))
        subplot = subPlotWidget(self)
        self._layout.insertWidget(idx[0], subplot)
        self._subplots.insert(idx[1], subplot)
        self._linkAxes()

        #self._dispLayoutContents()

    def addSubplotAbove(self, subplot):
        layout_idx, list_idx = self._getIndex(subplot)
        self.addSubplot((layout_idx, list_idx))

    def addSubplotBelow(self, subplot):
        layout_idx, list_idx = self._getIndex(subplot)
        self.addSubplot((layout_idx+1, list_idx+1))

    def removeSubplot(self, subplot):
        if len(self._subplots) <= 1:
            # Don't allow the only remaining plot to be removed
            return
        self._subplots.remove(subplot)
        item = self._layout.takeAt(self._layout.indexOf(subplot))
        subplot.deleteLater()

        #self._dispLayoutContents()

        if len(self._subplots) <= 1:
            # Nothing else to do here
            return

        # We need to handle the special case of the first subplot being removed!
        # Re-link all axes to the first plot in the list
        self._linkAxes()

    def updateXRange(self, xmin, xmax):
        # Because plots are linked we only need to do this for the first plot. Others will follow suite.
        self._subplots[0].pw.setXRange(min=xmin, max=xmax, padding=0)

    def updateXLimits(self, xmin, xmax):
        # X axis range is linked, but limits are not.
        for sp in self._subplots:
            sp.pw.setLimits(xMin=xmin, xMax=xmax)

    def _linkAxes(self):
        for sp in self._subplots:
            if sp is self._subplots[0]:
                continue
            sp.pw.setXLink(self._subplots[0].pw)

    def _getIndex(self, subplot):
        ''' This method returns the index of the subplot (both from the layout and the list) '''
        return self._layout.indexOf(subplot), self._subplots.index(subplot)

    def _dispLayoutContents(self):
        print(f"There are {self._layout.count()} items in the layout")
        for i in range(self._layout.count()):
            print(f"{i} : {self._layout.itemAt(i)}")
            try:
                print(f"      {self._layout.itemAt(i).widget()}")
            except:
                pass
