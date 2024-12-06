import sys
import os
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
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
)
from PySide6.QtCore import Qt, Signal, QObject

# Set up logging
logging.basicConfig(
    filename=os.path.join(os.getcwd(), 'file_sorter.log'),
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s',
)

DELETE_EXTENSIONS = {'.rdp', '.msi', '.ica', '.exe'}
MOVE_TO_ARCHIVE_EXTENSIONS = {'.zip'}

class WorkerSignals(QObject):
    update_progress = Signal(int, int)
    finished = Signal()
    error = Signal(str)


class FileSorterWorker:
    def __init__(self, signals, directory, folder_mapping, archive_folder):
        self.signals = signals
        self.directory = directory
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
            total_files = sum(len(files) for _, _, files in os.walk(self.directory))
            processed_files = 0

            for root, _, files in os.walk(self.directory):
                if not self.is_running:
                    break

                for file in files:
                    if not self.is_running:
                        break

                    file_path = os.path.join(root, file)
                    _, extension = os.path.splitext(file)

                    # Delete unwanted files
                    if extension.lower() in DELETE_EXTENSIONS:
                        self.delete_file(file_path)

                    # Move .zip files to Archive
                    elif extension.lower() in MOVE_TO_ARCHIVE_EXTENSIONS:
                        self.move_to_archive(file_path)

                    # Move other files to designated folders
                    elif extension.lower() in self.folder_mapping:
                        destination = self.folder_mapping[extension.lower()]
                        if not os.path.exists(destination):
                            os.makedirs(destination)
                        shutil.move(file_path, os.path.join(destination, file))
                        logging.info(f"Moved: {file_path} -> {destination}")

                    processed_files += 1
                    self.signals.update_progress.emit(processed_files, total_files)

            # Process zipped folders
            self.move_zipped_folders(self.directory)
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


class FileSorterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Sorter")
        self.resize(400, 300)

        # Main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Title label
        self.title_label = QLabel("File Sorting and Cleaning Tool", self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.layout.addWidget(self.title_label)

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

    def toggle_processing(self):
        if self.worker:
            self.stop_processing()
        else:
            self.start_processing()

    def start_processing(self):
        downloads_path = Path.home() / "Downloads"
        archive_path = downloads_path / "Archive"
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
        self.worker = FileSorterWorker(signals, downloads_path, folder_mapping, archive_path)
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
    app = QApplication(sys.argv)
    window = FileSorterApp()
    window.show()
    sys.exit(app.exec())
