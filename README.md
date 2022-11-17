# py-plot

## Quickstart

A conda environment yaml file has been provided for convenience which contains all of the necessary dependencies. You can create this environment by running:
```
conda env create --file environment.yml
```
This will create a conda environment with the name `py-plot`. If an existing conda environment is running, then deactivate it (i.e. `conda deactivate`) and activate the py-plot environement (i.e. `conda activate py-plot`).

From within the environment, run `python main.py` to launch py-plot.

## Required dependencies:

*  Qt5
*  numpy
*  pandas
*  pyqt5
*  pyqtgraph
*  pyopengl
*  pinocchio (a python module used for forward kinematics)
*  scipy


The recommended method for installing these dependencies is via `conda`. Alternatively, your system package manager and `pip` can be used instead (for all dependencies except `pinocchio`).
```
conda install -c conda-forge numpy pandas pyqt pyqtgraph pyopengl pinocchio scipy
```

When installing via the `apt` package manager the following additional dependencies are required:
```
sudo apt-get install python3-opengl python3-pyqt5.qtopengl
```
