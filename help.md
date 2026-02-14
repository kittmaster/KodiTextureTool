---

# Kodi TextureTool Guide

Welcome to the official help guide for the Kodi TextureTool. This document provides a complete overview of all features and offers guidance on how to use the application effectively. (Build Date: 10/10/2025)

---

## 1. Critical Requirement: Runtimes {#runtimes-anchor}

For the tool to function correctly, a specific version of the Microsoft Visual C++ 2010 (x86) Redistributable is required.

<p align="center">
  <img src="assets/InstallRuntimes.png" alt="Install Runtimes menu option" width="340" style="border: 1px solid #434c5e; border-radius: 4px;">
</p>

-   **Symptom of Missing Runtimes:** If you try to decompile a `.xbt` file and the output folder is empty, you are missing this component.
-   **How to Install:** The installer is included with the application. Go to **Options -> Install Runtimes**. This will request administrator permission. This only needs to be done once.
-   **Automatic Detection:** The tool will automatically enable or disable Compile/Decompile features based on whether these runtimes are detected on your system.

---

## 2. The Main Interface {#main-interface-anchor}

The application is divided into functional zones designed for a streamlined workflow.

-   **Compile Mode:** For packing image folders into `.xbt` files.
-   **Decompile Mode:** For extracting images from `.xbt` files.
-   **Log Viewer:** Displays real-time feedback, color-coded for errors and warnings.
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

---

## 4. Compile Mode {#compile-mode-anchor}

Pack a folder of images into a new Kodi-compatible `.xbt` file.

### Step-by-Step Usage
1.  **Select Input Directory:** Click `Select input folder` or drag and drop your source folder.
2.  **Select Output File:** Choose where to save the `.xbt`.
3.  **Dupecheck:** If enabled, the tool identifies identical images and stores only one copy, significantly reducing file size.
4.  **Open Last:** Quickly reloads the most recently used source folder.

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

---

## 7. Menu Bar & Advanced Settings {#menu-bar-anchor}

### File Menu
*   **Reload All:** Instantly restores the last used paths for both Compile and Decompile modes.
*   **Close All:** Clears all current selections and resets the UI.

### Display Menu
*   **Open PDF Report on Completion:** Toggle whether your PDF reader opens automatically after an export.
*   **Swap Positions:** Move the Log Viewer above or below the Image Previewer.
*   **Show Compile Mode on Top:** Switch the vertical order of the left-side toolboxes.
*   **Reset Window Position:** Centers the app on your primary monitor if the window is lost off-screen.

### Options Menu
*   **Check for Updates on Startup:** Toggles automatic version checking.
*   **Install/Reinstall Runtimes:** Manage the required Visual C++ components.

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

---

## 9. Troubleshooting {#troubleshooting-anchor}

### Empty Output Folder
This is 99% of the time caused by missing **Visual C++ 2010 (x86) Runtimes**. Even if you have "newer" versions, the underlying TexturePacker tools require this specific version. Use **Options -> Install Runtimes**.

### Support
Click the **Help/Support** button below the log. This will:
1.  Open the official Kodi community forum thread.
2.  Open your `TextureTool_Log.txt` file. 
**Note:** Always include the contents of this log file when asking for help!