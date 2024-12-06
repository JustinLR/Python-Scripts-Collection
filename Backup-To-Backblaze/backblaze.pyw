import os
import subprocess
import logging
from pathlib import Path
import requests
from cryptography.fernet import Fernet, InvalidToken
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QMenuBar, QDialogButtonBox,
    QPushButton, QProgressBar, QLabel, QTextEdit, QLineEdit, QFormLayout, QMessageBox, QDialog, QRadioButton, QButtonGroup, QHBoxLayout
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QThread, Signal

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Backblaze B2 directories
B2_BUCKET_NAME = "Scrivener-Backup"
SOURCE_DIR = Path.home() / "Dropbox" / "Scrivener"
DEST_DIR = f"b2://{B2_BUCKET_NAME}"

# Path to store encrypted credentials
CREDENTIALS_FILE = Path.home() / ".b2_credentials"
KEY_FILE = Path.home() / ".b2_key"


def generate_key():
    """
    Generate a new encryption key and save it to a file.
    """
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as key_file:
        key_file.write(key)


def load_key():
    """
    Load the encryption key from the key file. Generate one if it doesn't exist.
    """
    if not KEY_FILE.exists():
        generate_key()
    with open(KEY_FILE, "rb") as key_file:
        return key_file.read()


def save_credentials(account_id, account_key):
    """
    Save encrypted credentials to a file.
    """
    fernet = Fernet(load_key())
    credentials = f"{account_id}:{account_key}".encode()
    encrypted = fernet.encrypt(credentials)
    with open(CREDENTIALS_FILE, "wb") as cred_file:
        cred_file.write(encrypted)


def load_credentials():
    """
    Load and decrypt credentials from the file.
    """
    if not CREDENTIALS_FILE.exists():
        return None, None
    fernet = Fernet(load_key())
    try:
        with open(CREDENTIALS_FILE, "rb") as cred_file:
            encrypted = cred_file.read()
        decrypted = fernet.decrypt(encrypted).decode()
        return decrypted.split(":")
    except (InvalidToken, ValueError):
        logging.error("Failed to decrypt credentials.")
        return None, None


def validate_backblaze_credentials(account_id, account_key):
    """
    Validate Backblaze B2 credentials by sending a test request.
    """
    try:
        auth_url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
        response = requests.get(auth_url, auth=(account_id, account_key))
        if response.status_code == 200:
            logging.info("Backblaze B2 credentials validated successfully.")
            return True
        else:
            logging.error(f"Credential validation failed: {response.json().get('message', 'Unknown error')}")
            return False
    except Exception as e:
        logging.error(f"Error validating Backblaze credentials: {str(e)}")
        return False


