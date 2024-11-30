import os
import subprocess
import logging
from pathlib import Path
import re
from PyQt5 import QtWidgets, QtCore

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Backblaze B2 credentials and directories
B2_ACCOUNT_ID = "a38c54d7ab7c"
B2_ACCOUNT_KEY = "002be87dd2082ce8d1a88ebbc618dea1c9766c8e59"
B2_BUCKET_NAME = "Scrivener-Backup"
SOURCE_DIR = Path.home() / "Dropbox" / "Scrivener"
DEST_DIR = f"b2://{B2_BUCKET_NAME}"

class SyncWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int, str)  # Signal for progress updates
    finished = QtCore.pyqtSignal(str)  # Signal when finished
    error = QtCore.pyqtSignal(str)  # Signal for errors
    log_update = QtCore.pyqtSignal(str)  # Signal for logging messages

    def __init__(self):
        super().__init__()
        self._is_stopped = False  # Flag to control thread interruption
        self.files_updated = False  # Flag to check if any files were updated

    def run(self):
        self.log_update.emit("Calculating total size...")
        logging.info("Calculating total size...")

        # Calculate total size of files to be uploaded
        total_size = self.calculate_total_size(SOURCE_DIR)
        uploaded_size = 0

        # Emit initial progress state
        self.progress.emit(0, f"0 MB / {total_size / (1024 ** 2):.2f} MB")

        if total_size == 0:
            self.finished.emit("No files to upload.")
            logging.info("No files to upload.")
            return

        self.log_update.emit("Total size calculated, starting upload...")
        logging.info(f"Total size: {total_size / (1024 ** 2):.2f} MB")

        try:
            # Run the B2 sync process
            b2_command = ["b2", "sync", "--debug", "--compare-versions", "modTime", "--threads", "10", str(SOURCE_DIR), DEST_DIR]
            logging.info(f"Running command: {' '.join(b2_command)}")

            self.sync_process = subprocess.Popen(
                b2_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Capture output and error streams from subprocess
            while not self._is_stopped:
                output = self.sync_process.stdout.readline()
                error = self.sync_process.stderr.readline()

                if output == "" and self.sync_process.poll() is not None:
                    break
                if output:
                    logging.debug(f"Output: {output.strip()}")
                    uploaded_size, progress_percent = self.process_output(output.strip(), uploaded_size, total_size)
                    self.progress.emit(progress_percent, f"{uploaded_size / (1024 ** 2):.2f} MB / {total_size / (1024 ** 2):.2f} MB")

                    # Check for updates in the sync output
                    if "updated: 0 files" in output:
                        self.files_updated = False
                    elif "updated:" in output and int(output.split()[1]) > 0:
                        self.files_updated = True

                if error:
                    logging.error(f"Error: {error.strip()}")
                    self.error.emit(f"Error: {error.strip()}")

            self.sync_process.wait()

            if self.sync_process.returncode == 0:
                if not self.files_updated:
                    self.finished.emit("Files are up to date.")
                    logging.info("Files are up to date.")
                else:
                    self.finished.emit("Sync completed successfully!")
                    logging.info("Sync completed successfully!")
            else:
                error_message = self.sync_process.stderr.read().strip()
                self.error.emit(f"Error during sync: {error_message}")
                logging.error(f"Error during sync: {error_message}")

        except Exception as e:
            self.error.emit(f"An error occurred: {str(e)}")
            logging.error(f"An error occurred: {str(e)}")

    def process_output(self, output_line, uploaded_size, total_size):
        # Check if line contains file upload information
        size_match = re.search(r'uploading.*?(\d+(?:\.\d+)?)\s*MB', output_line)
        if size_match:
            # Add to uploaded size
            size_mb = float(size_match.group(1))
            uploaded_size += size_mb * (1024 ** 2)  # Convert MB to bytes

        # Calculate progress percentage
        progress_percent = int((uploaded_size / total_size) * 100) if total_size > 0 else 0
        return uploaded_size, progress_percent

    def calculate_total_size(self, directory):
        # Calculate the total size of files recursively in the directory
        total_size = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
        return total_size

    def stop_sync(self):
        # Set the flag to stop the sync process gracefully
        self._is_stopped = True
        if self.sync_process:
            self.sync_process.terminate()
            self.sync_process.wait()
            logging.info("Sync process terminated by user.")
            self.log_update.emit("Sync process terminated by user.")

class SyncApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.sync_worker = None

    def initUI(self):
        self.setWindowTitle("Backblaze B2 Sync")
        self.setGeometry(100, 100, 400, 200)

        # Layout
        layout = QtWidgets.QVBoxLayout()

        # Sync button
        self.sync_button = QtWidgets.QPushButton("Start Sync")
        self.sync_button.clicked.connect(self.toggle_sync)
        layout.addWidget(self.sync_button)

        # Progress bar
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        # Uploaded size label
        self.uploaded_label = QtWidgets.QLabel("0 MB / 0 MB")
        layout.addWidget(self.uploaded_label)

        # Status label
        self.status_label = QtWidgets.QLabel("Ready")
        layout.addWidget(self.status_label)

        # Log output
        self.log_output = QtWidgets.QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

    def toggle_sync(self):
        if self.sync_button.text() == "Start Sync":
            self.sync_button.setText("Stop Sync")
            self.status_label.setText("Initializing...")
            self.start_sync()
        else:
            if self.sync_worker:
                self.sync_worker.stop_sync()  # Stop the sync process gracefully
                self.status_label.setText("Sync stopping...")
                self.sync_button.setText("Start Sync")
                logging.info("Syncing stopped by user.")

    def start_sync(self):
        self.sync_worker = SyncWorker()
        self.sync_worker.progress.connect(self.update_progress)
        self.sync_worker.finished.connect(self.on_finished)
        self.sync_worker.error.connect(self.on_error)
        self.sync_worker.log_update.connect(self.update_log)
        self.sync_worker.start()

    def update_progress(self, progress, uploaded_text):
        self.progress_bar.setValue(progress)
        self.uploaded_label.setText(uploaded_text)

    def update_log(self, log_message):
        self.log_output.append(log_message)

    def on_finished(self, message):
        self.status_label.setText(message)
        self.sync_button.setText("Start Sync")

    def on_error(self, error_message):
        self.status_label.setText(error_message)
        self.sync_button.setText("Start Sync")

def main():
    import sys
    app = QtWidgets.QApplication(sys.argv)
    sync_app = SyncApp()
    sync_app.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
