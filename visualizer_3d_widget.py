# -*- coding: utf-8 -*-


from PyQt5.QtCore import Qt
from PyQt5.QtGui import QVector3D
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, \
    QLabel, QFileDialog

from pyqtgraph.opengl import GLViewWidget
import pyqtgraph.opengl as gl

import json
from docked_widget import DockedWidget
from geometry_helpers import create_triad, create_grid
from data_linked_geometry import DataLinkedSphere, DataLinkedRobotModel
from checkable_combo_box import CheckableComboBox

import os
from glob import glob
import numpy as np
import pinocchio as pin
from scipy.spatial.transform import Rotation

_LEG_NAMES_ = ("FL", "FR", "HL", "HR")
_DOF_NAMES_ = ("HX", "HY", "KN")
_DIR_ = ("x", "y", "z")
_QUAT_ = ("x", "y", "z", "w")

_estimator_str_ = "pos_acc_observer"

''' A thin QDockWidget wrapper around the Visualizer3DWidget object '''

kZero3d = np.zeros(3)
kZero3d.flags.writeable = False
kCartesianSize : int = 3
kQuaternionSize : int = 4

class DockedVisualizer3DWidget(DockedWidget):

    def __init__(self, parent=None, source=None):
        DockedWidget.__init__(self, "3D-Visualizer", parent=parent)

        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)

        self.setWidget(VisualizerWidget(parent=self, source=source))

    def set_source(self, source):
        self.widget().set_source(source)

    @property
    def has_source(self):
        return self.widget().has_source

    def update(self, tick):
        self.widget().update(tick)


class VisualizerWidget(QWidget):
    def __init__(self, parent=None, source=None):
        QWidget.__init__(self, parent=parent)

        self._source = source
        self._data_linked_geometry = []

        # Main layout that holds everything
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Add the 3D visualizer
        self._3d_viz = Visualizer3DWidget(parent=self, source=source)
        main_layout.addWidget(self._3d_viz)

        # Show and hide objects
        self._obj_list = CheckableComboBox()
        self._obj_list.model().itemChanged.connect(self.handleCheckStateChange)
        main_layout.addWidget(self._obj_list)

        self.addDefaultGeometry()
        self.addGeometryFromConfig("config/geometry.json")

    def addDefaultGeometry(self):
        self.addItem("ground_plane", create_grid())
        self.addItem("origin", create_triad())

    def addGeometryFromConfig(self, filename):
        resource_dir = os.path.dirname(filename)
        if not os.path.isfile(filename):
            return
        with open(filename, 'r') as f:
            config = json.load(f)
        for name, item in config.items():
            linked_geom = None
            if item["type"] == "sphere":
                print(item["data"])
                linked_geom = DataLinkedSphere(self._source, **item["data"])
            elif item["type"] == "robot":
                urdf_path = item["data"]["urdf_path"]
                # TODO: check if the path is absolute or relative then prepend the resource_dir
                if not os.path.isfile(urdf_path):
                    # Open a dialog box so the user can select a URDF file.
                    urdf_path, _ = QFileDialog.getOpenFileName(self, "Open URDF file",
                                                            resource_dir,
                                                            "URDF files (*.urdf)") 
                item["data"]["urdf_path"] = urdf_path
                linked_geom = DataLinkedRobotModel(self._source, **item["data"])
            elif item["type"] == "arrow":
                linked_geom = DataLinkedArrow(self._source, **item["data"])
            else:
                raise ValueError("Unknown geometry type: {}".format(item["type"]))

            if linked_geom is not None:
                self._data_linked_geometry.append(linked_geom)
                linked_geom.registerGeometry(lambda geom : self.addItem(name, geom))

    def addItem(self, name, item, checked=True):
        self._obj_list.addItem(name, item)
        self._obj_list.setItemChecked(self._obj_list.count() - 1, checked)
        self._3d_viz.addItem(item)

    def handleCheckStateChange(self, item):
        if item.checkState() == Qt.Unchecked:
            item.data(Qt.UserRole).hide()
        elif item.checkState() == Qt.Checked:
            item.data(Qt.UserRole).show()

    def update(self, tick):
        self._3d_viz.update_viz(tick)
        for g in self._data_linked_geometry:
            g.update(tick)

    @property
    def has_source(self):
        return self._source is not None

    def set_source(self, source):
        self._source = source
        for g in self._data_linked_geometry:
            g.set_source(source)


class Visualizer3DWidget(GLViewWidget):
    def __init__(self, parent=None, source=None):
        GLViewWidget.__init__(self, parent=parent)

        self.setMinimumSize(320, 240)
        self.resize(640, 480)
        self.setBackgroundColor((200, 200, 200, 255))
        self._source = source
        self.setCameraPosition(distance=1.0)
        self.geometry_to_track = None

    def trackGeometry(self, geometry):
        self.geometry_to_track = geometry

    def update_viz(self, tick):
        ''' Update the visualizer '''
        # Update the camera position to track the robot
        if self.geometry_to_track is not None:
            self.setCameraPosition(pos=QVector3D(*self._base_pos))
        # else:
        #     self.setCameraPosition(distance=1.0)
