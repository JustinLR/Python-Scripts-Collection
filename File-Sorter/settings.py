# settings.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QPushButton, QFormLayout, QLabel
from PySide6.QtCore import Signal
from pathlib import Path

class SettingsWindow(QWidget):
    settings_saved = Signal(list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Settings")
        self.setGeometry(300, 300, 300, 300)

        self.layout = QVBoxLayout(self)

        # Create the checkboxes for each directory
        self.form_layout = QFormLayout()

        # Directory checkboxes
        self.downloads_checkbox = QCheckBox("Downloads")
        self.pictures_checkbox = QCheckBox("Pictures")
        self.videos_checkbox = QCheckBox("Videos")
        self.documents_checkbox = QCheckBox("Documents")
        self.music_checkbox = QCheckBox("Music")
        self.desktop_checkbox = QCheckBox("Desktop")

        # Add checkboxes to the form layout
        self.form_layout.addRow(self.downloads_checkbox)
        self.form_layout.addRow(self.pictures_checkbox)
        self.form_layout.addRow(self.videos_checkbox)
        self.form_layout.addRow(self.documents_checkbox)
        self.form_layout.addRow(self.music_checkbox)
        self.form_layout.addRow(self.desktop_checkbox)

        # Add the form layout to the main layout
        self.layout.addLayout(self.form_layout)

        # Save button
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)
        self.layout.addWidget(self.save_button)

    def save_settings(self):
        selected_dirs = []

        # Check which directories the user wants to process
        if self.downloads_checkbox.isChecked():
            selected_dirs.append(Path.home() / "Downloads")
        if self.pictures_checkbox.isChecked():
            selected_dirs.append(Path.home() / "Pictures")
        if self.videos_checkbox.isChecked():
            selected_dirs.append(Path.home() / "Videos")
        if self.documents_checkbox.isChecked():
            selected_dirs.append(Path.home() / "Documents")
        if self.music_checkbox.isChecked():
            selected_dirs.append(Path.home() / "Music")
        if self.desktop_checkbox.isChecked():
            selected_dirs.append(Path.home() / "Desktop")

        if not selected_dirs:
            self.settings_saved.emit([])  # If no directories are selected
        else:
            self.settings_saved.emit(selected_dirs)  # Emit selected directories

        self.close()
