---

# Kodi TextureTool Guide

Welcome to the official help guide for the Kodi TextureTool. This document provides a complete overview of all features and offers guidance on how to use the application effectively. (Help Doc Updated: 09/04/2026)

---

## 1. Critical Requirement: Runtimes {#runtimes-anchor}

For the tool to function correctly, a specific version of the Microsoft Visual C++ 2010 (x86) Redistributable is required.

-   **Symptom of Missing Runtimes:** If you try to decompile a `.xbt` file and the output folder is empty, you are missing this component.
-   **How to Install:** The installer is included with the application. Go to **Options -> Install Runtimes**. This will request administrator permission. This only needs to be done once.
-   **Reinstalling:** If the runtimes are already detected, the menu swaps to **Options -> Reinstall Runtimes** instead, in case your install becomes corrupted. Only one of the two options is ever enabled at a time, based on what the tool currently detects.
-   **Automatic Detection:** The tool will automatically enable or disable Compile/Decompile features based on whether these runtimes are detected on your system.

---

## 2. The Main Interface {#main-interface-anchor}

The application is divided into functional zones designed for a streamlined workflow.

-   **Compile Mode:** For packing image folders into `.xbt` files.
-   **Decompile Mode:** For extracting images from `.xbt` files.
-   **Log Viewer:** Displays real-time feedback, color-coded by message type (info, error, warning, data, and load/progress messages), with numbers, versions, and timestamps highlighted for quick scanning. Below it, **Clear Log**, **Copy All Log**, and **Open Log File** buttons let you manage the session log directly.
-   **Image Previewer:** An advanced viewer for inspecting textures without full extraction.
-   **System Tray:** The application sits in your system tray. It will send popup notifications (balloons) to alert you when long-running tasks like compilation or PDF exports are finished.

---

## 3. Decompile Mode {#decompile-mode-anchor}

This mode allows you to unpack a Kodi texture file (`.xbt`) into its individual image files.

