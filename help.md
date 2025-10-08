# Kodi TextureTool Guide

Welcome to the official help guide for the Kodi TextureTool. This document provides a complete overview of all features and offers guidance on how to use the application effectively. (Build Date: 8/14/2025)

---

## 1. Critical Requirement: Runtimes {#runtimes-anchor}

For the tool to function correctly, a specific version of the Microsoft Visual C++ 2010 (x86) Redistributable is required.

<p align="center">
  <img src="assets/InstallRuntimes.png" alt="Install Runtimes menu option" width="340" style="max-width: 100%; border: 1px solid #434c5e; border-radius: 4px;">
</p>

-   **Symptom of Missing Runtimes:** If you try to decompile a `.xbt` file and the output folder is empty, you are missing this component.
-   **How to Install:** The installer is included with the application. Simply go to the **Options -> Install Runtimes** menu option. This will request administrator permission to install the necessary files. This only needs to be done once.

---

## 2. The Main Interface {#main-interface-anchor}

The application is divided into two main sections on the left, a log viewer on the right, and an image previewer at the bottom right.

<p align="center">
  <img src="assets/MainImage.png" alt="Kodi TextureTool Main Interface" width="900" style="max-width: 100%; border: 1px solid #434c5e; border-radius: 4px;">
</p>

-   **Compile Mode:** Used for packing a folder of images into a new `.xbt` file.
-   **Decompile Mode:** Used for extracting images from a `.xbt` file.
-   **Log Viewer:** Displays a real-time log of all operations, warnings, and errors.
-   **Image Previewer:** Allows you to view the images inside a `.xbt` file after running "Get Info".
-   **Help Dialog:** Accessed via **Help -> View Help File**, this searchable guide includes a table of contents, font controls, and Markdown rendering.

---

## 3. Decompile Mode {#decompile-mode-anchor}

This mode allows you to unpack a Kodi texture file (`.xbt`) into its individual image files (e.g., `.png`).

<p align="center">
  <img src="assets/DecompileMode.png" alt="Decompile Mode Interface" width="600" style="max-width: 100%; border: 1px solid #434c5e; border-radius: 4px;">
</p>

