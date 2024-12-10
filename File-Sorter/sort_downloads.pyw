import sys
import os
import shutil
import logging
from logging.handlers import RotatingFileHandler  # Explicit import
from pathlib import Path
from datetime import datetime
from threading import Thread
from zipfile import is_zipfile
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QPushButton,
    QProgressBar,
    QMessageBox,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QFormLayout,
    QMenuBar,
    QMenu
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, Signal, QObject, QCoreApplication
from PySide6.QtGui import QGuiApplication


# Set up logging with rotation (1MB max size, keeping 5 backup files)
log_file_path = os.path.join(os.getcwd(), 'file_sorter.log')
log_handler = RotatingFileHandler(
    log_file_path, maxBytes=1e6, backupCount=5  # max size of 1MB, keep 5 backup files
)
log_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
logging.getLogger().addHandler(log_handler)
logging.getLogger().setLevel(logging.INFO)

DELETE_EXTENSIONS = {'.rdp', '.msi', '.ica', '.exe'}
MOVE_TO_ARCHIVE_EXTENSIONS = {'.zip'}

class WorkerSignals(QObject):
    update_progress = Signal(int, int)
    finished = Signal()
    error = Signal(str)


class FileSorterWorker:
    def __init__(self, signals, selected_dirs, folder_mapping, archive_folder):
        self.signals = signals
        self.selected_dirs = selected_dirs  # List of directories to process
        self.folder_mapping = folder_mapping
        self.archive_folder = archive_folder
        self.is_running = True

    def stop(self):
        self.is_running = False

    def delete_file(self, file_path):
        try:
            os.remove(file_path)
            logging.info(f"Deleted: {file_path}")
        except Exception as e:
            logging.error(f"Error deleting {file_path}: {str(e)}")

    def move_to_archive(self, file_path):
        try:
            archive_path = os.path.join(self.archive_folder, os.path.basename(file_path))
            shutil.move(file_path, archive_path)
            logging.info(f"Moved to archive: {file_path} -> {archive_path}")
        except Exception as e:
            logging.error(f"Error moving {file_path} to archive: {str(e)}")

    def process_files(self):
        try:
            total_files = 0
            for dir_path in self.selected_dirs:
                total_files += sum(len(files) for _, _, files in os.walk(dir_path))

            processed_files = 0

            for dir_path in self.selected_dirs:
                if not self.is_running:
                    break

                for root, _, files in os.walk(dir_path):
                    if not self.is_running:
                        break

                    for file in files:
                        if not self.is_running:
                            break

                        file_path = os.path.join(root, file)
                        _, extension = os.path.splitext(file)

                        # Log the file being processed
                        logging.info(f"Processing file: {file_path}, Extension: {extension.lower()}")

                        # Delete unwanted files
                        if extension.lower() in DELETE_EXTENSIONS:
                            self.delete_file(file_path)

                        # Move .zip files to Archive
                        elif extension.lower() in MOVE_TO_ARCHIVE_EXTENSIONS:
                            self.move_to_archive(file_path)

                        # Sort other files by date and move to designated folders
                        elif extension.lower() in self.folder_mapping:
                            self.move_by_date(file_path, extension.lower())

                        processed_files += 1
                        self.signals.update_progress.emit(processed_files, total_files)

            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))

    def move_zipped_folders(self, directory):
        """Move folders that are zipped archives to the archive directory."""
        for root, dirs, _ in os.walk(directory):
            for dir_name in dirs:
                folder_path = os.path.join(root, dir_name)
                if is_zipfile(folder_path):
                    self.move_to_archive(folder_path)

    def move_by_date(self, file_path, file_extension):
        """Sort files into folders based on the modification date."""
        try:
            # Get the modification time of the file
            mod_time = os.path.getmtime(file_path)
            mod_date = datetime.fromtimestamp(mod_time)

            # Log modification date for debugging
            logging.info(f"File: {file_path}, Modification Date: {mod_date}")

            # Generate the folder path based on the year, month, and day (in the format: YYYY-MM-DD)
            base_folder = self.folder_mapping[file_extension]
            date_folder = base_folder / f"{mod_date.year}-{mod_date.month:02d}-{mod_date.day:02d}"

            # Log the target folder path for debugging
            logging.info(f"Target folder path: {date_folder}")

            # Create the date-based folder structure if it doesn't exist
            if not date_folder.exists():
                date_folder.mkdir(parents=True)
                logging.info(f"Created folder: {date_folder}")

            # Log the file being moved
            destination_path = date_folder / os.path.basename(file_path)
            logging.info(f"Moving file to: {destination_path}")

            # Move the file to the appropriate folder
            shutil.move(file_path, destination_path)
            logging.info(f"Moved: {file_path} -> {destination_path}")
        except Exception as e:
            logging.error(f"Error sorting file {file_path} by date: {str(e)}")


