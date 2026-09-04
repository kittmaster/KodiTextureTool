## <p align="center"><ins><strong>🎨 Texture Tool for Kodi 2026+</strong></ins></p>

<p align="center">
  <img width="120" src="https://github.com/kittmaster/KodiTextureTool/blob/main/assets/kodi_logo_1024.png" alt="Kodi Texture Tool Icon">
</p>

<p align="center">
  <img src="https://github.com/kittmaster/KodiTextureTool/blob/main/assets/MainImage.png" alt="Texture Tool GUI Screenshot">
</p>

<p align="center"><em>Updated GUI packer and unpacker for Kodi texture files</em></p>

---

### 🔧 Features

**Current release: v3.2.0 — Security, Stability & Interface**

- 🔒 HTTPS certificate verification restored for the auto-updater, with SHA-256 checksum verification on every downloaded update
- 🛡️ Command-injection flaw fixed — file/folder paths are no longer passed through a shell
- 🐛 Multiple crash/freeze fixes (background job cleanup races, silent Get Info crashes, hangs on heavy-warning texture files)
- ⚠️ Operations that used to silently report "complete" while actually failing (uppercase-extension images skipped, partial compiles, empty output) are now detected and reported as errors
- ⚡ "Get Info" is roughly 3x faster on large texture files
- 🌌 New **"Glass Midnight Navy"** interface — a frosted, translucent theme over a deep navy gradient, replacing the earlier flat grey/Nord look
- 🔎 Image previewer now zooms up to **8x with panning**, instead of cropping to a fixed center
- 💾 Window size/position, divider positions, zoom level, PDF paper choice, and dialog sizes are all remembered between runs via `config.ini`
- 📄 PDF export now supports **light or dark paper** themes, with a checkerboard transparency mat so pale artwork is never invisible

**Core feature set**

- 🌐 Unicode-aware logic for filenames, metadata, and UI
- 🈚 Enables seamless handling of non-ASCII characters, emoji glyphs, and multilingual assets
- 🧾 Prevents corruption, fallback artifacts, and encoding mismatches across platforms
- ✅ Fully rewritten in Python using **PySide6** for modern GUI skinning
- 🪟 Familiar Windows-style **menu system** with categorized recent items
- 🕘 Intelligent **Recent Files/Folders** tracking (last 8) with reload and clear options
- 🔐 **Interlocked execution** prevents invalid output without required runtimes
- 📦 Includes **silent Visual C++ 2010 x86 runtime installer** with UAC elevation, and auto-detects whether it needs installing or reinstalling
- ✨ Robust **log viewer** with HTML formatting, color-coded messages, and clipboard export
- 🗺️ Streamlined **GUI layout** with drag-and-drop support for files and folders
- 📋 Viewable **local changelog** and **Markdown-based help system**
- 🚫 No installer needed — fully **portable folder mode**
- 🎨 Output window with **status color accenting** and real-time progress updates
- ⏫ Fully operational **auto-updater** with changelog preview and ZIP extraction
- 🧼 Deprecated modes removed & improved .xbt status updates
- 📁 Moves working files to system `\temp` for cleanup on exit
- 🖼️ Built-in **image previewer** with search, navigation, and metadata display
- 📄 **PDF export** of texture info with gallery layout and Kodi branding
- 🧪 **Dev Mode** toggle with command preview and diagnostic logging
- 🔍 **Searchable Help Dialog** with TOC, Markdown rendering, and font controls
- 🧰 Internal **file integrity checks** for required DLLs and executables
- 🧠 Smart fallback for missing dependencies with graceful error handling
- 🧵 Thread-safe architecture using **QThread** and **QObject workers**
- 🧼 Cleans up orphaned subprocesses on exit to prevent file locking

---

### 🚀 Installation

**No installation required.**  
Simply run the `.exe` — available in both x86 and x64 builds — from any folder.  
Zero registry writes. Zero fuss.

---

### 🪟 Platform Compatibility

This tool is designed **exclusively for Windows 7/10/11**.  
Due to deep integration with Windows-specific APIs, GUI frameworks (PySide6), and runtime dependencies, cross-platform support is not feasible.  

Attempts to run on macOS or Linux — including via Wine or emulation — are **unsupported** and may result in unpredictable behavior or failure to launch.  

Developers are welcome to explore the source code, but official support remains **Windows-only by design**.

---

### 🌍 Translations

Currently supports **U.S. English only**.  
Multi-language support is on the roadmap. Stay tuned!

---

### 🏆 Credits

A modernized continuation of SUUP’s original work.  
Proudly updated for compatibility with **Windows 10/11** platforms.

---

### 📖 Learn More

📚 Visit the Kodi forum thread:  
[🔗 Texture Tool on Kodi Forum](https://forum.kodi.tv/showthread.php?tid=382565)

---

### 📜 License

This tool — and its texture assets — are provided **strictly for non-commercial use.**  
Please honor the license terms when redistributing or modifying.

---

### 🛠️ Support & Contact

For help, bug reports, and ongoing discussion, please use:

- 📣 [Kodi Forum Support Thread](https://forum.kodi.tv/showthread.php?tid=382565) (Basic reporting)
- 🐞 [GitHub Issues Page](https://github.com/kittmaster/KodiTextureTool/issues) (All operational issues)

Forum reporting helps consolidate fixes and avoid duplicates — thank you for keeping things tidy!