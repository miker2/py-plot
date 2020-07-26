# -*- coding: utf-8 -*-


from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QSettings, QSize, QPoint, QEvent
from PyQt5.QtWidgets import QWidget, QDockWidget
from PyQt5.QtGui import QVector3D

from pyqtgraph.opengl import GLViewWidget
import pyqtgraph.opengl as gl

import os
import numpy as np
import pinocchio as pin

_LEG_NAMES_ = ("FL", "FR", "HL", "HR")
_DOF_NAMES_ = ("HX", "HY", "KN")
_DIR_ = ("x", "y", "z")
_QUAT_ = ("x", "y", "z", "w")

''' A thin QDockWidget wrapper around the Visualizer3DWidget object '''
class DockedVisualizer3DWidget(QDockWidget):

    onClose = pyqtSignal()

    def __init__(self, parent=None, source=None):
        QDockWidget.__init__(self, "3D Visualizer", parent=parent)

        self._settings_read = False  # a hack until I can sort out the sizing logic
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)

        self._visualizer = Visualizer3DWidget(parent=self, source=source)
        self.setWidget(self._visualizer)

        self.topLevelChanged.connect(self._onDockStateChange)

        self._readSettings()

    def closeEvent(self, event):
        self._writeSettings()
        self._visualizer.close()
        self.onClose.emit()
        event.accept()

    def setSource(self, source):
        self._visualizer.setSource(source)

    @property
    def hasSource(self):
        return self._visualizer.hasSource

    def update(self, tick):
        self._visualizer.updateViz(tick)

    def _readSettings(self):
        settings = QSettings()

        settings.beginGroup("3DVisualizer")
        self._undocked_size = settings.value("size", QSize(640, 480))
        self._docked_size = settings.value("docked_size", QSize(320, 500))
        self._undocked_pos = settings.value("position")

        is_floating = bool(int(settings.value("floating", 1)))
        self.setFloating(is_floating)
        settings.endGroup()
        self._settings_read = True

    def _writeSettings(self):
        settings = QSettings()

        settings.beginGroup("3DVisualizer")
        # Convert to an int because it's easier to parse when reading
        settings.setValue("floating", int(self.isFloating()))
        settings.setValue("size", self._undocked_size)
        settings.setValue("docked_size", self._docked_size)
        if self.isFloating():
            settings.setValue("position", self.pos())
        settings.endGroup()

    def _onDockStateChange(self, is_floating):
        if is_floating:
            self.move(self._undocked_pos)
            self.resize(self._undocked_size)
        else:
            self.resize(self._docked_size)

    def resizeEvent(self, event):
        if self._settings_read:
            # Capture the size of the widget when it changes so that we can restore
            # the proper size on dock/undock events
            if self.isFloating():
                self._undocked_size = self.size()
            else:
                self._docked_size = self.size()
        super().resizeEvent(event)

    #def moveEvent(self, event):
    #    super().moveEvent(event)
    #    print("In moveEvent")
    #    if self.isFloating():
    #        self._undocked_pos = event.pos()

# Shape helpers:
def _createArrow(color=(1., 1., 1., 1.), width=2, pos=[0, 0, 0], vec=[0, 0, 0]):
    # Not much of an arrow at the moment, but it will have to do for now.
    pos = np.array(pos)
    vec = pos + np.array(vec)
    data = np.zeros((2, 3))
    data[0,:] = pos
    data[1,:] = vec
    arrow = gl.GLLinePlotItem(pos=data, color=color, width=width)
    return arrow

def _createSphere(radius=0.05, color=(1., 0, 0, 1.), draw_faces=True, draw_edges=False):
    sphere = gl.MeshData.sphere(rows=10, cols=10, radius=radius)
    mesh = gl.GLMeshItem(meshdata=sphere, smooth=True,
                         drawFaces=draw_faces, color=color,
                         drawEdges=draw_edges, edgeColor=color)
    return mesh


