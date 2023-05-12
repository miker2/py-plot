from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QMatrix4x4
from PyQt5.QtWidgets import QHBoxLayout, QComboBox, QSlider

from urdfpy import URDF
import pyqtgraph.opengl as gl
import numpy as np

import math
import os

from geometry_helpers import create_sphere

__LEAD_DENSITY__=11340  # kg / m^3

class RobotLink(gl.GLGraphicsItem.GLGraphicsItem):
    DEFAULT_COLOR=(0.7, 0.7, 0.7, 1.0)
    def __init__(self, link_info, color=None, display_link_com=False):
        gl.GLGraphicsItem.GLGraphicsItem.__init__(self)

        self.name = link_info.name
        self.parent_joint = None
        self._static_transform = QMatrix4x4()
        self._pos = 0

        # NOTE: Color logic:
        #  1. If a color is passed into this object, use it first
        #  2. If a color is specified in the URDF (via link_info), use it second
        #  3. If all else fails, use the default color.
        self.visuals = []
        for visual in link_info.visuals:
            opt='opaque'
            if color is None and visual.material is not None and visual.material.color is not None:
                color = visual.material.color
            elif color is None:
                color = RobotLink.DEFAULT_COLOR
            if color[-1] < 1:
                opt='translucent'
            edge_color = 0.8 * np.array(color)  # Make the edge colors slightly darker than the face colors
            for mesh in visual.geometry.meshes:
                mesh_data = gl.MeshData(vertexes=mesh.vertices, faces=mesh.faces)
                mesh = gl.GLMeshItem(meshdata=mesh_data, drawEdges=True, color=color, edgeColor=edge_color, \
                                     glOptions='translucent', shader='shaded')
                mesh.setTransform(visual.origin)
                mesh.setParentItem(self)
                self.visuals.append(mesh)

        if display_link_com:
            # Add a sphere representing the mass of the link (at the CoM location)
            # The sphere radius is determined using a representative sphere with the density of lead
            lead_volume = link_info.inertial.mass / __LEAD_DENSITY__
            lead_radius = (lead_volume * 3 / 4 / math.pi) ** (1/3)
            self.com = create_sphere(radius=lead_radius, color=(0., 0., 1., 0.9))
            self.com.setParentItem(self)
            self.com.setTransform(link_info.inertial.origin)
            self.inertia = []

    def setParentJoint(self, joint):
        self._type = joint.joint_type
        self._axis = joint.axis
        self._limit = joint.limit
        self._static_transform = QMatrix4x4(*joint.origin.ravel())
        self.setTransform(self._static_transform)

    @property
    def pos(self):
        return self._pos

    @property
    def limits(self):
        return self._limit

    def setJointQ(self, q):
        self._pos = q
        self.setTransform(self._static_transform)
        clamp = lambda x: max(self._limit.lower, min(x, self._limit.upper))
        j_transform = QMatrix4x4()
        if self._type == 'prismatic':
            j_transform.translate(*(clamp(q) * self._axis))
        elif self._type == 'revolute':
            j_transform.rotate(clamp(q)*180/math.pi, *self._axis)
        elif self._type == 'continuous':
            j_transform.rotate(q*180/math.pi, *self._axis)
        else:
            print(f"Unsupported joint type - '{self._type}'")

        self.applyTransform(j_transform, local=True)

    def hideCoM(self):
        self.com.hide()

    def showCoM(self):
        self.com.show()


class RobotModel(gl.GLGraphicsItem.GLGraphicsItem):

    joint_moved = pyqtSignal()

    def __init__(self, urdf_file, color=None):
        gl.GLGraphicsItem.GLGraphicsItem.__init__(self)

        # Create the layout here that will be used to hold the controls. This may be unused.
        self._layout = QHBoxLayout()

        print(f"Creating model from {os.path.basename(urdf_file)}")
        robot_info = URDF.load(urdf_file)

        self.links = {}
        for link in robot_info.links:
            self.links[link.name] = RobotLink(link, color=color)

        # A mapping of joint to child link names
        self.joints = {}
        for joint in robot_info.joints:
            print(f"Connected {joint.child} to {joint.parent}")
            self.links[joint.child].setParentJoint(joint)
            self.links[joint.child].setParentItem(self.links[joint.parent])
            if joint.joint_type == "fixed":
                continue
            # Store the child link in the joint map
            self.joints[joint.name] = joint.child

        self.links[robot_info.base_link.name].setParentItem(self)

    def setJointQ(self, joint, q):
        if joint in self.joints:
            self.links[self.joints[joint]].setJointQ(q)
            self.joint_moved.emit()
        else:
            print(f"Invalid joint name: '{joint}'")

    def setJointQs(self, qs):
        if len(qs) != len(self.joints):
            print(f"Error, supplied joint length doesn't match actual joint length ({len(qs)} != {len(self.joints)})")
            return

        for i, q in enumerate(qs):
            self.links[i+1].setJointQ(q)

    def hideCoM(self):
        for name, link in self.links.items():
            link.hideCoM()
        self.update()

    def showCoM(self):
        for name, link in self.links.items():
            link.showCoM()
        self.update()

class RobotCoMProxy:
    def __init__(self, robot):
        self.robot = robot

    def show(self):
        self.robot.showCoM()

    def hide(self):
        self.robot.hideCoM()