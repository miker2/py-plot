from PyQt5.QtWidgets import (QDialog, QLabel, QVBoxLayout, QGridLayout,
                             QSizePolicy)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class ShortcutsHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Keyboard Shortcuts")

        main_layout = QVBoxLayout()

        # Main Title
        title_label = QLabel("Keyboard Shortcuts")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        shortcut_sections = [
            {
                "title": "Plot Navigation",
                "shortcuts": [
                    ("Left Arrow", "Move cursor left (1 tick)"),
                    ("Right Arrow", "Move cursor right (1 tick)"),
                    ("Ctrl + Left Arrow", "Move cursor left (5 ticks)"),
                    ("Ctrl + Right Arrow", "Move cursor right (5 ticks)"),
                    ("Shift + Left Arrow", "Move cursor left (20 ticks)"),
                    ("Shift + Right Arrow", "Move cursor right (20 ticks)"),
                    ("Up Arrow", "Zoom in (time axis)"),
                    ("Down Arrow", "Zoom out (time axis)"),
                    ("Ctrl + Up Arrow", "Zoom in (time axis, larger step)"),
                    ("Ctrl + Down Arrow", "Zoom out (time axis, larger step)"),
                    ("Shift + Up Arrow", "Zoom in (time axis, even larger step)"),
                    ("Shift + Down Arrow", "Zoom out (time axis, even larger step)"),
                ]
            },
            {
                "title": "Plot Manipulation",
                "shortcuts": [
                    ("Ctrl + A", "Autoscale Y-axis of all plots in current tab"),
                ]
            },
            {
                "title": "File Menu",
                "shortcuts": [
                    ("Ctrl + O", "Open data file"),
                    ("Ctrl + Q", "Quit application"),
                ]
            },
            {
                "title": "Plot Menu",
                "shortcuts": [
                    ("Ctrl + N", "Add new subplot"),
                    ("Ctrl + T", "Add new plot tab"),
                    ("Ctrl + S", "Save plotlist for current tab"),
                    ("Ctrl + Shift + O", "Load plotlist for current tab"),
                ]
            }
        ]

        for section in shortcut_sections:
            section_title_label = QLabel(section["title"])
            section_font = QFont()
            section_font.setPointSize(12)
            section_font.setBold(True)
            section_title_label.setFont(section_font)
            main_layout.addWidget(section_title_label)

            grid_layout = QGridLayout()
            grid_layout.setColumnStretch(1, 1)  # Description column takes available space

            for i, (key, description) in enumerate(section["shortcuts"]):
                key_label = QLabel(key)
                description_label = QLabel(description)
                
                # Optional: Make key labels bold for better visual distinction
                # key_font = QFont()
                # key_font.setBold(True)
                # key_label.setFont(key_font)

                grid_layout.addWidget(key_label, i, 0)
                grid_layout.addWidget(description_label, i, 1)
            
            main_layout.addLayout(grid_layout)
            main_layout.addSpacing(10) # Add some space between sections

        self.setLayout(main_layout)
        self.resize(600, 400)