> If you encounter an empty output folder after decompiling, please see the [Troubleshooting](#troubleshooting-anchor) section for information on required runtimes.

### Step-by-Step Usage
1.  **Select Input File:** Click the `Select input file` button to browse for a `.xbt` file.
    -   *Tip:* You can also drag and drop a `.xbt` file directly onto the "Decompile Mode" group box.
    -   *Tip:* Use the `Open Last` button to quickly load the most recent file you used.

2.  **Select Output Directory:** Click the `Select output` button to choose a folder where the extracted images will be saved.
    -   *Tip:* You can also drag and drop a folder onto the "Decompile Mode" group box to set it as the output.

3.  **Choose an Action:**
    -   Click **Start** to begin the full extraction process.
    -   Click **Get Info** to scan the file and populate the [Image Previewer](#image-previewer-anchor) *without* saving the images to the output folder. This is the primary way to use the previewer.

-   **Clear:** Resets the input and output selections for this mode.
-   **Open Folder (Icon):** Opens the selected output directory in your system's file explorer.

---

## 4. Compile Mode {#compile-mode-anchor}

This mode allows you to create a new `.xbt` file from a folder containing your source images.

<p align="center">
  <img src="assets/CompileMode.png" alt="Compile Mode Interface" width="600" style="max-width: 100%; border: 1px solid #434c5e; border-radius: 4px;">
</p>

### Step-by-Step Usage
1.  **Select Input Directory:** Click the `Select input folder` button and choose the folder containing the images you want to pack.
    -   *Tip:* You can also drag and drop the source folder directly onto the "Compile Mode" group box.
    -   *Tip:* Use the `Open Last` button to quickly load the most recent folder you used.

2.  **Select Output File:** Click the `Select output file` button and choose where to save your new `.xbt` file, giving it a name.

3.  **Options:**
    -   **Enable dupecheck:** If checked, the compiler will identify duplicate images and only store one copy, referencing it multiple times. This is highly recommended as it can significantly reduce the final file size.

4.  **Start:** Click the `Start` button to begin the compilation process.

-   **Clear:** Resets the input and output selections for this mode.
-   **Open Folder (Icon):** Opens the folder containing your selected output file.

---

## 5. Image Previewer {#image-previewer-anchor}

The previewer is populated by using the **Get Info** button in Decompile Mode. It provides a powerful way to inspect the contents of a `.xbt` file.

<p align="center">
  <img src="assets/ImageViewer.png" alt="Image Previewer Interface" width="800" style="max-width: 100%; border: 1px solid #434c5e; border-radius: 4px;">
</p>

-   **Navigation Buttons (`<<`, `<`, `>`, `>>`):** Move to the first, previous, next, or last image.
-   **Navigation Slider:** Drag the slider to scrub through images quickly.
-   **Image Info:** The text above the image displays the current image number, total count, search status, and filename.
-   **Image Details:** Below the image, you can see the texture's dimensions and file format.
-   **Search by:** Use the dropdown to select a search criterion:
    -   `Filename`: Find images by typing part of their name.
    -   `Index`: Jump directly to an image number (e.g., `42`).
    -   `Dimensions`: Filter for images of a specific size (e.g., `128x128`).
-   **Search Navigation:** Use the `Previous` and `Next` buttons to cycle through matching search results.
-   **Export to PDF:** Creates a professional PDF gallery of all images and their metadata from the loaded `.xbt` file.
-   **Open Image:** Double-click the displayed image to open it in your system's default image viewer.

---

## 6. The Log Viewer & Getting Support {#log-viewer-anchor}

The Log Viewer is the central nervous system of the application, providing detailed, real-time feedback on every operation. Understanding it is key to troubleshooting issues.

<p align="center">
  <img src="assets/LogViewer.png" alt="Log Viewer Interface" width="850" style="max-width: 100%; border: 1px solid #434c5e; border-radius: 4px;">
</p>

**Key Features:**

- **Real-time Feedback:** Watch the log as you perform actions to see exactly what the underlying compiler/decompiler tools are doing.
- **Color-Coded Messages:** Messages are colored for easy identification:
    -   <span style="color:#81A1C1;">**[INFO]**</span>: General information and process status.
    -   <span style="color:#EBCB8B;">**[WARN]**</span>: Warnings that do not stop an operation but should be noted.
    -   <span style="color:#BF616A;">**[ERROR]**</span>: Critical failures that stopped a process.
    -   <span style="color:#B48EAD;">**[DATA]**</span>: Detailed output from the command-line tools.
- **Log Controls:** The buttons below the log provide quick access to:
    -   `Clear Log`: Clears the on-screen log viewer.
    -   `Copy ALL`: Copies the entire session log to your clipboard.
    -   `Open Log File`: Opens the persistent `TextureTool_Log.txt` file from your system's application data folder.
    -   `Help/Support`: The primary way to report an issue. This opens the Kodi forum thread and the log file for you.

---

## 7. Menu Bar & Advanced Features {#menu-bar--advanced-features-anchor}

This section details all functions available in the main application menu bar.

### File Menu
The File menu provides core actions for loading files, accessing recent paths, and controlling the application.

<p align="center">
  <img src="assets/FileMenu.png" alt="File Menu with Recent Items" width="273" style="max-width: 100%; border: 1px solid #434c5e; border-radius: 4px;">
</p>

*   **Compile / Decompile:** These sub-menus allow you to select input and output files/folders, mirroring the buttons on the main interface.
*   **Recent Compile / Recent Decompile:** Quickly access a list of the last 8 paths used for each category (e.g., Compile Files, Compile Folders). Each sub-menu also contains a `Clear Recent...` option to erase its history.
*   **Reload All:** Quickly loads the single most recent file and folder used in *both* Decompile and Compile modes.
*   **Close All:** Clears all current input and output selections from both modes.
*   **Exit:** Closes the application.

### Display Menu
This menu controls the application's appearance and behavior after tasks are completed.

<p align="center">
  <img src="assets/DisplayMenu.png" alt="Display Menu Options" width="425" style="max-width: 100%; border: 1px solid #434c5e; border-radius: 4px;">
</p>

*   **Open ... on Completion:**
    *   `Open Decompile/Compile Folder...`: Toggle whether the output folder is automatically opened after a successful operation.
    *   `Open PDF Report...`: Toggle whether a generated PDF gallery is automatically opened after a successful export.
*   **Swap Log Viewer/Image Previewer Position:** Toggles the vertical position of the Log Viewer and the Image Previewer.
*   **Show Compile Mode on Top:** Toggles the layout of the main panel. By default, this is checked and Compile Mode is shown first. Uncheck it to show Decompile Mode on top.
*   **Reset Window Position:** If the application window gets lost off-screen or improperly sized, this will reset it to the center of your primary monitor.
*   **Clear Event Log:** Clears all messages from the Log Viewer panel.

### Options Menu
This menu allows you to configure application startup behavior.

<p align="center">
  <img src="assets/OptionsMenu.png" alt="Options Menu" width="345" style="max-width: 100%; border: 1px solid #434c5e; border-radius: 4px;">
</p>

*   **Check for Updates on Startup:** Toggle whether the application automatically checks for a new version every time it is launched.
*   **Install Runtimes:** The critical function for installing the required Visual C++ runtimes. This option is enabled only if the runtimes are not detected.
*   **Reinstall Runtimes:** Allows you to run the installer again to repair a corrupt installation. This option is enabled only if the runtimes are already detected.

### Help Menu
Access documentation, support resources, and version information.

<p align="center">
  <img src="assets/HelpMenu.png" alt="Help Menu" width="261" style="max-width: 100%; border: 1px solid #434c5e; border-radius: 4px;">
</p>

*   **About:** Displays the application version, author, and build date.
*   **View Changelog:** Shows a history of all version changes and new features.
*   **View Help File:** Opens this interactive help guide.
*   **Check for Updates...:** Manually checks if a new version of the tool is available for download.

### Dev Mode (Hotkey)
This is a hidden feature primarily intended for debugging purposes.

*   Press `Shift+Alt+D` to enable a "Dev mode" checkbox on the main window.
*   When this checkbox is checked, running a compile or decompile process will first show you a dialog box with the exact command-line string that is being executed.

---

## 8. Tips, Tricks, & Technical Details {#technical-details-anchor}

### Drag & Drop Functionality
To speed up your workflow, both the Decompile and Compile group boxes act as drop targets:

*   **Decompile Mode:**
    *   Drag a `.xbt` file onto the box to set it as the **Input File**.
    *   Drag a `folder` onto the box to set it as the **Output Directory**.
*   **Compile Mode:**
    *   Drag a `folder` onto the box to set it as the **Input Directory**.
    *   Drag a `.xbt` file onto the box to set it as the **Output File**.

### Unicode Path Support
The application now fully supports Unicode in all file and folder paths. This is a significant upgrade from the previous tool that was limited to ANSI paths.

This means you can confidently use input and output paths that contain non-English characters, such as accents, symbols, or characters from different language scripts.

**Examples of now-supported paths:**

-   `C:\Users\Málaga\Desktop\My Textures\`
-   `D:\Kodi Skins\テクスチャ\`
-   `E:\Мои Документы\Images\`

### Configuration File (`config.ini`)
The application saves your settings and recent file paths to a configuration file named `config.ini`. This includes your preferences for opening folders on completion, update checks, and the log window position.

If you ever need to completely reset the application to its default state, you can safely delete this file. It is located in your system's application data folder, typically at:
`C:\Users\<YourUsername>\AppData\Local\KodiTextureTool\config.ini`

*Note: You can quickly access this folder by typing `%LOCALAPPDATA%\KodiTextureTool` into the Windows Explorer address bar.*

### Credits & Acknowledgements
This tool stands on the shoulders of giants and would not be possible without the following projects:

*   **TexturePacker:** The original command-line tools by the Kodi team.
*   **Python:** The programming language used to create this application.
*   **PySide6:** The Qt for Python framework used for the graphical user interface.
*   **QtAwesome:** For providing the FontAwesome icon set.
*   **Markdown & BeautifulSoup:** For rendering this help documentation.
*   **ReportLab:** For generating PDF gallery exports.

---

## 9. Troubleshooting {#troubleshooting-anchor}

### The decompile process finishes, but the output folder is empty.
This is the most common issue and is almost always caused by the missing **Visual C++ 2010 (x86) Runtimes**. Please see the [Critical Requirement: Runtimes](#runtimes-anchor) section of this guide and use the **Options -> Install Runtimes** menu option to resolve it.

### How do I report an issue or get support?
The best way to get help is by using the tools provided in the [Log Viewer](#log-viewer-anchor) section. The **Help/Support** button is your primary tool. Clicking it will:
1.  Open the official Kodi community forum thread in your web browser.
2.  Open the application's log file (`TextureTool_Log.txt`) in your text editor.

> When posting on the forum, please copy and paste the entire contents of this log file into your post. It contains vital diagnostic information.