class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Settings")
        self.resize(300, 200)

        layout = QVBoxLayout(self)

        # Create checkboxes for directories
        self.downloads_checkbox = QCheckBox("Downloads")
        self.downloads_checkbox.setChecked(True)  # Default to checked
        self.pictures_checkbox = QCheckBox("Pictures")
        self.videos_checkbox = QCheckBox("Videos")
        self.documents_checkbox = QCheckBox("Documents")
        self.music_checkbox = QCheckBox("Music")
        self.desktop_checkbox = QCheckBox("Desktop")

        # Add checkboxes to layout
        layout.addWidget(self.downloads_checkbox)
        layout.addWidget(self.pictures_checkbox)
        layout.addWidget(self.videos_checkbox)
        layout.addWidget(self.documents_checkbox)
        layout.addWidget(self.music_checkbox)
        layout.addWidget(self.desktop_checkbox)

        self.setLayout(layout)

    def get_selected_directories(self):
        selected_dirs = []
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
        return selected_dirs


class FileSorterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Sorter")
        self.resize(400, 400)

        # Main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Title label
        self.title_label = QLabel("File Sorting and Cleaning Tool", self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.layout.addWidget(self.title_label)

        # Create a menubar with a Settings option
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")
        settings_action = QAction("Open Settings", self)
        settings_action.triggered.connect(self.open_settings)
        settings_menu.addAction(settings_action)

        # Start button
        self.start_button = QPushButton("Start Processing", self)
        self.start_button.clicked.connect(self.toggle_processing)
        self.layout.addWidget(self.start_button)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready", self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.status_label)

        # Worker attributes
        self.worker = None
        self.worker_thread = None

        # Settings window instance
        self.settings_window = None

    def open_settings(self):
        if not self.settings_window:
            self.settings_window = SettingsWindow()
        self.settings_window.show()

    def toggle_processing(self):
        if self.worker:
            self.stop_processing()
        else:
            self.start_processing()

    def start_processing(self):
        selected_dirs = []

        # Always include the Downloads directory by default
        downloads_dir = Path.home() / "Downloads"
        selected_dirs.append(downloads_dir)

        # Check if settings window exists and retrieve selected directories
        if self.settings_window:
            selected_dirs.extend(
                dir for dir in self.settings_window.get_selected_directories()
                if dir not in selected_dirs  # Avoid duplicates
            )

        if not selected_dirs:
            QMessageBox.warning(self, "Warning", "Please select at least one directory to sort.")
            return

        archive_path = Path.home() / "Downloads" / "Archive"
        folder_mapping = {
            '.jpg': Path.home() / 'Pictures',
            '.jpeg': Path.home() / 'Pictures',
            '.png': Path.home() / 'Pictures',
            '.gif': Path.home() / 'Pictures',
            '.webp': Path.home() / 'Pictures',
            '.jfif': Path.home() / 'Pictures',
            '.psd': Path.home() / 'Pictures',
            '.docx': Path.home() / 'Documents',
            '.txt': Path.home() / 'Documents',
            '.pdf': Path.home() / 'Documents',
        }

        if not archive_path.exists():
            archive_path.mkdir()

        self.start_button.setText("Stop Processing")
        self.status_label.setText("Processing...")

        # Initialize worker
        signals = WorkerSignals()
        self.worker = FileSorterWorker(signals, selected_dirs, folder_mapping, archive_path)
        signals.update_progress.connect(self.update_progress)
        signals.finished.connect(self.processing_finished)
        signals.error.connect(self.processing_error)

        self.worker_thread = Thread(target=self.worker.process_files, daemon=True)
        self.worker_thread.start()

    def stop_processing(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.start_button.setText("Start Processing")
        self.status_label.setText("Stopped")

    def update_progress(self, current, total):
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)
        self.status_label.setText(f"Processing: {current}/{total} files")

    def processing_finished(self):
        self.worker = None
        self.start_button.setText("Start Processing")
        self.status_label.setText("Processing Complete")
        QMessageBox.information(self, "Success", "File processing completed!")

    def processing_error(self, error_message):
        self.worker = None
        self.start_button.setText("Start Processing")
        self.status_label.setText("Error Occurred")
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_message}")


if __name__ == "__main__":
    # Option 1: Try to set High DPI scaling policy before creating QApplication
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception as e:
        print(f"High DPI scaling policy could not be set directly: {e}")

    # Option 2: Use fallback attributes (marked deprecated but functional in many cases)
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Option 3: Enforce DPI scaling via environment variable
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "1.0"

    # Create QApplication instance
    app = QApplication(sys.argv)
    window = FileSorterApp()
    window.show()
    sys.exit(app.exec())