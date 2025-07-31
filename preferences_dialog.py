from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel, \
    QLineEdit, QPushButton, QFileDialog, QComboBox, QSpinBox, QColorDialog
from PyQt5.QtCore import QSettings

import os

class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Preferences")

        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        # This variable is to be used by each preference function to store a cache of
        # the result. The settings will only be written if the user "accepts" the dialog
        self._setting_cache = {}

        # Things we could set in here:
        #  1. Path to the base URDF file directory
        #  2. The thickness of the lines
        #  3. The background of the 3D visualizer window
        #  4. The default directory of "extra data"
        #  5. The default search & filter mode (for the var-list widget)

        pref_layout = QVBoxLayout()

        self._settings = QSettings()
        self._settings.beginGroup(self.windowTitle())
        # Register all settings here!
        # Note, for each setting, create a function that will read the setting, create a
        # layout for modifying the setting and register the output so the setting can be
        # stored on exit
        settings_functions = [
            self.urdf_settings,
            self.geometry_path_settings,
            self.phase_plot_settings,
            self.cursor_settings
        ]
        
        from PyQt5.QtWidgets import QFrame
        for i, settings_func in enumerate(settings_functions):
            # Add separator line before each section (except the first one)
            if i > 0:
                separator = QFrame()
                separator.setFrameShape(QFrame.HLine)
                separator.setFrameShadow(QFrame.Sunken)
                pref_layout.addWidget(separator)
            
            # Add the settings layout
            pref_layout.addLayout(settings_func())
        # End settings registration
        self._settings.endGroup()

        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(pref_layout)
        layout.addWidget(buttonBox)
        self.setLayout(layout)


    def saveSettings(self):
        # This should be called when "accept" has been called
        settings = QSettings()

        settings.beginGroup(self.windowTitle())
        for k, v in self._setting_cache.items():
            settings.setValue(k, v)
        settings.endGroup()

    def urdf_settings(self):
        setting_name = "urdf_path"
        urdf_path = self._settings.value(setting_name, os.path.expanduser("~"))

        hbox = QHBoxLayout()

        hbox.addWidget(QLabel("urdf base path"))
        urdf_path_line_edit = QLineEdit(urdf_path)
        hbox.addWidget(urdf_path_line_edit)
        f_dialog_btn = QPushButton("...")

        def on_file_dialog_button_pressed():
            f_dialog = QFileDialog(parent=self, caption='Set URDF base path', 
                                   directory=urdf_path)
            f_dialog.setFileMode(QFileDialog.FileMode.Directory)
            f_dialog.setOptions(QFileDialog.Option.ShowDirsOnly)
            if f_dialog.exec():
                filenames = f_dialog.selectedFiles()
                
                if len(filenames) == 1:
                    urdf_path_line_edit.setText(filenames[0])

        f_dialog_btn.clicked.connect(on_file_dialog_button_pressed)
        hbox.addWidget(f_dialog_btn)

        # Register the updated path with the cache so it will be written on 'accept'
        def update_setting(path_str):
            self._setting_cache[setting_name] = path_str
        urdf_path_line_edit.textChanged.connect(update_setting)

        return hbox

    def geometry_path_settings(self):
        setting_name = "geometry_json"
        default_path = os.path.join(os.path.dirname(__file__), "config/geometry.json")
        geometry_path = self._settings.value(setting_name, default_path)

        hbox = QHBoxLayout()

        hbox.addWidget(QLabel("geometry config path"))
        geometry_path_line_edit = QLineEdit(geometry_path)
        hbox.addWidget(geometry_path_line_edit)
        f_dialog_btn = QPushButton("...")

        def on_file_dialog_button_pressed():
            f_dialog = QFileDialog(parent=self, caption='Set 3D vis Geometry config path',
                                   directory=geometry_path)
            f_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            #f_dialog.setOptions(QFileDialog.Option.ShowDirsOnly)
            f_dialog.setNameFilter("JSON (*.json);;All Files (*)")
            if f_dialog.exec():
                filenames = f_dialog.selectedFiles()

                if len(filenames) == 1:
                    geometry_path_line_edit.setText(filenames[0])

        f_dialog_btn.clicked.connect(on_file_dialog_button_pressed)
        hbox.addWidget(f_dialog_btn)

        # Register the updated path with the cache so it will be written on 'accept'
        def update_setting(path_str):
            self._setting_cache[setting_name] = path_str
        geometry_path_line_edit.textChanged.connect(update_setting)

        return hbox

    def phase_plot_settings(self):
        # Create Phase Plot Settings group
        vbox = QVBoxLayout()
        vbox.addWidget(QLabel("Phase Plot Settings"))
        
        # Marker Type
        marker_type_hbox = QHBoxLayout()
        marker_type_hbox.addWidget(QLabel("Default Marker Type:"))
        self.marker_type_combo = QComboBox()
        self.marker_type_combo.addItems(["Circle", "Square", "Crosshairs"])
        current_marker_type = self._settings.value("phase_plot/default_marker_type", "Circle")
        self.marker_type_combo.setCurrentText(current_marker_type)
        marker_type_hbox.addWidget(self.marker_type_combo)
        vbox.addLayout(marker_type_hbox)
        
        # Marker Size
        marker_size_hbox = QHBoxLayout()
        marker_size_hbox.addWidget(QLabel("Default Marker Size:"))
        self.marker_size_spinbox = QSpinBox()
        self.marker_size_spinbox.setMinimum(1)
        self.marker_size_spinbox.setMaximum(50)
        current_marker_size = int(self._settings.value("phase_plot/default_marker_size", 10))
        self.marker_size_spinbox.setValue(current_marker_size)
        marker_size_hbox.addWidget(self.marker_size_spinbox)
        vbox.addLayout(marker_size_hbox)
        
        # Marker Color
        marker_color_hbox = QHBoxLayout()
        marker_color_hbox.addWidget(QLabel("Marker Color:"))
        self.marker_color_button = QPushButton()
        current_marker_color = self._settings.value("phase_plot/marker_color", "0,0,0,200")
        color_parts = [int(x) for x in current_marker_color.split(',')]
        rgb_color = f"rgb({color_parts[0]},{color_parts[1]},{color_parts[2]})"
        self.marker_color_button.setText(f"RGBA({current_marker_color})")
        self.marker_color_button.setStyleSheet(f"background-color: {rgb_color};")
        self.marker_color_button.clicked.connect(self.choose_marker_color)
        marker_color_hbox.addWidget(self.marker_color_button)
        vbox.addLayout(marker_color_hbox)
        
        # Register settings with cache
        def update_marker_type(text):
            self._setting_cache["phase_plot/default_marker_type"] = text
        def update_marker_size(value):
            self._setting_cache["phase_plot/default_marker_size"] = value
        def update_marker_color():
            marker_rgba = self.marker_color_button.text().replace("RGBA(", "").replace(")", "")
            self._setting_cache["phase_plot/marker_color"] = marker_rgba
            
        self.marker_type_combo.currentTextChanged.connect(update_marker_type)
        self.marker_size_spinbox.valueChanged.connect(update_marker_size)
        # marker color is updated in choose_marker_color method
        
        return vbox

    def cursor_settings(self):
        vbox = QVBoxLayout()
        vbox.addWidget(QLabel("Cursor Settings"))
        
        # Cursor Color
        cursor_color_hbox = QHBoxLayout()
        cursor_color_hbox.addWidget(QLabel("Cursor Color:"))
        self.cursor_color_button = QPushButton()
        current_cursor_color = self._settings.value("cursor/color", "#000000")
        self.cursor_color_button.setText(current_cursor_color)
        self.cursor_color_button.setStyleSheet(f"background-color: {current_cursor_color};")
        self.cursor_color_button.clicked.connect(self.choose_cursor_color)
        cursor_color_hbox.addWidget(self.cursor_color_button)
        vbox.addLayout(cursor_color_hbox)
        
        # Cursor Width
        cursor_width_hbox = QHBoxLayout()
        cursor_width_hbox.addWidget(QLabel("Cursor Width:"))
        self.cursor_width_spinbox = QSpinBox()
        self.cursor_width_spinbox.setMinimum(1)
        self.cursor_width_spinbox.setMaximum(10)
        current_cursor_width = int(self._settings.value("cursor/width", 2))
        self.cursor_width_spinbox.setValue(current_cursor_width)
        cursor_width_hbox.addWidget(self.cursor_width_spinbox)
        vbox.addLayout(cursor_width_hbox)
        
        # Register settings with cache
        def update_cursor_color():
            self._setting_cache["cursor/color"] = self.cursor_color_button.text()
        def update_cursor_width(value):
            self._setting_cache["cursor/width"] = value
            
        self.cursor_width_spinbox.valueChanged.connect(update_cursor_width)
        # cursor color is updated in choose_cursor_color method
        
        return vbox

    def choose_cursor_color(self):
        from PyQt5.QtGui import QColor
        current_color_text = self.cursor_color_button.text()
        current_color = QColor(current_color_text)
        color = QColorDialog.getColor(current_color, title="Choose Cursor Color")
        if color.isValid():
            color_name = color.name()  # Returns hex format like #000000
            self.cursor_color_button.setText(color_name)
            self.cursor_color_button.setStyleSheet(f"background-color: {color_name};")
            # Update cache
            self._setting_cache["cursor/color"] = color_name

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
            # Update cache
            self._setting_cache["phase_plot/marker_color"] = rgba_str