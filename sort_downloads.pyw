import sys
import os
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from tqdm import tqdm
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import threading

# Set up logging to save the log file in the same directory as the script
logging.basicConfig(filename=os.path.join(os.getcwd(), 'file_sorter.log'),
                    level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

# Set of photo extensions that should never be deleted
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.jfif', '.psd'}

# Flag to indicate if the process is running
is_running = False

# Function to delete a file if it's older than a certain threshold
def delete_old_file(file_path, days_old=60, skip_photos=False):
    try:
        file_name, file_extension = os.path.splitext(file_path)
        if skip_photos and file_extension.lower() in PHOTO_EXTENSIONS:
            return
        file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        if datetime.now() - file_mod_time > timedelta(days=days_old):
            os.remove(file_path)
            logging.info(f"Successfully deleted {file_path} (older than {days_old} days)")
        else:
            logging.info(f"{file_path} is not older than {days_old} days, skipping deletion.")
    except PermissionError:
        logging.error(f"Permission denied to delete {file_path}.")
    except Exception as e:
        logging.error(f"Failed to delete {file_path}. Error: {str(e)}")

# Function to recursively clear out files older than 60 days in a given directory
def clear_old_files_in_directory(directory, days_old=60, skip_photos=False, progress_callback=None):
    try:
        total_items = sum([len(files) + len(dirs) for _, dirs, files in os.walk(directory)])
        with tqdm(total=total_items, desc=f"Clearing old files in {directory}", unit="file") as pbar:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if not is_running:  # Check if the process should stop
                        return
                    file_path = os.path.join(root, file)
                    delete_old_file(file_path, days_old, skip_photos)
                    pbar.update(1)
                    if progress_callback:
                        progress_callback(pbar.n, total_items)
                for dir in dirs:
                    if not is_running:  # Check if the process should stop
                        return
                    dir_path = os.path.join(root, dir)
                    delete_old_file(dir_path, days_old, skip_photos)
                    pbar.update(1)
                    if progress_callback:
                        progress_callback(pbar.n, total_items)
    except Exception as e:
        logging.error(f"Error clearing old files in {directory}. Error: {str(e)}")

# Function to move a folder and its contents to a destination folder
def move_folder(folder_path, destination_folder, progress_callback=None):
    try:
        date_folder = datetime.now().strftime('%Y-%m-%d')
        destination_folder = os.path.join(destination_folder, date_folder)
        
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)
        
        shutil.move(folder_path, os.path.join(destination_folder, os.path.basename(folder_path)))
        logging.info(f"Successfully moved folder {folder_path} to {destination_folder}")
    except PermissionError:
        logging.error(f"Permission denied to move folder {folder_path}. Skipping.")
    except Exception as e:
        logging.error(f"Failed to move folder {folder_path} to {destination_folder}. Error: {str(e)}")

# Function to process items in a folder, evaluating files and moving folders
def process_existing_items(path, archive_folder, folder_mapping, progress_callback=None):
    try:
        items_processed = 0
        total_items = sum([len(files) + len(dirs) for _, dirs, files in os.walk(path)])

        with tqdm(total=total_items, desc="Processing items", unit="file") as pbar:
            for entry in os.scandir(path):
                if not is_running:  # Check if the process should stop
                    return
                if entry.is_file():
                    file_name, file_extension = os.path.splitext(entry.name)
                    if file_extension.lower() in folder_mapping:
                        destination_folder = folder_mapping[file_extension.lower()]
                        move_folder(entry.path, destination_folder, progress_callback)
                    pbar.update(1)
                elif entry.is_dir():
                    move_folder(entry.path, archive_folder, progress_callback)
                    pbar.update(1)
                if progress_callback:
                    progress_callback(pbar.n, total_items)

    except Exception as e:
        logging.error(f"Error processing items in {path}. Error: {str(e)}")

# Function to start the file processing and update the GUI progress
def start_processing():
    global is_running

    if is_running:
        stop_processing()
        return

    is_running = True
    start_button.config(text="Stop Processing")
    threading.Thread(target=process_files, daemon=True).start()

# Function to stop the processing
def stop_processing():
    global is_running
    is_running = False
    start_button.config(text="Start Processing")
    messagebox.showinfo("Process Stopped", "The file processing was stopped.")

# Function that wraps the entire file processing logic
def process_files():
    try:
        downloads_path = str(Path.home() / 'Downloads')
        archive_path = os.path.join(downloads_path, 'Archive')

        if not os.path.exists(archive_path):
            os.mkdir(archive_path)

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

        process_existing_items(downloads_path, archive_path, folder_mapping, progress_callback=update_progress)

        user_home = Path.home()
        clear_old_files_in_directory(user_home / 'Pictures', skip_photos=True, progress_callback=update_progress)
        clear_old_files_in_directory(user_home / 'Documents', skip_photos=True, progress_callback=update_progress)
        clear_old_files_in_directory(archive_path, skip_photos=True, progress_callback=update_progress)

        messagebox.showinfo("Process Complete", "File processing and cleanup completed successfully!")
    except Exception as e:
        logging.error(f"Error during processing: {str(e)}")
        messagebox.showerror("Error", f"An error occurred: {str(e)}")
    finally:
        is_running = False
        start_button.config(text="Start Processing")

# Function to update the progress bar and status label in the GUI
def update_progress(current, total):
    progress_bar["value"] = (current / total) * 100
    status_label.config(text=f"Processing: {current} of {total} files")
    window.update_idletasks()

# Set up the GUI
window = tk.Tk()
window.title("File Sorter")

# Create a label for the title
label = tk.Label(window, text="File Sorting and Cleaning Tool", font=("Helvetica", 16))
label.pack(pady=10)

# Create the start button
start_button = tk.Button(window, text="Start Processing", font=("Helvetica", 12), command=start_processing)
start_button.pack(pady=20)

# Create a label for the status (below the start button, above the progress bar)
status_label = tk.Label(window, text="Processing: 0 of 0 files", font=("Helvetica", 12))
status_label.pack(pady=10)

# Create a progress bar
progress_bar = ttk.Progressbar(window, length=300, mode='determinate')
progress_bar.pack(pady=10)

# Start the GUI loop
window.mainloop()