### Step-by-Step Usage
1.  **Select Input File:** Click `Select input file` or drag and drop a `.xbt` file onto the box.
2.  **Select Output Directory:** Click `Select output` or drag and drop a folder onto the box.
3.  **Actions:**
    *   **Start:** Full extraction of all images.
    *   **Get Info:** Scans the file and populates the [Image Previewer](#image-previewer-anchor). This creates a temporary cache for viewing images without cluttering your folders.
    *   **Open Last:** Quickly reloads the most recently used decompile file.

### Smart Drag & Drop
The Decompile boxes auto-detect what you drop, so you don't have to worry about which box a dropped item "belongs" in:
*   Dropping a **`.xbt` file** anywhere in Decompile mode sets it as the input file.
*   Dropping a **folder** sets it as the output folder.
*   Dropping something invalid (e.g. a non-`.xbt` file) is ignored and logged as a warning — nothing is changed.

### Recent Files & Folders
The **File** menu keeps a running list of your last 8 decompile input files and last 8 output folders, so you can jump straight back to a recent job without browsing. See [Recent Compile/Decompile Menus](#menu-bar-anchor) below.

---

## 4. Compile Mode {#compile-mode-anchor}

Pack a folder of images into a new Kodi-compatible `.xbt` file.

### Step-by-Step Usage
1.  **Select Input Directory:** Click `Select input folder` or drag and drop your source folder.
2.  **Select Output File:** Choose where to save the `.xbt`.
3.  **Dupecheck:** If enabled, the tool identifies identical images and stores only one copy, significantly reducing file size.
4.  **Open Last:** Quickly reloads the most recently used source folder.

### Smart Drag & Drop
The Compile boxes also auto-detect drops: dropping a **folder** sets the input folder, dropping a **file** sets it as the output `.xbt` file — regardless of which box you drop it on.

### Recent Files & Folders
Like Decompile mode, the **File** menu remembers your last 8 compile source folders and last 8 output files. See [Recent Compile/Decompile Menus](#menu-bar-anchor) below.

### Uppercase File Extension Check
Before compiling, the tool scans your source folder for images with **uppercase extensions** (e.g. `.PNG` instead of `.png`). `TextureCompiler.exe` silently skips these, which means they'd be missing from your finished `.xbt` with no warning. If any are found, you'll be asked to choose:
*   **Fix and Compile:** Compiles from a temporary copy with lowercased extensions. Your original source folder is left untouched.
*   **Compile Anyway:** Proceeds as-is; the log will warn you how many images will be missing from the output.
*   **Cancel:** Aborts the compile so you can rename the files yourself.

---

## 5. Image Previewer & Search {#image-previewer-anchor}

The previewer is a powerful inspection tool populated by the **Get Info** button.

### Navigation & Zoom
*   **Zoom Overlay:** A semi-transparent indicator in the top-left of the image shows your current zoom level (e.g., `1.5x`).
*   **Controls:** Use the `+` / `-` buttons or `Up`/`Down` arrow keys to zoom.
*   **Fit to Window:** Click the expansion icon to reset zoom and center the image.
*   **Navigation:** Use the slider or `Left`/`Right` arrow keys to browse.

### Dynamic Search & Filtering
*   **Filename/Index:** Type into the search box to jump to specific files.
*   **Dimensions Filter:** When you select "Dimensions" from the dropdown, the text box is replaced by a **Dimensions Filter Dropdown**. This list is automatically built from every unique image size found in the `.xbt`. Selecting a size (e.g., `256x256`) will filter the gallery to only show images of that exact size.

### Expanded Context Menu (Right-Click)
*   **Copy Image to Clipboard:** Copies the actual image data. You can paste it directly into image editors like Photoshop or GIMP.
*   **Copy Filename:** Copies the texture name to your clipboard.
*   **Open File Location:** Opens Windows Explorer and **automatically selects/highlights** the specific image in the temporary cache.

---

## 6. PDF Gallery Export {#pdf-export-anchor}

Generate professional PDF reports of your texture assets. Click the **Export to PDF** button to see three specialized options:

1.  **Export All:** Creates a full catalog of every texture in the `.xbt`.
2.  **Export Filtered:** Only exports the images currently visible in your search results. (e.g., Search for "button" then export only those results).
3.  **Export Selected:** Generates a single-page report for the image you are currently viewing.

### Paper Theme
Under the Export to PDF menu, choose **Paper -> Light** or **Paper -> Dark** to control the PDF's background — Light (white) is best for printing, Dark (midnight navy) is easier on the eyes on screen. Your choice is remembered for next time.

---

## 7. Menu Bar & Advanced Settings {#menu-bar-anchor}

### File Menu
*   **Compile -> File / Folder:** Manually browse for a compile output file or input folder, same as the buttons in Compile Mode.
*   **Decompile -> File / Folder:** Manually browse for a decompile input file or output folder, same as the buttons in Decompile Mode.
*   **Recent Compile -> Files / Folders:** Jump straight to any of your last 8 compile output files or last 8 source folders. Each submenu has its own **Clear Recent…** action to wipe that list.
*   **Recent Decompile -> Files / Folders:** Same as above, for your last 8 decompile input files and output folders.
*   **Reload All:** Instantly restores the last used paths for both Compile and Decompile modes.
*   **Close All:** Clears all current selections and resets the UI.
*   **Exit:** Closes the application.

### Display Menu
*   **Open Decompile Folder on Completion:** Toggle whether Windows Explorer automatically opens your output folder after a decompile finishes. Off by default.
*   **Open Compile Folder on Completion:** Same as above, but for the folder containing your finished `.xbt` after a compile. Off by default.
*   **Open PDF Report on Completion:** Toggle whether your PDF reader opens automatically after an export.
*   **Swap Positions:** Move the Log Viewer above or below the Image Previewer.
*   **Show Compile Mode on Top:** Switch the vertical order of the left-side toolboxes.
*   **Reset Window Position:** Centers the app on your primary monitor if the window is lost off-screen.
*   **Clear Event Log:** Wipes the on-screen log viewer and starts a fresh `TextureTool_Log.txt`. The log you just cleared is kept as `TextureTool_Log.prev.txt`, so nothing is lost.

### Options Menu
*   **Check for Updates on Startup:** Toggles automatic version checking.
*   **Install Runtimes:** Installs the required Visual C++ components (shown only when they're not currently detected — see [Runtimes](#runtimes-anchor)).
*   **Reinstall Runtimes:** Re-runs the installer over an existing install (shown only when the runtimes are already detected).

### Help Menu
*   **About:** Shows the current app version and build date.
*   **View Changelog:** Opens a dialog listing what changed in recent versions.
*   **View Help File:** Opens this help document.
*   **Kodi Forum:** Opens the official Kodi community forum thread in your browser.
*   **GitHub:** Opens the project's GitHub page in your browser.
*   **Check for Updates…:** Manually checks for a new version right now, instead of waiting for the automatic startup check.
*   **Check for Dev Update URL…:** Dev Mode only — see [Dev Mode Features](#technical-details-anchor).

---

## 8. Technical Details & Tips {#technical-details-anchor}

### Automatic Maintenance
*   **Cache Cleanup:** On startup, the tool automatically scans and deletes old temporary `ktt_info_cache` folders to save disk space.
*   **Path Normalization:** The tool automatically corrects Windows drive letter casing and supports modern **Unicode/Long Paths**, allowing you to work with files in folders containing non-English characters.

### Keyboard Shortcuts
-   **Left/Right:** Next/Previous Image.
-   **Up/Down:** Zoom In/Out.
-   **Enter:** (In search box) Find Next Match.
-   **Shift+Alt+D:** Activates **Dev Mode**.

### Dev Mode Features
Once activated via the hotkey, a "Dev Mode" checkbox appears:
-   **Command Preview:** Shows the exact command-line string before execution.
-   **Dev Update URL:** Accessible via **Help -> Check for Dev Update URL**, allowing testers to point the tool to a custom update manifest.

### Using This Help Window
The help window has its own toolbar: **Back/Forward** buttons to retrace your steps between sections, **font size +/-/reset** buttons for readability, and a filter box above the table of contents that also acts as a Find Next/Previous search within the currently displayed section. The divider between the table of contents and the content pane is draggable, and its position is remembered for next time.

### Updating the Tool
-   **Automatic Check:** On startup (if enabled — see Options Menu), and manually via **Help -> Check for Updates…**, the tool checks for a newer version.
-   **If an update is found:** A dialog shows the changelog and asks whether to download it. A progress dialog tracks the download.
-   **Safety Check:** Downloaded updates are verified with a SHA-256 checksum before being applied; if the checksum doesn't match, the update is rejected rather than installed.
-   **Applying the Update:** The tool closes itself, replaces its own files, and relaunches automatically — no manual reinstall needed.
-   **Notifications:** You'll get a tray notification for "Update Available," "Up to Date," or "Update Check Failed," even if the main window isn't focused.

---

## 9. Troubleshooting {#troubleshooting-anchor}

### Empty Output Folder
This is 99% of the time caused by missing **Visual C++ 2010 (x86) Runtimes**. Even if you have "newer" versions, the underlying TexturePacker tools require this specific version. Use **Options -> Install Runtimes**.

### Support
Click the **Help/Support** button below the log. This will:
1.  Open the official Kodi community forum thread.
2.  Open your `TextureTool_Log.txt` file. 
**Note:** Always include the contents of this log file when asking for help! You can also use the **Copy All Log** button under the Log Viewer to copy the current session's log straight to your clipboard, or **Open Log File** to open it without going through Help/Support.

### Which log file do I send?

The tool keeps two:

*   **`TextureTool_Log.txt`** — the session you are in right now.
*   **`TextureTool_Log.prev.txt`** — the session before it, kept automatically.

**If the tool crashed, send `TextureTool_Log.prev.txt`.** Starting the tool back up begins a new log, so the run that actually failed is the *previous* one. Both files live next to your `config.ini`; the exact path is printed near the top of every log under `Log File:`.

A log that ends with `----- Program Exit (clean) -----` shut down normally. If that line is missing, the tool was closed unexpectedly — worth mentioning when you report the problem.

Each log opens with a block of `[DATA]` lines recording your Windows version, the build you are running, where it is installed, and free disk space. Please leave those in — they answer most of the first round of questions.