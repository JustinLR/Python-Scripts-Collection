
# Python Scripts Collection

A collection of Python scripts to automate common tasks. These scripts are designed to make your life easier by automating tedious processes like backing up important data and organizing files.

## Scripts Included:

### 1. **Backup to Backblaze**
A Python script that automates backing up important files to **Backblaze B2 Cloud Storage**. It securely uploads files from your local machine to the cloud, providing off-site storage and disaster recovery options for your important files.

#### Features:
- Automates file uploads to Backblaze B2 Cloud Storage
- Supports multiple file types and directories
- Provides logging for successful and failed uploads
- Easy-to-use, with minimal configuration required

#### Requirements:
- Python 3.x
- `boto3` (Backblaze B2 SDK) library
- A Backblaze B2 account and API credentials

#### How to Use:
1. Install the required dependencies:
   ```bash
   pip install boto3
   ```
2. Set up your Backblaze B2 account and obtain your **Application Key** and **Bucket Name**.
3. Configure the script with your Backblaze credentials.
4. Run the script to start uploading files:
   ```bash
   python backup_to_backblaze.py
   ```

---

### 2. **File Sorter**
A Python script designed to organize and clean up files in a directory by moving them into categorized folders based on their file extensions. It also features a **Tkinter-based GUI** to make sorting files more user-friendly.

#### Features:
- Organizes files in a directory based on file types (e.g., `.jpg`, `.pdf`, `.txt`)
- Automatically moves files into predefined folders based on extensions
- GUI built with Tkinter for easy interaction
- Supports various file types and can be easily extended to support more

#### Requirements:
- Python 3.x
- `Tkinter` (for GUI support)

#### How to Use:
1. Install Python and Tkinter (Tkinter comes pre-installed with most Python distributions).
2. Run the script:
   ```bash
   python file_sorter.py
   ```
3. Select the folder you want to organize, and the script will automatically sort the files.

---

## How to Contribute
If you have ideas for new scripts or improvements to the existing ones, feel free to fork the repository and submit a pull request.

---

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