class Visualizer3DWidget(GLViewWidget):
    def __init__(self, parent=None, source=None):
        GLViewWidget.__init__(self, parent=parent)

        self.setMinimumSize(320, 240)
        self.resize(640, 480)

        self.setBackgroundColor((200, 200, 200, 255))

        self.setSource(source)

        self._tick = 0

        self.setCameraPosition(distance=1.0)

        # Use pinocchio to update the kinematics
        resource_dir, _ = os.path.split(os.path.realpath(__file__))
        filename = os.path.join(resource_dir, "laikago.urdf")
        self.kin_model = pin.buildModelFromUrdf(filename, pin.JointModelFreeFlyer())
        self.kin_data = self.kin_model.createData()

        # First, we need to draw the ground plane:
        grid = gl.GLGridItem()
        # grid.scale(1, 1, 1)
        #grid.setColor((0, 0, 255, 128))

        self.addItem(grid)

        self.p_com = _createSphere(radius=0.01, color=(1., 0, 0, 1.))
        self.addItem(self.p_com)

        self.p_cop = _createSphere(radius=0.01, color=(0, 0, 1., 1.))
        self.addItem(self.p_cop)

        # We want to create an array of "force_vectors" to display the foot forces
        self.foot_pos = [None]*len(_LEG_NAMES_)
        self.force_vectors = [None]*len(_LEG_NAMES_)
        self.leg_chains = [None]*len(_LEG_NAMES_)
        force_vec_color = (0, 204./255, 26./255, 1.)
        for i in range(len(_LEG_NAMES_)):
            self.foot_pos[i] = _createSphere(radius=0.01, color=force_vec_color)
            self.addItem(self.foot_pos[i])
            self.force_vectors[i] = _createArrow(color=force_vec_color)
            self.addItem(self.force_vectors[i])

            self.leg_chains[i] = gl.GLLinePlotItem(pos=np.zeros(3), width=3,
                                                   color=(0, 148./255, 1., 1.))
            self.addItem(self.leg_chains[i])

    def setSource(self, source):
        self._source = source
        if self._source:
            self._source.onClose.connect(self._removeSource)
            print(f"Source is: {self._source.filename}")

    @property
    def hasSource(self):
        return not self._source is None

    def _removeSource(self):
        self._source = None

    def updateViz(self, tick):
        self._tick = tick
        if not self.hasSource:
            return
        if tick >= self._source.model().tick_max:
            return
        # This is the meat of this widget. This is where the drawing should
        # happen!
        self.drawForceVectors()

        self.drawPositions()

        self.updateKinematics()

        base_pos = np.zeros(3)
        for i in range(len(_DIR_)):
            base_pos[i] = self._getValueAtTick(f"kin_pose_est.p_body_rt_world.{_DIR_[i]}")
        self.setCameraPosition(pos=QVector3D(*base_pos))

    def drawForceVectors(self):

        pos_str = "ctrl_data.{}.p_ft_rt_w.{}"
        force_str = "lemo.{}.ffe.f_ewrt_w.{}"
        for idx in range(len(self.force_vectors)):
            # We need to look up the position of the foot and the force:
            leg = _LEG_NAMES_[idx]
            pos = np.zeros(3)
            force = np.zeros(3)
            for i in range(len(_DIR_)):
                pos[i] = self._getValueAtTick(pos_str.format(leg, _DIR_[i]))
                force[i] = self._getValueAtTick(force_str.format(leg, _DIR_[i]))
            data = np.zeros((2, 3))
            data[0,:] = pos
            data[1,:] = pos + force / 200  # Scale the force a bit
            self.force_vectors[idx].setData(pos=data)
            self.foot_pos[idx].resetTransform()
            self.foot_pos[idx].translate(*pos)

    def drawPositions(self):
        p_com = np.zeros(3)
        p_cop = np.zeros(3)
        for i in range(len(_DIR_)):
            p_com[i] = self._getValueAtTick(f"ctrl_data.p_com.{_DIR_[i]}")
            p_cop[i] = self._getValueAtTick(f"p_cop_rt_world.{_DIR_[i]}")
        self.p_com.resetTransform()
        self.p_com.translate(*p_com)
        self.p_cop.resetTransform()
        self.p_cop.translate(*p_cop)

    def updateKinematics(self):
        q = np.zeros(self.kin_model.nq)
        # First, update the base position
        for i in range(len(_DIR_)):
            q[i] = self._getValueAtTick(f"kin_pose_est.p_body_rt_world.{_DIR_[i]}")
        # Get the orientation
        for i in range(len(_QUAT_)):
            q[i+3] = self._getValueAtTick(f"imu.quat.{_QUAT_[i]}")
        for l in _LEG_NAMES_:
            for ld in _DOF_NAMES_:
                dof = f"{l}.{ld}"
                jname = f"{dof}_joint"
                ji = self.kin_model.getJointId(jname)
                qi = self.kin_model.joints[ji].idx_q
                q[qi] = self._getValueAtTick(f"lemo.{dof}.q")
        pin.forwardKinematics(self.kin_model, self.kin_data, q)

        # Get the support for each foot, then collect the positions of each
        # joint in the support and update the leg chain values
        for l in range(len(_LEG_NAMES_)):
            leg = _LEG_NAMES_[l]
            foot_frame_id = self.kin_model.getFrameId(f"{leg}.foot_centre")

            supports = self.kin_model.supports[self.kin_model.frames[foot_frame_id].parent]
            n_dof = len(supports)
            # We want to ignore the "universe" joint but add the foot position
            j_pos = np.zeros((n_dof, 3))
            for i in range(1, n_dof):
                j = supports[i]
                # Get the joint position and add it to the position array
                o_T_i = self.kin_data.oMi[j]
                j_pos[i-1,:] = o_T_i.translation.flatten()
            # Finally, update the position of the foot frame and add it to the
            # end of the position array.
            pin.updateFramePlacement(self.kin_model, self.kin_data,
                                     foot_frame_id)
            j_pos[-1,:] = self.kin_data.oMf[foot_frame_id].translation.flatten()
            self.leg_chains[l].setData(pos=j_pos)

    def _getValueAtTick(self, varname):
        return self._source.model().getDataByName(varname)[self._tick]
