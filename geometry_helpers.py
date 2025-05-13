import numpy as np
from scipy.spatial.transform import Rotation
import pyqtgraph.opengl as gl
from urdfpy import URDF

def axis_angle_from_quat(quat):
    '''Extracts the axis and angle (in degrees) of a rotation from a quaternion'''
    rotation = Rotation.from_quat(quat)

    rotvec = rotation.as_rotvec(degrees=True)
    angle = np.linalg.norm(rotvec)
    if angle > 1e-5:
        axis = rotvec / angle
    else:
        axis = np.array([0, 0, 1])
    return axis, angle

def create_arrow(color=(1., 1., 1., 1.), width=2, pos=(0, 0, 0), vec=(0, 0, 0)):
    # Not much of an arrow at the moment, but it will have to do for now.
    pos = np.array(pos)
    vec = pos + np.array(vec)
    data = np.zeros((2, 3))
    data[0, :] = pos
    data[1, :] = vec
    arrow = gl.GLLinePlotItem(pos=data, color=color, width=width, glOptions='opaque')
    return arrow

def create_sphere(radius=0.05, color=(1., 0, 0, 1.), draw_faces=True, draw_edges=False):
    sphere = gl.MeshData.sphere(rows=10, cols=10, radius=radius)
    mesh = gl.GLMeshItem(meshdata=sphere, smooth=True,
                         drawFaces=draw_faces, color=color,
                         drawEdges=draw_edges, edgeColor=color)
    return mesh


TRIAD_SIZE = 0.1

def create_triad(triad_size=TRIAD_SIZE):
    triad = gl.GLAxisItem(glOptions='opaque')
    triad.setSize(x=triad_size, y=triad_size, z=triad_size)
    return triad


def create_grid(scale=None, color = None):
    grid = gl.GLGridItem()
    if scale is not None:
        grid.scale(scale, scale, scale)
    if color is not None:
        grid.setColor(color)
    return grid