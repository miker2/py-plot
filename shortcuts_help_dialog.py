from PyQt5.QtWidgets import (QDialog, QLabel, QVBoxLayout, QGridLayout,
                             QSizePolicy, QFrame) # Added QFrame
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class ShortcutsHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Keyboard Shortcuts")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10) # Overall spacing for the main layout

        # Main Title
        title_label = QLabel("Keyboard Shortcuts")
        title_font = QFont()
        title_font.setPointSize(18) # Slightly larger main title
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        main_layout.addSpacing(10) # Space after main title

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

        for section_index, section in enumerate(shortcut_sections):
            section_title_label = QLabel(section["title"])
            section_font = QFont()
            section_font.setPointSize(14) # Increased section header font size
            section_font.setBold(True)
            section_title_label.setFont(section_font)
            main_layout.addWidget(section_title_label)
            # main_layout.addSpacing(5) # Space after section title

            grid_layout = QGridLayout()
            grid_layout.setColumnStretch(1, 1)  # Description column takes available space
            grid_layout.setVerticalSpacing(5) # Spacing between rows in grid
            grid_layout.setHorizontalSpacing(10) # Spacing between key and description

            for i, (key, description) in enumerate(section["shortcuts"]):
                key_label = QLabel(key)
                description_label = QLabel(description)
                
                key_font = QFont()
                # key_font.setBold(True) # Optionally make keys bold
                key_label.setFont(key_font)

                # Align both key and description to the top of their cell
                grid_layout.addWidget(key_label, i, 0, Qt.AlignTop)
                grid_layout.addWidget(description_label, i, 1, Qt.AlignTop)
            
            main_layout.addLayout(grid_layout)
            
            # Add horizontal line separator, except after the last section
            if section_index < len(shortcut_sections) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setFrameShadow(QFrame.Sunken)
                main_layout.addWidget(line)
                # main_layout.addSpacing(10) # Space after line, handled by main_layout.setSpacing
            else:
                main_layout.addSpacing(5) # Add a little space at the very end if no line

        self.setLayout(main_layout)
        self.resize(650, 500) # Adjusted size for better content visibility
        # Apply a stylesheet for better visual appeal
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
            }
            QLabel {
                color: #333;
            }
            QLabel[isTitle="true"] { /* Dark blue for titles */
                color: #0050a0; /* Dark blue for titles */
            }
        """)
