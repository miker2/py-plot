# py-plot

## Required dependencies:

*  Qt5
*  pyqt5
*  pyqtgraph
*  pyopengl
*  pinocchio (a python module used for forward kinematics)


The recommended method for installing these dependencies is via `conda`. Alternatively, your system package manager and `pip` can be used instead (for all dependencies except `pinocchio`).
```
conda install -c conda-forge pyqtgraph pyopengl pinocchio
```

When installing via the `apt` package manager the following additional dependencies are required:
```
sudo apt-get install python3-opengl python3-pyqt5.qtopengl
```

