import os
import sys
import subprocess
import shutil

# --- Configuration ---
APP_NAME = "Kodi TextureTool"
TARGET_PY_FILE = "Kodi TextureTool.py"
ASSETS_DIR = "assets"
UTILS_DIR = "utils"
RUNTIMES_DIR = "runtimes"
CHANGELOG_FILE = "changelog.txt"
HELP_FILE = "help.md"
ICON_FILE = os.path.join(ASSETS_DIR, "fav.ico")

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
# Using os.pathsep for cross-platform compatibility in the --add-data flag.
# On Windows, os.pathsep is ';'. On Linux/macOS, it is ':'.
command = [
    "pyinstaller",
    f"--name={APP_NAME}",
    "--onefile",
    "--noconsole",      # This is the modern replacement for --noconsole
    "--noupx",
    f"--icon={ICON_FILE}",
    f"--add-data={ASSETS_DIR}{os.pathsep}{ASSETS_DIR}",
    f"--add-data={UTILS_DIR}{os.pathsep}{UTILS_DIR}",
    f"--add-data={RUNTIMES_DIR}{os.pathsep}{RUNTIMES_DIR}",
    f"--add-data={CHANGELOG_FILE}{os.pathsep}.",
    f"--add-data={HELP_FILE}{os.pathsep}.",
    TARGET_PY_FILE
]

#    "--windowed",      # This is the modern replacement for --noconsole

# --- Script Execution ---
print(f"\n>> Running the following command:\n   {' '.join(command)}\n")

try:
    subprocess.run(command, check=True, text=True)
    print(f"\n✅ Build process finished successfully. Check the 'dist' folder for '{APP_NAME}.exe'.")
except subprocess.CalledProcessError:
    print(f"\n❌ PyInstaller build failed. Please review the output above for errors.")
except Exception as e:
    print(f"\n❌ An unexpected error occurred: {e}")
finally:
    print("\nPress Enter to exit.")
    input()