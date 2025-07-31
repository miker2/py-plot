from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                            QLabel, QPushButton, QGroupBox, QFormLayout,
                            QLineEdit, QFileDialog, QComboBox, QSpinBox,
                            QColorDialog) # Added QColorDialog
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

        # Create Phase Plot Settings group
        phase_plot_group = QGroupBox("Phase Plot Settings")
        phase_plot_layout = QFormLayout()

        # Default Marker Type
        self.default_marker_type_combo = QComboBox()
        self.default_marker_type_combo.addItems(["Circle", "Square", "Crosshairs"]) # pyqtgraph symbols: 'o', 's', '+'
        current_marker_type = self.settings.value("phase_plot/default_marker_type", "Circle")
        self.default_marker_type_combo.setCurrentText(current_marker_type)
        phase_plot_layout.addRow("Default Marker Type:", self.default_marker_type_combo)

        # Default Marker Size
        self.default_marker_size_spinbox = QSpinBox()
        self.default_marker_size_spinbox.setMinimum(1)
        self.default_marker_size_spinbox.setMaximum(50)
        current_marker_size = int(self.settings.value("phase_plot/default_marker_size", 10))
        self.default_marker_size_spinbox.setValue(current_marker_size)
        phase_plot_layout.addRow("Default Marker Size:", self.default_marker_size_spinbox)

        # Marker Color
        marker_color_layout = QHBoxLayout()
        self.marker_color_button = QPushButton()
        current_marker_color = self.settings.value("phase_plot/marker_color", "0,0,0,200")
        color_parts = [int(x) for x in current_marker_color.split(',')]
        rgb_color = f"rgb({color_parts[0]},{color_parts[1]},{color_parts[2]})"
        self.marker_color_button.setText(f"RGBA({current_marker_color})")
        self.marker_color_button.setStyleSheet(f"background-color: {rgb_color};")
        self.marker_color_button.clicked.connect(self.choose_marker_color)
        marker_color_layout.addWidget(self.marker_color_button)
        phase_plot_layout.addRow("Marker Color:", marker_color_layout)

        phase_plot_group.setLayout(phase_plot_layout)
        layout.addWidget(phase_plot_group)

        # Create Cursor Settings group
        cursor_group = QGroupBox("Cursor Settings")
        cursor_layout = QFormLayout()

        # Cursor Color
        cursor_color_layout = QHBoxLayout()
        self.cursor_color_button = QPushButton()
        current_cursor_color = self.settings.value("cursor/color", "black")
        self.cursor_color_button.setText(current_cursor_color)
        self.cursor_color_button.setStyleSheet(f"background-color: {current_cursor_color}; color: white;")
        self.cursor_color_button.clicked.connect(self.choose_cursor_color)
        cursor_color_layout.addWidget(self.cursor_color_button)
        cursor_layout.addRow("Cursor Color:", cursor_color_layout)

        # Cursor Width
        self.cursor_width_spinbox = QSpinBox()
        self.cursor_width_spinbox.setMinimum(1)
        self.cursor_width_spinbox.setMaximum(10)
        current_cursor_width = int(self.settings.value("cursor/width", 2))
        self.cursor_width_spinbox.setValue(current_cursor_width)
        cursor_layout.addRow("Cursor Width:", self.cursor_width_spinbox)

        cursor_group.setLayout(cursor_layout)
        layout.addWidget(cursor_group)

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

    def choose_cursor_color(self):
        current_color = self.cursor_color_button.text()
        color = QColorDialog.getColor(title="Choose Cursor Color")
        if color.isValid():
            color_name = color.name()  # Returns hex format like #000000
            self.cursor_color_button.setText(color_name)
            self.cursor_color_button.setStyleSheet(f"background-color: {color_name}; color: white;")

    def choose_marker_color(self):
        from PyQt5.QtGui import QColor
        # Parse current RGBA values
        current_rgba = self.marker_color_button.text().replace("RGBA(", "").replace(")", "")
        color_parts = [int(x) for x in current_rgba.split(',')]
        current_color = QColor(color_parts[0], color_parts[1], color_parts[2], color_parts[3])

        color = QColorDialog.getColor(current_color, title="Choose Phase Plot Marker Color",
                                      options=QColorDialog.ShowAlphaChannel)
        if color.isValid():
            # Include alpha channel
            rgba_str = f"{color.red()},{color.green()},{color.blue()},{color.alpha()}"
            rgb_color = f"rgb({color.red()},{color.green()},{color.blue()})"
            self.marker_color_button.setText(f"RGBA({rgba_str})")
            self.marker_color_button.setStyleSheet(f"background-color: {rgb_color};")

    def saveSettings(self):
        """Save the current settings to QSettings"""
        self.settings.setValue("urdf_path", self.urdf_path.text())
        self.settings.setValue("geometry_json", self.geometry_json.text())

        # Save Phase Plot settings
        self.settings.setValue("phase_plot/default_marker_type", self.default_marker_type_combo.currentText())
        self.settings.setValue("phase_plot/default_marker_size", self.default_marker_size_spinbox.value())
        # Save marker color (extract RGBA values from button text)
        marker_rgba = self.marker_color_button.text().replace("RGBA(", "").replace(")", "")
        self.settings.setValue("phase_plot/marker_color", marker_rgba)

        # Save Cursor settings
        self.settings.setValue("cursor/color", self.cursor_color_button.text())
        self.settings.setValue("cursor/width", self.cursor_width_spinbox.value())

        self.settings.sync()