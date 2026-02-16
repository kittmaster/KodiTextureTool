# PATCHED_BY_SCRIPT_VERSION: v3.5.74 | Unlocks the Help Dialog TOC pane resizing by replacing fixed width with minimum width.

#.63 Filmstrip loads correctly now and able to render.
import ctypes; import atexit; import shutil; import tempfile; import subprocess;import webbrowser
import winreg; import configparser; import sys; import os; import traceback; import functools
import urllib.request; import json; import textwrap; import re; import qtawesome as qta
import shlex; import socket; import markdown; import math; import threading; import datetime; import gc
from enum import Enum
from collections import deque
from ctypes import wintypes
from datetime import datetime, timedelta
from PySide6.QtGui import (QAction, QFont, QIcon, QImage, QPixmap, QImageReader,
                           QTextDocument, QKeySequence, QShortcut)
from PySide6.QtCore import (Qt, QSize, QThread, QObject, Signal, QTimer, QSettings,
                            QUrl, QBuffer, QIODevice, QStandardPaths)
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFileDialog,
                               QFormLayout, QFrame, QGroupBox, QHBoxLayout,
                               QLabel, QMainWindow, QMenu, QMessageBox,
                               QProgressBar, QPushButton, QStyle, QSystemTrayIcon,
                               QTextEdit, QVBoxLayout, QWidget, QSplitter, QSlider,
                               QLineEdit, QComboBox, QStackedWidget, QGridLayout,
                               QListWidget, QTextBrowser, QScrollArea, QSizePolicy,
                               QListWidgetItem, QInputDialog)
