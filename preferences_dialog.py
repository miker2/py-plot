from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                            QLabel, QPushButton, QGroupBox, QFormLayout,
                            QLineEdit, QFileDialog)
import os

class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.settings = QSettings()

        # Get the repository root directory (where main.py is located)
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Create the main layout
        layout = QVBoxLayout()

        # Create 3D visualization settings group
        viz_group = QGroupBox("3D Visualization Settings")
        viz_layout = QFormLayout()

        # URDF base path
        urdf_layout = QHBoxLayout()
        self.urdf_path = QLineEdit()
        self.urdf_path.setText(self.settings.value("urdf_path", repo_root))
        urdf_browse = QPushButton("Browse...")
        urdf_browse.clicked.connect(self.browse_urdf_path)
        urdf_layout.addWidget(self.urdf_path)
        urdf_layout.addWidget(urdf_browse)
        viz_layout.addRow("URDF Base Path:", urdf_layout)

        # Geometry JSON path
        geom_layout = QHBoxLayout()
        self.geometry_json = QLineEdit()
        self.geometry_json.setText(self.settings.value("geometry_json", "config/geometry.json"))
        geom_browse = QPushButton("Browse...")
        geom_browse.clicked.connect(self.browse_geometry_json)
        geom_layout.addWidget(self.geometry_json)
        geom_layout.addWidget(geom_browse)
        viz_layout.addRow("Geometry Config:", geom_layout)

        viz_group.setLayout(viz_layout)
        layout.addWidget(viz_group)

        # Add buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def browse_urdf_path(self):
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select URDF Base Directory",
            self.urdf_path.text()
        )
        if dir_path:
            self.urdf_path.setText(dir_path)

    def browse_geometry_json(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Geometry Configuration File",
            self.geometry_json.text(),
            "JSON files (*.json)"
        )
        if file_path:
            self.geometry_json.setText(file_path)

    def saveSettings(self):
        """Save the current settings to QSettings"""
        self.settings.setValue("urdf_path", self.urdf_path.text())
        self.settings.setValue("geometry_json", self.geometry_json.text())
        self.settings.sync()