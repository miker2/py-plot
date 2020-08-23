# -*- coding: utf-8 -*-


from PyQt5.QtCore import Qt, pyqtSignal, QSettings, QSize, QPoint, QEvent
from PyQt5.QtGui import QVector3D
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, \
    QLabel

from pyqtgraph.opengl import GLViewWidget
import pyqtgraph.opengl as gl

from docked_widget import DockedWidget

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
class DockedVisualizer3DWidget(DockedWidget):

    def __init__(self, parent=None, source=None):
        DockedWidget.__init__(self, "3D-Visualizer", parent=parent)

        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)

        self.setWidget(VisualizerWidget(parent=self, source=source))

    def setSource(self, source):
        self.widget()._3d_viz.setSource(source)

    @property
    def hasSource(self):
        return self.widget()._3d_viz.hasSource

    def update(self, tick):
        self.widget()._3d_viz.updateViz(tick)


class VisualizerWidget(QWidget):
    def __init__(self, parent=None, source=None):
        QWidget.__init__(self, parent=parent)

        main_layout = QVBoxLayout()

        self._3d_viz = Visualizer3DWidget(parent=self, source=source)
        main_layout.addWidget(self._3d_viz)

        robo_selector_layout = QHBoxLayout()
        robo_selector_layout.addWidget(QLabel("Robot: "))
        self._robo_selector = QComboBox()
        for r in glob("*.urdf")+glob("**/*.urdf"):
            robot, _ = os.path.splitext(os.path.basename(r))
            self._robo_selector.addItem(robot, r)
        robo_selector_layout.addWidget(self._robo_selector)
        self._robo_selector.currentIndexChanged.connect(self._update_robot_model)
        main_layout.addLayout(robo_selector_layout)

        self.setLayout(main_layout)

    def _update_robot_model(self, idx):
        urdf_path = self._robo_selector.itemData(idx)
        self._3d_viz.setRobotModel(urdf_path)

# Shape helpers:
def _createArrow(color=(1., 1., 1., 1.), width=2, pos=[0, 0, 0], vec=[0, 0, 0]):
    # Not much of an arrow at the moment, but it will have to do for now.
    pos = np.array(pos)
    vec = pos + np.array(vec)
    data = np.zeros((2, 3))
    data[0,:] = pos
    data[1,:] = vec
    arrow = gl.GLLinePlotItem(pos=data, color=color, width=width, glOptions='opaque')
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

        self._base_pos = np.zeros(len(_DIR_))
        self._wRb = np.zeros(len(_QUAT_))

        self.setCameraPosition(distance=1.0)

        # Use pinocchio to update the kinematics
        self.setRobotModel("laikago.urdf")

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
                                                   color=(0, 148./255, 1., 1.),
                                                   glOptions='opaque')
            self.addItem(self.leg_chains[i])

        self.base_triad = gl.GLAxisItem(glOptions='opaque')
        BASE_TRIAD_SIZE = 0.1
        self.base_triad.setSize(x=BASE_TRIAD_SIZE, y=BASE_TRIAD_SIZE, z=BASE_TRIAD_SIZE)
        self.addItem(self.base_triad)

    def setSource(self, source):
        self._source = source
        if self._source:
            self._source.onClose.connect(self._removeSource)
            print(f"Source is: {self._source.filename}")

    @property
    def hasSource(self):
        return not self._source is None

    def setRobotModel(self, model_path):
        # Use pinocchio to update the kinematics
        resource_dir, _ = os.path.split(os.path.realpath(__file__))
        filename = os.path.join(resource_dir, model_path)
        self.kin_model = pin.buildModelFromUrdf(filename, pin.JointModelFreeFlyer())
        self.kin_data = self.kin_model.createData()
        self.paintGL()

    def _removeSource(self):
        self._source = None

    def updateViz(self, tick):
        self._tick = tick
        if not self.hasSource:
            return
        if tick >= self._source.model().tick_max:
            return

        # Cache the base position and orientation here since they'll be used in multiple places.
        for i in range(len(_DIR_)):
            self._base_pos[i] = self._getValueAtTick(f"{_estimator_str_}.p_body_rt_world.{_DIR_[i]}")
        for i in range(len(_QUAT_)):
            self._wRb[i] = self._getValueAtTick(f"imu.quat.{_QUAT_[i]}")

        # This is the meat of this widget. This is where the drawing should
        # happen!
        self.drawForceVectors()

        self.drawPositions()

        self.updateKinematics()

        self.updateBaseFrame()

        self.setCameraPosition(pos=QVector3D(*self._base_pos))

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
            q[i] = self._base_pos[i]
        # Get the orientation
        for i in range(len(_QUAT_)):
            q[i+3] = self._wRb[i]
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

    def updateBaseFrame(self):
        # Get base to world transform:
        wRb = Rotation.from_quat(self._wRb)

        self.base_triad.resetTransform()
        ax_ang = wRb.as_rotvec()
        ang = np.linalg.norm(ax_ang) * 180 / np.pi
        try:
            axis = ax_ang / np.linalg.norm(ax_ang)
        except Exception as ex:
            print(ex)
            axis = np.array([0, 0, 1])
        self.base_triad.rotate(ang, *axis)
        self.base_triad.translate(*self._base_pos)

    def _getValueAtTick(self, varname):
        return self._source.model().getDataByName(varname)[self._tick]