from bs4 import BeautifulSoup
from bs4.element import Tag
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, quote
import platform
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# ---- Global variables from original script
# ---- These will be managed as instance attributes in the main class
APP_VERSION = "v3.1.7"
APP_TITLE = "Kodi TextureTool"
APP_AUTHOR = "Chris Bertrand"
BUILD_DATE = datetime.now().strftime("%m-%d-%Y %H:%M:%S")

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller. """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))

    if sys.platform == "win32":
        # On Windows, _MEIPASS can return an 8.3 short path. We convert it to
        # its long path form for consistency. This requires setting up the
        # ctypes function prototype to prevent stack corruption errors.
        try:
            # Define the function prototype from kernel32.dll
            GetLongPathNameW = ctypes.windll.kernel32.GetLongPathNameW
            GetLongPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
            GetLongPathNameW.restype = wintypes.DWORD

            # Prepare the buffer
            buffer_size = wintypes.MAX_PATH
            buffer = ctypes.create_unicode_buffer(buffer_size)

            # Call the function and check the result
            result = GetLongPathNameW(base_path, buffer, buffer_size)
            if result > 0 and result < buffer_size:
                # Success: the return value is the length of the string, and it fits the buffer.
                base_path = buffer.value
            # If result is 0, the function failed; we'll just use the original base_path.
            # If result > buffer_size, the buffer was too small; we'll also use the original.
        except Exception:
            # In case of any ctypes error, fall back gracefully to the original path.
            pass

    return os.path.normpath(os.path.join(base_path, relative_path))

class RecentGroup(Enum):
    """Defines constant identifiers for recent item categories."""
    COMPILE_FILES = 'compile_files'
    COMPILE_FOLDERS = 'compile_folders'
    DECOMPILE_FILES = 'decompile_files'
    DECOMPILE_FOLDERS = 'decompile_folders'
class Worker(QObject):
    finished = Signal(int, str)
    error = Signal(str)
    progress_updated = Signal(int, str)  # Emits progress percentage and message
    info_line_parsed = Signal(str, str)  # Emits formatted HTML and the raw filename

    class StreamReader(QObject):
        lines_ready = Signal(list)
        finished = Signal()

        def __init__(self, stream):
            super().__init__()
            self.stream = stream

        def run(self):
            if not self.stream:
                self.finished.emit()
                return

            # Batching logic to prevent signal flooding on large file outputs
            batch = []
            # iter(readline, '') blocks until a line is read or EOF is reached.
            for line in iter(self.stream.readline, ''):
                clean_line = line.strip()
                if clean_line:
                    batch.append(clean_line)

                # Emit batch if size threshold reached (e.g., 25 lines)
                if len(batch) >= 25:
                    self.lines_ready.emit(batch)
                    batch = []

            # Flush any remaining lines
            if batch:
                self.lines_ready.emit(batch)
            self.finished.emit()

    def __init__(self, command, cwd, show_window: bool = False):
        super().__init__()
        self.command = command
        self.cwd = cwd
        self.show_window = show_window
        self.process = None
        self.reader_thread = None
        self.stdout_reader = None
        self.stderr_reader = None
        self.full_stdout = []
        self.full_stderr = []
        self.stdout_finished = False
        self.stderr_finished = False
        self.last_emitted_progress = -1  # Initialize progress tracker

    def run(self):
        try:
            # THE DEFINITIVE FIX: Replicate the successful .bat file test environment.
            # We will run the command inside cmd.exe, after forcing its codepage to UTF-8.
            final_command = self.command
            is_string_command = isinstance(self.command, str)

            if sys.platform == "win32":
                # Ensure the original command is a list of strings
                if is_string_command:
                    original_command_list = shlex.split(self.command)
                else:
                    original_command_list = self.command

                # Quote each argument to handle spaces correctly when passed to the shell.
                # The first argument (the executable path) must be handled carefully.
                quoted_exe = f'"{original_command_list[0]}"'
                quoted_args = " ".join(f'"{arg}"' for arg in original_command_list[1:])
                full_command_str = f"{quoted_exe} {quoted_args}"

                # The final command string for cmd.exe. It first sets the codepage to UTF-8,
                # then executes our actual command.
                final_command = f'cmd.exe /c "chcp 65001 > nul && {full_command_str}"'
                is_string_command = True # We are now passing a single string to Popen

            self.process = subprocess.Popen(
                final_command,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=is_string_command, # This needs to be True for the cmd.exe string
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=0 if self.show_window else (subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            )

            self.reader_thread = QThread(self)

            if self.process.stdout:
                self.stdout_reader = self.StreamReader(self.process.stdout)
                self.stdout_reader.moveToThread(self.reader_thread)
                # BATCHED SIGNAL CONNECTION
                self.stdout_reader.lines_ready.connect(self._on_stdout_batch)
                self.stdout_reader.finished.connect(self._on_stream_finished)
                self.reader_thread.started.connect(self.stdout_reader.run)
            else:
                self.stdout_finished = True

            if self.process.stderr:
                self.stderr_reader = self.StreamReader(self.process.stderr)
                self.stderr_reader.moveToThread(self.reader_thread)
                # BATCHED SIGNAL CONNECTION
                self.stderr_reader.lines_ready.connect(self._on_stderr_batch)
                self.stderr_reader.finished.connect(self._on_stream_finished)
                if not self.reader_thread.isRunning():
                    self.reader_thread.started.connect(self.stderr_reader.run)
            else:
                self.stderr_finished = True

            if not (self.stdout_finished and self.stderr_finished):
                self.reader_thread.start()
            else:
                QTimer.singleShot(100, self._finalize_process)

        except Exception as e:
            self._emit_error(f"Failed to start process: {e}")

    def _on_stdout_batch(self, lines):
        # Process a batch of lines to prevent signal flooding
        for line in lines:
            if line.startswith("PROGRESS:"):
                try:
                    parts = line.split(':', 2)
                    percentage = int(parts[1])
                    message = parts[2] if len(parts) > 2 else ""

                    # --- THROTTLING LOGIC ---
                    # Only emit the signal if the percentage has actually changed.
                    if percentage > self.last_emitted_progress:
                        self.last_emitted_progress = percentage
                        self.progress_updated.emit(percentage, message)

                except (ValueError, IndexError):
                    pass
            elif line.startswith("Texture:"):
                try:
                    details_part = line.split("Texture:", 1)[1].strip()
                    png_index = details_part.rfind('.png')
                    if png_index != -1:
                        filename = details_part[:png_index + 4]
                        self.info_line_parsed.emit(line.strip(), filename)
                except IndexError:
                    pass
            else: # For all other lines like "Dimensions", "Format", etc.
                clean_line = line.strip()
                if clean_line:
                    self.info_line_parsed.emit(clean_line, "") # Emit with no filename

    def _on_stderr_batch(self, lines):
        self.full_stderr.extend(lines)

    def _on_stream_finished(self):
        sender = self.sender()
        if sender == self.stdout_reader:
            self.stdout_finished = True
        elif sender == self.stderr_reader:
            self.stderr_finished = True

        if self.stdout_finished and self.stderr_finished:
            QTimer.singleShot(100, self._finalize_process)

    def _finalize_process(self):
        if self.process is None:
            return

        if self.process.poll() is None:
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()

        if self.reader_thread and self.reader_thread.isRunning():
            self.reader_thread.quit()
            self.reader_thread.wait()

        # The 'output' is now just stderr, since stdout was handled live.
        # This prevents the entire log from being re-processed at the end.
        stderr_str = "\n".join(self.full_stderr)

        if self.process.returncode == 0:
            self.finished.emit(self.process.returncode, stderr_str) # Pass empty string for stdout
        else:
            error_message = f"Process failed with exit code {self.process.returncode}:\n{stderr_str.strip()}"
            self.error.emit(error_message)

    def _emit_error(self, message):
        tb_str = traceback.format_exc()
        error_msg = f"An unexpected fatal error occurred in the worker thread: {message}\n\nTraceback:\n{tb_str}"
        self.error.emit(error_msg)

class ProcessMonitorWorker(QObject):
    """A worker that waits for a Windows process handle to close."""
    finished = Signal(str)
    error = Signal(str)
    
    def __init__(self, process_handle):
        super().__init__()
        self.process_handle = process_handle

    def run(self):
        try:
            wait_result = ctypes.windll.kernel32.WaitForSingleObject(self.process_handle, 0xFFFFFFFF)
            if wait_result == 0:
                self.finished.emit("")
            else:
                self.error.emit(f"WaitForSingleObject failed with code: {wait_result}")
        except Exception as e:
            self.error.emit(f"An unexpected error occurred in the monitor thread: {e}")
        finally:
            ctypes.windll.kernel32.CloseHandle(self.process_handle)

class UpdateCheckWorker(QObject):
    finished = Signal(dict); error = Signal(str)
    
    def __init__(self, url): super().__init__(); self.url = url
    def run(self):
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(5)  # Set a shorter, more responsive global timeout.
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'KodiTextureTool-Update-Checker'})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    self.finished.emit(json.loads(response.read().decode('utf-8')))
                else:
                    self.error.emit(f"Server returned status {response.status}")
        except Exception as e:
            self.error.emit(f"Failed to check for updates: {e}")
        finally:
            # IMPORTANT: Always restore the original timeout to not affect other network operations.
            socket.setdefaulttimeout(original_timeout)
class DownloadWorker(QObject):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)
    
    def __init__(self, url, dest_folder):
        super().__init__()
        self.url = url
        self.dest_folder = dest_folder

    def run(self):
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".zip", dir=self.dest_folder)
            os.close(fd)

            req = urllib.request.Request(self.url, headers={'User-Agent': 'KodiTextureTool-Update-Downloader'})
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.getheader('Content-Length', 0))
                bytes_read = 0
                with open(temp_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_read += len(chunk)
                        if total_size > 0:
                            percent = int((bytes_read / total_size) * 100)
                            self.progress.emit(percent)
            self.finished.emit(temp_path)
        except Exception as e:
            self.error.emit(f"Download failed: {e}")

class UpdateProgressDialog(QDialog):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        #self.setWindowTitle("Downloading Update")
        self.setWindowTitle(f"{APP_TITLE} - {APP_VERSION} - Downloading Update")
        self.setWindowIcon(parent.app_icon if parent else QIcon())
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Connecting to server...")
        self.progress_bar = QProgressBar()
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.status_label.setText(f"Downloading... {value}%")

    def set_finished(self):
        self.status_label.setText("Download complete. Preparing to install...")
        self.progress_bar.setValue(100)
class FileLogger:
    """A simple logger to write messages to a file, keeping the handle open for efficiency."""
    
    def __init__(self, log_path="TextureTool_Log.txt"):
        self.log_path = os.path.abspath(log_path)
        self.log_file = None
        self.reset() # Open the file in write mode initially, clearing it.
        atexit.register(self.close)

    def write(self, message):
        if not self.log_file or self.log_file.closed:
            # Attempt to reopen in append mode if it was closed unexpectedly.
            try:
                self.log_file = open(self.log_path, "a", encoding="utf-8")
            except Exception as e:
                print(f"Failed to reopen log file for appending: {e}")
                return # Can't write if file can't be opened.

        try:
            self.log_file.write(message + "\n")
            self.log_file.flush() # Ensure data is written to disk.
        except Exception as e:
            print(f"Failed to write to log file: {e}")

    def close(self):
        if self.log_file and not self.log_file.closed:
            try:
                self.log_file.close()
            except Exception as e:
                print(f"Error closing log file: {e}")
        self.log_file = None

    def reset(self):
        """Clears the log by closing the current handle and reopening the file in write mode."""
        self.close()
        try:
            self.log_file = open(self.log_path, "w", encoding="utf-8")
        except Exception as e:
            print(f"Failed to open log file for writing: {e}")

class CustomHelpDialog(QDialog):
    def __init__(self, parent=None):

        super().__init__(parent)
        self.setWindowTitle(f"{APP_TITLE} - {APP_VERSION} - Help & Support")
        self.setWindowIcon(parent.app_icon if parent else QIcon())
        self.setFixedSize(400, 200)

        main_layout = QVBoxLayout(self)
        content_layout = QHBoxLayout()

        icon_label = QLabel()
        icon_pixmap = QPixmap(get_resource_path("assets/kodi_logo_96.png")).scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setFixedSize(96, 96)

        text_label = QLabel(
            "Support (Moral & Otherwise) for Kodi TextureTool is provided through the Kodi community forums.<br><br>"
            "Opening a log file from the application directory. Please copy/paste and include this log when submitting an issue.<br><br>"
            "Click <b>OK</b> to open the official Kodi forum thread and the log file."
        )
        text_label.setWordWrap(True)

        content_layout.addWidget(icon_label, 0)
        content_layout.addWidget(text_label, 1)

        button_box = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.setMinimumSize(100, 30)
        ok_button.clicked.connect(self.accept)
        button_box.addStretch()
        button_box.addWidget(ok_button)
        button_box.addStretch()

        main_layout.addLayout(content_layout)
        main_layout.addStretch()
        main_layout.addLayout(button_box)
class CustomAboutDialog(QDialog):
    def __init__(self, parent=None):
        """Initializes the About dialog with a layout matching Translation Tracker."""
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_TITLE} - {APP_VERSION}")
        self.setWindowIcon(parent.app_icon if parent else QIcon())

        # --- Epoch Suffix Calculation ---
        epoch_start = datetime(2021, 7, 13) + timedelta(days=1)
        delta = datetime.now() - epoch_start
        epoch_day = max(1, delta.days)
        display_version = f"{APP_VERSION}.{epoch_day}"
        # --- End Calculation ---

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout, 1)

        # Left side: Splash Image
        logo_path = get_resource_path("assets/splash.png")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            logo_pixmap = QPixmap(logo_path)
            if not logo_pixmap.isNull():
                logo_label.setPixmap(logo_pixmap)
                logo_label.setScaledContents(True)
                logo_label.setFixedSize(256, 256)
                content_layout.addWidget(logo_label)
                content_layout.addSpacing(20)
                self.setFixedSize(700, 350)
            else:
                self.setFixedSize(450, 300)
        else:
            self.setFixedSize(450, 300)

        # Right side: Details
        details_layout = QVBoxLayout()
        content_layout.addLayout(details_layout, 1)

        title_label = QLabel(APP_TITLE)
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)

        description_label = QLabel("The ultimate tool for compiling and decompiling Kodi texture files (.xbt).")
        description_label.setWordWrap(True)
        description_label.setStyleSheet("font-style: italic; margin-bottom: 15px;")
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        version_label = QLabel(f"<b>Version:</b> {display_version}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        build_label = QLabel(f"<b>Build Date:</b> {BUILD_DATE}")
        build_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        author_label = QLabel(f"<b>Designed by:</b> {APP_AUTHOR}")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        details_layout.addWidget(title_label)
        details_layout.addWidget(description_label)
        details_layout.addStretch(1)
        details_layout.addWidget(version_label)
        details_layout.addWidget(build_label)
        details_layout.addWidget(author_label)
        details_layout.addStretch(2)

        current_year = datetime.now().year
        copyright_label = QLabel(f"Copyright © {current_year} {APP_AUTHOR}. All rights reserved.")
        copyright_label.setStyleSheet("font-size: 8pt;")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details_layout.addWidget(copyright_label)

        # Bottom Button
        button_box = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.setMinimumSize(100, 30)
        ok_button.clicked.connect(self.accept)
        button_box.addStretch()
        button_box.addWidget(ok_button)
        button_box.addStretch()
        main_layout.addLayout(button_box)

class DropGroupBox(QGroupBox):
    """A QGroupBox that accepts file drops and emits a signal with the file path."""
    fileDropped = Signal(str)

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setAcceptDrops(True)
    def dragEnterEvent(self, event):
        '''Accept the event and apply highlight if it contains file URLs.'''
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragging", True)
            self.style().polish(self)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Accept the move event if it contains file URLs."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    def dropEvent(self, event):
        '''Handle the drop, emit the path, and remove the highlight.'''
        self.setProperty("dragging", False)
        self.style().polish(self)
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                self.fileDropped.emit(path)
            event.acceptProposedAction()
        else:
            event.ignore()
    def dragLeaveEvent(self, event):
        '''Remove the highlight when the drag operation leaves the widget.'''
        self.setProperty("dragging", False)
        self.style().polish(self)
        event.accept()
class TextureToolApp(QMainWindow):

    def _get_short_path_name(self, long_path: str) -> str:
        """
        Passes through the long path without conversion. 8.3 short path names
        are deprecated and do not support full Unicode character sets, which can
        cause issues with international file paths. The underlying TexturePacker
        executables have been updated to support modern long file paths.
        """
        return long_path
    # Maximum number of recent items to track
    MAX_RECENT = 8
    update_check_complete = Signal(dict, bool)

    def _init_recent(self):
        self.recent_compile_files = []
        self.recent_compile_folders = []
        self.recent_decompile_files = []
        self.recent_decompile_folders = []
        # These will be set in _create_menu_bar, but ensure they exist for error-free access
        self.recent_compile_files_menu = None
        self.recent_compile_folders_menu = None
        self.recent_decompile_files_menu = None
        self.recent_decompile_folders_menu = None
        self.clear_compile_files_action = None
        self.clear_compile_folders_action = None
        self.clear_decompile_files_action = None
        self.clear_decompile_folders_action = None
        self._load_recent()
    
    def _load_recent(self):
        self.config.read(self.config_path, encoding='utf-8')
        if not self.config.has_section('Recent'):
            return
        for group in RecentGroup:
            try:
                # Dynamically get the list from config and set the instance attribute
                recent_items = json.loads(self.config.get('Recent', group.value, fallback='[]'))
                setattr(self, f'recent_{group.value}', recent_items)
            except Exception:
                 # On failure, set an empty list for that specific group
                setattr(self, f'recent_{group.value}', [])
    
    def _save_recent(self):
        self.config.read(self.config_path, encoding='utf-8')
        if not self.config.has_section('Recent'):
            self.config.add_section('Recent')
        for group in RecentGroup:
            # Dynamically get the instance attribute and save it to config
            recent_list = getattr(self, f'recent_{group.value}')
            self.config.set('Recent', group.value, json.dumps(recent_list))
        with open(self.config_path, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)

    def _add_recent(self, group: RecentGroup, path):
        # Get the string value from the enum member for dynamic attribute access
        group_name = group.value
        recent_list = getattr(self, f'recent_{group_name}')
        if path in recent_list:
            recent_list.remove(path)
        recent_list.insert(0, path)
        if len(recent_list) > self.MAX_RECENT:
            recent_list.pop()
        setattr(self, f'recent_{group_name}', recent_list)
        self._save_recent()
        self._update_recent_menus()

    def _clear_recent(self, group: RecentGroup):
        # Get the string value from the enum member for dynamic attribute access
        group_name = group.value
        setattr(self, f'recent_{group_name}', [])
        self._save_recent()
        self._update_recent_menus()

    def _update_recent_menus(self):
        # Update all recent submenus
        def update_menu(menu, items, handler, clear_action):
            menu.clear()
            if items:
                for path in items:
                    act = QAction(path, self)
                    # Use functools.partial to avoid late binding bug
                    act.triggered.connect(functools.partial(handler, path))
                    menu.addAction(act)
                menu.addSeparator()
            menu.addAction(clear_action)

        update_menu(self.recent_compile_files_menu, self.recent_compile_files, self._open_recent_compile_file, self.clear_compile_files_action)
        update_menu(self.recent_compile_folders_menu, self.recent_compile_folders, self._open_recent_compile_folder, self.clear_compile_folders_action)
        update_menu(self.recent_decompile_files_menu, self.recent_decompile_files, self._open_recent_decompile_file, self.clear_decompile_files_action)
        update_menu(self.recent_decompile_folders_menu, self.recent_decompile_folders, self._open_recent_decompile_folder, self.clear_decompile_folders_action)
        
        if hasattr(self, 'browse_decompile_input_btn'):
            self.browse_decompile_input_btn.setEnabled(bool(self.recent_decompile_files))
        if hasattr(self, 'browse_compile_input_btn'):
            self.browse_compile_input_btn.setEnabled(bool(self.recent_compile_folders))
        
        if hasattr(self, 'reload_all_action'):
            can_reload = any([
                self.recent_compile_files,
                self.recent_compile_folders,
                self.recent_decompile_files,
                self.recent_decompile_folders
            ])
            self.reload_all_action.setEnabled(can_reload)
            
            if hasattr(self, 'reload_all_btn'):
                self.reload_all_btn.setEnabled(can_reload)
    def _open_recent_compile_file(self, path):
        if os.path.exists(path):
            self.compile_output_file = path
            _display_path_1 = os.path.basename(path)
            self.compile_output_label.setText("..\\{}".format(os.path.basename(_display_path_1)))
            self.compile_output_label.setToolTip(_display_path_1)
            self.compile_output_label.setToolTip(path)
            self.compile_output_label.setProperty("state", "selected")
            self.compile_output_label.style().unpolish(self.compile_output_label)
            self.compile_output_label.style().polish(self.compile_output_label)
            self._set_config_path('compileoutput', os.path.dirname(path))
            self._log_message('[DATA] Path to output file: "{}"'.format(os.path.normpath(self.compile_output_file)))
            self._log_message("[INFO] Output folder destination loaded successfully.")
            self._add_recent(RecentGroup.COMPILE_FILES, path)
            self._update_button_states()
            self._update_status_label()
        else:
            self._log_message("[WARN] Recent compile file not found, removing from list: {}".format(path))
            self.recent_compile_files.remove(path)
            self._save_recent()
            self._update_recent_menus()
            QMessageBox.warning(self, "Recent File Not Found", "The recent compile file could not be found and has been removed from the list:\n\n{}".format(path))
    def _open_recent_compile_folder(self, path):
        if os.path.exists(path):
            self.compile_input_folder = path
            _display_path_2 = os.path.basename(path)
            self.compile_input_label.setText("..\\{}".format(os.path.basename(_display_path_2)))
            self.compile_input_label.setToolTip(_display_path_2)
            self.compile_input_label.setToolTip(path)
            self.compile_input_label.setProperty("state", "selected")
            self.compile_input_label.style().unpolish(self.compile_input_label)
            self.compile_input_label.style().polish(self.compile_input_label)
            self._set_config_path('compileinput', path)
            self._log_message('[DATA] Path to directory: "{}"'.format(os.path.normpath(self.compile_input_folder)))
            self._log_message("[INFO] Image folder input selection loaded successfully.")
            self._add_recent(RecentGroup.COMPILE_FOLDERS, path)
            self._update_button_states()
            self._update_status_label()
        else:
            self._log_message("[WARN] Recent compile folder not found, removing from list: {}".format(path))
            self.recent_compile_folders.remove(path)
            self._save_recent()
            self._update_recent_menus()
            QMessageBox.warning(self, "Recent Folder Not Found", "The recent compile folder could not be found and has been removed from the list:\n\n{}".format(path))
    def _open_recent_decompile_file(self, path):
        if os.path.exists(path):
            self._clear_gallery()
            self.decompile_input_file = path
            _display_path_3 = os.path.basename(path)
            self.decompile_input_label.setText("..\\{}".format(os.path.basename(_display_path_3)))
            self.decompile_input_label.setToolTip(_display_path_3)
            self.decompile_input_label.setToolTip(path)
            self.decompile_input_label.setProperty("state", "selected")
            self.decompile_input_label.style().unpolish(self.decompile_input_label)
            self.decompile_input_label.style().polish(self.decompile_input_label)
            self._set_config_path('decompileinput', os.path.dirname(path))
            self._log_message('[DATA] Decompile input file: "{}"'.format(os.path.normpath(self.decompile_input_file)))
            self._log_message("[INFO] Input selection loaded successfully.")
            self._add_recent(RecentGroup.DECOMPILE_FILES, path)
            self._update_button_states()
            self._update_status_label()
        else:
            self._log_message("[WARN] Recent decompile file not found, removing from list: {}".format(path))
            self.recent_decompile_files.remove(path)
            self._save_recent()
            self._update_recent_menus()
            QMessageBox.warning(self, "Recent File Not Found", "The recent decompile file could not be found and has been removed from the list:\n\n{}".format(path))
    def _open_recent_decompile_folder(self, path):
        if os.path.exists(path):
            self.decompile_output_folder = path
            _display_path_4 = os.path.basename(path)
            self.decompile_output_label.setText("..\\{}".format(os.path.basename(_display_path_4)))
            self.decompile_output_label.setToolTip(_display_path_4)
            self.decompile_output_label.setToolTip(path)
            self.decompile_output_label.setProperty("state", "selected")
            self.decompile_output_label.style().unpolish(self.decompile_output_label)
            self.decompile_output_label.style().polish(self.decompile_output_label)
            self._set_config_path('decompileoutput', path)
            self._log_message('[DATA] Decompile output directory: "{}"'.format(os.path.normpath(self.decompile_output_folder)))
            self._log_message("[INFO] Output folder destination loaded successfully.")
            self._add_recent(RecentGroup.DECOMPILE_FOLDERS, path)
            self._update_button_states()
            self._update_status_label()
        else:
            self._log_message("[WARN] Recent decompile folder not found, removing from list: {}".format(path))
            self.recent_decompile_folders.remove(path)
            self._save_recent()
            self._update_recent_menus()
            QMessageBox.warning(self, "Recent Folder Not Found", "The recent decompile folder could not be found and has been removed from the list:\n\n{}".format(path))
    
    def _open_last_decompile_input(self):
        """Opens the most recent decompile input file."""
        if self.recent_decompile_files:
            self._open_recent_decompile_file(self.recent_decompile_files[0])
    
    def _open_last_compile_input(self):
        """Opens the most recent compile input folder."""
        if self.recent_compile_folders:
            self._open_recent_compile_folder(self.recent_compile_folders[0])
    """
    The main class for the Kodi TextureTool application.
    It encapsulates the UI, state, and business logic.
    """
    # Define consistent color palette as class attributes (Nord theme inspired)
    COLOR_CYAN = "#81A1C1"
     # For timestamps and '[INFO]'
    COLOR_GREEN = "#A3BE8C"
     # For '-----' success headers
    COLOR_RED = "#BF616A"
     # For '[ERROR]'
    COLOR_YELLOW = "#EBCB8B"
     # For '[WARN]'
    COLOR_MAGENTA = "#B48EAD"
     # For '[DATA]'
    COLOR_ORANGE = "#D08770"
     # For '[LOAD]'
    COLOR_DEFAULT = "#D8DEE9"
     # For 'Notifications Checking'
    COLOR_SOFT_GOLD = "#D4AF37"
     # Default text color
    COLOR_NUMERIC = "#88C0D0"
    def __init__(self):
        self.main_splitter = None
        self.last_displayed_index = -1 # Track for zoom reset logic.
        self.is_image_zoomed = False   # Track for zoom reset logic.
        self.current_zoom_level = 1.0  # Track zoom factor for overlay display
        super().__init__() # CRITICAL FIX: Call the parent constructor FIRST.



        self.log_lock = threading.RLock()

        self.open_decompile_on_complete = True
        self.open_compile_on_complete = True
        self.open_pdf_on_complete = True
        self.log_on_top = True
        self.decompile_on_top = False

        self.check_for_updates_on_startup = True
        self.config = configparser.ConfigParser()
        config_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        self.config_path = os.path.join(config_dir, 'config.ini')
        if not os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    f.write('[Recent]\n')
            except Exception as e:
                print(f"WARNING: Could not create initial config file at {self.config_path}: {e}")

        self.workspace_dir = None
        self.app_dir = get_resource_path('.')
        temp_dir_to_clean = os.path.join(self.app_dir, "_temp")
        cleanup_was_performed = False
        if os.path.exists(temp_dir_to_clean):
            try:
                shutil.rmtree(temp_dir_to_clean)
                cleanup_was_performed = True
            except OSError as e:
                print(f"Error removing temp directory on startup: {e}")

        # --- CAROUSEL & EXPORT STATE ---
        self.info_cache_dir = None
        self.preview_images = [] # This now stores comprehensive dictionaries
        self.current_preview_index = -1
        # --- SEARCH STATE ---
        self.last_search_query = ("", "") # (query, criterion)
        self.search_results = []
        self.current_search_index = -1
        # --- END SEARCH STATE ---
        self.decompile_for_info_thread = None
        self.decompile_for_info_worker = None
        self.pdf_export_thread = None
        self.pdf_export_worker = None

        # --- PDF Export Menu State ---
        self.export_pdf_menu = None
        self.export_all_action = None
        self.export_filtered_action = None
        self.export_selected_action = None

        # --- LOGGING REFACTOR: Buffer raw messages, not pre-formatted HTML ---
        self.log_message_buffer = deque() # Use deque for efficient pop
        self.log_batch_timer = QTimer(self)
        self.log_batch_timer.setInterval(10) # Process chunks quickly
        self.log_batch_timer.timeout.connect(self._process_log_message_buffer)
        # --- END STATE ---

        self.REQUIRED_FILES = ["utils/TexturePacker_Compile/gif.dll", "utils/TexturePacker_Compile/jpeg62.dll", "utils/TexturePacker_Compile/libpng16.dll", "utils/TexturePacker_Compile/lzo2.dll", "utils/TexturePacker_Compile/TextureCompiler.exe", "utils/TexturePacker_Compile/zlib1.dll", "utils/TexturePacker_Decompile/getopt.dll", "utils/TexturePacker_Decompile/gif.dll", "utils/TexturePacker_Decompile/jpeg62.dll", "utils/TexturePacker_Decompile/libpng16.dll", "utils/TexturePacker_Decompile/lzo2.dll", "utils/TexturePacker_Decompile/squish.dll", "utils/TexturePacker_Decompile/TextureExtractor.exe", "utils/TexturePacker_Decompile/zlib1.dll"]
        self._init_recent()

        self.file_logger = FileLogger(log_path=os.path.join(config_dir, 'TextureTool_Log.txt'))
        self.app_icon = QIcon(get_resource_path("assets/fav.ico"))
        self.tray_icon = QSystemTrayIcon(QIcon(get_resource_path("assets/fav.ico")), None)
        self.tray_icon.setToolTip(APP_TITLE)
        self.tray_icon.show()
        self.decompile_thread, self.decompile_worker = None, None
        self.compile_thread, self.compile_worker = None, None
        self.installer_thread, self.installer_worker = None, None
        self.info_thread, self.info_worker = None, None

        self.decompile_input_file, self.decompile_output_folder, self.compile_input_folder, self.compile_output_file = "", "", "", ""
        self.aDiagnosticMessages = []
        self.update_action = None
        self.install_runtimes_action = None
        self.reinstall_runtimes_action = None
        self.vcredist_checks_passed = False # Pre-initialize attribute to prevent crash
        self.update_thread, self.update_worker = None, None
        self.update_check_complete.connect(self._handle_update_ui)
        self._load_settings()
        self._setup_ui()
        if cleanup_was_performed:
            self._log_message(f"[INFO] Removed leftover temporary directory: {os.path.normpath(temp_dir_to_clean)}")
        self._setup_temp_workspace()
        atexit.register(self._cleanup_workspace)
        self._perform_startup_checks()
        self._populate_initial_log()
    def _update_button_states(self):
        # --- Decompile Mode ---
        decompile_input_selected = bool(self.decompile_input_file)
        decompile_output_selected = bool(self.decompile_output_folder)
        decompile_ready = decompile_input_selected and decompile_output_selected and self.vcredist_checks_passed

        self.decompile_output_btn.setEnabled(decompile_input_selected)
        self.decompile_info_btn.setEnabled(decompile_input_selected)
        self.browse_decompile_output_btn.setEnabled(decompile_output_selected)
        self.decompile_start_btn.setEnabled(decompile_ready)
        self.decompile_clear_btn.setEnabled(decompile_input_selected or decompile_output_selected)

        # --- Compile Mode ---
        compile_input_selected = bool(self.compile_input_folder)
        compile_output_selected = bool(self.compile_output_file)
        compile_ready = compile_input_selected and compile_output_selected and self.vcredist_checks_passed

        self.compile_output_btn.setEnabled(compile_input_selected)
        self.browse_compile_output_btn.setEnabled(compile_output_selected)
        self.compile_start_btn.setEnabled(compile_ready)
        self.compile_clear_btn.setEnabled(compile_input_selected or compile_output_selected)
    
    def _get_config_path(self, key):
        """Reads a path from the config.ini file."""
        self.config.read(self.config_path, encoding='utf-8')
        return self.config.get('Paths', key, fallback=self.app_dir)
    
    def _set_config_path(self, key, path):
        """Writes a path to the config.ini file."""
        self.config.read(self.config_path, encoding='utf-8')
        if not self.config.has_section('Paths'):
            self.config.add_section('Paths')
        self.config.set('Paths', key, path)
        with open(self.config_path, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)
    def _setup_temp_workspace(self):

        try:
            self.workspace_dir = os.path.join(self.app_dir, "_temp")
            # Clean up old directory if it exists, then create a fresh one
            if os.path.exists(self.workspace_dir):
                shutil.rmtree(self.workspace_dir)
            os.makedirs(self.workspace_dir, exist_ok=True)
            self._log_message(f"[INFO] Created local workspace: {os.path.normpath(self.workspace_dir)}")

            for filename in self.REQUIRED_FILES:
                source_path = os.path.join(self.app_dir, filename)
                dest_path_in_workspace = os.path.join(self.workspace_dir, filename)
                if os.path.exists(source_path):
                    os.makedirs(os.path.dirname(dest_path_in_workspace), exist_ok=True)
                    shutil.copy2(source_path, dest_path_in_workspace)
                else:
                    self._log_message(f"[WARN] Required file not found, skipping: {filename}")
        except Exception as e:
            self._log_message(f"[ERROR] Could not create temp workspace: {e}")
            self.workspace_dir = None
    
    def _check_vcredist_installed(self):
        """
    Checks if the required Visual C++ 2010 x86 Redistributable is installed
    by searching the Windows Uninstall registry keys.
    """
        if sys.platform != "win32":
            return True  # Not a Windows check, assume it's not needed.

        # Note the two spaces between "2010" and "x86" as seen in user screenshots.
        target_display_name = "Microsoft Visual C++ 2010  x86 Redistributable - 10.0.40219"

        uninstall_keys = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
        ]

        for key_path in uninstall_keys:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                # Use a default value to avoid crashing on missing DisplayName
                                display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                if display_name == target_display_name:
                                    return True
                        except (FileNotFoundError, OSError):
                            # This can happen if a subkey doesn't have a DisplayName, which is common.
                            continue
            except FileNotFoundError:
                # This happens if the entire Uninstall path doesn't exist (unlikely).
                continue
            except Exception as e:
                # Log any other unexpected errors during the check.
                self._add_diagnostic_message(f"[WARN] Error checking registry key {key_path}: {e}")
                continue

        return False
    def _cleanup_workspace(self):
        '''Removes the temporary workspace directory upon application exit.'''
        # Clean up main temp workspace
        if self.workspace_dir and os.path.exists(self.workspace_dir):
            try:
                shutil.rmtree(self.workspace_dir)
            except Exception:
                pass # Fail silently on exit

        # Clean up info cache directory
        if self.info_cache_dir and os.path.exists(self.info_cache_dir):
            try:
                shutil.rmtree(self.info_cache_dir)
            except Exception:
                pass # Fail silently on exit
    def _update_status_label(self):
        decompile_input_selected = bool(self.decompile_input_file)
        decompile_output_selected = bool(self.decompile_output_folder)
        decompile_ready = decompile_input_selected and decompile_output_selected and self.vcredist_checks_passed

        compile_input_selected = bool(self.compile_input_folder)
        compile_output_selected = bool(self.compile_output_file)
        compile_ready = compile_input_selected and compile_output_selected and self.vcredist_checks_passed

        # The new logic prioritizes the "ready" states with more specific messages.
        if decompile_ready:
            self.status_label.setText("Ready to Decompile. Press Start to begin.")
        elif compile_ready:
            self.status_label.setText("Ready to Compile. Press Start to begin.")
        elif decompile_input_selected and not decompile_output_selected:
            self.status_label.setText("Step 2 enabled >> Select save location folder")
        elif compile_input_selected and not compile_output_selected:
            self.status_label.setText("Step 2 enabled >> Select save location file")
        else:
            self.status_label.setText("Select an operation mode to begin.")
    
    def _finalize_ui_reset(self):
        '''Resets the progress bar and status label after a delay.'''
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._update_status_label()
    def _perform_startup_checks(self):
        self._add_diagnostic_message('[INFO] ----- Program Start -----')
        self._add_diagnostic_message(f'[INFO] Current Time: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}')
        self._add_diagnostic_message(f'[INFO] Running Version: {APP_VERSION}')
        self._add_diagnostic_message("[INFO] Checking for required Visual C++ 2010 x86 Redistributable...")
        self.vcredist_checks_passed = self._check_vcredist_installed()
        if self.vcredist_checks_passed:
            self._add_diagnostic_message("[INFO] Required Visual C++ Redistributable check: [Passed]")
        else:
            self._add_diagnostic_message("[ERROR] Required Visual C++ Redistributable check...Failed")
            self._add_diagnostic_message("[DATA] Target: Microsoft Visual C++ 2010  x86 Redistributable - 10.0.40219")
            self._add_diagnostic_message("[WARN] Decompile & Compile functions are disabled until runtimes are properly installed.")
            self._add_diagnostic_message("[WARN] Use the 'Display -> Install Runtimes' menu option to resolve this issue.")
            self._show_vcredist_notification()

        # --- THE FIX: Update the menu item's state NOW ---
        self._update_runtime_menu_actions_state()

        self._add_diagnostic_message("[INFO] Set DEV hot key sequence... Complete")
        self._add_diagnostic_message('[INFO] To enable DEV Mode press and hold the keyboard sequence: "Shift" > "Alt" > "D"')
        self._add_diagnostic_message("[INFO] Getting file metadata & information.")
        files_to_check = {
            os.path.join("utils", "TexturePacker_Compile", "TextureCompiler.exe"): "",
            os.path.join("utils", "TexturePacker_Decompile", "TextureExtractor.exe"): "",
            os.path.join("assets", "kodi_logo_512.png"): "",
            os.path.join("assets", "fav.ico"): ""
        }
        self._add_diagnostic_message("[INFO] System DLL integrity check (Compile).")
        compile_dlls = ["gif.dll", "jpeg62.dll", "libpng16.dll", "lzo2.dll", "zlib1.dll"]
        all_compile_dlls_found = True
        for dll in compile_dlls:
            dll_path = os.path.normpath(get_resource_path(f"utils/TexturePacker_Compile/{dll}"))
            status = "Installed" if os.path.exists(dll_path) else "Not Installed"
            if status == "Not Installed":
                all_compile_dlls_found = False
            self._add_diagnostic_message(f"[DATA] {dll_path}: {status}")
        if all_compile_dlls_found:
            self._add_diagnostic_message("[INFO] System DLL integrity check (Compile): [Passed]")
        else:
            self._add_diagnostic_message("[INFO] System DLL integrity check (Compile): [Failed]")

        self._add_diagnostic_message("[INFO] System DLL integrity check (Decompile).")
        decompile_dlls = ["getopt.dll", "gif.dll", "jpeg62.dll", "libpng16.dll", "lzo2.dll", "squish.dll", "zlib1.dll"]
        all_decompile_dlls_found = True
        for dll in decompile_dlls:
            dll_path = os.path.normpath(get_resource_path(f"utils/TexturePacker_Decompile/{dll}"))
            status = "Installed" if os.path.exists(dll_path) else "Not Installed"
            if status == "Not Installed":
                all_decompile_dlls_found = False
            self._add_diagnostic_message(f"[DATA] {dll_path}: {status}")
        if all_decompile_dlls_found:
            self._add_diagnostic_message("[INFO] System DLL integrity check (Decompile): [Passed]")
        else:
            self._add_diagnostic_message("[INFO] System DLL integrity check (Decompile): [Failed]")
        for file_name, version in files_to_check.items():
            file_path = os.path.normpath(get_resource_path(file_name))
            if os.path.exists(file_path):
                modified_date = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%d-%m-%Y')
                file_size = f"{os.path.getsize(file_path) / 1024:.0f}KB"
                self._add_diagnostic_message(f"[DATA] {os.path.basename(file_name)} version: {version if version else '[No Data]'}")
                self._add_diagnostic_message(f"[DATA] {os.path.basename(file_name)} modified date: {modified_date}")
                self._add_diagnostic_message(f"[DATA] {os.path.basename(file_name)} status: Stable")
                self._add_diagnostic_message(f"[DATA] {os.path.basename(file_name)} file size: {file_size}")
            else:
                self._add_diagnostic_message(f"[ERROR] {file_path} not found.")
        self._add_diagnostic_message(f'[INFO] Getting file versions. [Complete]')
        if self.vcredist_checks_passed:
            if self.check_for_updates_on_startup:
                self._add_diagnostic_message("[INFO] Runtimes found. Scheduling automatic update check.")
                QTimer.singleShot(3000, self._check_for_updates)
            else:
                self._add_diagnostic_message("[INFO] Automatic update check disabled by user setting.")
        else:
            self._add_diagnostic_message("[WARN] Runtimes not found. Automatic update check deferred until runtimes are installed.")
    def _setup_ui(self):



        self.setWindowTitle(f"{APP_TITLE} - {APP_VERSION}")
        self.setWindowIcon(QIcon(get_resource_path("assets/fav.ico")))
        self.setMinimumSize(1410, 920)
        try:
            screen_geometry = QApplication.primaryScreen().geometry()
            window_geometry = self.frameGeometry()
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)
            top_left_point = window_geometry.topLeft()
            self.move(top_left_point.x(), top_left_point.y() - 20)
        except Exception as e:
            print(f"Could not center window: {e}")

        # --- DEV MODE HOTKEY ---
        self.dev_mode_shortcut = QShortcut(QKeySequence("Shift+Alt+D"), self)
        self.dev_mode_shortcut.activated.connect(self._enable_dev_mode)
        # --- END DEV MODE ---

        self._create_menu_bar()

        # --- UPGRADE: Use QSplitter for a saveable layout ---
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.main_splitter)

        left_panel_widget = self._create_left_panel()
        right_panel_widget = self._create_right_panel() # This is the right-side splitter

        self.main_splitter.addWidget(left_panel_widget)
        self.main_splitter.addWidget(right_panel_widget)

        # Set initial size ratio, user can override and it will be saved.
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 2)
        # --- END UPGRADE ---

        self._update_recent_menus()
        self.settings = QSettings("KodiTextureTool", "TextureTool")

        # --- RESTORE GEOMETRY AND LAYOUT ---
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        main_splitter_state = self.settings.value("mainSplitter")
        if main_splitter_state and self.main_splitter:
            self.main_splitter.restoreState(main_splitter_state)

        right_splitter_state = self.settings.value("rightPanelSplitter")
        if right_splitter_state:
            # self.right_panel_splitter is created in _create_right_panel
            if hasattr(self, 'right_panel_splitter') and self.right_panel_splitter:
                 self.right_panel_splitter.restoreState(right_splitter_state)
        shortcut_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        shortcut_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        shortcut_up = QShortcut(QKeySequence(Qt.Key.Key_Up), self)
        shortcut_down = QShortcut(QKeySequence(Qt.Key.Key_Down), self)
        
        shortcut_left.activated.connect(self._nav_prev)
        shortcut_right.activated.connect(self._nav_next)
        shortcut_up.activated.connect(self._zoom_in)
        shortcut_down.activated.connect(self._zoom_out)
    def closeEvent(self, event):
        # STABILITY FIX: Ensure any running subprocess is terminated before exiting.
        # This prevents orphaned processes and potential file-locking issues.
        for thread_attr, worker_attr in [
            ('compile_thread', 'compile_worker'), ('decompile_thread', 'decompile_worker'),
            ('info_thread', 'info_worker'), ('installer_thread', 'installer_worker'),
            ('decompile_for_info_thread', 'decompile_for_info_worker')
        ]:
            worker = getattr(self, worker_attr, None)
            if worker and hasattr(worker, 'process') and worker.process:
                if worker.process.poll() is None: # Check if process is still running
                    try:
                        self._log_message(f"[WARN] Terminating active '{thread_attr}' process before exit.")
                        worker.process.kill()
                    except Exception as e:
                        self._log_message(f"[ERROR] Could not terminate process on exit: {e}")

        # --- UPGRADE: SAVE GEOMETRY AND LAYOUT ---
        self.settings.setValue("geometry", self.saveGeometry())
        if hasattr(self, 'main_splitter') and self.main_splitter:
            self.settings.setValue("mainSplitter", self.main_splitter.saveState())
        if hasattr(self, 'right_panel_splitter') and self.right_panel_splitter:
            self.settings.setValue("rightPanelSplitter", self.right_panel_splitter.saveState())

        super().closeEvent(event)

    def _reset_window_geometry(self):
        """Resets the window to the center of the screen and clears the saved geometry."""
        self.settings.remove("geometry")
        screen_geometry = QApplication.primaryScreen().geometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        top_left_point = window_geometry.topLeft()
        self.move(top_left_point.x(), top_left_point.y() - 20)
        self._log_message("[INFO] Window position has been reset to the default.")
    def _create_left_panel(self):
        self.decompile_input_btn = QPushButton(qta.icon('fa5s.file-alt'), " Select input file")
        self.decompile_input_label = QLabel("[Not Selected]")
        self.decompile_input_btn.setToolTip("Select .xbt to decompile")
        self.decompile_output_btn = QPushButton(qta.icon('fa5s.folder-open'), " Select output")
        self.decompile_output_label = QLabel("[Not Selected]")
        self.decompile_output_btn.setToolTip("Select folder to extract texture images to")
        self.decompile_start_btn = QPushButton(qta.icon('fa5s.play'), " Start")
        self.decompile_start_btn.setToolTip("Start decompile extraction")
        self.decompile_info_btn = QPushButton(qta.icon('fa5s.info-circle'), " Get Info")
        self.decompile_info_btn.setToolTip("Get information from the selected .xbt file")
        self.decompile_info_btn.setEnabled(False)
        self.browse_decompile_input_btn = QPushButton(qta.icon('fa5s.history'), ' Open Last')
        self.browse_decompile_input_btn.setToolTip('Open the last used decompile input file')
        self.browse_decompile_output_btn = QPushButton(qta.icon('fa5s.folder-open'), " Open Folder")
        self.browse_decompile_output_btn.setToolTip("Open the selected output folder")
        self.compile_input_btn = QPushButton(qta.icon('fa5s.folder'), " Select input folder")
        self.compile_input_label = QLabel("[Not Selected]")
        self.compile_input_btn.setToolTip("Select folder with source images")
        self.compile_output_btn = QPushButton(qta.icon('fa5s.file-code'), " Select output file")
        self.compile_output_label = QLabel("[Not Selected]")
        self.compile_output_btn.setToolTip("Select folder to compile texture file")
        self.compile_start_btn = QPushButton(qta.icon('fa5s.play'), " Start")
        self.compile_start_btn.setToolTip("Start compile process")
        self.browse_compile_input_btn = QPushButton(qta.icon('fa5s.history'), ' Open Last')
        self.browse_compile_input_btn.setToolTip('Open the last used compile input folder')
        self.browse_compile_output_btn = QPushButton(qta.icon('fa5s.folder-open'), " Open Folder")
        self.browse_compile_output_btn.setToolTip("Open the selected output folder")
        self.decompile_output_btn.setEnabled(False)
        self.decompile_start_btn.setEnabled(False)
        self.browse_decompile_output_btn.setEnabled(False)
        self.compile_output_btn.setEnabled(False)
        self.compile_start_btn.setEnabled(False)
        self.browse_compile_output_btn.setEnabled(False)

        # Apply object names for styling
        for label in [self.decompile_input_label, self.decompile_output_label, self.compile_input_label, self.compile_output_label]:
            label.setProperty("state", "unselected")

        left_widget = QWidget()
        self.left_panel_layout = QVBoxLayout(left_widget)
        self.left_panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        logo_container_widget = QWidget()
        top_layout = QHBoxLayout(logo_container_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        kodi_logo = QLabel()
        pixmap = QPixmap(get_resource_path("assets/kodi_logo_512.png"))
        kodi_logo.setPixmap(pixmap.scaled(512, 320, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        kodi_logo.setFixedHeight(320)
        top_layout.addStretch()
        top_layout.addWidget(kodi_logo)
        top_layout.addStretch()
        self.decompile_box = DropGroupBox("Decompile Mode")
        decompile_layout = QFormLayout(self.decompile_box)
        self.decompile_box.fileDropped.connect(self._on_decompile_file_dropped)
        decompile_input_row = QHBoxLayout()
        decompile_input_row.addWidget(self.decompile_input_btn)
        self.browse_decompile_input_btn.clicked.connect(self._open_last_decompile_input)
        self.browse_decompile_input_btn.setEnabled(False)
        decompile_input_row.addWidget(self.browse_decompile_input_btn)
        decompile_output_row = QHBoxLayout()
        decompile_output_row.addWidget(self.decompile_output_btn)
        self.browse_decompile_output_btn.clicked.connect(self._open_decompile_output_folder)
        decompile_output_row.addWidget(self.browse_decompile_output_btn)
        decompile_layout.addRow("1. Select the input file:", decompile_input_row)
        decompile_layout.addRow("File:", self.decompile_input_label)
        decompile_layout.addRow("2. Select the output directory:", decompile_output_row)
        decompile_layout.addRow("Directory:", self.decompile_output_label)
        decompile_actions_row = QHBoxLayout()
        decompile_actions_row.addWidget(self.decompile_start_btn, 1)
        decompile_actions_row.addWidget(self.decompile_info_btn, 1)
        self.decompile_clear_btn = QPushButton(qta.icon('fa5s.times-circle'), " Clear")
        self.decompile_clear_btn.setToolTip("Clear decompile selections")
        self.decompile_clear_btn.setEnabled(False)
        decompile_actions_row.addWidget(self.decompile_clear_btn)
        decompile_layout.addRow("3. Press start to begin:", decompile_actions_row)
        self.compile_box = DropGroupBox("Compile Mode")
        self.compile_box.fileDropped.connect(self._on_compile_folder_dropped)
        compile_layout = QFormLayout(self.compile_box)
        compile_input_row = QHBoxLayout()
        compile_input_row.addWidget(self.compile_input_btn)
        self.browse_compile_input_btn.clicked.connect(self._open_last_compile_input)
        self.browse_compile_input_btn.setEnabled(False)
        compile_input_row.addWidget(self.browse_compile_input_btn)
        compile_output_row = QHBoxLayout()
        compile_output_row.addWidget(self.compile_output_btn)
        self.browse_compile_output_btn.clicked.connect(self._open_compile_output_folder)
        compile_output_row.addWidget(self.browse_compile_output_btn)
        compile_actions_row = QHBoxLayout()
        compile_actions_row.addWidget(self.compile_start_btn, 1)
        self.compile_clear_btn = QPushButton(qta.icon('fa5s.times-circle'), " Clear")
        self.compile_clear_btn.setToolTip("Clear compile selections")
        self.compile_clear_btn.setEnabled(False)
        compile_actions_row.addWidget(self.compile_clear_btn)
        compile_layout.addRow("1. Select the input directory:", compile_input_row)
        compile_layout.addRow("Directory:", self.compile_input_label)
        compile_layout.addRow("2. Select the output file:", compile_output_row)
        compile_layout.addRow("File:", self.compile_output_label)
        compile_layout.addRow("3. Press start to begin:", compile_actions_row)
        options_layout = QHBoxLayout()
        self.dupecheck_cb = QCheckBox("Enable dupecheck")
        self.dupecheck_cb.setToolTip("Prevents duplicate textures from being added during compilation.")
        self.dupecheck_cb.toggled.connect(self._on_dupecheck_toggled)
        self.dev_mode_cb = QCheckBox("Dev mode")
        self.dev_mode_cb.setToolTip("Enable developer mode features. Requires hotkey (Shift+Alt+D) to enable.")
        self.dev_mode_cb.setEnabled(False)
        self.dev_mode_cb.toggled.connect(self._on_dev_mode_toggled)
        self.help_support_btn = QPushButton("Help/Support")
        self.help_support_btn.setToolTip("Open the Kodi forum thread for help and support.")
        self.reload_all_btn = QPushButton(qta.icon('fa5s.sync-alt'), " Reload All")
        self.close_all_btn = QPushButton(qta.icon('fa5s.ban'), " Close All")
        self.close_all_btn.setToolTip("Close all active file/folder selections")
        self.close_all_btn.clicked.connect(self._close_all)
        self.reload_all_btn.setToolTip("Reload the last used paths for all modes")
        self.reload_all_btn.clicked.connect(self._reload_all)
        self.info_btn = QPushButton(qta.icon('fa5s.question-circle'), " About")
        self.info_btn.setToolTip("Show application version, build date, and author information.")
        self.clear_log_btn = QPushButton(qta.icon('fa5s.times-circle'), " Clear Log")
        self.clear_log_btn.setToolTip("Clear event log")
        self.copy_all_btn = QPushButton(qta.icon('fa5s.copy'), " Copy ALL")
        self.copy_all_btn.setToolTip("Copy the entire log to the clipboard")
        self.open_log_file_btn = QPushButton(qta.icon('fa5s.file-alt'), " Open Log File")
        self.open_log_file_btn.setToolTip("Open the current session log file in the default editor.")
        options_layout.addWidget(self.dev_mode_cb)
        options_layout.addWidget(self.dupecheck_cb)
        options_layout.addStretch()
        options_layout.addWidget(self.reload_all_btn)
        options_layout.addWidget(self.close_all_btn)
        options_layout.addWidget(self.info_btn)
        self.status_label = QLabel("Select an operation mode to begin.")
        self.status_label.setObjectName("StatusLabel")
        self.progress_bar = QProgressBar()

        self.info_btn.clicked.connect(self._show_about_dialog)
        self.clear_log_btn.clicked.connect(self._clear_log)
        self.copy_all_btn.clicked.connect(self._copy_all_log)
        self.open_log_file_btn.clicked.connect(self._open_log_file)
        self.decompile_input_btn.clicked.connect(self._select_decompile_input)
        self.decompile_output_btn.clicked.connect(self._select_decompile_output)
        self.decompile_start_btn.clicked.connect(self._start_decompile)
        self.decompile_info_btn.clicked.connect(self._start_get_info)
        self.compile_input_btn.clicked.connect(self._select_compile_input)
        self.compile_output_btn.clicked.connect(self._select_compile_output)
        self.compile_start_btn.clicked.connect(self._start_compile)
        self.help_support_btn.clicked.connect(self._submit_log)
        self.decompile_clear_btn.clicked.connect(self._clear_decompile_selections)
        self.compile_clear_btn.clicked.connect(self._clear_compile_selections)

        logo_container_widget.setMinimumHeight(320)
        self.left_panel_layout.addWidget(logo_container_widget)

        self.separator_between_modes = QFrame()
        self.separator_between_modes.setFrameShape(QFrame.Shape.HLine)
        self.separator_between_modes.setFrameShadow(QFrame.Shadow.Plain)

        if self.decompile_on_top:
            self.left_panel_layout.addWidget(self.decompile_box)
            self.left_panel_layout.addWidget(self.separator_between_modes)
            self.left_panel_layout.addWidget(self.compile_box)
        else:
            self.left_panel_layout.addWidget(self.compile_box)
            self.left_panel_layout.addWidget(self.separator_between_modes)
            self.left_panel_layout.addWidget(self.decompile_box)

        self.left_panel_layout.addLayout(options_layout)
        self.left_panel_layout.addWidget(self.status_label)
        self.left_panel_layout.addWidget(self.progress_bar)

        return left_widget
    def _create_right_panel(self):

        # --- Nested class for clickable label with resize signal ---
        class ClickableLabel(QLabel):
            doubleClicked = Signal()
            resized = Signal()
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
            def mouseDoubleClickEvent(self, event):
                self.doubleClicked.emit()
                super().mouseDoubleClickEvent(event)
            def resizeEvent(self, event):
                self.resized.emit()
                super().resizeEvent(event)

        # --- Top Widget (Log Viewer) ---
        self.log_container = QWidget()
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(0,0,0,0)
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setFont(QFont("Cascadia Code", 10))
        self.log_widget.setObjectName("LogWidget")
        log_button_layout = QHBoxLayout()
        log_button_layout.addWidget(self.clear_log_btn)
        log_button_layout.addWidget(self.copy_all_btn)
        log_button_layout.addWidget(self.open_log_file_btn)
        log_button_layout.addWidget(self.help_support_btn)
        log_layout.addWidget(self.log_widget)
        log_layout.addLayout(log_button_layout)
        # --- Bottom Widget (Image Previewer) ---
        self.previewer_box = QGroupBox("Image Previewer")
        previewer_layout = QVBoxLayout(self.previewer_box)

        # --- NEW: Image Container for Overlay ---
        image_container = QWidget()
        image_container_layout = QGridLayout(image_container)
        image_container_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Image Display Label
        self.image_display_label = ClickableLabel("Run 'Get Info' on a file to preview textures.")
        self.image_display_label.doubleClicked.connect(self._open_current_preview_image)
        # --- UPGRADE: Add context menu for more actions ---
        self.image_display_label.setToolTip("Double-click to open image in default viewer.\nRight-click for more options.")
        self.image_display_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.image_display_label.customContextMenuRequested.connect(self._show_image_preview_context_menu)
        # --- END UPGRADE ---
        self.image_display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_display_label.setMinimumHeight(200)
        self.image_display_label.setStyleSheet("border: 1px solid #4c566a; border-radius: 3px; background-color: #3b4252;")
        image_container_layout.addWidget(self.image_display_label, 0, 0)

        # --- Resize Handling ---
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(100) # 100ms debounce to prevent lag
        self.resize_timer.timeout.connect(self._handle_resize_timeout)
        self.image_display_label.resized.connect(lambda: self.resize_timer.start())

        # --- NEW: Zoom Level Overlay Label ---
        self.zoom_level_label = QLabel()
        self.zoom_level_label.setObjectName("ZoomLevelLabel")
        self.zoom_level_label.setVisible(False) # Initially hidden
        image_container_layout.addWidget(self.zoom_level_label, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # 2. Main Info/Filename Label
        self.image_info_label = QLabel("(0 / 0)")
        self.image_info_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.image_info_label.setWordWrap(False)
        # self.image_info_label.setFixedWidth(628) # REMOVED: No longer needed with the new layout.
        #self.image_info_label.setFrameShape(QFrame.Shape.Panel) Used for debug only, don't delete.
        # --- Create all control widgets before laying them out ---
        self.btn_first = QPushButton(qta.icon('fa5s.fast-backward'), "")
        self.btn_first.setToolTip("Jump to the first image")
        self.btn_prev = QPushButton(qta.icon('fa5s.step-backward'), "")
        self.btn_prev.setToolTip("Go to the previous image")
        self.btn_next = QPushButton(qta.icon('fa5s.step-forward'), "")
        self.btn_next.setToolTip("Go to the next image")
        self.btn_last = QPushButton(qta.icon('fa5s.fast-forward'), "")
        self.btn_last.setToolTip("Jump to the last image")
        self.image_details_label = QLabel("")
        self.image_details_label.setObjectName("ImageDetailsLabel")
        self.image_details_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # --- MODIFIED: Create Export Button with Dropdown Menu ---
        self.export_pdf_btn = QPushButton(qta.icon('fa5s.file-pdf'), " Export to PDF")
        self.export_pdf_btn.setToolTip("Export the retrieved image info to a PDF gallery")
        self.export_pdf_btn.setEnabled(False)
        self.export_pdf_menu = QMenu(self)
        self.export_all_action = QAction("Export All...", self)
        self.export_filtered_action = QAction("Export Filtered...", self)
        self.export_selected_action = QAction("Export Selected...", self)
        self.export_pdf_menu.addAction(self.export_all_action)
        self.export_pdf_menu.addAction(self.export_filtered_action)
        self.export_pdf_menu.addAction(self.export_selected_action)
        self.export_pdf_btn.setMenu(self.export_pdf_menu)
        # --- END MODIFICATION ---

        # --- ZOOM CONTROLS (NEW) ---
        self.btn_zoom_in = QPushButton(qta.icon('fa5s.search-plus'), "")
        self.btn_zoom_in.setToolTip("Zoom In")
        self.btn_zoom_out = QPushButton(qta.icon('fa5s.search-minus'), "")
        self.btn_zoom_out.setToolTip("Zoom Out")
        self.btn_fit_to_window = QPushButton(qta.icon('fa5s.expand'), "")
        self.btn_fit_to_window.setToolTip("Fit to Window")
        # --- SEARCH CONTROLS ---
        jump_to_label = QLabel("Search by:")
        self.search_criteria_combo = QComboBox()
        self.search_criteria_combo.addItems(["Filename", "Index", "Dimensions"])
        self.search_criteria_combo.setToolTip("Select the criteria to search by.")
        self.image_jump_to_edit = QLineEdit()
        self.image_jump_to_edit.setToolTip("Enter search term and press Enter or use Find buttons.")
        self.dimensions_filter_combo = QComboBox()
        self.dimensions_filter_combo.setToolTip("Filter images by their dimensions.")
        self._populate_dimensions_filter()
        self.search_input_stack = QStackedWidget()
        self.search_input_stack.addWidget(self.image_jump_to_edit)
        self.search_input_stack.addWidget(self.dimensions_filter_combo)
        self.btn_find_prev = QPushButton(qta.icon('fa5s.chevron-left'), "")
        self.btn_find_prev.setToolTip("Find Previous Match")
        self.btn_find_next = QPushButton(qta.icon('fa5s.chevron-right'), "")
        self.btn_find_next.setToolTip("Find Next Match")
        self.image_nav_slider = QSlider(Qt.Orientation.Horizontal)
        self.image_nav_slider.setToolTip("Scrub through images quickly.")
        # Set fixed sizes for a consistent look matching the mock-up
        for btn in [self.btn_first, self.btn_prev, self.btn_next, self.btn_last, self.export_pdf_btn, self.btn_find_prev, self.btn_find_next, self.btn_zoom_out, self.btn_zoom_in, self.btn_fit_to_window]:
            btn.setFixedHeight(30)
        for btn in [self.btn_find_prev, self.btn_find_next, self.btn_first, self.btn_prev, self.btn_next, self.btn_last, self.btn_zoom_out, self.btn_zoom_in, self.btn_fit_to_window]:
            btn.setFixedWidth(40)
        self.search_criteria_combo.setFixedWidth(100)
        self.search_input_stack.setFixedWidth(360)

        # --- LAYOUT RESTRUCTURE ---
        # (CORRECTED) Top Controls Row with asymmetric split to preserve visual alignment
        top_controls_layout = QHBoxLayout()
        # Create the zoom controls layout
        zoom_controls_layout = QHBoxLayout()
        zoom_controls_layout.setContentsMargins(0, 0, 0, 0)
        zoom_controls_layout.addWidget(self.btn_zoom_in)        
        zoom_controls_layout.addWidget(self.btn_zoom_out)
        zoom_controls_layout.addWidget(self.btn_fit_to_window)
        # Add widgets to the top row layout to center the group
        #top_controls_layout.addStretch(1)
        top_controls_layout.addLayout(zoom_controls_layout)
        top_controls_layout.addSpacing(66) # Increased from 20 to create the 40px shift
        top_controls_layout.addWidget(self.image_info_label)
        top_controls_layout.addStretch(1)

        # 3. Middle Controls Row: Navigation buttons and image details (UNCHANGED FROM ORIGINAL)
        middle_controls_layout = QHBoxLayout()
        middle_controls_layout.setContentsMargins(0, 5, 0, 5)
        middle_controls_layout.addWidget(self.btn_first)
        middle_controls_layout.addWidget(self.btn_prev)
        middle_controls_layout.addWidget(self.btn_next)
        middle_controls_layout.addWidget(self.btn_last)
        middle_controls_layout.addSpacing(20)
        middle_controls_layout.addWidget(self.image_details_label)
        middle_controls_layout.addStretch(1)
        # 4. Bottom Controls Row: Export button and search controls (UNCHANGED FROM ORIGINAL)
        bottom_controls_layout = QHBoxLayout()
        #bottom_controls_layout.addSpacing(32)
        bottom_controls_layout.setContentsMargins(0, 0, 0, 0)
        # NOTE: The zoom controls have been moved to the top_controls_layout.
        # Then the export button
        bottom_controls_layout.addWidget(self.export_pdf_btn)
        bottom_controls_layout.addSpacing(84)
        bottom_controls_layout.addStretch(0)
        bottom_controls_layout.addWidget(jump_to_label)
        bottom_controls_layout.addWidget(self.search_criteria_combo)
        bottom_controls_layout.addWidget(self.search_input_stack)
        bottom_controls_layout.addSpacing(0)
        bottom_controls_layout.addStretch(1)
        bottom_controls_layout.addWidget(self.btn_find_prev)
        bottom_controls_layout.addWidget(self.btn_find_next)
        # --- Add all widgets and layouts to the main previewer layout ---
        previewer_layout.addWidget(image_container, 1) # Give vertical stretch
        previewer_layout.addLayout(top_controls_layout)
        previewer_layout.addLayout(middle_controls_layout)
        previewer_layout.addLayout(bottom_controls_layout)
        previewer_layout.addWidget(self.image_nav_slider)
        # --- Connect signals and slots ---
        def handle_slider_change(value):
            if not self.preview_images or self.current_preview_index == value: return
            self._reset_search_state()
            self.current_preview_index = value
            self._update_previewer_ui()

        # --- MODIFIED: Connect new menu actions ---
        self.export_all_action.triggered.connect(lambda: self._handle_pdf_export_request("ALL"))
        self.export_filtered_action.triggered.connect(lambda: self._handle_pdf_export_request("FILTERED"))
        self.export_selected_action.triggered.connect(lambda: self._handle_pdf_export_request("SELECTED"))
        # --- END MODIFICATION ---

        self.btn_first.clicked.connect(self._nav_first)
        self.btn_prev.clicked.connect(self._nav_prev)
        self.btn_next.clicked.connect(self._nav_next)
        self.btn_last.clicked.connect(self._nav_last)
        # --- CONNECT ZOOM BUTTONS (NEW) ---
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        self.btn_fit_to_window.clicked.connect(self._fit_to_window)
        self.image_jump_to_edit.returnPressed.connect(self._find_next_match)
        self.image_jump_to_edit.textChanged.connect(self._find_first_match)
        self.btn_find_prev.clicked.connect(self._find_previous_match)
        self.btn_find_next.clicked.connect(self._find_next_match)
        self.search_criteria_combo.currentIndexChanged.connect(self._on_search_criterion_changed)
        self.dimensions_filter_combo.currentIndexChanged.connect(self._find_first_match)
        self.image_nav_slider.valueChanged.connect(handle_slider_change)
        # --- Final Splitter setup (unchanged) ---
        self.right_panel_splitter = QSplitter(Qt.Orientation.Vertical)
        if self.log_on_top:
            self.right_panel_splitter.addWidget(self.log_container)
            self.right_panel_splitter.addWidget(self.previewer_box)
        else:
            self.right_panel_splitter.addWidget(self.previewer_box)
            self.right_panel_splitter.addWidget(self.log_container)
        log_index = self.right_panel_splitter.indexOf(self.log_container)
        previewer_index = self.right_panel_splitter.indexOf(self.previewer_box)
        self.right_panel_splitter.setStretchFactor(log_index, 3)
        self.right_panel_splitter.setStretchFactor(previewer_index, 1)
        splitter_style = """
