#!/home/ariel/venvs/pydrive2/bin/python

# backup_to_drive.py
# Purpose: Authenticate with Google Drive and upload all files from a local folder
# Requirements: pip install pydrive2

import os
import argparse
import shutil
import tempfile
from pydrive2.auth import GoogleAuth, RefreshError
from pydrive2.drive import GoogleDrive

# Parse command line arguments
parser = argparse.ArgumentParser(description="Backup a local folder to Google Drive.")
parser.add_argument("-s", "--source", required=True, help="Local source path to back up")
parser.add_argument("-d", "--destination", required=True, help="Target Google Drive folder ID")
parser.add_argument("-z", "--zip", action="store_true", help="Zip files before uploading (to be implemented)")
args = parser.parse_args()

# Step 1: Authenticate
gauth = GoogleAuth()

# Load saved client credentials
gauth.LoadCredentialsFile("credentials.json")

if gauth.credentials is None:
    # Authenticate if they're not there
    gauth.LocalWebserverAuth()
elif gauth.access_token_expired:
    # Refresh them if expired
    try:
        gauth.Refresh()
    except RefreshError as e:
        print(f"Refresh token error: {e}")
        print("Deleting expired credentials and re-authenticating...")
        if os.path.exists("credentials.json"):
            os.remove("credentials.json")
        gauth.credentials = None
        gauth.LocalWebserverAuth()
else:
    # Initialize the saved creds
    gauth.Authorize()

# Save credentials for next time
gauth.SaveCredentialsFile("credentials.json")

drive = GoogleDrive(gauth)

# CONFIG: Use command line arguments mapping
LOCAL_FOLDER = args.source
DRIVE_FOLDER_ID = args.destination
ZIP_SUPPORT = args.zip

# Folders to exclude from backup (names only, not paths)
EXCLUDE_DIRS = [".obsidian", "__pycache__", ".git", ".vscode"]

# Cache of created Drive folders (local path → Drive folder ID)
folder_cache = {}

total_files_uploaded = 0
total_folders_uploaded = 0
total_bytes_uploaded = 0

def format_bytes(size):
    power = 1024
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"

def get_or_create_drive_folder(local_path, parent_id):
    """Ensure the corresponding folder exists in Drive and return its ID."""
    if local_path in folder_cache:
        return folder_cache[local_path]

    folder_name = os.path.basename(local_path)
    # Search if folder already exists under parent
    file_list = drive.ListFile({
        "q": f"'{parent_id}' in parents and trashed=false "
             f"and mimeType='application/vnd.google-apps.folder' "
             f"and title='{folder_name}'"
    }).GetList()

    if file_list:
        folder_id = file_list[0]["id"]
    else:
        # Create folder
        metadata = {
            "title": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [{"id": parent_id}]
        }
        folder = drive.CreateFile(metadata)
        folder.Upload()
        folder_id = folder["id"]

    folder_cache[local_path] = folder_id
    return folder_id

def file_exists_in_drive(filename, parent_id, local_size):
    """Check if a file with the same name and size exists in Drive."""
    file_list = drive.ListFile({
        "q": f"'{parent_id}' in parents and trashed=false and title='{filename}'"
    }).GetList()

    for gfile in file_list:
        if int(gfile.get("fileSize", 0)) == local_size:
            return True, gfile  # found matching file
    return False, None

# Step 2: Walk local folder and upload
if ZIP_SUPPORT:
    print("Zip mode enabled. Zipping first-level directories...")
    # Iterate over immediate children
    for item in os.listdir(LOCAL_FOLDER):
        if item in EXCLUDE_DIRS:
            continue
            
        item_path = os.path.join(LOCAL_FOLDER, item)
        
        if os.path.isfile(item_path):
            # Upload loose file directly to DRIVE_FOLDER_ID
            local_size = os.path.getsize(item_path)
            exists, gfile = file_exists_in_drive(item, DRIVE_FOLDER_ID, local_size)
            if exists:
                print(f"Skipping loose file {item_path} (already uploaded, same size)")
                continue

            print(f"Uploading loose file {item_path} → Drive folder {DRIVE_FOLDER_ID}")
            metadata = {"title": item, "parents": [{"id": DRIVE_FOLDER_ID}]}
            gfile = drive.CreateFile(metadata)
            gfile.SetContentFile(item_path)
            gfile.Upload()
            
            total_files_uploaded += 1
            total_bytes_uploaded += local_size
            
        elif os.path.isdir(item_path):
            # Zip this directory to a temp file
            temp_dir = tempfile.gettempdir()
            zip_base_name = os.path.join(temp_dir, item)
            
            print(f"Zipping directory {item_path} -> {zip_base_name}.zip")
            shutil.make_archive(zip_base_name, 'zip', item_path)
            zip_file_path = f"{zip_base_name}.zip"
            zip_file_name = f"{item}.zip"
            
            local_size = os.path.getsize(zip_file_path)
            exists, gfile = file_exists_in_drive(zip_file_name, DRIVE_FOLDER_ID, local_size)
            if exists:
                print(f"Skipping {zip_file_path} (already uploaded, same size)")
                os.remove(zip_file_path)
                continue

            print(f"Uploading zip {zip_file_path} → Drive folder {DRIVE_FOLDER_ID}")
            metadata = {"title": zip_file_name, "parents": [{"id": DRIVE_FOLDER_ID}]}
            gfile = drive.CreateFile(metadata)
            gfile.SetContentFile(zip_file_path)
            gfile.Upload()
            
            total_folders_uploaded += 1
            total_bytes_uploaded += local_size
            
            # Clean up PyDrive file references
            gfile = None
            
            # Clean up temp file
            try:
                os.remove(zip_file_path)
            except PermissionError:
                # Force garbage collection if Windows still holds the file handle
                import gc
                gc.collect()
                os.remove(zip_file_path)

else:
    for root, dirs, files in os.walk(LOCAL_FOLDER):
        # Remove any excluded dirs from traversal
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        # Map local root → Drive folder
        rel_path = os.path.relpath(root, LOCAL_FOLDER)
        if rel_path == ".":
            current_parent = DRIVE_FOLDER_ID
        else:
            # Create subfolders as needed
            parts = rel_path.split(os.sep)
            parent_id = DRIVE_FOLDER_ID
            accumulated = LOCAL_FOLDER
            for part in parts:
                accumulated = os.path.join(accumulated, part)
                parent_id = get_or_create_drive_folder(accumulated, parent_id)
            current_parent = parent_id

        # Upload files into this Drive folder
        for filename in files:
            filepath = os.path.join(root, filename)
            local_size = os.path.getsize(filepath)

            exists, gfile = file_exists_in_drive(filename, current_parent, local_size)
            if exists:
                print(f"Skipping {filepath} (already uploaded, same size)")
                continue

            print(f"Uploading {filepath} → Drive folder {current_parent}")
            metadata = {"title": filename, "parents": [{"id": current_parent}]}
            gfile = drive.CreateFile(metadata)
            gfile.SetContentFile(filepath)
            gfile.Upload()
            
            total_files_uploaded += 1
            total_bytes_uploaded += local_size

print("Incremental backup complete!")
print(f"Total files uploaded: {total_files_uploaded}")
print(f"Total folders uploaded (as zip): {total_folders_uploaded}")
print(f"Total data uploaded: {format_bytes(total_bytes_uploaded)}")
