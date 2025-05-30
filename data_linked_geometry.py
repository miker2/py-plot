import os

from PyQt5.QtWidgets import QFileDialog

from geometry_helpers import (axis_angle_from_quat, create_arrow,
                              create_sphere, create_triad)
from robot_geometry import RobotModel


class DataLinkedGeometry:
    def __init__(self, data_source):
        self._data_source = data_source

    def _get_value_at_tick(self, tick, varname): 
        data = self._data_source.model().get_data_by_name(varname)
        if data is None:
            return 0
        return data[tick]

    def registerGeometry(self, register_fn, remove_fn):
        register_fn(self._geom)

        def on_close():
            self._data_source = None
            remove_fn(self._geom)

        self._data_source.onClose.connect(on_close)

    def update(self, tick):
        raise NotImplementedError

    def has_source(self):
        return self._data_source is not None

class DataLinkedRobotModel(DataLinkedGeometry):
    def __init__(self, data_source, *, urdf_path, joint_pattern, base_pos_pattern, base_pos_names, base_quat_pattern, base_quat_names, color=None):
        DataLinkedGeometry.__init__(self, data_source)

        self._geom = RobotModel(urdf_path, color=color)
        self._joint_pattern = joint_pattern
        self.base_pos_names = [base_pos_pattern.format(name) for name in base_pos_names]
        self.base_quat_names = [base_quat_pattern.format(name) for name in base_quat_names]
        
        self.has_floating_base =  data_source.model().has_key(self.base_pos_names[0])

    def update(self, tick):
        if self.has_source():
            # TODO: check that the box is checked, don't update if it's not
            self._geom.show()
            # Base link
            self._geom.resetTransform()

            # Rotate
            if self.has_floating_base:
                quat = [self._get_value_at_tick(tick, name) for name in self.base_quat_names]
                axis, angle = axis_angle_from_quat(quat)
                self._geom.rotate(angle, *axis)

                # Translate
                self._geom.translate(*[self._get_value_at_tick(tick, name) for name in self.base_pos_names])

            # Joints
            for joint in self._geom.joints:
                self._geom.setJointQ(joint, self._get_value_at_tick(tick, self._joint_pattern.format(joint)))
        else:
            self._geom.hide()

class DataLinkedSphere(DataLinkedGeometry):
    def __init__(self, data_source, *, pos_pattern, pos_names, color=(1., 1., 1., 1.), radius=0.05):
        DataLinkedGeometry.__init__(self, data_source)
        self._geom = create_sphere(radius, color)
        self._pos_names = [pos_pattern.format(name) for name in pos_names]

    def update(self, tick):
        if self.has_source():
            # TODO: check that the box is checked
            self._geom.show()
            pos = [self._get_value_at_tick(tick, name) for name in self._pos_names]
            self._geom.resetTransform()
            self._geom.translate(*pos)
        else:
            self._geom.hide()

class DataLinkedArrow(DataLinkedGeometry):
    def __init__(self, data_source, *, pos_pattern, pos_names, color=(1., 1., 1., 1.), width=2, pos=(0, 0, 0), vec=(0, 0, 0)):
        DataLinkedGeometry.__init__(self, data_source)
        self._geom = create_arrow(color, width, pos, vec)

    def update(self, tick):
        if self.has_source():
            # TODO: check that the box is checked
            self._geom.show()
            self._geom.resetTransform()
            axis, angle = axis_angle_from_quat(quat)
            self._geom.rotate(angle, *axis)
            self._geom.translate(*pos)
        else:
            self._geom.hide()

class DataLinkedFrame(DataLinkedGeometry):
    # TODO: Add label
    def __init__(self, data_source, *, pos_pattern, pos_names, quat_pattern, quat_names):
        DataLinkedGeometry.__init__(self, data_source)
        self._geom = create_triad()
        self._pos_names = [pos_pattern.format(name) for name in pos_names]
        self._quat_names = [quat_pattern.format(name) for name in quat_names]

    def update(self, tick):
        if self.has_source():
            # TODO: check that the box is checked
            self._geom.show()
            self._geom.resetTransform()

            # Rotate
            quat = [self._get_value_at_tick(tick, name) for name in self._quat_names]
            axis, angle = axis_angle_from_quat(quat)
            self._geom.rotate(angle, *axis)

            # Translate
            pos = [self._get_value_at_tick(tick, name) for name in self._pos_names]
            self._geom.resetTransform()
            self._geom.translate(*pos)
        else:
            self._geom.hide()