QSplitter::handle:vertical {
    background-color: transparent;
    border: none;
    border-top: 1px solid #4c566a;
    height: 1px;
    margin-top: 4px;
    margin-bottom: 4px;
}
QSplitter::handle:vertical:hover {
    border-top: 1px solid #81a1c1;
}
"""
        self.right_panel_splitter.setStyleSheet(splitter_style)
        self._update_previewer_ui()
        return self.right_panel_splitter
    def _populate_initial_log(self):
        """Pushes all stored diagnostic messages to the GUI log and file log."""
        self._log_message("[INFO] Create GUI and Controls. [Started]")

        for msg in self.aDiagnosticMessages:
            self._log_message(msg) 

        self._log_message("[INFO] Create GUI and Controls. [Complete]")
        self._log_message("[INFO] Initialization. [Complete]")
        self._log_message("[INFO] ----- Ready -----")

    def _add_diagnostic_message(self, message):
        """Adds a message to the pre-GUI startup message list."""
        self.aDiagnosticMessages.append(message)
    def _log_message(self, message):
        """
Logs a single message to the GUI and the log file, then ensures it's visible.
This function is thread-safe. For batch operations, use the log_message_buffer instead.
"""
        with self.log_lock:
            html_message, display_message = self._format_log_message(message)

            self.file_logger.write(display_message)
            if hasattr(self, 'log_widget'):
                self.log_widget.append(html_message)
                # --- REGRESSION FIX: Force scroll to the bottom ---
                # This is more reliable than ensureCursorVisible() when dialogs are opened.
                scrollbar = self.log_widget.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
    def _clear_log(self):
        """Clears the log widget and restarts the file log. This is thread-safe."""
        with self.log_lock:
            self.log_widget.clear()
            if self.file_logger:
                self.file_logger.reset()
            self._log_message("[INFO] Log cleared... Ready.")

    def _copy_all_log(self):
        """Copies the entire content of the log widget to the clipboard."""
        QApplication.clipboard().setText(self.log_widget.toPlainText())
        self._log_message("[INFO] Log content copied to clipboard.")
    def _show_tray_message(self, title, message, icon=None):
        """
    A helper function to show a system tray notification.
    Accepts QIcon objects or QSystemTrayIcon.MessageIcon enums.
    """
        if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            # If no icon is provided, default to the Information enum.
            final_icon = icon if icon is not None else QSystemTrayIcon.MessageIcon.Information
            # PySide6's showMessage is overloaded and correctly handles both QIcon and MessageIcon.
            self.tray_icon.showMessage(title, message, final_icon, 3000)
    def _show_vcredist_notification(self):
        """Shows a notification about Visual C++ Redistributable if checks fail."""
        self._log_message("[INFO] Prompting user to install required VC++ Runtimes.")
        msg_box = QMessageBox(self)
        msg_box.setWindowIcon(self.app_icon)
        msg_box.setWindowTitle(f"{APP_TITLE} - Visual C++ Redistributable Required")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText("<b>TextureTool Notice</b><br><br>"
                        "TextureTool requires a <b>specific</b> version of the Visual C++ 2010 Redistributable for Visual Studio.<br><br>"
                        "If this version is not installed, decompiling any <code>Kodi.xbt</code> file will result in an <b>empty output folder</b>.<br><br>"
                        "<u>Important:</u>\n"
                        "<ul>"
                        "<li>This will <b>not</b> affect your current installation of modern or up-to-date C++ runtimes.</li>"
                        "<li>The program uses switch bypasses to avoid Windows exit routines triggered by 'newer version found', which causes the tool to fail.</li>"
                        "<li><b>TextureTool is compatible with Windows XP and above.</b></li>"
                        "</ul>\n"
                        "Clicking <b>Yes</b> will request administrator permission (UAC Prompt) to proceed with the installation.<br><br>"
                        "This will only need to be done <b>once</b> for first installation.<br><br>"
                        "Click <b>No</b> to cancel.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        yes_button = msg_box.button(QMessageBox.StandardButton.Yes)
        yes_button.setMinimumSize(100, 30)
        no_button = msg_box.button(QMessageBox.StandardButton.No)
        no_button.setMinimumSize(100, 30)
        msg_box.setIcon(QMessageBox.Icon.Information)
        ret = msg_box.exec()
        if ret == QMessageBox.StandardButton.Yes:
            self._log_message("[INFO] User initiated runtime installation from startup prompt.")
            self._install_runtimes()
    def _select_decompile_input(self):
        self._log_message("[INFO] ----- Decompile Mode Selected -----")
        last_path = self._get_config_path('decompileinput')
        file_path, _ = QFileDialog.getOpenFileName(self, "Browse .xbt file to extract...", last_path, "Kodi Texture File (*.xbt)")
        if file_path:
            self._handle_decompile_input_path(file_path)



    def _open_decompile_input_folder(self):
        """Opens the folder containing the selected decompile input file."""
        if self.decompile_input_file:
            folder = os.path.dirname(self.decompile_input_file)
            if os.path.exists(folder):
                if sys.platform == "win32":
                    os.startfile(folder)
                else:
                    webbrowser.open("file://" + os.path.abspath(folder))

    def _open_decompile_folder(self):
        if self.decompile_input_file:
            path = os.path.dirname(self.decompile_input_file)
            if os.path.exists(path):
                if sys.platform == "win32":
                    os.startfile(path)
                else:
                    webbrowser.open("file://" + os.path.abspath(path))

    def _open_decompile_output_folder(self):
        """Opens the folder selected as the decompile output directory."""
        if self.decompile_output_folder:
            folder = self.decompile_output_folder
            if os.path.exists(folder):
                if sys.platform == "win32":
                    os.startfile(folder)
                else:
                    webbrowser.open("file://" + os.path.abspath(folder))
    def _select_decompile_output(self):
        last_path = self._get_config_path('decompileoutput')
        folder_path = QFileDialog.getExistingDirectory(self, "Select save location folder...", last_path)
        if folder_path:
            self._handle_decompile_output_path(folder_path)
    def _start_decompile(self):
        task_is_active = any(
            thread is not None
            for thread in (self.decompile_thread, self.compile_thread, self.info_thread, self.installer_thread)
        )
        if task_is_active:
            self._log_message("[WARN] Another task is already in progress. Please wait.")
            return

        if not self.workspace_dir:
            self._log_message("[ERROR] Cannot start task, workspace not available.")
            return

        self._set_ui_task_active(True)
        task_name = "decompile"
        title_message = "[INFO] ----- Decompilation Start -----"
        status_message = "Decompile in progress... Please wait"
        process_cwd = os.path.join(self.workspace_dir, "utils", "TexturePacker_Decompile")
        exe_path = os.path.join(process_cwd, "TextureExtractor.exe")
        norm_output_folder = os.path.normpath(self.decompile_output_folder)
        command = [exe_path, "-o", norm_output_folder, "-c", os.path.normpath(self.decompile_input_file)]

        self._log_message(title_message)

        self.progress_bar.setValue(0)
        self.status_label.setText(status_message)
        self._show_tray_message(APP_TITLE, status_message)

        log_command = " ".join([f'"{arg}"' if " " in arg else arg for arg in command])
        self._log_message(f'[DATA] {datetime.now().strftime("%H:%M:%S")}: Running command: {log_command}')

        self.decompile_thread = QThread(self)
        self.decompile_worker = Worker(command, process_cwd, show_window=False)
        self.decompile_worker.moveToThread(self.decompile_thread)

        self.decompile_worker.progress_updated.connect(functools.partial(self._update_progress_from_worker, prefix="Decompiling"))

        self.decompile_thread.started.connect(self.decompile_worker.run)
        self.decompile_worker.finished.connect(lambda code, out: self._on_process_finished(task_name, code, out))
        self.decompile_worker.error.connect(lambda err: self._on_process_finished(task_name, -1, err))
        self.decompile_worker.finished.connect(self.decompile_thread.quit)
        self.decompile_thread.finished.connect(self.decompile_thread.deleteLater)
        self.decompile_worker.finished.connect(self.decompile_worker.deleteLater)
        self.decompile_thread.start()
    def _start_get_info(self):
        '''Orchestrates the two-stage Get Info process: silent extract, then info scan.'''
        if any(t is not None for t in (self.decompile_thread, self.compile_thread, self.info_thread, self.installer_thread, self.decompile_for_info_thread)):
            self._log_message("[WARN] Another task is already in progress. Please wait.")
            return

        if not self.workspace_dir:
            self._log_message("[ERROR] Cannot start task, workspace not available.")
            return
        assert self.workspace_dir is not None

        # --- Garbage Collection for old info caches ---
        self._log_message("[INFO] Performing cleanup of old temporary info caches...")
        temp_dir = tempfile.gettempdir()
        prefix = "ktt_info_cache_"
        found_and_cleaned = 0
        try:
            for item_name in os.listdir(temp_dir):
                if item_name.startswith(prefix):
                    item_path = os.path.join(temp_dir, item_name)
                    if os.path.isdir(item_path):
                        # Convert to long path on Windows
                        long_item_path = item_path
                        if sys.platform == "win32":
                            buffer = ctypes.create_unicode_buffer(512)
                            if ctypes.windll.kernel32.GetLongPathNameW(item_path, buffer, 512):
                                long_item_path = buffer.value

                        try:
                            shutil.rmtree(long_item_path)
                            self._log_message("[INFO] Removed orphaned cache directory: {}".format(long_item_path))
                            found_and_cleaned += 1
                        except Exception as e:
                            self._log_message("[WARN] Could not remove old cache directory '{}': {}".format(long_item_path, e))
            if found_and_cleaned == 0:
                self._log_message("[INFO] No old info caches found to clean up.")
        except Exception as e:
            self._log_message("[WARN] An error occurred during temp folder cleanup: {}".format(e))

        # --- PHASE 1: SILENT DECOMPILATION ---
        self._log_message("[INFO] ----- Starting Get Info -----")

        # --- CRITICAL FIX: UNLOAD UI BEFORE FILE DELETION ---
        # 1. Clear data source to release locks
        self.preview_images.clear()
        self.current_preview_index = -1

        # 2. Reset search (updates UI to empty state)
        self._reset_search_state()

        # 3. Explicitly force UI update to ensure pixmap is released
        self._update_previewer_ui()

        # 4. NOW safe to delete the old directory
        if self.info_cache_dir and os.path.exists(self.info_cache_dir):
            try:
                shutil.rmtree(self.info_cache_dir, ignore_errors=True)
            except Exception as e:
                self._log_message("[WARN] Could not fully remove previous cache: {}".format(e))

        try:
            # Create the temp directory
            short_path_cache_dir = tempfile.mkdtemp(prefix="ktt_info_cache_")

            # Convert to long path
            long_path_cache_dir = short_path_cache_dir
            if sys.platform == "win32":
                buffer = ctypes.create_unicode_buffer(512)
                if ctypes.windll.kernel32.GetLongPathNameW(short_path_cache_dir, buffer, 512):
                    long_path_cache_dir = buffer.value

            self.info_cache_dir = long_path_cache_dir
            self._log_message("[INFO] Created temporary image cache: {}".format(self.info_cache_dir))
        except Exception as e:
            self._log_message("[ERROR] Could not create temporary cache directory: {}".format(e))
            self.info_cache_dir = None
            return

        self._set_ui_task_active(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText("Step 1/2: Caching images...")

        decompile_cwd = os.path.join(self.workspace_dir, "utils", "TexturePacker_Decompile")
        decompile_exe = os.path.join(decompile_cwd, "TextureExtractor.exe")
        decompile_command = [decompile_exe, "-o", self.info_cache_dir, "-c", os.path.normpath(self.decompile_input_file)]

        self.decompile_for_info_thread = QThread(self)
        self.decompile_for_info_worker = Worker(decompile_command, decompile_cwd, show_window=False)
        self.decompile_for_info_worker.moveToThread(self.decompile_for_info_thread)

        self.decompile_for_info_worker.progress_updated.connect(self._on_get_info_cache_progress)

        self.decompile_for_info_worker.finished.connect(self.decompile_for_info_thread.quit)
        self.decompile_for_info_worker.finished.connect(self.decompile_for_info_worker.deleteLater)
        self.decompile_for_info_thread.finished.connect(self.decompile_for_info_thread.deleteLater)

        self.decompile_for_info_thread.started.connect(self.decompile_for_info_worker.run)
        self.decompile_for_info_worker.finished.connect(self._start_get_info_phase2)
        self.decompile_for_info_worker.error.connect(self._on_get_info_extract_failed)

        self.decompile_for_info_thread.start()
    def _select_compile_input(self):
        self._log_message("[INFO] ----- Compile Mode Selected -----")
        last_path = self._get_config_path('compileinput')
        folder_path = QFileDialog.getExistingDirectory(self, "Browse images source folder...", last_path)
        if folder_path:
            self._handle_compile_input_path(folder_path)
    def _select_compile_output(self):
        last_path = self._get_config_path('compileoutput')
        # Combine the last used directory with the desired default filename.
        default_file_path = os.path.join(last_path, "Textures.xbt")
        file_path, _ = QFileDialog.getSaveFileName(self, "Select save location for .xbt file...", default_file_path, "Kodi Texture File (*.xbt)")
        if file_path:
            self._handle_compile_output_path(file_path)


    def _open_compile_folder(self):
        if self.compile_input_folder:
            path = self.compile_input_folder
            if os.path.exists(path):
                os.startfile(path) if sys.platform == "win32" else webbrowser.open("file://" + os.path.abspath(path))

    def _open_compile_input_folder(self):
        """Opens the folder containing the selected compile input folder."""
        if self.compile_input_folder:
            folder = self.compile_input_folder
            if os.path.exists(folder):
                if sys.platform == "win32":
                    os.startfile(folder)
                else:
                    webbrowser.open("file://" + os.path.abspath(folder))

    def _open_compile_output_folder(self):
        """Opens the folder containing the selected compile output file."""
        if self.compile_output_file:
            folder = os.path.dirname(self.compile_output_file)
            if os.path.exists(folder):
                if sys.platform == "win32":
                    os.startfile(folder)
                else:
                    webbrowser.open("file://" + os.path.abspath(folder))
    def _start_compile(self):
        task_is_active = any(
            thread is not None
            for thread in (self.decompile_thread, self.compile_thread, self.info_thread, self.installer_thread)
        )
        if task_is_active:
            self._log_message("[WARN] Another task is already in progress. Please wait.")
            return

        self._log_message("[INFO] ----- Compilation Start -----")
        if not self.workspace_dir:
            self._log_message("[ERROR] Cannot compile, workspace not available.")
            return

        norm_input_folder = os.path.normpath(self.compile_input_folder)
        norm_output_file = os.path.normpath(self.compile_output_file)

        try:
            with open(norm_output_file, 'w', encoding='utf-8') as f:
                pass
        except IOError as e:
            self._log_message(f"[ERROR] Could not create output file: {e}")
            return

        self._set_ui_task_active(True)
        process_cwd = os.path.join(self.workspace_dir, "utils", "TexturePacker_Compile")
        exe_path = os.path.join(process_cwd, "TextureCompiler.exe")

        command_parts = [exe_path]
        if self.dupecheck_cb.isChecked():
            command_parts.append("-dupecheck")

        command_parts.extend(["-input", norm_input_folder, "-output", norm_output_file])

        # --- DEV MODE LOGIC ---
        if self.dev_mode_cb.isChecked():
            log_command = " ".join([f'"{arg}"' if " " in arg else arg for arg in command_parts])
            QMessageBox.information(self, "Dev Mode: Command Preview", f"The following command will be executed:\n\n{log_command}")
            self._log_message(f"[DEV] Displayed command preview to user.")
        # --- END DEV MODE ---

        self.progress_bar.setValue(0)
        self.status_label.setText("Compile in progress... Please wait")
        self._show_tray_message(APP_TITLE, "Compile in progress...")

        log_command = " ".join([f'"{arg}"' if " " in arg else arg for arg in command_parts])
        self._log_message(f'[DATA] {datetime.now().strftime("%H:%M:%S")}: Running command: {log_command}')

        self.compile_thread = QThread(self)
        self.compile_worker = Worker(command_parts, process_cwd)
        self.compile_worker.moveToThread(self.compile_thread)

        self.compile_worker.progress_updated.connect(functools.partial(self._update_progress_from_worker, prefix="Compiling"))

        self.compile_thread.started.connect(self.compile_worker.run)
        self.compile_worker.finished.connect(lambda code, out: self._on_process_finished("compile", code, out))
        self.compile_worker.error.connect(lambda err: self._on_process_finished("compile", -1, err))
        self.compile_worker.finished.connect(self.compile_thread.quit)
        self.compile_thread.finished.connect(self.compile_thread.deleteLater)
        self.compile_worker.finished.connect(self.compile_worker.deleteLater)
        self.compile_thread.start()

    def _submit_log(self):
        self._log_message("[INFO] Help/Support button selected.")
        dialog = CustomHelpDialog(self)
        if dialog.exec():
            webbrowser.open("https://forum.kodi.tv/forumdisplay.php?fid=314")
            log_path = self.file_logger.log_path
            if os.path.exists(log_path):
                if sys.platform == "win32":
                    os.startfile(log_path)
                else:
                    webbrowser.open("file://" + os.path.abspath(log_path))
    
    def _show_about_dialog(self):
        self._log_message("[INFO] About window opened.")
        dialog = CustomAboutDialog(self)
        dialog.exec()
    
    def _open_folder(self, path):
        """Opens a given folder path in the system's file explorer."""
        if path and os.path.exists(path):
            try:
                if sys.platform == "win32":
                    os.startfile(path)
                else:
                    webbrowser.open("file://" + os.path.abspath(path))
                self._log_message(f"[INFO] Opened output folder: {path}")
            except Exception as e:
                self._log_message(f"[ERROR] Could not open folder {path}: {e}")
    
    def _delayed_open_folder(self, path):
        """
    Opens a folder after a short delay. This helps prevent race conditions
    on Windows where a file handle from a finished subprocess may not
    have been released by the OS yet.
    """
        if path and os.path.exists(path):
            QTimer.singleShot(250, lambda: self._open_folder(path))
            
    def _reset_ui_after_task(self):
        '''Resets UI, re-enables controls, and clears all task handles to release the lock.'''
        # Clear ALL possible task handles to allow a new task to start
        self.decompile_thread, self.decompile_worker = None, None
        self.compile_thread, self.compile_worker = None, None
        self.info_thread, self.info_worker = None, None
        self.installer_thread, self.installer_worker = None, None
        self.decompile_for_info_thread, self.decompile_for_info_worker = None, None
        self.pdf_export_thread, self.pdf_export_worker = None, None

        # Re-enable the UI controls IMMEDIATELY.
        self._set_ui_task_active(False)

        # Update the button states IMMEDIATELY.
        self._update_button_states()

        # For compile/decompile, we use a delay to show the "complete" message.
        # For "Get Info", this is handled by the buffer processor, so this call
        # effectively just resets the status for the next operation.
        QTimer.singleShot(2000, self._finalize_ui_reset)
    def _on_process_finished(self, task_name, return_code, output):
        if task_name == "decompile_info":
            if return_code != 0:
                self._log_message("[ERROR] Get Info task failed with code: {}.".format(return_code))
                if output: self._log_message("[ERROR] {}".format(output))
                self.log_message_buffer.clear()
                self._reset_ui_after_task()
                return

            self._log_message("[INFO] ----- Get Info Complete (Data Parsed) -----")

            # --- FALLBACK SCAN START ---
            try:
                if not self.preview_images:
                    self._scan_cache_dir_fallback()
            except Exception as e:
                self._log_message("[ERROR] Fallback scan failed: {}".format(e))
            # --- FALLBACK SCAN END ---

            if self.preview_images:
                self.current_preview_index = 0

            # Update UI safely
            self._update_previewer_ui()
            self._populate_dimensions_filter()

            # --- RESET UI LOGIC ---
            self.info_thread, self.info_worker = None, None
            self._set_ui_task_active(False)
            self._update_button_states()

            self.status_label.setText("Info retrieval complete. Rendering log to window...")

            QTimer.singleShot(0, self._process_log_message_buffer)
            return

        # Generic completion logic
        self.progress_bar.setValue(100)
        if return_code == 0:
            final_message = "{} process complete".format(task_name.capitalize())
            self.status_label.setText(final_message)
            self._log_message("[INFO] ----- {} Complete -----".format(task_name.capitalize()))
            if task_name == "decompile" and self.open_decompile_on_complete:
                self._delayed_open_folder(self.decompile_output_folder)
            elif task_name == "compile" and self.open_compile_on_complete:
                self._delayed_open_folder(os.path.dirname(self.compile_output_file))
            self._show_tray_message(APP_TITLE, "{} complete!".format(task_name.capitalize()))
        else:
            self._log_message("[ERROR] {}".format(output))
            self.status_label.setText("Error during {} (Code: {})".format(task_name, return_code))
            self._show_tray_message(APP_TITLE, "Error during {}".format(task_name), QSystemTrayIcon.MessageIcon.Warning)

        self._reset_ui_after_task()
    def _install_runtimes(self):
        """Launches the runtime installer with elevation and monitors for completion."""
        self._log_message("[INFO] Starting runtime installation...")
        if sys.platform != "win32":
            self._log_message("[WARN] Runtime installer is only available on Windows.")
            return

        if any(t is not None for t in (self.decompile_thread, self.compile_thread, self.info_thread, self.installer_thread)):
            self._log_message("[WARN] Another task is already in progress. Please wait.")
            return

        installer_path = get_resource_path(os.path.join("runtimes", "Install_all.bat"))
        if not os.path.exists(installer_path):
            self._log_message(f"[ERROR] Runtime installer not found at: {installer_path}")
            return

        self._set_ui_task_active(True)
        self._log_message(f"[INFO] Requesting elevation to launch installer: {installer_path}")
        self.status_label.setText("Waiting for installer to finish...")

        class ShellExecuteInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
                ("lpVerb", ctypes.c_wchar_p), ("lpFile", ctypes.c_wchar_p), ("lpParameters", ctypes.c_wchar_p),
                ("lpDirectory", ctypes.c_wchar_p), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p), ("lpClass", ctypes.c_wchar_p), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE),
            ]

        info = ShellExecuteInfo()
        info.cbSize = ctypes.sizeof(info)
        info.fMask = 0x00000040 # SEE_MASK_NOCLOSEPROCESS
        info.hwnd = self.winId()
        info.lpVerb = "runas" # Request elevation
        info.lpFile = installer_path
        info.lpParameters = None
        info.nShow = 1 # SW_SHOWNORMAL

        if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
            self._log_message("[ERROR] Failed to start installer process. The request may have been cancelled.")
            self._set_ui_task_active(False)
            self.status_label.setText("Installer launch failed.")
            return

        self.installer_thread = QThread(self)
        self.installer_worker = ProcessMonitorWorker(info.hProcess)
        self.installer_worker.moveToThread(self.installer_thread)
        self.installer_thread.started.connect(self.installer_worker.run)
        self.installer_worker.finished.connect(self._on_installer_finished)
        self.installer_worker.error.connect(self._on_installer_finished) # Error also calls finished
        self.installer_worker.finished.connect(self.installer_thread.quit)
        self.installer_worker.finished.connect(self.installer_worker.deleteLater)
        self.installer_thread.finished.connect(self.installer_thread.deleteLater)
        self.installer_thread.start()
    def _on_installer_finished(self, error_msg=""):
        """Handles the completion of the runtime installer process."""
        if error_msg:
            self._log_message(f"[ERROR] Installer monitoring failed: {error_msg}")
            self.status_label.setText("Installer finished with an error.")
            self._show_tray_message(APP_TITLE, "Runtime Installation Failed", QSystemTrayIcon.MessageIcon.Warning)
        else:
            self._log_message("[INFO] Runtime installer process finished successfully.")
            self.status_label.setText("Installer finished.")
            self._show_tray_message(APP_TITLE, "Runtime Installation Complete", QSystemTrayIcon.MessageIcon.Information)
            # Re-check vcredist status after installation
            self._log_message("[INFO] Re-checking Visual C++ Redistributable status after installation.")
            self.vcredist_checks_passed = self._check_vcredist_installed()
            if self.vcredist_checks_passed:
                self._log_message("[INFO] Visual C++ Redistributable check: [Passed] after installation.")
            else:
                self._log_message("[ERROR] Visual C++ Redistributable check: [Failed] after installation. Please check log for details.")
        self._reset_ui_after_task()

        # --- THE FIX: Update the menu item's state after successful installation ---
        self._update_runtime_menu_actions_state()
        self._update_button_states() # Update button states based on new vcredist status

    def _reload_all(self):
        """Reloads the most recent item from each category if available."""
        self._log_message("[INFO] Reloading last used paths from recent items...")
        reloaded_something = False

        if self.recent_decompile_files:
            self._open_recent_decompile_file(self.recent_decompile_files[0])
            reloaded_something = True

        if self.recent_decompile_folders:
            self._open_recent_decompile_folder(self.recent_decompile_folders[0])
            reloaded_something = True

        if self.recent_compile_folders:
            self._open_recent_compile_folder(self.recent_compile_folders[0])
            reloaded_something = True

        if self.recent_compile_files:
            self._open_recent_compile_file(self.recent_compile_files[0])
            reloaded_something = True

        if not reloaded_something:
            self._log_message("[WARN] No recent items available to reload.")
        else:
            self._log_message("[INFO] Reload of recent paths complete.")
        
        self._update_button_states()
        self._update_status_label()
    def _close_all(self):
        self._clear_decompile_selections()
        self._clear_compile_selections()
        self._log_message("[INFO] All active selections have been closed.")
    def _handle_decompile_input_path(self, file_path):
        self._clear_gallery()
        self.decompile_input_file = file_path
        _display_path = os.path.basename(file_path)
        self.decompile_input_label.setText(f"..\\{_display_path}")
        self.decompile_input_label.setToolTip(file_path)
        self.decompile_input_label.setProperty("state", "selected")
        self.decompile_input_label.style().unpolish(self.decompile_input_label)
        self.decompile_input_label.style().polish(self.decompile_input_label)
        self._set_config_path('decompileinput', os.path.dirname(file_path))
        self._log_message(f'[DATA] Decompile input file: "{os.path.normpath(file_path)}"')
        self._log_message("[INFO] Input selection loaded successfully.")
        self._add_recent(RecentGroup.DECOMPILE_FILES, file_path)
        self._update_button_states()
        self._update_status_label()
    def _handle_decompile_output_path(self, folder_path):
        self.decompile_output_folder = folder_path
        _display_path = os.path.basename(folder_path)
        self.decompile_output_label.setText(f"..\\{_display_path}")
        self.decompile_output_label.setToolTip(folder_path)
        self.decompile_output_label.setProperty("state", "selected")
        self.decompile_output_label.style().unpolish(self.decompile_output_label)
        self.decompile_output_label.style().polish(self.decompile_output_label)
        self._set_config_path('decompileoutput', folder_path)
        if not self.vcredist_checks_passed:
            self.decompile_start_btn.setToolTip("Disabled. Required C++ Runtimes are missing. See Display menu.")
        self._log_message(f'[DATA] Decompile output directory: "{os.path.normpath(self.decompile_output_folder)}"')
        self._log_message("[INFO] Output folder destination loaded successfully.")
        self._add_recent(RecentGroup.DECOMPILE_FOLDERS, folder_path)
        self._update_button_states()
        self._update_status_label()
    def _handle_compile_input_path(self, folder_path):
        self.compile_input_folder = folder_path
        _display_path = os.path.basename(folder_path)
        self.compile_input_label.setText(f"..\\{_display_path}")
        self.compile_input_label.setToolTip(folder_path)
        self.compile_input_label.setProperty("state", "selected")
        self.compile_input_label.style().unpolish(self.compile_input_label)
        self.compile_input_label.style().polish(self.compile_input_label)
        self._set_config_path('compileinput', folder_path)
        self._log_message(f'[DATA] Path to directory: "{os.path.normpath(self.compile_input_folder)}"')
        self._log_message("[INFO] Image folder input selection loaded successfully.")
        self._add_recent(RecentGroup.COMPILE_FOLDERS, folder_path)
        self._update_button_states()
        self._update_status_label()
    def _handle_compile_output_path(self, file_path):
        self.compile_output_file = file_path
        _display_path = os.path.basename(file_path)
        self.compile_output_label.setText(f"..\\{_display_path}")
        self.compile_output_label.setToolTip(file_path)
        self.compile_output_label.setProperty("state", "selected")
        self.compile_output_label.style().unpolish(self.compile_output_label)
        self.compile_output_label.style().polish(self.compile_output_label)
        self._set_config_path('compileoutput', os.path.dirname(file_path))
        if not self.vcredist_checks_passed:
            self.compile_start_btn.setToolTip("Disabled. Required C++ Runtimes are missing. See Display menu.")
        self._log_message(f'[DATA] Path to output file: "{os.path.normpath(self.compile_output_file)}"')
        self._log_message("[INFO] Output folder destination loaded successfully.")
        self._add_recent(RecentGroup.COMPILE_FILES, file_path)
        self._update_button_states()
        self._update_status_label()

    def _on_decompile_file_dropped(self, path):
        if os.path.isdir(path):
            self._log_message(f"[INFO] Decompile output folder dropped: {os.path.basename(path)}")
            self._handle_decompile_output_path(path)
        elif os.path.isfile(path):
            if path.lower().endswith(".xbt"):
                self._log_message(f"[INFO] Decompile input file dropped: {os.path.basename(path)}")
                self._handle_decompile_input_path(path)
            else:
                self._log_message(f"[WARN] Invalid file type for Decompile input. Please drop a '.xbt' file.")
        else:
            self._log_message(f"[WARN] Invalid item dropped on Decompile box: {path}")

    def _on_decompile_folder_dropped(self, path):
        self._log_message(f"[INFO] Decompile output folder dropped: {os.path.basename(path)}")
        self._handle_decompile_output_path(path)

    def _on_compile_folder_dropped(self, path):
        if os.path.isdir(path):
            self._log_message(f"[INFO] Compile input folder dropped: {os.path.basename(path)}")
            self._handle_compile_input_path(path)
        elif os.path.isfile(path):
            self._log_message(f"[INFO] Compile output file dropped: {os.path.basename(path)}")
            self._handle_compile_output_path(path)
        else:
            self._log_message(f"[WARN] Invalid item dropped on Compile box: {path}")

    def _on_compile_file_dropped(self, path):
        self._log_message(f"[INFO] Compile output file dropped: {os.path.basename(path)}")
        self._handle_compile_output_path(path)
    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        compile_menu = file_menu.addMenu(qta.icon('fa5s.file-archive'), "Compile")
        compile_file_menu = compile_menu.addMenu("File")
        open_compile_file_action = QAction("Open", self)
        open_compile_file_action.setToolTip("Select the output file location for compilation (e.g., MySkin.xbt)")
        open_compile_file_action.triggered.connect(self._select_compile_output)
        compile_file_menu.addAction(open_compile_file_action)
        compile_folder_menu = compile_menu.addMenu("Folder")
        open_compile_folder_action = QAction("Open", self)
        open_compile_folder_action.setToolTip("Select the input folder containing images to compile")
        open_compile_folder_action.triggered.connect(self._select_compile_input)
        compile_folder_menu.addAction(open_compile_folder_action)
        decompile_menu = file_menu.addMenu(qta.icon('fa5s.box-open'), "Decompile")
        decompile_file_menu = decompile_menu.addMenu("File")
        open_decompile_file_action = QAction("Open", self)
        open_decompile_file_action.setToolTip("Select the input .xbt file to decompile")
        open_decompile_file_action.triggered.connect(self._select_decompile_input)
        decompile_file_menu.addAction(open_decompile_file_action)
        decompile_folder_menu = decompile_menu.addMenu("Folder")
        open_decompile_folder_action = QAction("Open", self)
        open_decompile_folder_action.setToolTip("Select the output folder where extracted images will be saved")
        open_decompile_folder_action.triggered.connect(self._select_decompile_output)
        decompile_folder_menu.addAction(open_decompile_folder_action)
        file_menu.addSeparator()
        self.recent_compile_menu = file_menu.addMenu(qta.icon('fa5s.history'), "Recent Compile")
        self.recent_compile_files_menu = self.recent_compile_menu.addMenu("Files")
        self.clear_compile_files_action = QAction("Clear Recent Files", self)
        self.clear_compile_files_action.setToolTip("Clear the list of recent compile output files")
        self.clear_compile_files_action.triggered.connect(lambda: self._clear_recent(RecentGroup.COMPILE_FILES))
        self.recent_compile_folders_menu = self.recent_compile_menu.addMenu("Folders")
        self.clear_compile_folders_action = QAction("Clear Recent Folders", self)
        self.clear_compile_folders_action.setToolTip("Clear the list of recent compile input folders")
        self.clear_compile_folders_action.triggered.connect(lambda: self._clear_recent(RecentGroup.COMPILE_FOLDERS))
        self.recent_decompile_menu = file_menu.addMenu(qta.icon('fa5s.history'), "Recent Decompile")
        self.recent_decompile_files_menu = self.recent_decompile_menu.addMenu("Files")
        self.clear_decompile_files_action = QAction("Clear Recent Files", self)
        self.clear_decompile_files_action.setToolTip("Clear the list of recent decompile input files")
        self.clear_decompile_files_action.triggered.connect(lambda: self._clear_recent(RecentGroup.DECOMPILE_FILES))
        self.recent_decompile_folders_menu = self.recent_decompile_menu.addMenu("Folders")
        self.clear_decompile_folders_action = QAction("Clear Recent Folders", self)
        self.clear_decompile_folders_action.setToolTip("Clear the list of recent decompile output folders")
        self.clear_decompile_folders_action.triggered.connect(lambda: self._clear_recent(RecentGroup.DECOMPILE_FOLDERS))
        self._update_recent_menus()
        file_menu.addSeparator()
        self.reload_all_action = QAction(qta.icon('fa5s.sync-alt'), "Reload All", self)
        self.reload_all_action.setToolTip("Reload the most recently used paths for all modes")
        self.reload_all_action.triggered.connect(self._reload_all)
        file_menu.addAction(self.reload_all_action)
        close_all_action = QAction(qta.icon('fa5s.ban'), "Close All", self)
        close_all_action.setToolTip("Clear all active input and output selections")
        close_all_action.triggered.connect(self._close_all)
        file_menu.addAction(close_all_action)
        file_menu.addSeparator()
        exit_action = QAction("&Exit", self)
        exit_action.setToolTip("Exit the application")
        exit_action.setIcon(qta.icon('fa5s.sign-out-alt'))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        display_menu = menu_bar.addMenu("&Display")
        self.open_decompile_on_complete_action = QAction("Open Decompile Folder on Completion", self)
        self.open_decompile_on_complete_action.setToolTip("Automatically open the output folder after a successful decompile")
        self.open_decompile_on_complete_action.setCheckable(True)
        self.open_decompile_on_complete_action.setChecked(self.open_decompile_on_complete)
        self.open_decompile_on_complete_action.triggered.connect(self._toggle_open_decompile_on_complete)
        display_menu.addAction(self.open_decompile_on_complete_action)
        self.open_compile_on_complete_action = QAction("Open Compile Folder on Completion", self)
        self.open_compile_on_complete_action.setToolTip("Automatically open the output folder after a successful compile")
        self.open_compile_on_complete_action.setCheckable(True)
        self.open_compile_on_complete_action.setChecked(self.open_compile_on_complete)
        self.open_compile_on_complete_action.triggered.connect(self._toggle_open_compile_on_complete)
        display_menu.addAction(self.open_compile_on_complete_action)
        self.open_pdf_on_complete_action = QAction("Open PDF Report on Completion", self)
        self.open_pdf_on_complete_action.setToolTip("Automatically open the generated PDF report after a successful export")
        self.open_pdf_on_complete_action.setCheckable(True)
        self.open_pdf_on_complete_action.setChecked(self.open_pdf_on_complete)
        self.open_pdf_on_complete_action.triggered.connect(self._toggle_open_pdf_on_complete)
        display_menu.addAction(self.open_pdf_on_complete_action)
        display_menu.addSeparator()
        self.log_position_action = QAction("Swap Log Viewer/Image Previewer Position", self)
        self.log_position_action.setToolTip("Toggle the position of the log viewer (top or bottom)")
        self.log_position_action.setCheckable(True)
        self.log_position_action.setChecked(self.log_on_top)
        self.log_position_action.triggered.connect(self._toggle_log_previewer_position)
        display_menu.addAction(self.log_position_action)
        self.swap_groups_action = QAction("Show Compile Mode on Top", self)
        self.swap_groups_action.setToolTip("Display the Compile Mode group at the top of the panel.")
        self.swap_groups_action.setCheckable(True)
        self.swap_groups_action.setChecked(not self.decompile_on_top)
        self.swap_groups_action.triggered.connect(self._toggle_compile_decompile_position)
        display_menu.addAction(self.swap_groups_action)
        display_menu.addSeparator()
        reset_geometry_action = QAction(qta.icon('fa5s.window-restore'), "Reset Window Position", self)
        reset_geometry_action.setToolTip("Reset the main window size and position to the default")
        reset_geometry_action.triggered.connect(self._reset_window_geometry)
        display_menu.addAction(reset_geometry_action)
        display_menu.addSeparator()
        clear_log_action = QAction("&Clear Event Log", self)
        clear_log_action.setToolTip("Clear all messages from the log viewer")
        clear_log_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton))
        clear_log_action.triggered.connect(self._clear_log)
        display_menu.addAction(clear_log_action)
        options_menu = menu_bar.addMenu("&Options")
        self.update_check_on_startup_action = QAction("Check for Updates on Startup", self)
        self.update_check_on_startup_action.setToolTip("Enable or disable automatic update checks when the application starts")
        self.update_check_on_startup_action.setCheckable(True)
        self.update_check_on_startup_action.setChecked(self.check_for_updates_on_startup)
        self.update_check_on_startup_action.triggered.connect(self._toggle_update_check_on_startup)
        options_menu.addAction(self.update_check_on_startup_action)
        options_menu.addSeparator()
        self.install_runtimes_action = QAction("&Install Runtimes", self)
        self.install_runtimes_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.install_runtimes_action.triggered.connect(self._install_runtimes)
        options_menu.addAction(self.install_runtimes_action)
        self.reinstall_runtimes_action = QAction("&Reinstall Runtimes", self)
        self.reinstall_runtimes_action.setIcon(qta.icon('fa5s.sync-alt'))
        self.reinstall_runtimes_action.triggered.connect(self._install_runtimes)
        options_menu.addAction(self.reinstall_runtimes_action)
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction(qta.icon('fa5s.info-circle'), "&About", self)
        about_action.setToolTip("Show application information")
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)
        changelog_action = QAction("&View Changelog", self)
        changelog_action.setToolTip("View the application's version history and changes")
        changelog_action.setIcon(qta.icon('fa5s.file-alt'))
        changelog_action.triggered.connect(self._show_changelog_dialog)
        help_menu.addAction(changelog_action)
        help_action = QAction(qta.icon('fa5s.question-circle'), "&View Help File", self)
        help_action.setToolTip("Open the detailed help documentation")
        help_action.triggered.connect(self._show_help_dialog)
        help_menu.addAction(help_action)
        kodi_forum_action = QAction(qta.icon('fa5s.users'), "Kodi Forum Link", self)
        kodi_forum_action.setToolTip("Open the official Kodi support forum thread")
        kodi_forum_action.triggered.connect(lambda: webbrowser.open("https://forum.kodi.tv/showthread.php?tid=382565"))
        help_menu.addAction(kodi_forum_action)
        github_action = QAction(qta.icon('fa5b.github'), "GitHub Link", self)
        github_action.setToolTip("Open the project's GitHub repository")
        github_action.triggered.connect(lambda: webbrowser.open("https://github.com/kittmaster/KodiTextureTool"))
        help_menu.addAction(github_action)
        help_menu.addSeparator()
        self.update_action = QAction("&Check for Updates...", self)
        self.update_action.setIcon(qta.icon('fa5s.cloud-download-alt'))
        self.update_action.triggered.connect(lambda: self._check_for_updates(manual=True))
        self.update_action.setEnabled(False)
        self.update_action.setToolTip("Disabled. Requires the VC++ Runtimes to be installed.")
        help_menu.addAction(self.update_action)
        help_menu.addSeparator()
        self.dev_update_action = QAction(qta.icon('fa5s.vial'), "&Check for Dev Update URL...", self)
        self.dev_update_action.setToolTip("Manually provide a URL to a version.json file for update testing.")
        self.dev_update_action.setVisible(False)
        self.dev_update_action.triggered.connect(self._check_for_updates_dev)
        help_menu.addAction(self.dev_update_action)


    def _compare_versions(self, version1, version2):
        def _normalize(v):
            try: return [int(p) for p in v.lstrip('v').split('.')]
            except (ValueError, AttributeError): return [0]
        return _normalize(version2) > _normalize(version1)
    def _check_for_updates(self, manual=False):
        """Public-facing method to check for updates from the official URL."""
        prod_url = 'https://raw.githubusercontent.com/kittmaster/KodiTextureTool/main/version.json'
        self._start_update_check(prod_url, manual)
    def _on_update_check_error(self, err, manual):
        self._log_message(f'[INFO] {datetime.now().strftime("%H:%M:%S")}: Checking KittmasterRepo repository for an update. [Complete]')
        self._log_message(f"[ERROR] Update check failed: {err}")
        if manual:
            self.status_label.setText("Update check failed.")
            self._reset_ui_state()
            msg_box = QMessageBox(self)
            msg_box.setWindowIcon(self.app_icon)
            msg_box.setWindowTitle(f"{APP_TITLE} - Update Check Failed")
            # --- PATCH START: Use a custom, more appropriate icon ---
            icon_pixmap = qta.icon('fa5s.times-circle', color=self.COLOR_RED).pixmap(QSize(64, 64))
            msg_box.setIconPixmap(icon_pixmap)
            # --- PATCH END ---
            msg_box.setText(f"Could not check for updates.\n\nDetails: {err}")
            ok_button = msg_box.addButton(QMessageBox.StandardButton.Ok)
            ok_button.setMinimumSize(100, 30)
            msg_box.exec()
        else:
            self._show_tray_message("Update Check Failed", "Could not check for updates.", QSystemTrayIcon.MessageIcon.Warning)
        self.update_thread = None
        self.update_worker = None
    def _show_changelog_dialog(self):
        try:
            self._log_message("[INFO] Changelog window opened.")
            changelog_path = get_resource_path('changelog.txt')
            with open(changelog_path, "r", encoding="utf-8") as f: content = f.read() # Don't replace newlines here
            # The dialog now handles the HTML structure internally via the file.
            dialog = ChangelogDialog(content, self)
            dialog.exec()
        except FileNotFoundError:
            self._log_message("[ERROR] changelog.txt not found.")
            msg_box = QMessageBox(self)
            msg_box.setWindowIcon(self.app_icon)
            msg_box.setWindowTitle(f"{APP_TITLE} - File Not Found")
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setText("The changelog.txt file could not be found.")
            ok_button = msg_box.addButton(QMessageBox.StandardButton.Ok)
            ok_button.setMinimumSize(100, 30)
            msg_box.exec()
    
    def _on_update_check_finished(self, data, manual):
        self.update_check_complete.emit(data, manual)
        self.update_thread = None
        self.update_worker = None
    def _handle_update_ui(self, data, manual):
        latest_version = data.get("latest_version")
        if not latest_version:
            self._log_message("[ERROR] version.json is missing 'latest_version' key.")
            if manual:
                self._reset_ui_state()
            return

        if self._compare_versions(APP_VERSION, latest_version):
            self._log_message(f"[INFO] New version available: {latest_version}")
            # --- PATCH START: Show contextual tray notification ---
            update_available_icon = qta.icon('fa5s.cloud-download-alt', color='#88c0d0')
            self._show_tray_message("Update Available", f"Version {latest_version} is ready to download.", update_available_icon)
            # --- PATCH END ---
            download_url_raw = data.get("update_package_url", "https://github.com/kittmaster/KodiTextureTool/releases/latest")
            changelog_items = data.get("changelog", ["No changelog available."])
            changelog_html_parts = []
            for i, item in enumerate(changelog_items):
                clean_item = item.strip()
                if clean_item.startswith("- v"):
                    if i > 0:
                        changelog_html_parts.append("")
                    changelog_html_parts.append(f"<b>{clean_item}</b>")
                else:
                    changelog_html_parts.append(f"&nbsp;&nbsp;{clean_item}")
            changelog_html = "<br>".join(changelog_html_parts)
            self._log_message("[INFO] Prompting user to download new version.")
            dialog = self.UpdateDialog(latest_version, changelog_html, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                try:
                    parts = urlsplit(download_url_raw)
                    safe_path = quote(parts.path)
                    download_url = urlunsplit(parts._replace(path=safe_path))
                    self._log_message(f"[INFO] Sanitized download URL: {download_url}")
                except Exception as e:
                    self._log_message(f"[ERROR] Could not parse download URL '{download_url_raw}': {e}. Aborting update.")
                    QMessageBox.critical(self, "Download Error", f"The provided update URL is invalid:\n\n{download_url_raw}")
                    self._reset_ui_state()
                    return
                self.update_progress_dialog = UpdateProgressDialog(self)
                self.update_progress_dialog.show()
                self.download_thread = QThread()
                self.download_worker = DownloadWorker(download_url, self.workspace_dir)
                self.download_worker.moveToThread(self.download_thread)
                self.download_worker.progress.connect(self.update_progress_dialog.update_progress)
                self.download_worker.finished.connect(self._trigger_install)
                self.download_worker.error.connect(self._on_download_error)
                self.download_thread.started.connect(self.download_worker.run)
                self.download_thread.finished.connect(self.download_thread.quit)
                self.download_worker.finished.connect(self.download_worker.deleteLater)
                self.download_thread.finished.connect(self.download_thread.deleteLater)
                self.download_thread.start()
            else:
                if manual:
                    self._reset_ui_state()
        elif manual:
            self._log_message("[INFO] Application is up to date.")
            self._reset_ui_state()
            msg_box = QMessageBox(self)
            msg_box.setWindowIcon(self.app_icon)
            msg_box.setWindowTitle(f"{APP_TITLE} - Up to Date")
            msg_box.setText(f"You are running the latest version: {APP_VERSION}")

            # --- PATCH START: Use a custom, more appropriate icon ---
            icon_pixmap = qta.icon('fa5s.check-circle', color=self.COLOR_GREEN).pixmap(QSize(64, 64))
            msg_box.setIconPixmap(icon_pixmap)
            # --- PATCH END ---

            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            ok_button = msg_box.button(QMessageBox.StandardButton.Ok)
            ok_button.setMinimumSize(100, 30)
            msg_box.exec()
        else:
            self._log_message("[INFO] Application is up to date.")
            # --- PATCH START: Use contextual icon for tray notification ---
            up_to_date_icon = qta.icon('fa5s.check-circle', color=self.COLOR_GREEN)
            self._show_tray_message("Up to Date", f"You are running the latest version: {APP_VERSION}", up_to_date_icon)
            # --- PATCH END ---
        self._log_message(f'[INFO] {datetime.now().strftime("%H:%M:%S")}: Checking KittmasterRepo repository for an update... [Complete]')
    def _trigger_install(self, zip_path):
        if not self.workspace_dir:
            self._log_message("[ERROR] Cannot install update: workspace directory is not available.")
            return
        self._log_message("Starting update installation process...")

        app_dir = self.app_dir
        key_file_to_find = "Kodi TextureTool.exe"

        # Determine the correct exe to kill and the full command to relaunch
        executable_path = sys.executable
        app_exe_to_kill = os.path.basename(executable_path)

        # The relaunch_cmd is now fully constructed inside the batch script to handle the _internal path correctly.
        batch_script_template = """@echo off
setlocal enabledelayedexpansion

echo --- Kodi TextureTool Updater ---
echo This window will close automatically on success.
echo.

:: Set variables
set "ZIP_PATH={zip_path}"
set "APP_DIR={app_dir}"
set "KEY_FILE={key_file_to_find}"
set "APP_EXE_TO_KILL={app_exe_to_kill}"
set "EXTRACT_TEMP_DIR=%~dp0extract_temp"
set "SOURCE_DIR="

:: Close running application
echo Closing application: %APP_EXE_TO_KILL%
taskkill /f /im "%APP_EXE_TO_KILL%" > NUL 2>&1
echo Waiting for application to release file handles...
timeout /t 3 /nobreak > NUL

:: Prepare extraction folder
echo Creating temporary extraction folder...
if exist "%EXTRACT_TEMP_DIR%" ( rd /s /q "%EXTRACT_TEMP_DIR%" )
mkdir "%EXTRACT_TEMP_DIR%"

:: Extract update archive
echo.
echo Extracting update from "%ZIP_PATH%"...
powershell -ExecutionPolicy Bypass -NoProfile -Command "Expand-Archive -Path \"%ZIP_PATH%\" -DestinationPath \"%EXTRACT_TEMP_DIR%\" -Force"
if %errorlevel% neq 0 (
    echo ERROR: Failed to extract the update archive.
    pause
    exit /b 1
)

:: Locate payload by finding the key file
echo.
echo Searching for payload in extracted files...
pushd "%EXTRACT_TEMP_DIR%"
for /r %%f in (*) do (
    if /i "%%~nxf"=="%KEY_FILE%" (
        set "SOURCE_DIR=%%~dpf"
        goto :found_payload
    )
)

:found_payload
popd

if not defined SOURCE_DIR (
    echo ERROR: Could not find "%KEY_FILE%" in the update package.
    echo Update cannot continue.
    pause
    exit /b 1
)

:: Copy updated files using a robust method to the PARENT directory
echo.
echo Moving updated files into place...
cd /d "%SOURCE_DIR%"
echo Source: "%CD%"
echo Destination: "%APP_DIR%\\.."
robocopy . "%APP_DIR%\\.." /E /IS /IT /NFL /NDL /NJH /NJS
if %errorlevel% geq 8 (
    echo ERROR: Robocopy failed to move updated files. Your installation may be corrupt.
    pause
    exit /b 1
)

:: Cleanup temporary files before relaunch
echo.
echo Cleaning up temporary files...
cd /d "%~dp0"
rd /s /q "%EXTRACT_TEMP_DIR%"
del "%ZIP_PATH%"

:: Relaunch application from its PARENT directory
echo.
echo Relaunching application...
start "" /d "%APP_DIR%\\.." "%APP_DIR%\\..\\%APP_EXE_TO_KILL%"

:: Self-destruct the batch file and exit the window
(goto) 2>nul & del "%~f0" & exit
"""
        batch_script_content = batch_script_template.format(
            zip_path=zip_path,
            app_dir=app_dir,
            key_file_to_find=key_file_to_find,
            app_exe_to_kill=app_exe_to_kill
        )
        updater_path = os.path.join(self.workspace_dir, "update.bat")
        with open(updater_path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(batch_script_content))
        self._log_message(f"Updater script created at: {updater_path}")

        subprocess.Popen(f'start "Kodi TextureTool Updater" "{updater_path}"', shell=True)

        os._exit(0)
    def _load_settings(self):
        """Loads settings from the config file."""
        self.config.read(self.config_path, encoding='utf-8')
        if not self.config.has_section('Settings'):
            self.config.add_section('Settings')
        self.open_decompile_on_complete = self.config.getboolean('Settings', 'open_decompile_on_complete', fallback=True)
        self.open_compile_on_complete = self.config.getboolean('Settings', 'open_compile_on_complete', fallback=True)
        self.open_pdf_on_complete = self.config.getboolean('Settings', 'open_pdf_on_complete', fallback=True)
        self.check_for_updates_on_startup = self.config.getboolean('Settings', 'check_for_updates_on_startup', fallback=True)
        self.log_on_top = self.config.getboolean('Settings', 'log_on_top', fallback=True)
        self.decompile_on_top = self.config.getboolean('Settings', 'decompile_on_top', fallback=False)
        self.dev_update_url = self.config.get('Settings', 'dev_update_url', fallback='https://raw.githubusercontent.com/kittmaster/KodiTextureTool/main/version.json')
    def _save_settings(self):
        """Saves current settings to the config file."""
        self.config.read(self.config_path, encoding='utf-8')
        if not self.config.has_section('Settings'):
            self.config.add_section('Settings')
        self.config.set('Settings', 'open_decompile_on_complete', str(self.open_decompile_on_complete))
        self.config.set('Settings', 'open_compile_on_complete', str(self.open_compile_on_complete))
        self.config.set('Settings', 'open_pdf_on_complete', str(self.open_pdf_on_complete))
        self.config.set('Settings', 'check_for_updates_on_startup', str(self.check_for_updates_on_startup))
        self.config.set('Settings', 'log_on_top', str(self.log_on_top))
        self.config.set('Settings', 'decompile_on_top', str(self.decompile_on_top))
        self.config.set('Settings', 'dev_update_url', str(self.dev_update_url))
        with open(self.config_path, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)

    def _toggle_update_check_on_startup(self):
        """Handles the toggling of the 'Check for Updates on Startup' menu action."""
        self.check_for_updates_on_startup = self.update_check_on_startup_action.isChecked()
        self._save_settings()
        self._log_message(f"[INFO] Setting 'Check for Updates on Startup' is now {'Enabled' if self.check_for_updates_on_startup else 'Disabled'}.")
    def _set_ui_task_active(self, is_active: bool):
        '''Disables or enables all interactive widgets to enforce a hard UI lock during tasks.'''
        locked = is_active
        self.decompile_box.setEnabled(not locked)
        self.compile_box.setEnabled(not locked)
        self.reload_all_btn.setEnabled(not locked)
        self.close_all_btn.setEnabled(not locked)
        self.info_btn.setEnabled(not locked)
        self.menuBar().setEnabled(not locked)
    def _enable_dev_mode(self):
        '''Enables the Dev mode checkbox, allowing it to be checked by the user.'''
        if not self.dev_mode_cb.isEnabled():
            self.dev_mode_cb.setEnabled(True)
            self._log_message("[INFO] Dev mode checkbox has been enabled by hotkey.")
        else:
            self._log_message("[INFO] Dev mode is already enabled.")
    def _update_previewer_ui(self):
        '''Updates the entire image previewer widget based on the current state. Safe version.'''
        try:
            has_ui = hasattr(self, 'image_nav_slider')
            if has_ui:
                self.image_nav_slider.blockSignals(True)

            if self.current_preview_index != self.last_displayed_index:
                self.is_image_zoomed = False
                self.last_displayed_index = self.current_preview_index
                self.current_zoom_level = 1.0
            self._update_zoom_overlay()

            self.previewer_box.setVisible(True)
            is_search_active = bool(self.search_results) and self.current_search_index != -1

            if not self.preview_images or self.current_preview_index == -1:
                placeholder_icon = qta.icon('fa5s.ban', color='#4c566a')
                placeholder_pixmap = placeholder_icon.pixmap(QSize(128, 128))
                self.image_display_label.setPixmap(placeholder_pixmap)
                self.image_info_label.setText("Run 'Get Info' to preview textures")
                self.image_info_label.setToolTip("")
                self.image_details_label.setText("Dimensions: ... | Format: ... | Size: ...")
                self.btn_first.setEnabled(False)
                self.btn_prev.setEnabled(False)
                self.btn_next.setEnabled(False)
                self.btn_last.setEnabled(False)
                self.export_pdf_btn.setEnabled(False)
                if has_ui:
                    self.btn_zoom_in.setEnabled(False)
                    self.btn_zoom_out.setEnabled(False)
                    self.btn_fit_to_window.setEnabled(False)
                    self.image_jump_to_edit.setEnabled(False)
                    self.btn_find_prev.setEnabled(False)
                    self.btn_find_next.setEnabled(False)
                    self.image_nav_slider.setEnabled(False)
                    self.image_nav_slider.setValue(0)
            else:
                total_previews = len(self.preview_images)
                current_preview = self.current_preview_index

                if has_ui:
                    if self.image_nav_slider.maximum() != total_previews - 1:
                        self.image_nav_slider.setRange(0, total_previews - 1)
                    self.image_nav_slider.setValue(current_preview)

                image_data = self.preview_images[current_preview]

                # --- SAFER LOADING STRATEGY ---
                original_pixmap = None
                error_reason = "Unknown Error"

                try:
                    if not os.path.exists(image_data['path']):
                        error_reason = "File not found"
                    else:
                        reader = QImageReader(image_data['path'])
                        reader.setAllocationLimit(0) 
                        reader.setAutoTransform(True)

                        if reader.canRead():
                            size = reader.size()

                            # Lazy update of dimensions if missing
                            if image_data.get('dimensions') == 'N/A' or not image_data.get('dimensions'):
                                image_data['dimensions'] = "{}x{}".format(size.width(), size.height())

                            max_dim = 8192

                            if size.width() > max_dim or size.height() > max_dim:
                                reader.setScaledSize(size.scaled(max_dim, max_dim, Qt.AspectRatioMode.KeepAspectRatio))

                            img = reader.read()
                            if not img.isNull():
                                original_pixmap = QPixmap.fromImage(img)
                            else:
                                error_reason = reader.errorString()
                        else:
                            error_reason = reader.errorString()
                except Exception as e:
                    error_reason = str(e)

                # --- UI UPDATE ---
                if original_pixmap is None or original_pixmap.isNull():
                    fail_msg = "Preview Unavailable\n\nReason: {}\n({})".format(error_reason, os.path.basename(image_data['path']))
                    self.image_display_label.setText(fail_msg)
                    self.image_display_label.setStyleSheet("border: 1px solid #BF616A; color: #BF616A; font-weight: bold;")
                else:
                    self.image_display_label.setStyleSheet("border: 1px solid #4c566a; border-radius: 3px; background-color: #3b4252;")
                    label_size = self.image_display_label.size()
                    if label_size.width() > 0 and label_size.height() > 0:
                        if not self.image_display_label.pixmap() or self.is_image_zoomed is False:
                            if original_pixmap.width() > label_size.width() or original_pixmap.height() > label_size.height():
                                scaled_pixmap = original_pixmap.scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            else:
                                scaled_pixmap = original_pixmap
                            self.image_display_label.setPixmap(scaled_pixmap)

                base_info_str = "({} / {})".format(current_preview + 1, total_previews)
                full_text_str = ""
                if is_search_active:
                    current_match_num = self.current_search_index + 1
                    full_text_str = "{} Match {} of {}: {}".format(base_info_str, current_match_num, len(self.search_results), image_data['filename'])
                else:
                    full_text_str = "{} {}".format(base_info_str, image_data['filename'])

                self.image_info_label.setText(full_text_str)
                self.image_info_label.setToolTip(full_text_str)

                dims = image_data.get('dimensions', 'N/A')
                fmt = image_data.get('format', 'N/A')
                size_bytes = image_data.get('size', 0)
                formatted_size = self._format_file_size(size_bytes)
                self.image_details_label.setText("Dimensions: {} | Format: {} | Size: {}".format(dims, fmt, formatted_size))

                self.btn_first.setEnabled(current_preview > 0)
                self.btn_prev.setEnabled(current_preview > 0)
                self.btn_next.setEnabled(current_preview < total_previews - 1)
                self.btn_last.setEnabled(current_preview < total_previews - 1)

                self.export_pdf_btn.setEnabled(True)
                if self.export_all_action and self.export_selected_action and self.export_filtered_action:
                    self.export_all_action.setEnabled(True)
                    self.export_selected_action.setEnabled(True)
                    self.export_filtered_action.setEnabled(is_search_active)
                    self.export_all_action.setText("Export All ({} items)...".format(total_previews))
                    if is_search_active:
                        self.export_filtered_action.setText("Export Filtered ({} items)...".format(len(self.search_results)))
                    else:
                        self.export_filtered_action.setText("Export Filtered...")
                    self.export_selected_action.setText("Export Selected (1 item)...")

                if has_ui:
                    self.btn_zoom_in.setEnabled(True)
                    self.btn_zoom_out.setEnabled(True)
                    self.btn_fit_to_window.setEnabled(self.is_image_zoomed)
                    self.image_jump_to_edit.setEnabled(True)
                    self.image_nav_slider.setEnabled(True)
                    self.btn_find_prev.setEnabled(is_search_active)
                    self.btn_find_next.setEnabled(is_search_active)

            if has_ui:
                self.image_nav_slider.blockSignals(False)

        except Exception as e:
            self._log_message("[ERROR] Previewer UI Update error: {}".format(e))
            traceback.print_exc()
    def _nav_first(self):
        self._reset_search_state()
        self.current_preview_index = 0
        self._update_previewer_ui()
    def _nav_prev(self):
        self._reset_search_state()
        if self.current_preview_index > 0:
            self.current_preview_index -= 1
            self._update_previewer_ui()
    def _nav_next(self):
        self._reset_search_state()
        if self.current_preview_index < len(self.preview_images) - 1:
            self.current_preview_index += 1
            self._update_previewer_ui()
    def _nav_last(self):
        self._reset_search_state()
        self.current_preview_index = len(self.preview_images) - 1
        self._update_previewer_ui()
    def _update_progress_from_worker(self, percentage, message, prefix="Processing"):
        # Modify the incoming message to be context-specific for decompile/compile tasks.
        display_message = message
        if (prefix == "Decompiling" or prefix == "Compiling") and "Caching file" in message:
            display_message = message.replace("Caching file", "File")

        fixed_message = display_message
        if sys.platform == "win32":
            try:
                fixed_message = display_message.encode('latin-1').decode('utf-8', 'replace')
            except Exception:
                fixed_message = display_message

        self.progress_bar.setValue(percentage)
        status_text = f"{prefix}: {fixed_message}"
        if len(status_text) > 80:
            # Dynamically calculate how many characters of the message to keep
            # based on the prefix length to ensure the total is about 80 chars.
            # 80 total - len(prefix) - len(": ...") = 80 - len(prefix) - 5
            chars_to_keep = max(10, 75 - len(prefix)) # Ensure we keep at least 10 chars
            status_text = f"{prefix}: ...{fixed_message[-chars_to_keep:]}"
        self.status_label.setText(status_text)
    def _on_info_progress_updated(self, percentage, message):
        """A lightweight slot to only update the progress bar and status text."""
        self.progress_bar.setValue(percentage)
        status_text = f"Step 2/2: Reading texture info... {message}"
        if len(status_text) > 80:
            status_text = f"Step 2/2: ...{status_text[-74:]}"
        self.status_label.setText(status_text)
    def _on_get_info_extract_failed(self, error_message):
        """Handles failure during the silent extraction phase of Get Info."""
        self._log_message(f"[ERROR] Failed during silent extraction phase: {error_message}")
        self.status_label.setText("Error caching images.")
        self.progress_bar.setRange(0, 100)
        self._reset_ui_after_task()
    def _start_get_info_phase2(self, return_code, output):
        '''The second phase of Get Info: scanning the file for texture names.'''
        try:
            if return_code != 0:
                self._on_get_info_extract_failed("TextureExtractor exited with code {}.\n{}".format(return_code, output))
                return

            # Clear previous thread refs
            self.decompile_for_info_thread = None
            self.decompile_for_info_worker = None

            if not self.info_cache_dir or not self.workspace_dir:
                self._on_get_info_extract_failed("Cache or workspace directory does not exist. Cannot proceed.")
                return

            assert self.workspace_dir is not None

            self._log_message("[INFO] Image cache created successfully.")
            self.status_label.setText("Step 2/2: Reading texture information...")
            self.progress_bar.setRange(0, 100)

            process_cwd = os.path.join(self.workspace_dir, "utils", "TexturePacker_Compile")
            exe_path = os.path.join(process_cwd, "TextureCompiler.exe")
            command = [exe_path, "-info", os.path.normpath(self.decompile_input_file)]

            self.info_thread = QThread(self)
            self.info_worker = Worker(command, process_cwd, show_window=False)
            self.info_worker.moveToThread(self.info_thread)

            # Clear buffers again to be safe
            self.preview_images.clear()
            self.log_message_buffer.clear()

            self.info_worker.progress_updated.connect(self._on_info_progress_updated)
            self.info_worker.info_line_parsed.connect(self._on_info_line_received)

            self.info_worker.finished.connect(self.info_thread.quit)
            self.info_worker.finished.connect(self.info_worker.deleteLater)
            self.info_thread.finished.connect(self.info_thread.deleteLater)

            self.info_thread.started.connect(self.info_worker.run)
            self.info_worker.finished.connect(lambda code, out: self._on_process_finished("decompile_info", code, out))
            self.info_worker.error.connect(lambda err: self._on_process_finished("decompile_info", -1, err))

            self.info_thread.start()
        except Exception as e:
             self._log_message("[ERROR] Exception during Phase 2 start: {}".format(e))
             self._on_get_info_extract_failed(str(e))
    def _on_get_info_cache_progress(self, percentage, message):
        '''Handles progress updates specifically for the Phase 1 caching process.'''
        self.progress_bar.setValue(percentage)
        self.status_label.setText(f"Step 1/2: {message}")
    def _on_pdf_export_finished(self, result_message, pdf_path=None):
        """Handles the completion or failure of the PDF export background task."""
        if pdf_path:
            self._log_message(f"[INFO] {result_message}")
            self.status_label.setText("PDF export complete.")
            self._show_tray_message("Export Complete", result_message)
            if self.open_pdf_on_complete:
                self._delayed_open_folder(pdf_path)
        else:
            self._log_message(f"[ERROR] {result_message}")
            self.status_label.setText("PDF export failed.")
            self._show_tray_message("Export Failed", result_message, QSystemTrayIcon.MessageIcon.Warning)

        self._reset_ui_after_task()
    
    class PdfExportWorker(QObject):
        """A worker to generate a PDF report in a background thread."""
        finished = Signal(str)
        error = Signal(str)

        def __init__(self, info_data, output_path):
            super().__init__()
            self.info_data = info_data
            self.output_path = output_path
        def run(self):
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter
                from reportlab.lib.utils import ImageReader
                from reportlab.lib.units import inch
                from reportlab.lib import colors
                from datetime import datetime
                import gc
                from PySide6.QtGui import QImageReader
            except ImportError:
                self.error.emit("ERROR: reportlab library not found. Please install it using 'pip install reportlab'.")
                return

            # Pre-scan and populate missing dimension data to prevent UI freezes.
            # This is necessary because dimensions are often lazy-loaded in the UI.
            for item_data in self.info_data:
                if item_data.get('dimensions') == 'N/A' or not item_data.get('dimensions'):
                    try:
                        # Use QImageReader as it's robust and matches the main app's logic.
                        reader = QImageReader(item_data['path'])
                        reader.setAllocationLimit(0) # Match main app setting
                        if reader.canRead():
                            size = reader.size()
                            item_data['dimensions'] = "{}x{}".format(size.width(), size.height())
                    except Exception:
                        # If reading fails, it remains 'N/A'.
                        pass

            # --- Color & Font Definitions (Nord Theme Inspired) ---
            COLOR_HEADER_BG = colors.HexColor('#434c5e')
            COLOR_TEXT_LIGHT = colors.HexColor('#d8dee9')
            COLOR_TEXT_DARK = colors.HexColor('#2e3440')
            COLOR_TEXT_LABEL = colors.HexColor('#4c566a')
            COLOR_IMAGE_BG = colors.HexColor('#E5E9F0')
            COLOR_BORDER = colors.HexColor('#d8dee9')
            COLOR_CELL_BG = colors.HexColor('#f8f9fa')
            PAGE_WIDTH, PAGE_HEIGHT = letter

            c = None
            try:
                c = canvas.Canvas(self.output_path, pagesize=letter)
                total_images = len(self.info_data)
                logo_path = get_resource_path("assets/kodi_logo_96.png")

                IMAGES_PER_PAGE = 9
                total_gallery_pages = (total_images + IMAGES_PER_PAGE - 1) // IMAGES_PER_PAGE
                total_doc_pages = 1 + total_gallery_pages

                # --- REVISED: Define header/footer heights as constants ---
                HEADER_HEIGHT = 0.5 * inch
                FOOTER_HEIGHT = 0.20 * inch

                def draw_page_chrome(canvas_obj, page_num):
                    canvas_obj.saveState()
                    # Header
                    canvas_obj.setFillColor(COLOR_HEADER_BG)
                    canvas_obj.rect(0, PAGE_HEIGHT - HEADER_HEIGHT, PAGE_WIDTH, HEADER_HEIGHT, fill=1, stroke=0)
                    try:
                        logo = ImageReader(logo_path)
                        canvas_obj.drawImage(logo, 0.25 * inch, PAGE_HEIGHT - 0.45 * inch, width=0.4 * inch, height=0.4 * inch, preserveAspectRatio=True, mask='auto')
                    except Exception: pass
                    canvas_obj.setFont("Helvetica-Bold", 14)
                    canvas_obj.setFillColor(COLOR_TEXT_LIGHT)
                    canvas_obj.drawString(0.75 * inch, PAGE_HEIGHT - 0.325 * inch, "Kodi TextureTool - Image Report")

                    # Footer
                    canvas_obj.setFillColor(COLOR_HEADER_BG)
                    canvas_obj.rect(0, 0, PAGE_WIDTH, FOOTER_HEIGHT, fill=1, stroke=0)
                    canvas_obj.setFont("Helvetica", 9)
                    canvas_obj.setFillColor(COLOR_TEXT_LIGHT)
                    canvas_obj.drawRightString(PAGE_WIDTH - 0.25 * inch, 0.07 * inch, "Page {} of {}".format(page_num, total_doc_pages))
                    canvas_obj.restoreState()

                # --- 1. Draw Title Page ---
                draw_page_chrome(c, 1)
                c.setFont("Helvetica-Bold", 28)
                c.setFillColor(COLOR_TEXT_DARK)
                c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 2.0 * inch, "Image Asset Report")
                c.setFont("Helvetica", 12)
                c.setFillColor(COLOR_TEXT_LABEL)
                c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 2.5 * inch, "Generated by Kodi TextureTool")

                info_box_y = PAGE_HEIGHT - 4.5 * inch
                c.setStrokeColor(COLOR_BORDER)
                c.setFillColor(COLOR_CELL_BG)
                c.roundRect(1.5 * inch, info_box_y - (1.5 * inch), PAGE_WIDTH - 3 * inch, 1.5 * inch, 4, stroke=1, fill=1)

                text = c.beginText(1.75 * inch, info_box_y - 0.4 * inch)
                text.setFont("Helvetica-Bold", 11)
                text.setFillColor(COLOR_TEXT_DARK)
                source_file = os.path.basename(self.info_data[0]['path'].split('_cache_')[0]) if self.info_data else "Unknown"
                text.textLine("Source File: {}".format(source_file))
                text.moveCursor(0, 20)
                text.textLine("Total Images: {}".format(total_images))
                text.moveCursor(0, 20)
                text.textLine("Report Date:  {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                c.drawText(text)
                c.showPage()

                # --- 2. Draw Gallery Pages ---
                COLUMNS, ROWS = 3, 3
                MARGIN = 0.5 * inch
                GUTTER = 0.25 * inch

                # --- REVISED LAYOUT CALCULATIONS to prevent overlap with footer ---
                # Total vertical space available for the gallery content (cells + gutters + margins)
                GALLERY_AREA_HEIGHT = PAGE_HEIGHT - HEADER_HEIGHT - FOOTER_HEIGHT
                # Total vertical space for just the cells and the gutters between them
                CONTENT_HEIGHT = GALLERY_AREA_HEIGHT - (2 * MARGIN)  # Subtract top and bottom margins

                CELL_WIDTH = (PAGE_WIDTH - (2 * MARGIN) - ((COLUMNS - 1) * GUTTER)) / COLUMNS
                CELL_HEIGHT = (CONTENT_HEIGHT - ((ROWS - 1) * GUTTER)) / ROWS
                # --- END REVISED CALCULATIONS ---

                last_percentage = -1

                for i, data in enumerate(self.info_data):
                    percentage = int(((i + 1) / total_images) * 100)
                    if percentage > last_percentage:
                        self.progress.emit(percentage)
                        last_percentage = percentage

                    page_idx = i // IMAGES_PER_PAGE
                    if i % IMAGES_PER_PAGE == 0:
                        draw_page_chrome(c, page_idx + 2)

                    item_on_page = i % IMAGES_PER_PAGE
                    col = item_on_page % COLUMNS
                    row = item_on_page // COLUMNS
                    x = MARGIN + col * (CELL_WIDTH + GUTTER)
                    # Calculate y from the top of the gallery area to ensure it doesn't overlap the footer
                    y = (PAGE_HEIGHT - HEADER_HEIGHT - MARGIN) - CELL_HEIGHT - (row * (CELL_HEIGHT + GUTTER))

                    c.setFillColor(COLOR_CELL_BG)
                    c.setStrokeColor(COLOR_BORDER)
                    c.roundRect(x, y, CELL_WIDTH, CELL_HEIGHT, 4, stroke=1, fill=1)

                    IMG_AREA_HEIGHT = CELL_HEIGHT * 0.60
                    img_x, img_y = x + 5, y + CELL_HEIGHT - IMG_AREA_HEIGHT - 5
                    img_w, img_h = CELL_WIDTH - 10, IMG_AREA_HEIGHT

                    c.setFillColor(COLOR_IMAGE_BG) 
                    c.setStrokeColor(COLOR_BORDER)
                    c.rect(img_x, img_y, img_w, img_h, fill=1, stroke=1)

                    try:
                        img_reader = ImageReader(data['path'])
                        c.drawImage(img_reader, img_x, img_y, width=img_w, height=img_h, preserveAspectRatio=True, anchor='c', mask='auto')
                        del img_reader
                    except Exception:
                        c.setFont("Helvetica", 10)
                        c.setFillColor(colors.red)
                        c.drawCentredString(img_x + img_w / 2, img_y + img_h / 2, "[Image Error]")

                    text_x = x + 5
                    text_y = y + CELL_HEIGHT - IMG_AREA_HEIGHT - 25

                    c.setFont("Helvetica-Bold", 7)
                    c.setFillColor(COLOR_TEXT_DARK)
                    title_text = data['filename']
                    available_width = CELL_WIDTH - 10
                    while c.stringWidth(title_text, "Helvetica-Bold", 7) > available_width and len(title_text) > 4:
                        title_text = title_text[:-4] + "..."
                    c.drawString(text_x, text_y, title_text)

                    text_y -= 12
                    c.setFont("Helvetica", 7)
                    c.setFillColor(COLOR_TEXT_LABEL)
                    c.drawString(text_x, text_y, "Index: {}".format(i + 1))

                    dims_str = data.get('dimensions', 'N/A')
                    if 'x' in dims_str and dims_str != 'N/A':
                        try:
                            width, height = dims_str.split('x')
                            formatted_dims = "{}px x {}px".format(width.strip(), height.strip())
                        except ValueError:
                            formatted_dims = dims_str
                    else:
                        formatted_dims = dims_str

                    text_y -= 10
                    c.drawString(text_x, text_y, "Dimensions: {}".format(formatted_dims))
                    text_y -= 10
                    c.drawString(text_x, text_y, "Format: {}".format(data.get('format', 'N/A')))

                    if (i + 1) % IMAGES_PER_PAGE == 0 and (i + 1) < total_images:
                        c.showPage()

                    if i > 0 and i % 100 == 0:
                        gc.collect()

                c.save()
                self.finished_with_path.emit("Successfully exported {} items to PDF.".format(len(self.info_data)), self.output_path)
            except Exception as e:
                tb_str = traceback.format_exc()
                self.error.emit("ERROR: Failed to generate PDF. Details: {}\n{}".format(e, tb_str))
            finally:
                del c
                if hasattr(self, 'info_data'):
                    del self.info_data
                gc.collect()
        progress = Signal(int)
        finished_with_path = Signal(str, str)
    def _on_pdf_export_progress(self, percentage):
        '''Updates the progress bar during the PDF export process.'''
        self.progress_bar.setValue(percentage)
        self.status_label.setText(f"Generating PDF... {percentage}% complete.")
    def _clear_decompile_selections(self):
        '''Clears only the decompile mode file and folder selections.'''
        self.decompile_input_file = ""
        self.decompile_output_folder = ""
        self.decompile_input_label.setText("[Not Selected]")
        self.decompile_input_label.setToolTip("")
        self.decompile_input_label.setProperty("state", "unselected")
        self.decompile_input_label.style().unpolish(self.decompile_input_label)
        self.decompile_input_label.style().polish(self.decompile_input_label)
        self.decompile_output_label.setText("[Not Selected]")
        self.decompile_output_label.setToolTip("")
        self.decompile_output_label.setProperty("state", "unselected")
        self.decompile_output_label.style().unpolish(self.decompile_output_label)
        self.decompile_output_label.style().polish(self.decompile_output_label)
        self.preview_images.clear()
        self.current_preview_index = -1
        # Also reset search state when clearing
        self._reset_search_state()
        self._populate_dimensions_filter()
        self._update_previewer_ui()
        self._update_button_states()
        self._update_status_label()
    def _clear_compile_selections(self):
        '''Clears only the compile mode file and folder selections.'''
        self.compile_input_folder = ""
        self.compile_output_file = ""
        self.compile_input_label.setText("[Not Selected]")
        self.compile_input_label.setToolTip("")
        self.compile_input_label.setProperty("state", "unselected")
        self.compile_input_label.style().unpolish(self.compile_input_label)
        self.compile_input_label.style().polish(self.compile_input_label)
        self.compile_output_label.setText("[Not Selected]")
        self.compile_output_label.setToolTip("")
        self.compile_output_label.setProperty("state", "unselected")
        self.compile_output_label.style().unpolish(self.compile_output_label)
        self.compile_output_label.style().polish(self.compile_output_label)
        self._update_button_states()
        self._update_status_label()
    
    def _open_current_preview_image(self):
        '''Opens the currently displayed image in the system's default viewer.'''
        if self.preview_images and self.current_preview_index != -1:
            image_path = self.preview_images[self.current_preview_index]['path']
            if os.path.exists(image_path):
                self._log_message(f"[INFO] Opening image in default viewer: {os.path.basename(image_path)}")
                if sys.platform == "win32":
                    os.startfile(os.path.normpath(image_path))
                else:
                    webbrowser.open("file://" + os.path.abspath(image_path))
            else:
                self._log_message(f"[WARN] Cannot open image, file not found: {image_path}")
    def _show_help_dialog(self):
        '''Displays the advanced help dialog.'''
        self._log_message("[INFO] Help dialog window opened.")
        help_file = get_resource_path("help.md")
        dialog = HelpDialog(help_file, self)
        dialog.exec()
    def _toggle_log_previewer_position(self):
        """Swaps the log and previewer widgets based on the menu checkbox state."""
        self.log_on_top = self.log_position_action.isChecked()
        self._save_settings()
        self._log_message(f"[INFO] Log viewer position set to {'top' if self.log_on_top else 'bottom'}.")

        # Re-position the widgets using insertWidget, which moves them if they already exist
        if self.log_on_top:
            self.right_panel_splitter.insertWidget(0, self.log_container)
        else:
            self.right_panel_splitter.insertWidget(0, self.previewer_box)

        # Re-apply the stretch factors to the correct widgets regardless of position
        log_index = self.right_panel_splitter.indexOf(self.log_container)
        previewer_index = self.right_panel_splitter.indexOf(self.previewer_box)
        self.right_panel_splitter.setStretchFactor(log_index, 3)
        self.right_panel_splitter.setStretchFactor(previewer_index, 1)
    def _reset_search_state(self):
        """Clears the search query, results, and resets UI state."""
        self.last_search_query = ("", "")
        self.search_results.clear()
        self.current_search_index = -1
        if hasattr(self, 'image_jump_to_edit'):
            self.image_jump_to_edit.clear()
            self.image_jump_to_edit.setStyleSheet("")
        if hasattr(self, 'dimensions_filter_combo'):
            self.dimensions_filter_combo.setCurrentIndex(0)

        # Explicitly disable find buttons when search is reset
        if hasattr(self, 'btn_find_prev'):
            self.btn_find_prev.setEnabled(False)
            self.btn_find_next.setEnabled(False)

        if hasattr(self, 'image_info_label'):
                self._update_previewer_ui()
    def _perform_search(self):
        """
Populates the search_results list, updates find button states, and returns True if results were found.
"""
        if not self.preview_images:
            if hasattr(self, 'btn_find_prev'):
                self.btn_find_prev.setEnabled(False)
                self.btn_find_next.setEnabled(False)
            return False

        query = ""
        criterion = self.search_criteria_combo.currentText()
        active_search_widget = self.image_jump_to_edit
        is_valid_query = True

        if criterion == "Dimensions":
            query = self.dimensions_filter_combo.currentText()
            active_search_widget = self.dimensions_filter_combo
            if self.dimensions_filter_combo.currentIndex() <= 0:
                is_valid_query = False
        else:
            query = self.image_jump_to_edit.text().strip()
            if not query:
                is_valid_query = False

        if not is_valid_query:
            self._reset_search_state()
            return False

        current_search_tuple = (query, criterion)
        if current_search_tuple != self.last_search_query:
            self.last_search_query = current_search_tuple
            self.search_results.clear()
            self.current_search_index = -1

            if criterion == "Index":
                try:
                    num_index = int(query) - 1
                    if 0 <= num_index < len(self.preview_images):
                        self.search_results.append(num_index)
                except (ValueError, TypeError): pass
            elif criterion == "Dimensions":
                query_lower = query.lower()
                for i, image_data in enumerate(self.preview_images):
                    if query_lower == image_data.get('dimensions', 'N/A').lower():
                        self.search_results.append(i)
            else: # Filename
                query_lower = query.lower()
                for i, image_data in enumerate(self.preview_images):
                    if query_lower in image_data['filename'].lower():
                        self.search_results.append(i)

        if self.search_results:
            active_search_widget.setStyleSheet("")
            self.btn_find_prev.setEnabled(True)
            self.btn_find_next.setEnabled(True)
            return True
        else:
            self.search_results.clear()
            self.current_search_index = -1
            if isinstance(active_search_widget, QLineEdit):
                active_search_widget.setStyleSheet("background-color: #BF616A;")

            self.btn_find_prev.setEnabled(False)
            self.btn_find_next.setEnabled(False)
            return False
    
    def _find_first_match(self):
        """Triggered by Enter key. Finds results and jumps to the first one."""
        if self._perform_search():
            self.current_search_index = 0
            self._jump_to_search_result()
    def _find_next_match(self):
        """Jumps to the next item in the search results, wrapping around."""
        query = self.image_jump_to_edit.text().strip()
        criterion = self.search_criteria_combo.currentText()
        current_search_tuple = (query, criterion)

        # If no active search, or if query/criterion changed, perform one first.
        if not self.search_results or current_search_tuple != self.last_search_query:
            if not self._perform_search():
                return
            # Start from the beginning for a new search
            self.current_search_index = -1

        if not self.search_results: return # Guard against no results

        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        self._jump_to_search_result()
    def _find_previous_match(self):
        """Jumps to the previous item in the search results, wrapping around."""
        query = self.image_jump_to_edit.text().strip()
        criterion = self.search_criteria_combo.currentText()
        current_search_tuple = (query, criterion)

        # If no active search, or if query/criterion changed, perform one first.
        if not self.search_results or current_search_tuple != self.last_search_query:
            if not self._perform_search():
                return
            # On new search, pressing 'previous' should go to the last item.
            # Setting index to 0 allows the decrement to wrap correctly to -1 -> last item.
            self.current_search_index = 0

        if not self.search_results: return # Guard against no results

        self.current_search_index = (self.current_search_index - 1 + len(self.search_results)) % len(self.search_results)
        self._jump_to_search_result()
    
    def _jump_to_search_result(self):
        """Updates the main previewer to show the currently selected search result."""
        if not self.search_results or self.current_search_index == -1: return

        target_index = self.search_results[self.current_search_index]
        if self.current_preview_index != target_index:
            self.current_preview_index = target_index
        # Always call update to refresh labels (e.g., search count X of Y)
        self._update_previewer_ui()
    def _toggle_open_decompile_on_complete(self):
        """Handles the 'Open Decompile Folder on Completion' menu action."""
        self.open_decompile_on_complete = self.open_decompile_on_complete_action.isChecked()
        self._save_settings()
        status = 'Enabled' if self.open_decompile_on_complete else 'Disabled'
        self._log_message(f"[INFO] Setting 'Open Decompile Folder on Completion' is now {status}.")
    
    def _toggle_open_compile_on_complete(self):
        """Handles the 'Open Compile Folder on Completion' menu action."""
        self.open_compile_on_complete = self.open_compile_on_complete_action.isChecked()
        self._save_settings()
        status = 'Enabled' if self.open_compile_on_complete else 'Disabled'
        self._log_message(f"[INFO] Setting 'Open Compile Folder on Completion' is now {status}.")
    def _on_info_line_received(self, raw_line, filename):
        '''
A lightweight slot that buffers raw data from the worker and updates the
previewer data structure in near real-time.
'''
        # Add the raw message, prefixed for correct formatting, to the log buffer.
        # The actual logging to GUI/file is handled by the batched processor.
        self.log_message_buffer.append(f"[DATA] {raw_line}")

        if filename and self.info_cache_dir:
            # This is a 'Texture:' line, which starts a new record.
            image_path = os.path.join(self.info_cache_dir, filename)
            new_record = {'path': image_path, 'filename': filename, 'dimensions': 'N/A', 'format': 'N/A', 'size': 0}

            # --- UPGRADE: Get and store file size ---
            if os.path.exists(image_path):
                try:
                    new_record['size'] = os.path.getsize(image_path)
                except OSError:
                    pass # Keep size as 0 on error

            self.preview_images.append(new_record)

        elif self.preview_images:
            # This is a detail line (e.g., "Dimensions:"), add it to the last record.
            if "Dimensions:" in raw_line:
                try:
                    dims = raw_line.split("Dimensions:", 1)[1].strip()
                    self.preview_images[-1]['dimensions'] = dims
                except IndexError:
                    pass
            elif "Format:" in raw_line:
                try:
                    fmt = raw_line.split("Format:", 1)[1].strip()
                    self.preview_images[-1]['format'] = fmt
                except IndexError:
                    pass
    def _process_log_message_buffer(self):
        """
Processes the entire log buffer in a single, efficient operation to prevent UI freezes and race conditions.
"""
        if not self.log_message_buffer:
            self._reset_ui_after_task() # Ensure reset even if buffer is empty
            return

        with self.log_lock:
            # Step 1: Format all buffered messages into a single HTML block and a plain text block for the file.
            all_html = []
            all_plain = []

            while self.log_message_buffer:
                message = self.log_message_buffer.popleft()
                html, plain = self._format_log_message(message)
                all_html.append(html)
                all_plain.append(plain)

            # Step 2: Perform a single, efficient write to the log file.
            self.file_logger.write("\n".join(all_plain))

            # Step 3: Perform a single, efficient update to the UI.
            if hasattr(self, 'log_widget') and all_html:
                self.log_widget.append("<br>".join(all_html))
                # --- REGRESSION FIX: Force scroll to the bottom ---
                scrollbar = self.log_widget.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())

        # Step 4: Now that all work is truly complete, log the final message and reset the UI.
        self._log_message("[INFO] ----- Log Rendering Complete -----")
        self._reset_ui_after_task()
    def _format_log_message(self, message: str) -> tuple[str, str]:
        """
    Centralized log message formatter. Takes a raw string and returns (html, plain_text).
    This is the single source of truth for log appearance.
    """
        now_str = datetime.now().strftime("%H:%M:%S")

        # Capitalize drive letter for any Windows path in the message
        if sys.platform == "win32":
            message = re.sub(r'\b([a-z]):\\', lambda m: m.group(1).upper() + ':\\', message)

        if message.startswith(("[INFO]", ">>>", "******************", "-----")):
            content = message.strip("*- ")
            if message.startswith(("[INFO]", ">>>")):
                content = message[message.find(" ") + 1:].strip()

            # Check for the special header format FIRST, before any other processing.
            if "-----" in content:
                display_message = f"[INFO] {content}"
                html_message = f'<span style="color:{self.COLOR_GREEN};"><b>{display_message}</b></span>'
                return html_message, display_message

            # Normalize content for regular INFO messages
            if "... [Complete]" in content: content = content.replace("... [Complete]", " [Complete]")
            if "... Complete" in content: content = content.replace("... Complete", " [Complete]")
            if "...[Passed]" in content: content = content.replace("...[Passed]", ": [Passed]")
            if "...Passed]" in content: content = content.replace("...Passed]", ": [Passed]")
            if "[Started]." in content: content = content.replace("[Started].", "[Started]")

            display_message = f"[INFO] {content}"
            html_content = display_message.replace("[INFO] ", "")
            html_content = html_content.replace("[Complete]", f'<span style="color:{self.COLOR_GREEN};">[Complete]</span>')
            html_content = html_content.replace("[Started]", f'<span style="color:{self.COLOR_GREEN};">[Started]</span>')
            html_content = html_content.replace("[Passed]", f'<span style="color:{self.COLOR_GREEN};">[Passed]</span>')
            html_content = html_content.replace("...Failed", f'... <span style="color:{self.COLOR_RED};">[Failed]</span>')
            html_content = re.sub(r'(v\d+\.\d+\.\d+)', f'<span style="color:{self.COLOR_NUMERIC};">\\1</span>', html_content)
            html_content = re.sub(r'(\d{{2}}:\d{{2}}:\d{{2}})', f'<span style="color:{self.COLOR_NUMERIC};">\\1</span>', html_content)
            html_content = re.sub(r'("Shift" > "Alt" > "D")', f'<span style="color:{self.COLOR_NUMERIC};">\\1</span>', html_content)
            html_content = re.sub(r'(KittmasterRepo repository)', f'<span style="color:{self.COLOR_NUMERIC};">\\1</span>', html_content)
            html_message = f'<span style="color:{self.COLOR_CYAN};"><b>[INFO]</b></span> <span style="color:{self.COLOR_DEFAULT};">{html_content}</span>'
            return html_message, display_message

        elif message.startswith(("[ERROR]", "ERROR:")):
            content_start_index = message.find(':')
            if content_start_index == -1: content_start_index = message.find(']')
            content = message[content_start_index + 1:].strip()
            display_message = f"[ERROR] {content}"
            html_message = f'<span style="color:{self.COLOR_RED};"><b>[ERROR]</b></span> <span style="color:{self.COLOR_DEFAULT};">{content}</span>'
            return html_message, display_message

        elif message.startswith("[WARN]"):
            content = message[message.find("]") + 1:].strip()
            display_message = f"[WARN] {content}"
            html_message = f'<span style="color:{self.COLOR_YELLOW};"><b>[WARN]</b></span> <span style="color:{self.COLOR_DEFAULT};">{content}</span>'
            return html_message, display_message

        elif message.startswith("[DATA]"):
            content = message[message.find("]") + 1:].strip()
            plain_content = content.replace(": Installed", ": [Installed]").replace(" Stable", " [Stable]")
            display_message = f"[DATA] {plain_content}"
            html_content = plain_content.replace("[No Data]", f'<span style="color:{self.COLOR_NUMERIC};">[No Data]</span>')
            html_content = html_content.replace("[ERROR] Not Installed", f'<span style="color:{self.COLOR_RED};">[ERROR] Not Installed</span>')
            html_content = html_content.replace("[Installed]", f'<span style="color:{self.COLOR_GREEN};">[Installed]</span>')
            html_content = html_content.replace("[Stable]", f'<span style="color:{self.COLOR_GREEN};">[Stable]</span>')
            html_content = re.sub(r'(v\d+(?:\.\d+)*)', f'<span style="color:{self.COLOR_NUMERIC};">\\1</span>', html_content)
            html_content = re.sub(r'(\d+KB)', f'<span style="color:{self.COLOR_NUMERIC};">\\1</span>', html_content)
            html_content = re.sub(r'(\d{{2}}-\d{{2}}-\d{{4}})', f'<span style="color:{self.COLOR_NUMERIC};">\\1</span>', html_content)
            html_message = f'<span style="color:{self.COLOR_MAGENTA};"><b>[DATA]</b></span> <span style="color:{self.COLOR_DEFAULT};">{html_content}</span>'
            return html_message, display_message

        elif message.startswith("[LOAD]"):
            content = message[message.find("]") + 1:].strip()
            display_message = f"[LOAD] {content}"
            html_message = f'<span style="color:{self.COLOR_ORANGE};"><b>[LOAD]</b></span> <span style="color:{self.COLOR_DEFAULT};">{content}</span>'
            return html_message, display_message

        else:
            # Treat messages without a prefix as INFO messages.
            display_message = f"[INFO] {message}"
            html_message = f'<span style="color:{self.COLOR_CYAN};"><b>[INFO]</b></span> <span style="color:{self.COLOR_DEFAULT};">{message}</span>'
            return html_message, display_message
    def _on_search_criterion_changed(self, index):
        """Swaps the search input widget based on the selected criterion."""
        criterion = self.search_criteria_combo.itemText(index)
        if criterion == "Dimensions":
            self.search_input_stack.setCurrentWidget(self.dimensions_filter_combo)
        else:
            self.search_input_stack.setCurrentWidget(self.image_jump_to_edit)
        self._reset_search_state()
    
    def _populate_dimensions_filter(self):
        """Populates the dimensions combo box with unique dimensions from the image data."""
        self.dimensions_filter_combo.blockSignals(True)
        self.dimensions_filter_combo.clear()
        self.dimensions_filter_combo.addItem("-- Filter by Dimensions --")

        if self.preview_images:
            all_dims = [img.get('dimensions', 'N/A') for img in self.preview_images]
            def sort_key(dim_str):
                try:
                    width, height = map(int, dim_str.split('x'))
                    return (width, height)
                except (ValueError, AttributeError):
                    return (99999, 99999)

            unique_dims = sorted(list(set(d for d in all_dims if d != 'N/A')), key=sort_key)
            self.dimensions_filter_combo.addItems(unique_dims)
            self.dimensions_filter_combo.setEnabled(True)
        else:
            self.dimensions_filter_combo.setEnabled(False)

        self.dimensions_filter_combo.blockSignals(False)
    def _toggle_open_pdf_on_complete(self):
        """Handles the 'Open PDF Report on Completion' menu action."""
        self.open_pdf_on_complete = self.open_pdf_on_complete_action.isChecked()
        self._save_settings()
        status = 'Enabled' if self.open_pdf_on_complete else 'Disabled'
        self._log_message(f"[INFO] Setting 'Open PDF Report on Completion' is now {status}.")
    def _open_log_file(self):
        """Opens the log file in the default text editor."""
        self._log_message("[INFO] Opening log file from application data folder.")
        log_path = self.file_logger.log_path
        if os.path.exists(log_path):
            try:
                if sys.platform == "win32":
                    os.startfile(log_path)
                else:
                    webbrowser.open("file://" + os.path.abspath(log_path))
            except Exception as e:
                self._log_message(f"[ERROR] Could not open log file: {e}")
        else:
            self._log_message(f"[WARN] Log file not found at: {log_path}")
    def _clear_gallery(self):
        """Clears the image previewer gallery and resets its state."""
        self.preview_images.clear()
        self.current_preview_index = -1
        self._reset_search_state()
        self._populate_dimensions_filter()
        self._update_previewer_ui()
    class UpdateDialog(QDialog):
        def __init__(self, version, changelog_html, parent=None):
            super().__init__(parent)

            #self.setWindowTitle("Update Available!")
            self.setWindowTitle(f"{APP_TITLE} - Update Available!")
            self.setWindowIcon(parent.app_icon if parent else QIcon())
            self.setMinimumWidth(600)

            main_layout = QVBoxLayout(self)
            main_layout.setSpacing(10)

            # --- Top Section (Icon + Title) ---
            top_container_widget = QWidget()
            top_container_widget.setMinimumHeight(80) 

            container_v_layout = QVBoxLayout(top_container_widget)
            container_v_layout.setContentsMargins(0, 0, 0, 0)

            content_h_layout = QHBoxLayout()

            icon_label = QLabel()

            # --- PATCH START: Use a contextual update icon instead of the brand logo ---
            update_icon = qta.icon('fa5s.cloud-download-alt', color='#88c0d0') # Use theme accent color
            icon_pixmap = update_icon.pixmap(QSize(64, 64))
            # --- PATCH END ---

            icon_label.setPixmap(icon_pixmap)
            # The label size MUST match the pixmap size to prevent jagged re-scaling
            icon_label.setFixedSize(70, 70)

            title_label = QLabel("A new version is available!")
            title_label.setStyleSheet("font-size: 14pt;")

            content_h_layout.addWidget(icon_label)
            content_h_layout.addSpacing(15)
            content_h_layout.addWidget(title_label)
            content_h_layout.addStretch()

            container_v_layout.addStretch(1)
            container_v_layout.addLayout(content_h_layout)
            container_v_layout.addStretch(1)

            main_layout.addWidget(top_container_widget)

            # --- Scrollable Content Section ---
            scroll_area = QScrollArea(self)
            scroll_area.setWidgetResizable(True)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll_area.setStyleSheet("QScrollArea { border: 1px solid #4c566a; border-radius: 3px; background-color: #3b4252; } QWidget { background-color: #3b4252; }")

            scroll_area.setMaximumHeight(400) 

            scroll_content_widget = QWidget()
            scroll_layout = QVBoxLayout(scroll_content_widget)
            scroll_layout.setContentsMargins(15, 15, 15, 15)

            informative_content = f"""
    <b>Version: {version}</b>
    <br><br>
    <b>Changes:</b><br>
    {changelog_html}
"""
            content_label = QLabel(informative_content.strip())
            content_label.setTextFormat(Qt.TextFormat.RichText)
            content_label.setWordWrap(True)
            content_label.setAlignment(Qt.AlignmentFlag.AlignTop)
            content_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)


            scroll_layout.addWidget(content_label)
            scroll_content_widget.setLayout(scroll_layout)
            scroll_area.setWidget(scroll_content_widget)

            main_layout.addWidget(scroll_area)

            # --- Bottom Question and Buttons ---
            question_label = QLabel("Would you like to download and update now?")
            question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(question_label)

            button_box = QHBoxLayout()
            yes_button = QPushButton("Yes")
            yes_button.setMinimumSize(100, 30)
            yes_button.clicked.connect(self.accept)

            no_button = QPushButton("No")
            no_button.setMinimumSize(100, 30)
            no_button.clicked.connect(self.reject)

            button_box.addStretch()
            button_box.addWidget(yes_button)
            button_box.addWidget(no_button)
            button_box.addStretch()

            main_layout.addLayout(button_box)
    def _start_update_check(self, url, manual):
        """Core logic to start the update worker with a given URL after a pre-emptive network check."""
        # --- PRE-EMPTIVE NETWORK CHECK ---
        if not self._is_network_available():
            err_msg = "No internet connection detected."
            self._log_message(f"[ERROR] Update check failed: {err_msg}")
            if manual:
                # We can call the error handler directly because we know the cause.
                self._on_update_check_error(err_msg, manual=True)
            return # Abort the update check entirely.

        if self.update_thread is not None:
            self._log_message("[WARN] An update check is already in progress.")
            return
        if any(
            thread is not None
            for thread in (self.decompile_thread, self.compile_thread, self.installer_thread)
        ):
            self._log_message("[WARN] Cannot check for updates, another critical task is running.")
            return

        self._log_message(f'[INFO] {datetime.now().strftime("%H:%M:%S")}: Checking for update from {url}. [Started]')
        if manual:
            self._log_message("[INFO] Manually checking for updates.")
            self.status_label.setText("Checking for updates...")
        else:
            #checking_icon = qta.icon('fa5s.cloud-download-alt', color='#D4AF37') # Soft gold color
            checking_icon = qta.icon('mdi.cloud-search-outline', color=self.COLOR_SOFT_GOLD)  # Soft gold color
            self._show_tray_message(APP_TITLE, "Checking for updates...", checking_icon)

        self.update_thread = QThread(self)
        self.update_worker = UpdateCheckWorker(url)
        self.update_worker.moveToThread(self.update_thread)
        self.update_worker.finished.connect(functools.partial(self._on_update_check_finished, manual=manual))
        self.update_worker.error.connect(functools.partial(self._on_update_check_error, manual=manual))
        self.update_thread.started.connect(self.update_worker.run)
        self.update_thread.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.start()
    def _check_for_updates_dev(self):
        """Prompts the user for a custom version.json URL and starts the update check."""

        dialog = QInputDialog(self)
        dialog.setWindowTitle("Developer Update Check")
        dialog.setLabelText("Enter the full URL to the version.json file for testing:")
        dialog.setTextValue(self.dev_update_url)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)

        # Find and style the buttons for consistency
        buttons = dialog.findChildren(QPushButton)
        for button in buttons:
            button.setMinimumSize(100, 30)

        ok = dialog.exec()
        url = dialog.textValue()

        if ok and url:
            self.dev_update_url = url
            self._save_settings()
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url
                self._log_message(f"[INFO] Prepended 'http://' to dev URL: {url}")
            self._start_update_check(url, manual=True)
        else:
            self._log_message("[INFO] Developer update check cancelled.")
    def _on_download_error(self, error_message):
        """A thread-safe slot to handle and display download errors."""
        self._log_message(f"[ERROR] Download failed: {error_message}")
        if self.update_progress_dialog:
            self.update_progress_dialog.close()

        QMessageBox.critical(self, "Download Error", f"Failed to download the update package.\n\nDetails: {error_message}")

        # Clean up the worker and thread
        if self.download_thread:
            self.download_thread.quit()
            self.download_thread.wait()
        self.download_thread = None
        self.download_worker = None
        self._reset_ui_after_task()
    def _reset_ui_state(self):
        '''Resets UI controls and status label without touching thread handles.'''
        self._set_ui_task_active(False)
        self._update_button_states()
        QTimer.singleShot(2000, self._finalize_ui_reset)
    def _on_dev_mode_toggled(self, checked):
        '''Handles the toggling of the dev mode checkbox.'''
        self.dev_update_action.setVisible(checked)
        status = "activated" if checked else "deactivated"
        self._log_message(f"[INFO] Dev mode has been {status}.")
    def _on_dupecheck_toggled(self, checked):
        '''Handles the toggling of the dupecheck checkbox.'''
        status = "enabled" if checked else "disabled"
        self._log_message(f"[INFO] Dupecheck has been {status}.")
    def _is_network_available(self):
        """
    Checks for a live internet connection by attempting to connect to a reliable
    external server with a very short timeout. Returns True if successful, False otherwise.
    """
        # Use a reliable, common DNS server for the check.
        # Port 53 is for DNS, which is a good indicator of general internet access.
        host = "8.8.8.8"
        port = 53
        timeout = 2  # Seconds
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except (socket.error, TimeoutError) as ex:
            self._log_message(f"[INFO] Network availability check failed: {ex}")
            return False
    def _toggle_compile_decompile_position(self):
        """Swaps the compile and decompile group boxes based on the menu checkbox state."""
        self.decompile_on_top = not self.swap_groups_action.isChecked()
        self._save_settings()
        self._log_message(f"[INFO] Compile/Decompile group position swapped. Compile mode is now on {'top' if not self.decompile_on_top else 'bottom'}.")

        # The widgets are parented to the layout, which manages their memory.
        # We just need to re-order them. We can do this by taking them out and
        # re-inserting them at specific positions. The logo is at index 0.

        # Taking widgets out of a layout doesn't delete them, just removes them from view management.
        self.left_panel_layout.removeWidget(self.decompile_box)
        self.left_panel_layout.removeWidget(self.compile_box)
        self.left_panel_layout.removeWidget(self.separator_between_modes)

        # Re-add them in the new order. insertWidget adds them back under layout control.
        # Index 1 is right after the logo.
        if self.decompile_on_top:
            self.left_panel_layout.insertWidget(1, self.decompile_box)
            self.left_panel_layout.insertWidget(2, self.separator_between_modes)
            self.left_panel_layout.insertWidget(3, self.compile_box)
        else:
            self.left_panel_layout.insertWidget(1, self.compile_box)
            self.left_panel_layout.insertWidget(2, self.separator_between_modes)
            self.left_panel_layout.insertWidget(3, self.decompile_box)
    def _update_runtime_menu_actions_state(self):
        """Updates the enabled state and tooltips of runtime-related menu items."""
        if self.update_action:
            self.update_action.setEnabled(self.vcredist_checks_passed)
            if self.vcredist_checks_passed:
                self.update_action.setToolTip("Manually check for new application updates")
            else:
                self.update_action.setToolTip("Disabled. Requires the VC++ Runtimes to be installed.")

        if self.install_runtimes_action:
            self.install_runtimes_action.setEnabled(not self.vcredist_checks_passed)
            if self.vcredist_checks_passed:
                self.install_runtimes_action.setToolTip("Runtimes are already installed.")
            else:
                self.install_runtimes_action.setToolTip("Install the required Visual C++ 2010 Runtimes (requires administrator).")

        if self.reinstall_runtimes_action:
            self.reinstall_runtimes_action.setEnabled(self.vcredist_checks_passed)
            if self.vcredist_checks_passed:
                self.reinstall_runtimes_action.setToolTip("Force a reinstallation of the runtimes (for repair).")
            else:
                self.reinstall_runtimes_action.setToolTip("Runtimes must be installed first before they can be reinstalled.")
    def _zoom_out(self):
        """Reduces the zoom level of the displayed image."""
        if not self.preview_images or self.current_preview_index == -1:
            return
        current_pixmap = self.image_display_label.pixmap()
        if current_pixmap and not current_pixmap.isNull():
            # Get the current size of the label
            label_size = self.image_display_label.size()
            # Calculate a smaller size (e.g., 80% of current width/height)
            new_width = int(current_pixmap.width() * 0.8)
            new_height = int(current_pixmap.height() * 0.8)
            # Ensure minimum size to avoid disappearing
            new_width = max(new_width, 10)
            new_height = max(new_height, 10)
            scaled_pixmap = current_pixmap.scaled(new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_display_label.setPixmap(scaled_pixmap)
            self.is_image_zoomed = True
            self.btn_fit_to_window.setEnabled(True)
            self.current_zoom_level *= 0.8
            self._update_zoom_overlay()
    def _zoom_in(self):
        """Increases the zoom level of the displayed image."""
        if not self.preview_images or self.current_preview_index == -1:
            return
        current_pixmap = self.image_display_label.pixmap()
        if current_pixmap and not current_pixmap.isNull():
            # Get the current size of the label
            label_size = self.image_display_label.size()
            # Calculate a larger size (e.g., 120% of current width/height)
            new_width = int(current_pixmap.width() * 1.2)
            new_height = int(current_pixmap.height() * 1.2)
            # Cap the size to avoid excessive memory usage
            max_size = min(label_size.width() * 2, label_size.height() * 2)
            new_width = min(new_width, max_size)
            new_height = min(new_height, max_size)
            scaled_pixmap = current_pixmap.scaled(new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_display_label.setPixmap(scaled_pixmap)
            self.is_image_zoomed = True
            self.btn_fit_to_window.setEnabled(True)
            self.current_zoom_level *= 1.2
            self._update_zoom_overlay()
    def _fit_to_window(self):
        """Resets the image to fit within the display label's boundaries. Uses safe loading via _update_previewer_ui."""
        # We delegate to the robust _update_previewer_ui by resetting the zoom state.
        self.is_image_zoomed = False
        self.current_zoom_level = 1.0
        self._update_previewer_ui()
    def _update_zoom_overlay(self):
        """Updates the zoom level overlay's text and visibility."""
        if not hasattr(self, 'zoom_level_label'):
            return

        # The overlay should be visible whenever an image is displayed.
        image_is_visible = bool(self.preview_images and self.current_preview_index != -1)
        self.zoom_level_label.setVisible(image_is_visible)

        if image_is_visible:
            level = self.current_zoom_level

            if level < 0.1:
                zoom_text = f"{level:.2f}x"
            elif level < 10:
                zoom_text = f"{level:.1f}x"
            else:
                zoom_text = f"{round(level)}x"

            self.zoom_level_label.setText(zoom_text)
    def _handle_pdf_export_request(self, export_type: str):
        """Prepares data and initiates a PDF export based on the user's choice."""
        if any(t is not None for t in (self.decompile_thread, self.compile_thread, self.info_thread, self.installer_thread, self.pdf_export_thread)):
            self._log_message("[WARN] Another task is already in progress. Please wait.")
            return

        if not self.preview_images:
            self._log_message("[WARN] No image information available to export.")
            return

        data_to_export = []
        export_description = ""

        if export_type == "ALL":
            data_to_export = self.preview_images
            export_description = f"{len(data_to_export)} total images"
        elif export_type == "FILTERED":
            if not self.search_results:
                self._log_message("[WARN] No active search filter to export.")
                return
            data_to_export = [self.preview_images[i] for i in self.search_results]
            export_description = f"{len(data_to_export)} filtered images"
        elif export_type == "SELECTED":
            if self.current_preview_index != -1:
                data_to_export = [self.preview_images[self.current_preview_index]]
                export_description = "the selected image"
            else:
                self._log_message("[WARN] No image is currently selected to export.")
                return

        if not data_to_export:
            self._log_message("[WARN] No data was selected for export.")
            return

        self._start_pdf_export_worker(data_to_export, export_description)
    
    def _start_pdf_export_worker(self, image_data: list, export_description: str):
        """Gets a save path from the user and starts the PDF export worker thread."""
        base_name = os.path.basename(self.decompile_input_file)
        pdf_name = os.path.splitext(base_name)[0] + "_Report.pdf"

        last_path = self._get_config_path('decompileoutput')
        save_path, _ = QFileDialog.getSaveFileName(self, "Save PDF Report", os.path.join(last_path, pdf_name), "PDF Files (*.pdf)")

        if not save_path:
            self._log_message("[INFO] PDF export cancelled by user.")
            return

        self._log_message(f"[INFO] ----- Starting PDF Export of {export_description} to {os.path.basename(save_path)} -----")
        self.status_label.setText("Exporting to PDF... Please wait.")
        self.progress_bar.setValue(0)
        self._set_ui_task_active(True)

        self.pdf_export_thread = QThread(self)
        self.pdf_export_worker = self.PdfExportWorker(image_data, save_path)
        self.pdf_export_worker.moveToThread(self.pdf_export_thread)

        self.pdf_export_worker.progress.connect(self._on_pdf_export_progress)
        self.pdf_export_thread.started.connect(self.pdf_export_worker.run)

        self.pdf_export_worker.finished_with_path.connect(self._on_pdf_export_finished)
        self.pdf_export_worker.error.connect(lambda msg: self._on_pdf_export_finished(msg, pdf_path=None))

        self.pdf_export_worker.finished_with_path.connect(self.pdf_export_thread.quit)
        self.pdf_export_worker.error.connect(self.pdf_export_thread.quit)
        self.pdf_export_worker.finished_with_path.connect(self.pdf_export_worker.deleteLater)
        self.pdf_export_thread.finished.connect(self.pdf_export_thread.deleteLater)

        self.pdf_export_thread.start()
    
    def _show_image_preview_context_menu(self, position):
        """Creates and shows a context menu for the image previewer."""
        if not self.preview_images or self.current_preview_index == -1:
            return

        menu = QMenu()
        copy_image_action = menu.addAction(qta.icon('fa5s.copy'), "Copy Image to Clipboard")
        copy_filename_action = menu.addAction(qta.icon('fa5s.quote-left'), "Copy Filename")
        open_location_action = menu.addAction(qta.icon('fa5s.folder-open'), "Open File Location")

        copy_image_action.triggered.connect(self._copy_preview_image_to_clipboard)
        copy_filename_action.triggered.connect(self._copy_preview_filename_to_clipboard)
        open_location_action.triggered.connect(self._open_preview_image_location)

        menu.exec(self.image_display_label.mapToGlobal(position))
    
    def _copy_preview_image_to_clipboard(self):
        """Copies the currently displayed preview image to the system clipboard."""
        if self.preview_images and self.current_preview_index != -1:
            image_path = self.preview_images[self.current_preview_index]['path']
            if os.path.exists(image_path):
                image = QImage(image_path)
                if not image.isNull():
                    QApplication.clipboard().setImage(image)
                    self._log_message(f"[INFO] Copied image '{os.path.basename(image_path)}' to clipboard.")
                else:
                    self._log_message(f"[ERROR] Failed to load image for clipboard: {image_path}")
            else:
                self._log_message(f"[WARN] Cannot copy image, file not found: {image_path}")
    
    def _copy_preview_filename_to_clipboard(self):
        """Copies the filename of the currently displayed image to the clipboard."""
        if self.preview_images and self.current_preview_index != -1:
            filename = self.preview_images[self.current_preview_index]['filename']
            QApplication.clipboard().setText(filename)
            self._log_message(f"[INFO] Copied filename '{filename}' to clipboard.")
    
    def _open_preview_image_location(self):
        """Opens the temporary cache folder and highlights the current image."""
        if self.preview_images and self.current_preview_index != -1:
            image_path = os.path.normpath(self.preview_images[self.current_preview_index]['path'])
            if os.path.exists(image_path):
                self._log_message(f"[INFO] Opening file location for: {os.path.basename(image_path)}")
                if sys.platform == "win32":
                    subprocess.run(['explorer', '/select,', image_path])
                else:
                    # Fallback for non-Windows: just open the containing folder.
                    folder = os.path.dirname(image_path)
                    webbrowser.open("file://" + os.path.abspath(folder))
            else:
                self._log_message(f"[WARN] Cannot open location, file not found: {image_path}")
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Formats a size in bytes into a human-readable string (KB, MB, etc.)."""

        if size_bytes <= 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"
    def _scan_cache_dir_fallback(self):
        """Scans the info cache directory for images. Safe version: No QImageReader checks in loop."""
        if not self.info_cache_dir or not os.path.exists(self.info_cache_dir):
            return

        if self.preview_images:
            return

        self._log_message("[WARN] TextureCompiler returned no text data. Scanning cache directory directly...")

        found_count = 0
        try:
            # Just walk and trust extensions for speed and stability.
            for root, dirs, files in os.walk(self.info_cache_dir):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        image_path = os.path.join(root, file)

                        # Create record with placeholders. Real data loaded when viewed.
                        new_record = {
                            'path': image_path, 
                            'filename': file, 
                            'dimensions': 'N/A', 
                            'format': os.path.splitext(file)[1][1:].upper(), 
                            'size': 0
                        }

                        try:
                            if os.path.exists(image_path):
                                new_record['size'] = os.path.getsize(image_path)
                        except Exception:
                            pass

                        self.preview_images.append(new_record)
                        found_count += 1

            if found_count > 0:
                self._log_message("[INFO] Fallback scan found {} images.".format(found_count))
                self.preview_images.sort(key=lambda x: x['filename'])
            else:
                self._log_message("[WARN] Fallback scan found no images in cache.")

        except Exception as e:
            self._log_message("[ERROR] Error during fallback scan: {}".format(e))
    def _handle_resize_timeout(self):
        """Called when the resize timer expires to auto-fit the image."""
        if self.preview_images and not self.is_image_zoomed:
            self._update_previewer_ui()
    
class ChangelogDialog(QDialog):

    def __init__(self, changelog_text, parent=None):
        super().__init__(parent)
        #self.setWindowTitle("Changelog")
        self.setWindowTitle(f"{APP_TITLE} - {APP_VERSION} - Changelog")
        self.setWindowIcon(parent.app_icon if parent else QIcon())
        self.setMinimumSize(600, 500)
        layout = QVBoxLayout(self)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml(changelog_text)
        text_edit.document().setDocumentMargin(0)
        layout.addWidget(text_edit)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        
class HelpDialog(QDialog):
    def __init__(self, markdown_file_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_TITLE} - {APP_VERSION} - Help")
        self.setMinimumSize(800, 600)
        self.resize(1250, 800)

        main_layout = QVBoxLayout(self)
        top_bar_layout = QHBoxLayout()

        # --- Navigation and Font Controls ---
        self.back_button = QPushButton(qta.icon('fa5s.arrow-left'), "")
        self.back_button.setToolTip("Back")
        self.back_button.setEnabled(False)
        self.forward_button = QPushButton(qta.icon('fa5s.arrow-right'), "")
        self.forward_button.setToolTip("Forward")
        self.forward_button.setEnabled(False)

        font_decrease_button = QPushButton(qta.icon('fa5s.search-minus'), "")
        font_decrease_button.setToolTip("Decrease Font Size")
        font_increase_button = QPushButton(qta.icon('fa5s.search-plus'), "")
        font_increase_button.setToolTip("Increase Font Size")
        font_reset_button = QPushButton(qta.icon('fa5s.home'), "")
        font_reset_button.setToolTip("Reset Font Size")

        top_bar_layout.addWidget(self.back_button)
        top_bar_layout.addWidget(self.forward_button)
        top_bar_layout.addSpacing(20)
        top_bar_layout.addWidget(font_decrease_button)
        top_bar_layout.addWidget(font_increase_button)
        top_bar_layout.addWidget(font_reset_button)
        top_bar_layout.addStretch()

        main_layout.addLayout(top_bar_layout)

        search_widget = self._create_search_bar()
        main_layout.addWidget(search_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, 1)

        self.toc_list_widget = QListWidget()
        # Changed from setFixedWidth to setMinimumWidth to allow resizing via splitter
        self.toc_list_widget.setMinimumWidth(100) 
        self.toc_list_widget.setWordWrap(True)

        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True)
        self.initial_font_size = self.content_browser.document().defaultFont().pointSize()
        self.content_browser.document().setDefaultStyleSheet("""
    h1 { color: #88c0d0; border-bottom: 2px solid #4c566a; padding-bottom: 5px; margin-top: 15px; }
    h2 { color: #81a1c1; border-bottom: 1px solid #434c5e; padding-bottom: 3px; margin-top: 10px; }
    h3 { color: #d8dee9; font-weight: bold; }
    p, li { color: #d8dee9; font-size: 11pt; }
    a { color: #88c0d0; text-decoration: none; }
    code { background-color: #434c5e; color: #ebcb8b; padding: 2px 4px; border-radius: 3px; font-family: Consolas, monospace; }
    pre > code { display: block; padding: 10px; border-radius: 5px; }
    blockquote {
        background-color: #3b4252; color: #eceff4; border-left: 5px solid #5e81ac;
        padding: 10px; margin-left: 0px;
    }
""")

        splitter.addWidget(self.toc_list_widget)
        splitter.addWidget(self.content_browser)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 990])

        self._load_and_process_markdown(markdown_file_path)

        # --- Connect Signals ---
        self.toc_list_widget.itemClicked.connect(self._on_toc_item_clicked)
        self.search_input.returnPressed.connect(self._find_next)
        self.search_input.textChanged.connect(self._filter_toc)
        self.clear_search_button.clicked.connect(self.search_input.clear)
        self.back_button.clicked.connect(self.content_browser.backward)
        self.forward_button.clicked.connect(self.content_browser.forward)
        self.content_browser.backwardAvailable.connect(self.back_button.setEnabled)
        self.content_browser.forwardAvailable.connect(self.forward_button.setEnabled)
        font_decrease_button.clicked.connect(lambda: self._change_font_size(-1))
        font_increase_button.clicked.connect(lambda: self._change_font_size(1))
        font_reset_button.clicked.connect(self._reset_font_size)

    def _create_search_bar(self):
        search_widget = QWidget()
        layout = QHBoxLayout(search_widget)
        layout.setContentsMargins(0, 5, 0, 5)

        label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter TOC or find text...")
        self.search_input.setToolTip("Filter the table of contents or enter text to find in the document.")

        self.clear_search_button = QPushButton(qta.icon('fa5s.times'), "")
        self.clear_search_button.setToolTip("Clear Search")

        find_prev_button = QPushButton("Previous")
        find_prev_button.setFixedWidth(80)
        find_prev_button.setToolTip("Find the previous occurrence of the search text.")
        find_prev_button.clicked.connect(self._find_previous)

        find_next_button = QPushButton("Next")
        find_next_button.setFixedWidth(80)
        find_next_button.setToolTip("Find the next occurrence of the search text.")
        find_next_button.clicked.connect(self._find_next)

        layout.addWidget(label)
        layout.addWidget(self.search_input, 1)
        layout.addWidget(self.clear_search_button)
        layout.addWidget(find_prev_button)
        layout.addWidget(find_next_button)

        return search_widget

    def _load_and_process_markdown(self, file_path):

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                md_text = f.read()

            md_extensions = ['toc', 'fenced_code', 'tables', 'attr_list']
            md = markdown.Markdown(extensions=md_extensions)
            html_content = md.convert(md_text)
            toc_html = getattr(md, 'toc', '')

            soup = BeautifulSoup(html_content, 'html.parser')
            doc = self.content_browser.document()
            dpr = self.devicePixelRatioF()

            for img_tag in soup.find_all('img'):
                if isinstance(img_tag, Tag):
                    src = img_tag.get('src')
                    if isinstance(src, str) and not src.startswith(('http', 'file:', 'data:')):
                        absolute_path = get_resource_path(src)
                        pixmap = QPixmap(absolute_path)
                        if not pixmap.isNull():
                            width_attr = img_tag.get('width')
                            
                            # --- PYLANCE-SAFE CONVERSION FIX ---
                            try:
                                logical_width = int(str(width_attr))
                            except (ValueError, TypeError):
                                # Fallback if width attribute is missing, None, or not a valid number
                                logical_width = pixmap.width() / dpr
                            # --- END FIX ---
                            
                            target_width = int(logical_width * dpr)
                            scaled_pixmap = pixmap.scaledToWidth(target_width, Qt.TransformationMode.SmoothTransformation)
                            scaled_pixmap.setDevicePixelRatio(dpr)
                            
                            resource_name = Path(absolute_path).as_uri()
                            buffer = QBuffer()
                            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                            scaled_pixmap.save(buffer, "PNG")
                            doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(resource_name), buffer.data())
                            
                            img_tag['src'] = resource_name

            final_html = str(soup)
            self.content_browser.setHtml(final_html)
            self._populate_toc(toc_html)

        except FileNotFoundError:
            self.content_browser.setHtml(f"<h1>Error</h1><p>Help file not found at: {file_path}</p>")
        except Exception as e:
            self.content_browser.setHtml(f"<h1>Error</h1><p>Could not process help file: {e}<br><pre>{traceback.format_exc()}</pre></p>")
    def _populate_toc(self, toc_html):

        if not toc_html:
            return

        soup = BeautifulSoup(toc_html, 'html.parser')

        for li in soup.find_all('li'):
            if isinstance(li, Tag):
                a = li.find('a')
                if isinstance(a, Tag) and 'href' in a.attrs:
                    text, anchor = a.text, a['href'][1:]
                    level = len(li.find_parents(['ul', 'ol'])) - 1

                    item = QListWidgetItem(self.toc_list_widget)
                    item.setText("{}{}".format('    ' * level, text))
                    item.setData(Qt.ItemDataRole.UserRole, anchor)

    def _find_next(self):
        query = self.search_input.text()
        if query:
            self.content_browser.find(query)

    def _find_previous(self):
        query = self.search_input.text()
        if query:
            self.content_browser.find(query, QTextDocument.FindFlag.FindBackward)

    def _on_toc_item_clicked(self, item):
        anchor = item.data(Qt.ItemDataRole.UserRole)
        if anchor:
            self.content_browser.setSource(QUrl(f"#{anchor}"))
    def _filter_toc(self, text):
        filter_text = text.lower()
        for i in range(self.toc_list_widget.count()):
            item = self.toc_list_widget.item(i)
            item_text = item.text()
            item.setHidden(filter_text not in item_text.lower())

    def _change_font_size(self, delta):
        doc = self.content_browser.document()
        font = doc.defaultFont()
        current_size = font.pointSize()
        new_size = max(8, current_size + delta)
        font.setPointSize(new_size)
        doc.setDefaultFont(font)

    def _reset_font_size(self):
        if hasattr(self, 'initial_font_size'):
            doc = self.content_browser.document()
            font = doc.defaultFont()
            font.setPointSize(self.initial_font_size)
            doc.setDefaultFont(font)



if __name__ == "__main__":
    # Set application name and organization name
    app = QApplication(sys.argv)
    # Removes the default limit (128MB/256MB) on image loading to allow large filmstrips
    QImageReader.setAllocationLimit(0)     
    app.setStyle("Fusion")
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Kittmaster's Kodi TextureTool")
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("KodiTextureTool")

    # 1. Get the correct, absolute path to the SVG using your helper function
    checkmark_path = get_resource_path('assets/checkmark.svg').replace('\\', '/')

    # 2. Your stylesheet with ALL CSS braces escaped ({{ and }})
    stylesheet = """

/* MENU_FIX_APPLIED_v1.7.4 */
        QWidget {{
            background-color: #2e3440;
            color: #d8dee9;
            font-size: 10pt;
        }}
        QMainWindow {{
            background-color: #2e3440;
        }}
        QMenuBar {{
            background-color: #2e3440;
            border-bottom: 1px solid #4c566a;
        }}
        QMenuBar::item {{
            color: #d8dee9; /* Fix for black text/icons on Win10/7 */
        }}
        QMenuBar::item:selected {{
            background-color: #434c5e;
        }}
        QMenu {{
            background-color: #3b4252;
            border: 1px solid #4c566a;
        }}
        QMenu::item {{
            color: #d8dee9; /* Fix for black text/icons on Win10/7 */
        }}
        QGroupBox {{
            font-weight: bold;
            border: 1px solid #4c566a;
            border-radius: 5px;
            margin-top: 1ex;
            padding-top: 8px;
        }}
        DropGroupBox[dragging="true"] {{
            border: 2px solid #88c0d0;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 3px;
        }}
        QFrame {{
            margin-top: 5px;
            margin-bottom: 5px;
        }}
        QPushButton {{
            background-color: #434c5e;
            color: #d8dee9; /* This ensures icons are white on Win10/7 */
            border: 1px solid #4c566a;
            padding: 5px;
            border-radius: 3px;
        }}
        QPushButton:hover {{
            background-color: #4c566a;
        }}
        QPushButton:pressed {{
            background-color: #81a1c1;
            color: #2e3440;
        }}
        QPushButton:disabled {{
            background-color: #3b4252;
            color: #4c566a;
        }}

        QCheckBox:disabled {{
            color: #4c566a;
        }}
        QMenu::item:selected {{
            background-color: #81a1c1;
            color: #2e3440;
        }}

        /* FINAL CHECKMARK FIX */
        QMenu::indicator {{
            width: 13px;
            height: 13px;
        }}
        QMenu::indicator:non-exclusive:checked {{
            image: url({checkmark_svg_path});
        }}

        QTextEdit#LogWidget {{
            background-color: #3b4252;
            border: 1px solid #4c566a;
            border-radius: 3px;
        }}
        QLabel#StatusLabel {{
            color: #88c0d0;
        }}
        QLabel[state="unselected"] {{
            color: #4c566a;
            font-style: italic;
        }}
        QLabel[state="selected"] {{
            color: #d8dee9;
            font-weight: bold;
        }}
        QProgressBar {{
            border: 1px solid #4c566a;
            border-radius: 3px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: #88c0d0;
        }}
        QPushButton:focus {{
            outline: none;
        }}

        /* --- NEW: Zoom Level Overlay --- */
        QLabel#ZoomLevelLabel {{
            background-color: rgba(46, 52, 64, 0.85); /* #2e3440 with 85% opacity */
            color: #d8dee9;
            font-weight: bold;
            font-size: 9pt;
            padding: 4px 8px;
            border-radius: 4px;
            margin: 8px; /* Give it some space from the corner */
        }}

        /* Custom Tooltip Style */
        QToolTip {{
            background-color: #3b4252;
            color: #d8dee9;
            border: 1px solid #4c566a;
            padding: 4px;
            border-radius: 3px;
        }}
"""

    # 3. Format the stylesheet string, injecting the correct path
    formatted_stylesheet = stylesheet.format(checkmark_svg_path=checkmark_path)

    # 4. Apply the fully formatted stylesheet
    app.setStyleSheet(formatted_stylesheet)

    window = TextureToolApp()
    window.show()
    sys.exit(app.exec())