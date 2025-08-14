import os
import sys
import subprocess
import shutil
import re

# --- Configuration ---
APP_NAME = "Kodi TextureTool"
TARGET_PY_FILE = "Kodi TextureTool.py"
ASSETS_DIR = "assets"
UTILS_DIR = "utils"
RUNTIMES_DIR = "runtimes"
CHANGELOG_FILE = "changelog.txt"
HELP_FILE = "help.md"
ICON_FILE = os.path.join(ASSETS_DIR, "fav.ico")

def get_app_version(file_path):
    """Reads the APP_VERSION variable from the Python file without executing it."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', content, re.M)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"\n⚠️ Warning: Could not read version from '{file_path}': {e}")
    return "unknown-version"

# --- Pre-build Checks ---
print("--- PyInstaller Build Script ---")
if not os.path.exists(TARGET_PY_FILE):
    print(f"\n❌ Error: The target file '{TARGET_PY_FILE}' was not found.")
    sys.exit(1)
if not os.path.exists(ICON_FILE):
    print(f"\n❌ Error: The icon file '{ICON_FILE}' was not found.")
    sys.exit(1)
if not os.path.exists(ASSETS_DIR):
    print(f"\n⚠️ Warning: The '{ASSETS_DIR}' directory was not found. Assets will be missing.")
if not os.path.exists(UTILS_DIR):
    print(f"\n⚠️ Warning: The '{UTILS_DIR}' directory was not found. Core utilities will be missing.")
if not os.path.exists(RUNTIMES_DIR):
    print(f"\n⚠️ Warning: The '{RUNTIMES_DIR}' directory was not found. Runtime installers will be missing.")

# --- Clean Previous Builds ---
print("\n>> Cleaning up previous build artifacts...")
for folder in ["build", "dist"]:
    if os.path.isdir(folder):
        shutil.rmtree(folder)
if os.path.exists(f"{APP_NAME}.spec"):
    os.remove(f"{APP_NAME}.spec")

# --- Define PyInstaller Command ---
command = [
    "pyinstaller",
    f"--name={APP_NAME}",
    "--noconsole",
    "--noupx",
    f"--icon={ICON_FILE}",
    f"--add-data={ASSETS_DIR}{os.pathsep}{ASSETS_DIR}",
    f"--add-data={UTILS_DIR}{os.pathsep}{UTILS_DIR}",
    f"--add-data={RUNTIMES_DIR}{os.pathsep}{RUNTIMES_DIR}",
    f"--add-data={CHANGELOG_FILE}{os.pathsep}.",
    f"--add-data={HELP_FILE}{os.pathsep}.",
    TARGET_PY_FILE
]

# --- Script Execution ---
print(f"\n>> Running the following command:\n   {' '.join(command)}\n")

try:
    # 1. Run the PyInstaller build process
    subprocess.run(command, check=True, text=True)
    print(f"\n✅ PyInstaller build process finished successfully.")
    
    # --- AUTO-ZIP SECTION ---
    print("\n>> Starting auto-zip process...")
    app_version = get_app_version(TARGET_PY_FILE)
    source_dir = os.path.join("dist", APP_NAME)
    
    if os.path.isdir(source_dir):
        zip_filename_base = f"{APP_NAME}-{app_version}"
        zip_output_path = os.path.join("dist", zip_filename_base)
        
        # Using root_dir makes the archive flat (contains files, not the parent folder)
        final_zip_path = shutil.make_archive(zip_output_path, 'zip', root_dir=source_dir)
        
        print(f"✅ Successfully created flat ZIP archive: {final_zip_path}")
        
        # --- NEW: FLATTEN DIST FOLDER SECTION ---
        print("\n>> Flattening the 'dist' directory...")
        for item in os.listdir(source_dir):
            shutil.move(os.path.join(source_dir, item), "dist")
        
        # Remove the now-empty source directory
        os.rmdir(source_dir)
        print("✅ 'dist' directory has been flattened.")
        
        print(f"\nDistribution files are ready in the 'dist' folder.")
    else:
        print(f"❌ Error: Could not find the build output directory '{source_dir}' to process.")

except subprocess.CalledProcessError:
    print(f"\n❌ PyInstaller build failed. Please review the output above for errors.")
except Exception as e:
    print(f"\n❌ An unexpected error occurred: {e}")
finally:
    print("\nPress Enter to exit.")
    input()