# DrivePy Backup

DrivePy is a Python script designed to autonomously and incrementally back up local directories to Google Drive. It features intelligent file-size matching to skip already uploaded files, custom zip compression with native progress bars, and configurable exclusion lists to ignore intermediate build files or specific directories.

## Features

- **Incremental Backups**: Checks the exact file size of existing files on Google Drive to skip re-uploading identical files.
- **Zip Support (`-z`)**: Compress directories into `.zip` files on the fly before uploading. Includes a built-in ASCII progress bar.
- **Configurable Compression**: Choose between the fast, standard `deflate` algorithm or the stronger `lzma` algorithm for smaller file sizes.
- **Dry-Run Mode**: Test your backups and accurately predict the resulting file and zip sizes without actually uploading anything to Drive.
- **Auto-Authentication Resilience**: Safely handles token expirations (such as the 7-day limit on "Testing" Google Cloud projects) by automatically deleting expired credentials and re-triggering the web authentication flow.
- **Exclusion Configurations**: Easily ignore specific directories (like `.git` or `.vscode`) and file extensions (like `.obj` or `.pdb`) using a straightforward JSON config.

## Requirements
- Python 3.7+
- `pydrive2`

Install dependencies:
```bash
pip install pydrive2
```

## Setup & Authentication

Before running the script, you must have a Google Cloud Project with the Google Drive API enabled. 
1. Create an OAuth 2.0 Client ID for a Desktop Application.
2. Download the client secrets and save them as `client_secrets.json` in the same folder as the script.
3. Upon running the script for the first time, a browser window will open asking you to authenticate. This generates a `credentials.json` file which is saved locally for future runs.

**Note on `settings.yaml`:**
The script utilizes a `settings.yaml` file to tell `pydrive2` to explicitly request an offline *Refresh Token* (`get_refresh_token: True`). This prevents the need to log in through the browser every time the 1-hour access token expires.

## Usage

```bash
python drive.py -s <SOURCE_FOLDER> -d <DRIVE_FOLDER_ID> [OPTIONS]
```

### Options
- `-s`, `--source`: **(Required)** Local source path to back up.
- `-d`, `--destination`: **(Required)** Target Google Drive folder ID (the string of characters in the URL of the Drive folder).
- `-z`, `--zip`: Compress top-level directories into `.zip` files before uploading.
- `-c`, `--compression`: Choose the compression algorithm (`deflate` or `lzma`). Defaults to `deflate`.
- `-n`, `--limit`: Maximum number of files/folders to process (useful for testing). Default is `0` (no limit).
- `--folders-only`: Process only directories and entirely skip loose files in the source path.
- `--dry-run`: Simulate the backup, run the zipping engine to calculate sizes, and report the total output without hitting the Google Drive API.

### Examples

**Standard Incremental Backup:**
```bash
python drive.py -s "D:\MyData" -d xxx-xxxxxxxxxxxx

**Zip Folders and Skip Loose Files:**
```bash
python drive.py -s "D:\MyProjects" -d xxx-xxxxxxxxxxx -z --folders-only
```

**Dry Run with Max Compression:**
```bash
python drive.py -s "D:\Media" -d xxx-xxxxxxxxxxxx -z -c lzma --dry-run
```

## Configuration (`exclude.json`)

The script will automatically generate an `exclude.json` file on its first run if one is not present. You can modify this file to ignore specific directories or file extensions.

Default configuration:
```json
{
    "exclude_dirs": [
        ".obsidian",
        "__pycache__",
        ".git",
        ".vscode"
    ],
    "exclude_extensions": [
        ".obj",
        ".o",
        ".ilk",
        ".pdb",
        ".tlog",
        ".idb",
        ".reapeaks"
    ]
}
```