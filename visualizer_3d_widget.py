# -*- coding: utf-8 -*-


import os
import pprint
from glob import glob

import commentjson as json
import numpy as np
import pyqtgraph.opengl as gl
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QColorDialog, QFileDialog, QMenu, QVBoxLayout,
                             QWidget)
from pyqtgraph.opengl import GLViewWidget

from checkable_combo_box import CheckableComboBox
from data_linked_geometry import (DataLinkedArrow, DataLinkedRobotModel,
                                  DataLinkedSphere)
from docked_widget import DockedWidget
from geometry_helpers import create_grid, create_triad
from robot_geometry import RobotLink

''' A thin QDockWidget wrapper around the Visualizer3DWidget object '''

kZero3d = np.zeros(3)
kZero3d.flags.writeable = False
kCartesianSize : int = 3
kQuaternionSize : int = 4

class DockedVisualizer3DWidget(DockedWidget):

    def __init__(self, parent=None, sources=None):
        DockedWidget.__init__(self, "3D-Visualizer", parent=parent)

        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)

        self.setWidget(VisualizerWidget(parent=self, sources=sources))

    def set_source(self, name, source):
        self.widget().set_source(name, source)

    def has_source(self, name):
        return self.widget().has_source(name)

    def update(self, tick):
        self.widget().update(tick)


class VisualizerWidget(QWidget):
    DEFAULT_BGCOLOR=QColor(200, 200, 200, 255)
    DEFAULT_GRIDCOLOR=QColor(255, 255, 255, 76)
    SETTING_BGCOLOR="background_color"
    SETTING_GRIDCOLOR="grid_color"
    def __init__(self, parent=None, sources=None):
        QWidget.__init__(self, parent=parent)

        self._sources = dict()
        if sources is not None:
            self._sources = sources
            pprint.pprint(self._sources)

        self._data_linked_geometry = dict()

        self._tick = 0

        # Main layout that holds everything
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Add the 3D visualizer
        self._3d_viz = Visualizer3DWidget(parent=self)
        main_layout.addWidget(self._3d_viz)

        # Show and hide objects
        self._obj_list = CheckableComboBox()
        self._obj_list.model().itemChanged.connect(self.handleCheckStateChange)
        main_layout.addWidget(self._obj_list)

        self._source_info = dict()

        prefs = QSettings()
        prefs.beginGroup("Preferences")
        self._urdf_base_path = prefs.value("urdf_path", "~")
        self._geometry_json_path = prefs.value("geometry_json", "config/geometry.json")
        prefs.endGroup()

        self.addDefaultGeometry()
        self.loadConfig(self._geometry_json_path)

    @property
    def settings(self):
        # Expose the parent settings so child objects have access
        return self.parent()._settings

    def addDefaultGeometry(self):
        grid_color = self.settings.value(VisualizerWidget.SETTING_GRIDCOLOR,
                                               VisualizerWidget.DEFAULT_GRIDCOLOR)
        self.addItem("ground_plane", create_grid(color=grid_color))
        self.addItem("origin", create_triad())

    def loadConfig(self, filename):
        if not os.path.isfile(filename):
            return
        try:
            with open(filename, 'r') as f:
                config = json.load(f)
            for source_config in config["sources"]:
                source_name = source_config["name"]
                self._source_info[source_name] = source_config["geometry"]
            if len(self._source_info.keys()) == 0:
                print(f"Warning: No sources found in geometry config ({filename})")
        except KeyError as e:
            print(e.args)
            print(f"Error loading geometry config ({filename}) - missing element: {e}")
        except json.commentjson.JSONLibraryException as e:
            print(f"Error loading geometry config ({filename}). Malformed JSON:\n{e}")

    def createGeometryFromConfig(self, source, source_name):
        # Reload the URDF path here in case it has changed since startup
        prefs = QSettings()
        prefs.beginGroup("Preferences")
        self._urdf_base_path = prefs.value("urdf_path", self._urdf_base_path)
        prefs.endGroup()

        source_type = os.path.basename(source_name)
        resource_dir = os.path.dirname(self._geometry_json_path)

        if source_type not in self._source_info:
            return

        # TODO: Check if we still need to track this _data_linked_geometry
        self._data_linked_geometry[source_name] = []
        for name, item in self._source_info[source_type].items():
            linked_geom = None
            if item["type"] == "sphere":
                linked_geom = DataLinkedSphere(source, **item["data"])
            elif item["type"] == "robot":
                urdf_path = item["data"]["urdf_path"]
                if not os.path.isabs(urdf_path):
                    # Prepend the urdf directory from the preferences
                    urdf_path = os.path.join(self._urdf_base_path, urdf_path)
                if not os.path.isfile(urdf_path):
                    # Open a dialog box so the user can select a URDF file.
                    urdf_path, _ = QFileDialog.getOpenFileName(self, "Open URDF file",
                                                            resource_dir,
                                                            "URDF files (*.urdf)")
                item["data"]["urdf_path"] = urdf_path
                linked_geom = DataLinkedRobotModel(source, **item["data"])
            elif item["type"] == "arrow":
                linked_geom = DataLinkedArrow(source, **item["data"])
            else:
                raise ValueError("Unknown geometry type: {}".format(item["type"]))

            if linked_geom is not None:
                self._data_linked_geometry[source_name].append(linked_geom)
                linked_geom.registerGeometry(lambda geom : self.addItem(name, geom),
                                             lambda geom : self.removeItem(name, geom))

    def addItem(self, name, item, checked=True):
        self._obj_list.addItem(name, item)
        self._obj_list.setItemChecked(self._obj_list.count() - 1, checked)
        self._3d_viz.addItem(item)

    def removeItem(self, name, item):
        idx = self._obj_list.findData(item)
        self._obj_list.removeItem(idx)
        self._3d_viz.removeItem(item)

    def handleCheckStateChange(self, item):
        if item.checkState() == Qt.Unchecked:
            item.data(Qt.UserRole).hide()
        elif item.checkState() == Qt.Checked:
            item.data(Qt.UserRole).show()

    def update(self, tick):
        self._tick = tick
        for name, geometries in self._data_linked_geometry.items():
            if not self.has_source(name):
                continue
            for g in geometries:
                g.update(tick)
        self._3d_viz.update_viz(tick)

    def has_source(self, name):
        return name in self._sources

    def set_source(self, name, source):
        source_type = os.path.basename(name)

        # Don't create duplicate geometry if this file has been opened twice
        if name in self._sources:
            return

        self._sources[name] = source
        self.createGeometryFromConfig(source, name)

        for g in self._data_linked_geometry[name]:
            # Call first update to put everything in the right place
            g.update(self._tick)

