#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ----------------------------------------------------------------------------
#
#   Kodi TextureTool - Deployment and Packaging Script
#
#   Purpose: This script automates the creation of a clean, source-free,
#   distributable package for the Kodi TextureTool. It automatically reads
#   the version from the main Python file to ensure consistency.
#
#   To Use:
#   1. Make sure you have successfully built the application using PyInstaller.
#   2. Place this script in the root directory of your project.
#   3. Double-click to run. It will create a new, versioned and timestamped
#      'release_...' folder containing the organized files and the final .zip archive.
#
# ----------------------------------------------------------------------------

import os
import shutil
import re
from datetime import datetime
from colorama import init, Fore, Style

# Initialize Colorama for colored console output
init(autoreset=True)

# --- SCRIPT CONFIGURATION ---
# The version is now read automatically from the target Python file.
TARGET_PY_FILE = "Kodi TextureTool.py"
APP_EXE_NAME = "Kodi TextureTool.exe"

# --- Internal Paths and File Lists (Modify only if your project structure changes) ---
RELEASE_FOLDER_BASE = "release" # The base name for the release folder.
SOURCE_EXE_FOLDER = "dist"      # The folder where PyInstaller places the executable.

# These top-level files are required for the release.
REQUIRED_FILES = [
    "changelog.txt",
    "README.md",
    "help.md",
    "requirements.txt",
]

# These folders and all their contents are required for the release.
REQUIRED_FOLDERS = [
    "assets",
    "runtimes",
    "utils",
]


def get_app_version(file_path):
    """Reads the APP_VERSION variable from the Python file without executing it."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            # This regex finds a line like 'APP_VERSION = "v3.1.0"' and captures the number part.
            match = re.search(r'^APP_VERSION\s*=\s*"v([^"]+)"', content, re.M)
            if match:
                return match.group(1)  # Returns "3.1.0"
    except Exception as e:
        print(f"\n{Fore.YELLOW}Warning: Could not read version from '{file_path}': {e}{Style.RESET_ALL}")
    return None # Return None on failure


def main():
    """Main function to run the deployment packaging process."""

    # --- Get Version Automatically ---
    print(f"{Fore.YELLOW}Reading version from '{TARGET_PY_FILE}'...")
    app_version = get_app_version(TARGET_PY_FILE)

    if not app_version:
        print(f"{Fore.RED}FATAL ERROR: Could not determine application version from '{TARGET_PY_FILE}'.")
        print(f"{Fore.RED}Please ensure the file exists and contains a line like: APP_VERSION = \"vX.Y.Z\"")
        input("\nPress Enter to exit.")
        return

    print(f"{Fore.GREEN}Detected App Version: {app_version}{Style.RESET_ALL}\n")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    release_folder_name = f"{RELEASE_FOLDER_BASE}_v{app_version}_{timestamp}"

    print(f"{Style.BRIGHT}{Fore.CYAN}--- Kodi TextureTool Deployment Script v{app_version} ---{Style.RESET_ALL}\n")

    # --- Pre-flight Checks ---
    print(f"{Fore.YELLOW}Step 1: Performing pre-flight checks...")
    source_exe_path = os.path.join(SOURCE_EXE_FOLDER, APP_EXE_NAME)
    if not os.path.exists(source_exe_path):
        print(f"{Fore.RED}FATAL ERROR: Executable not found at '{source_exe_path}'.")
        print(f"{Fore.RED}Please run your PyInstaller build script first to generate the .exe file.")
        input("\nPress Enter to exit.")
        return

    for folder in REQUIRED_FOLDERS:
        if not os.path.exists(folder) or not os.path.isdir(folder):
            print(f"{Fore.RED}FATAL ERROR: Required folder '{folder}' not found.")
            print(f"{Fore.RED}Please ensure the script is in the project's root directory.")
            input("\nPress Enter to exit.")
            return

    print(f"{Fore.GREEN}All required files and folders found.{Style.RESET_ALL}\n")

    # --- Setup Release Folder ---
    print(f"{Fore.YELLOW}Step 2: Preparing versioned release folder...")

    try:
        os.makedirs(release_folder_name)
        print(f"{Fore.GREEN}Successfully created clean '{release_folder_name}' folder.{Style.RESET_ALL}\n")
    except OSError as e:
        print(f"{Fore.RED}FATAL ERROR: Could not create release folder: {e}")
        input("\nPress Enter to exit.")
        return

    # --- Assemble Package Contents ---
    print(f"{Fore.YELLOW}Step 3: Assembling release package contents...")

    try:
        # Copy the main executable
        print(f"  - Copying Executable: '{source_exe_path}'")
        shutil.copy2(source_exe_path, release_folder_name)

        # Copy required top-level files
        for file_name in REQUIRED_FILES:
            if os.path.exists(file_name):
                print(f"  - Copying File:       '{file_name}'")
                shutil.copy2(file_name, release_folder_name)
            else:
                print(f"  - {Fore.YELLOW}Warning: Optional file '{file_name}' not found. Skipping.")

        # Copy required folders
        for folder_name in REQUIRED_FOLDERS:
            dest_folder = os.path.join(release_folder_name, folder_name)
            print(f"  - Copying Directory:  '{folder_name}'")
            shutil.copytree(folder_name, dest_folder)

        print(f"{Fore.GREEN}All files successfully copied to '{release_folder_name}'.{Style.RESET_ALL}\n")

    except (IOError, OSError) as e:
        print(f"{Fore.RED}FATAL ERROR during file copy: {e}")
        input("\nPress Enter to exit.")
        return

    # --- Create Zip Archive ---
    print(f"{Fore.YELLOW}Step 4: Creating ZIP archive inside release folder...")

    # Define a temporary name for the zip, then we will move it.
    temp_zip_base_name = f"temp_archive_for_{timestamp}"
    final_zip_name = f"KodiTextureTool_Release_v{app_version}.zip"
    final_zip_path = os.path.join(release_folder_name, final_zip_name)

    try:
        # Create the archive in the root directory first
        temp_archive_path_with_ext = shutil.make_archive(
            base_name=temp_zip_base_name,
            format='zip',
            root_dir=release_folder_name
        )

        # Move the created archive into the release folder
        shutil.move(temp_archive_path_with_ext, final_zip_path)

        print(f"{Fore.GREEN}Archive created successfully.{Style.RESET_ALL}\n")

    except Exception as e:
        print(f"{Fore.RED}FATAL ERROR while creating zip archive: {e}")
        # Clean up temp zip file if it exists
        if os.path.exists(f"{temp_zip_base_name}.zip"):
             os.remove(f"{temp_zip_base_name}.zip")
        input("\nPress Enter to exit.")
        return

    # --- Success Message ---
    print(f"{Style.BRIGHT}{Fore.GREEN}-----------------------------------------------------------")
    print(f"{Style.BRIGHT}{Fore.GREEN}          DEPLOYMENT PACKAGE CREATED SUCCESSFULLY!         ")
    print(f"{Style.BRIGHT}{Fore.GREEN}-----------------------------------------------------------")
    print(f"Release Folder:  {Style.BRIGHT}{release_folder_name}{Style.RESET_ALL}")
    print(f"Package Archive: {Style.BRIGHT}{final_zip_path}{Style.RESET_ALL}")
    print("\nYou can now upload the .zip file from the release folder to GitHub.")
    input("\nPress Enter to exit.")


if __name__ == "__main__":
    main()