from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel, \
    QLineEdit, QPushButton, QFileDialog
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
        pref_layout.addLayout(self.urdf_settings())
        pref_layout.addLayout(self.geometry_path_settings())
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