class Visualizer3DWidget(GLViewWidget):
    def __init__(self, parent=None):
        GLViewWidget.__init__(self, parent=parent)

        self.setMinimumSize(320, 240)
        self.resize(640, 480)
        # Read the background color from the settings if it exists, otherwise, use the default
        self.bg_color = parent.settings.value(VisualizerWidget.SETTING_BGCOLOR,
                                               VisualizerWidget.DEFAULT_BGCOLOR)
        self.setBackgroundColor(self.bg_color)
        # Fix the slightly wonky perspective
        self.setCameraParams(distance=4.00, fov=20)
        self.geometry_to_track = None

    def trackGeometry(self, geometry):
        self.geometry_to_track = geometry

    def update_viz(self, tick):
        ''' Update the visualizer '''
        # Update the camera position to track the robot
        if self.geometry_to_track is not None:
            self.setCameraPosition(pos=self.geometry_to_track.viewTransform().column(3).toVector3D())
        # else:
        #     self.setCameraPosition(distance=1.0)

    def  contextMenuEvent(self, event):
        # Collect a list of robot links that are under the event location (within a 10x10 pixel area)
        items = self.itemsAt((event.x()-5, event.y()-5, 10, 10))
        links = {}
        ground_plane = None
        for item in items:
            link = None
            if isinstance(item, RobotLink):
                link = item
            elif isinstance(item.parentItem(), RobotLink):
                link = item.parentItem()
            elif isinstance(item, gl.GLGridItem):
                ground_plane = item

            # If one of the items (or its parent) is a robot link, add it to the dictionary
            if link is not None:
                links[link.name] = link

        # If a link is being tracked add a mechanism to stop tracking
        if self.geometry_to_track is not None:
            links["none"] = None

        menu = QMenu(self)
        bgColorAction = menu.addAction("Set background color")
        gridColorAction = menu.addAction("Set grid color")
        if ground_plane is not None:
            gridColorAction.setData(ground_plane)
        else:
            gridColorAction.setVisible(False)

        for name, link in links.items():
            trackLinkAction = menu.addAction(f"Track {name}")
            trackLinkAction.setData(link)

        action = menu.exec_(self.mapToGlobal(event.pos()))

        if action == bgColorAction:
            bg_color = QColorDialog.getColor(self.bg_color, self, "Select background color")
            if bg_color.isValid():
                self.bg_color = bg_color
                self.setBackgroundColor(self.bg_color)
                self.parent().settings.setValue(VisualizerWidget.SETTING_BGCOLOR,
                                                self.bg_color)
        if action == gridColorAction:
            grid_color = QColorDialog.getColor(VisualizerWidget.DEFAULT_GRIDCOLOR, self, "Select grid color",
                                               QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if grid_color.isValid():
                action.data().setColor(grid_color)
                self.parent().settings.setValue(VisualizerWidget.SETTING_GRIDCOLOR,
                                                grid_color)
        elif action is not None and action.text().startswith("Track"):
            self.trackGeometry(action.data())