class SyncWorker(QThread):
    progress = Signal(int, str)  # Progress updates
    finished = Signal(str)  # When sync completes
    error = Signal(str)  # On errors
    log_update = Signal(str)  # For log messages

    def __init__(self):
        super().__init__()
        self._is_stopped = False  # Flag to stop the thread
        self.files_updated = False  # Flag to track if files were updated

    def run(self):
        account_id, account_key = load_credentials()
        if not account_id or not account_key:
            self.error.emit("B2 credentials are not set.")
            logging.error("B2 credentials are not set.")
            return

        self.log_update.emit("Calculating total size...")
        logging.info("Calculating total size...")

        total_size = self.calculate_total_size(SOURCE_DIR)
        uploaded_size = 0

        self.progress.emit(0, f"0 MB / {total_size / (1024 ** 2):.2f} MB")

        if total_size == 0:
            self.finished.emit("No files to upload.")
            logging.info("No files to upload.")
            return

        self.log_update.emit("Total size calculated, starting upload...")
        logging.info(f"Total size: {total_size / (1024 ** 2):.2f} MB")

        try:
            b2_command = [
                "b2", "sync", "--debug", "--compare-versions", "modTime", "--threads", "10",
                str(SOURCE_DIR), DEST_DIR
            ]
            logging.info(f"Running command: {' '.join(b2_command)}")

            self.sync_process = subprocess.Popen(
                b2_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            while not self._is_stopped:
                output = self.sync_process.stdout.readline()
                error = self.sync_process.stderr.readline()

                if output == "" and self.sync_process.poll() is not None:
                    break

                if output:
                    logging.debug(f"Output: {output.strip()}")
                    self.log_update.emit(output.strip())

                if error:
                    logging.error(f"Error: {error.strip()}")
                    self.error.emit(f"Error: {error.strip()}")

            self.sync_process.wait()

            if self.sync_process.returncode == 0:
                self.finished.emit("Sync completed successfully!")
                logging.info("Sync completed successfully!")
            else:
                error_message = self.sync_process.stderr.read().strip()
                self.error.emit(f"Error during sync: {error_message}")
                logging.error(f"Error during sync: {error_message}")

        except Exception as e:
            self.error.emit(f"An error occurred: {str(e)}")
            logging.error(f"An error occurred: {str(e)}")

    def calculate_total_size(self, directory):
        total_size = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
        return total_size

    def stop_sync(self):
        self._is_stopped = True
        if self.sync_process:
            self.sync_process.terminate()
            self.sync_process.wait()
            logging.info("Sync process terminated by user.")
            self.log_update.emit("Sync process terminated by user.")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Cloud Credentials")
        self.setGeometry(300, 300, 400, 200)

        # Layouts
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        radio_layout = QHBoxLayout()

        # Account ID field
        self.account_id_field = QLineEdit(self)
        account_id, _ = load_credentials()
        self.account_id_field.setText(account_id or "")
        form_layout.addRow("Account ID:", self.account_id_field)

        # Account Key field
        self.account_key_field = QLineEdit(self)
        _, account_key = load_credentials()
        self.account_key_field.setText(account_key or "")
        self.account_key_field.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Account Key:", self.account_key_field)

        # Add the form layout
        main_layout.addLayout(form_layout)

        # Buttons (OK and Cancel)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.validate_and_save)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def validate_and_save(self):
        account_id = self.account_id_field.text().strip()
        account_key = self.account_key_field.text().strip()

        if not account_id or not account_key:
            QMessageBox.warning(self, "Invalid Input", "Both Account ID and Key are required.")
            return

        if validate_backblaze_credentials(account_id, account_key):
            save_credentials(account_id, account_key)
            QMessageBox.information(self, "Credentials Set", "Backblaze B2 credentials validated and saved successfully.")
            self.accept()
        else:
            QMessageBox.critical(self, "Validation Failed", "Invalid Backblaze B2 Account ID or Key. Please try again.")


class SyncApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.sync_worker = None

    def initUI(self):
        self.setWindowTitle("Cloud Sync Application")
        self.setGeometry(100, 100, 600, 400)

        # Central widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Menu bar
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        # Settings menu
        settings_menu = menu_bar.addMenu("Settings")
        credentials_action = QAction("Set Credentials", self)
        credentials_action.triggered.connect(self.open_settings_dialog)
        settings_menu.addAction(credentials_action)

        # Sync button
        self.sync_button = QPushButton("Start Sync")
        self.sync_button.clicked.connect(self.toggle_sync)
        layout.addWidget(self.sync_button)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        # Uploaded size label
        self.uploaded_label = QLabel("0 MB / 0 MB")
        layout.addWidget(self.uploaded_label)

        # Status label
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

    def toggle_sync(self):
        if self.sync_button.text() == "Start Sync":
            self.sync_button.setText("Stop Sync")
            self.status_label.setText("Initializing...")
            self.start_sync()
        else:
            if self.sync_worker:
                self.sync_worker.stop_sync()
                self.status_label.setText("Stopping sync...")
                self.sync_button.setText("Start Sync")

    def start_sync(self):
        self.sync_worker = SyncWorker()
        self.sync_worker.progress.connect(self.update_progress)
        self.sync_worker.finished.connect(self.on_finished)
        self.sync_worker.error.connect(self.on_error)
        self.sync_worker.log_update.connect(self.update_log)
        self.sync_worker.start()

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

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
    app = QApplication([])
    sync_app = SyncApp()
    sync_app.show()
    app.exec()


if __name__ == '__main__':
    main()
