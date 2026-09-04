"""
Kodi TextureTool - compiles and decompiles Kodi .xbt texture archives.

The authoritative version is APP_VERSION below. Nothing else in this file
declares one.

Q-01: two stray header comments used to sit here --
    # PATCHED_BY_SCRIPT_VERSION: v3.5.74 | Unlocks the Help Dialog TOC pane ...
    #.63 Filmstrip loads correctly now and able to render.
Neither was an application version. The first was a marker left by the earlier
patching tooling, naming *its own* version and the single patch it applied; the
second was a stray note. Together they made the file look like it declared a
v3.5.74 that never existed, which is most of why "which version is authoritative"
was an open question at all. Removed.
"""
# STR-01: this was twenty modules on four semicolon-joined lines. Removed here:
#   import datetime  -- immediately shadowed by `from datetime import datetime`
#                       below, so the module object was unreachable and
#                       `datetime.datetime` would have raised AttributeError.
#   import platform  -- unused. All 23 textual hits in this file are sys.platform.
#   import textwrap  -- became unused when SEC-03 removed the no-op dedent() call.
#   import gc        -- kept here, but it was ALSO re-imported inside
#                       PdfExportWorker.run; that shadowing import is gone.
import atexit
import base64
import configparser
import ctypes
import functools
import gc
import hashlib
import json
import math
import os
import platform
import re
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
import webbrowser
import winreg
from collections import deque
from ctypes import wintypes
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, quote

import markdown
import PySide6
import qtawesome as qta
from bs4 import BeautifulSoup
from bs4.element import Tag
from PySide6.QtGui import (QAction, QActionGroup, QFont, QIcon, QImage, QPixmap,
                           QImageReader, QTextDocument, QKeySequence, QShortcut)
from PySide6.QtCore import (Qt, QSize, QThread, QObject, Signal, QTimer, QSettings,
                            QUrl, QBuffer, QByteArray, QIODevice, QStandardPaths,
                            qVersion)
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFileDialog,
                               QFormLayout, QFrame, QGroupBox, QHBoxLayout,
                               QLabel, QMainWindow, QMenu, QMessageBox,
                               QProgressBar, QPushButton, QStyle, QSystemTrayIcon,
                               QTextEdit, QVBoxLayout, QWidget, QSplitter, QSlider,
                               QLineEdit, QComboBox, QStackedWidget, QGridLayout,
                               QListWidget, QTextBrowser, QScrollArea, QSizePolicy,
                               QListWidgetItem, QInputDialog)

# SEC-01: the module-scope line that used to sit here reassigned
#   ssl._create_default_https_context = ssl._create_unverified_context
# which disabled certificate verification for EVERY https request made by this
# process, including the update download that is then executed over the install
# directory. Removed. Do not reintroduce it. If a certificate genuinely fails to
# validate, fix the certificate or the trust store -- do not disable the check.

# ---- Global variables from original script
# ---- These will be managed as instance attributes in the main class
# Q-01: v3.2.0 is the new baseline. A MINOR bump rather than a patch because two
# changes are observable enough that users must read the notes -- operations that
# used to report success now report failure (BUG-14), and installs whose VC++
# check wrongly failed will start working (BUG-06). Not a MAJOR: nothing about
# how the tool is used changed, no format or config broke. MAJOR is reserved for
# a genuine break, such as replacing the C++ executables to fix BUG-15.
# Support for every version prior to v3.2.0 is closed off as of this release.
APP_VERSION = "v3.2.0"
APP_TITLE = "Kodi TextureTool"
APP_AUTHOR = "Chris Bertrand"

# BUG-08: this was `datetime.now()`, evaluated at import, so the About dialog
# reported when the *user launched the app*, not when the build was produced.
# A release script may stamp BUILD_DATE_STAMP below; otherwise the date is taken
# from the artefact's own mtime. Never fabricate a plausible-but-wrong value.
BUILD_DATE_STAMP = ""  # stamped at build time; empty means "derive it"

def _resolve_build_date():
    """Returns the build date: the stamped value, else the artefact mtime."""
    if BUILD_DATE_STAMP:
        return BUILD_DATE_STAMP
    try:
        target = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        return datetime.fromtimestamp(os.path.getmtime(target)).strftime("%m-%d-%Y %H:%M:%S")
    except Exception:
        return "Unknown"

BUILD_DATE = _resolve_build_date()

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

# ---------------------------------------------------------------------------
# UI-02 -- the Glass Midnight Navy palette, defined once
# ---------------------------------------------------------------------------
# This replaces the Nord palette the app shipped with through v3.2.0. The
# structure is unchanged and deliberately so: one class, every colour named for
# the role it plays, and nothing anywhere else in the file spelling out a hex
# value of its own. What changed is the colours themselves and the surface
# model they serve.
#
# The seven base values are the "Glass Midnight Navy" row from StreamWeaver's
# themes.py (_GLASS_SPECS), used as the reference for this port:
#
#     accent   grad0     grad1     grad2     edge      text_dim  text
#     #5b8def  #070c1a   #0b1226   #111a34   #26335c   #8892b8   #e8ecfa
#
# Glass is not a blur -- Qt cannot do a real backdrop blur. The frosted look is
# three things working together, and all three have to stay in step or it falls
# apart into a flat dark theme:
#
#   1. the window paints a deep diagonal gradient (GROUND -> PANEL -> GROUND),
#   2. every widget is transparent by default so that gradient shows through,
#   3. panels are translucent WHITE films over it (FILM_*), not opaque fills,
#      with a brighter hairline along the top edge -- the "lit glass" cue.
#
# Because of (2), anything that must not be see-through -- menus, popups, item
# views, tooltips -- has to re-declare an explicit background. That is the one
# rule to remember when adding a widget to this app.
#
# There is exactly one theme. No switching, no THEMES dict, no persisted choice.
class Glass:
    # -- the five surface steps, darkest first --------------------------------
    GROUND = "#070c1a"        # grad0 -- the gradient's dark ends; deepest wells
    WINDOW = "#0b1226"        # grad1 -- flat window fill behind the gradient
    PANEL = "#111a34"         # grad2 -- the gradient's lit middle; opaque popups
    EDGE = "#26335c"          # hairline borders, scroll handles
    EDGE_LIT = "#3f5490"      # above EDGE -- hover borders and lit edges
    # Disabled text. EDGE is the border colour and was the obvious choice, but
    # a border only has to be *found*, whereas disabled text still has to be
    # READ -- against a ground this dark, EDGE rendered "Select output file"
    # and the greyed START label as very nearly invisible. This sits between
    # EDGE_LIT and TEXT_DIM: plainly inactive, still legible.
    DISABLED = "#5a6795"

    # -- text ----------------------------------------------------------------
    TEXT = "#e8ecfa"          # body text
    TEXT_DIM = "#8892b8"      # secondary text, placeholders, disabled labels
    BRIGHT = "#ffffff"        # text and icons on an accent fill

    # -- accent ramp ---------------------------------------------------------
    # ACCENT is the theme's one hue. DEEP and SHADE fill the primary action --
    # a pale accent fill would swallow the light qtawesome glyphs drawn on it.
    # ACCENT_BRIGHT lights hover states above it.
    ACCENT = "#5b8def"
    ACCENT_BRIGHT = "#8fb4f7"
    ACCENT_DEEP = "#3f6bc4"
    ACCENT_SHADE = "#2d4c8f"

    # -- log-line semantics --------------------------------------------------
    # Retuned from the old Aurora set for a navy ground: those values were
    # picked against #2e3440, and several of them sat too close to the
    # background once it dropped to #0b1226. Each of these is the accent of one
    # of StreamWeaver's sibling glass themes, so they stay in family.
    INFO_BLUE = "#7cc7ff"     # the [INFO] tag -- sky, so it is not the accent
    OK_GREEN = "#4bd99a"      # '-----' headers, [Complete]/[Started]/[Passed]
    ERROR_RED = "#ff7591"     # the [ERROR] tag and [Failed]
    WARN_YELLOW = "#ffcc66"   # the [WARN] tag
    DATA_PURPLE = "#b98cff"   # the [DATA] tag
    LOAD_ORANGE = "#ffb24a"   # the [LOAD] tag
    NUMERIC = "#58d7e0"       # versions, timestamps, dates, sizes -- aqua, so a
                              # highlighted number never reads as an accent link

    SOFT_GOLD = "#d4af37"     # not glass: the 'checking for updates' icon

    # -- PDF export ----------------------------------------------------------
    # Paper is not a screen: the window's films and wells are alpha over a
    # gradient and mean nothing printed, and a body text picked for a dark
    # window prints weakly. So the report has a few colours of its own -- but
    # they live HERE, with everything else, because "one palette, one place"
    # does not get an exemption for print. PDF_THEMES below only arranges them.
    PAPER_WHITE = "#ffffff"     # the light report's sheet
    PAPER_CARD = "#f8f9fa"      # its cells: off-white, so they read on the sheet
    PAPER_RULE = "#c9d1e0"      # its hairlines
    PAPER_LABEL = "#5a6480"     # its field labels; darker than TEXT_DIM for ink

    # The transparency mat, chosen by measuring rather than by eye. A mat serves
    # BOTH kinds of artwork only if neither contrast ratio collapses, so the
    # pair is the one that maximises the WORST case across white art and
    # near-black art:
    #
    #   mat                     white art    dark art    worst
    #   #e5e9f0 (the old flat)     1.22:1     15.13:1     1.22   <- white lost
    #   #d3d9e5 / #b9c1d2          1.42:1     13.01:1     1.42   <- barely better
    #   #7d87a8 / #6b7594          3.56:1      4.03:1     3.56   <- shipped
    #
    # Both shipped numbers clear the 3:1 floor for non-text content. Any mat
    # lighter than this sacrifices the white art, which is precisely the bug.
    # Mid-value navy rather than neutral grey so it belongs to the same family
    # as the rest of the report; the 1.28:1 between the two squares is what
    # makes it read as a checker rather than as a flat fill.
    CHECKER_A = "#7d87a8"
    CHECKER_B = "#6b7594"


def _rgba(hex_color, alpha):
    """'#rrggbb' + alpha -> a QSS 'rgba(r, g, b, a)' string.

    Ported from StreamWeaver's themes.py. Plain hex parsing rather than QColor
    so the palette stays usable before a QApplication exists -- these constants
    are built at import time, long before main() runs.
    """
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "rgba({}, {}, {}, {})".format(r, g, b, alpha)


# The films. A glass panel is white at very low alpha over the gradient, which
# is what makes it read as lit from above rather than as a lighter grey. Wells
# go the other way -- black at moderate alpha, cut *into* the glass.
FILM_PANEL = "rgba(255, 255, 255, 0.045)"    # group boxes: the faintest card
FILM_RAISED = "rgba(255, 255, 255, 0.07)"    # buttons and other raised controls
FILM_HOVER = "rgba(255, 255, 255, 0.11)"     # a raised control under the pointer
FILM_LINE = "rgba(255, 255, 255, 0.10)"      # hairline border
FILM_LINE_LIT = "rgba(255, 255, 255, 0.18)"  # the lit top edge
FILM_LINE_SOFT = "rgba(255, 255, 255, 0.06)" # the quietest divider
FILM_DISABLED = "rgba(0, 0, 0, 0.18)"        # an inactive control, sunk out
WELL = "rgba(0, 0, 0, 0.28)"                 # inputs, the log, item views
WELL_DEEP = "rgba(0, 0, 0, 0.36)"            # a focused input, the preview mat


# ---------------------------------------------------------------------------
# PDF-01 -- the two papers, and the checkerboard
# ---------------------------------------------------------------------------
# The gallery's job is to let someone SEE a texture. Most of these assets are
# transparent PNGs, and the artwork inside them is drawn in whatever colour the
# skin needed -- white glyphs in one file, near-black in the next. A flat mat
# can only ever serve one of those: on the near-white mat this replaces, every
# white-on-transparent logo in the maintainer's own report had vanished, while
# the dark ones read fine. Reversing it to black would simply swap which half
# disappears.
#
# So the mat is a mid-value CHECKERBOARD, the way every image editor does it.
# It gives both extremes something to contrast against, and it says "these
# pixels are transparent" rather than leaving the reader to wonder whether that
# white is paper or paint. It is deliberately the SAME in both papers: it is the
# window onto the artwork, and keeping it constant is what makes two exports
# comparable.
CHECKER_LIGHT = Glass.CHECKER_A
CHECKER_DARK = Glass.CHECKER_B
CHECKER_SQUARE = 5          # points. Fine enough to read as a backdrop rather
                            # than as a graphic in its own right, coarse enough
                            # that a page stays a few thousand rectangles.

PDF_THEMES = {
    # Prints cleanly, reads as a document, survives a photocopier.
    "light": {
        "page": Glass.PAPER_WHITE,
        "band": Glass.PANEL,        # the header/footer navy, from the theme
        "band_text": Glass.TEXT,
        "rule": Glass.ACCENT,       # a hairline under the band
        "card": Glass.PAPER_CARD,
        "card_border": Glass.PAPER_RULE,
        "title": Glass.GROUND,
        "label": Glass.PAPER_LABEL,
    },
    # Screen-first. Matches the app, and the artwork carries much harder.
    # Not cheaper on toner than dark cards would be -- nine cards already cover
    # most of a page -- so if the ink is being spent, it is spent on the whole
    # sheet rather than on cards floating in white margins.
    "dark": {
        "page": Glass.GROUND,
        "band": Glass.PANEL,
        "band_text": Glass.TEXT,
        "rule": Glass.ACCENT,
        "card": Glass.WINDOW,
        "card_border": Glass.EDGE,
        "title": Glass.TEXT,
        "label": Glass.TEXT_DIM,
    },
}


# The keys the global stylesheet template is formatted with. Kept as an explicit
# mapping so a typo in a placeholder name fails loudly at startup rather than
# silently rendering the literal text "{glass_edge}" into the QSS.
QSS_VARS = {
    'glass_ground': Glass.GROUND,
    'glass_window': Glass.WINDOW,
    'glass_panel': Glass.PANEL,
    'glass_edge': Glass.EDGE,
    # EDGE_LIT and the log-line colours are deliberately absent: they are read
    # from Glass directly by the Python that needs them (the placeholder icon,
    # the log formatter, the help sheet) and the QSS has no use for them. A
    # token in this map that no rule substitutes is a token free to drift.
    'glass_text': Glass.TEXT,
    'glass_dim': Glass.TEXT_DIM,
    'glass_bright': Glass.BRIGHT,
    'glass_disabled': Glass.DISABLED,
    'glass_accent': Glass.ACCENT,
    'glass_accent_bright': Glass.ACCENT_BRIGHT,
    'glass_accent_deep': Glass.ACCENT_DEEP,
    'glass_accent_shade': Glass.ACCENT_SHADE,
    # Accent at three alphas: the bloom that replaces the old solid hover and
    # selection fills. Selection is the strongest of the three so a selected row
    # still reads as selected while the pointer is somewhere else.
    'glass_accent_soft': _rgba(Glass.ACCENT, 0.32),
    'glass_accent_hover': _rgba(Glass.ACCENT, 0.22),
    'glass_accent_press': _rgba(Glass.ACCENT, 0.40),
    # The films, so the sheet names them rather than repeating alpha values.
    'film_panel': FILM_PANEL,
    'film_raised': FILM_RAISED,
    'film_hover': FILM_HOVER,
    'film_line': FILM_LINE,
    'film_line_lit': FILM_LINE_LIT,
    'film_line_soft': FILM_LINE_SOFT,
    'film_disabled': FILM_DISABLED,
    'well': WELL,
    'well_deep': WELL_DEEP,
}


# STR-08: the two smaller stylesheets, alongside the global APP_STYLESHEET at the
# bottom of this file. All three draw their colours from Glass above; none of
# them spells out a hex value of its own.
SPLITTER_STYLESHEET = f"""
QSplitter::handle:vertical {{
    background-color: transparent;
    border: none;
    border-top: 1px solid {FILM_LINE};
    height: 1px;
    margin-top: 4px;
    margin-bottom: 4px;
}}
QSplitter::handle:vertical:hover {{
    border-top: 1px solid {Glass.ACCENT};
}}
"""

HELP_STYLESHEET = f"""
    h1 {{ color: {Glass.ACCENT}; border-bottom: 2px solid {Glass.EDGE}; padding-bottom: 6px; margin-top: 18px; }}
    h2 {{ color: {Glass.INFO_BLUE}; border-bottom: 1px solid {Glass.EDGE}; padding-bottom: 4px; margin-top: 14px; }}
    h3 {{ color: {Glass.BRIGHT}; font-weight: bold; margin-top: 10px; }}
    p, li {{ color: {Glass.TEXT}; font-size: 11pt; }}
    a {{ color: {Glass.ACCENT_BRIGHT}; text-decoration: none; }}
    code {{ background-color: {Glass.GROUND}; color: {Glass.WARN_YELLOW}; padding: 2px 5px; border-radius: 4px; font-family: Consolas, monospace; }}
    pre > code {{ display: block; padding: 12px; border-radius: 8px; }}
    blockquote {{
        background-color: {Glass.PANEL}; color: {Glass.BRIGHT}; border-left: 4px solid {Glass.ACCENT};
        padding: 12px; margin-left: 0px;
    }}
"""

# ---------------------------------------------------------------------------
# STR-07 -- diagnostics for deliberately-swallowed exceptions
# ---------------------------------------------------------------------------
# The file had 68 exception handlers, 32 of which recorded nothing at all. Some
# of those are legitimate -- narrow, expected, and on per-line hot paths where
# logging would drown the file. Others hid conditions that matter in the field:
# a workspace that could not be deleted, a rejected update payload left on disk,
# a corrupt recent-files list silently reset to empty, an output reader thread
# dying mid-job. When a user reports "it made an empty folder", none of that was
# recoverable afterwards.
#
# These now land in TextureTool_Log.txt and nowhere else. The in-app log widget
# and the dialogs are deliberately untouched: this is diagnostic material for
# chasing root causes, not something to start showing users.
# BUG-20: compiled once at import rather than looked up in re's cache on every
# call. `_format_log_message` runs per log message, and a Get Info over a large
# archive puts ~22,750 of them through it in one blocking pass.
_DRIVE_LETTER_RE = re.compile(r'\b([a-z]):\\')
_VERSION_RE = re.compile(r'(v\d+(?:\.\d+)*)')
_KB_RE = re.compile(r'(\d+KB)')
_DATE_RE = re.compile(r'(\d{2}-\d{2}-\d{4})')

_DIAGNOSTIC_LOGGER = None      # the FileLogger, once TextureToolApp has built it
_PENDING_DIAGNOSTICS = []      # anything recorded before that point


def bind_diagnostic_logger(logger):
    """Attaches the file logger and flushes anything recorded before startup."""
    global _DIAGNOSTIC_LOGGER
    _DIAGNOSTIC_LOGGER = logger
    while _PENDING_DIAGNOSTICS:
        logger.write(_PENDING_DIAGNOSTICS.pop(0))


def log_diagnostic(context, exc=None, **details):
    """
    Records a swallowed exception to the log file only.

    `context` says what was being attempted, in plain words. `details` carries
    the values needed to reproduce it -- paths, keys, indexes. `exc` adds the
    exception type, its message and a full traceback.

    Module-level rather than a method because the workers, the dialogs and the
    module-scope helpers all need it, and none of them hold a reference to the
    main window.
    """
    try:
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[DIAG] {stamp} {context}"
        if details:
            line += " | " + " | ".join(f"{k}={v!r}" for k, v in details.items())
        if exc is not None:
            line += f" | {type(exc).__name__}: {exc}"

        entries = [line]
        if exc is not None and getattr(exc, "__traceback__", None) is not None:
            formatted = traceback.format_exception(type(exc), exc, exc.__traceback__)
            for tb_line in "".join(formatted).rstrip().splitlines():
                entries.append(f"[DIAG]     {tb_line}")

        for entry in entries:
            if _DIAGNOSTIC_LOGGER is None:
                _PENDING_DIAGNOSTICS.append(entry)
            else:
                _DIAGNOSTIC_LOGGER.write(entry)
    except Exception:
        # A diagnostic path must never itself raise, or a swallowed error
        # becomes a crash. There is nothing useful left to do here.
        pass


# STR-08 follow-up (see STR-08-REGRESSION in AUDIT.md): this lives at module
# scope because UpdateDialog is its only consumer and UpdateDialog is not a
# TextureToolApp. STR-08 deduped the palette by filing this constant on
# TextureToolApp while leaving `self.STYLE_SCROLL_AREA` behind in
# UpdateDialog.__init__, where `self` is the dialog -- an AttributeError that
# killed the dialog in its constructor and took the entire update prompt with
# it. The sibling STYLE_* constants are genuinely per-widget state of the main
# window and correctly remain on TextureToolApp.
STYLE_SCROLL_AREA = (f"QScrollArea {{ border: 1px solid {FILM_LINE}; border-radius: 8px; "
                     f"background-color: {WELL}; }} "
                     f"QWidget {{ background-color: transparent; }}")


# ---------------------------------------------------------------------------
# LAYOUT-01 -- where the window layout is kept, and why it moved
# ---------------------------------------------------------------------------
# The main window's geometry and splitter positions were already being saved --
# but to QSettings, which on Windows is the REGISTRY. That is invisible in
# config.ini (so it looked like the app saved nothing), and, more importantly,
# it does not travel: copy the install and its config to another machine and the
# layout is simply gone, because the registry key went nowhere.
#
# Everything now lives in config.ini beside every other preference, so the file
# IS the settings. Qt's geometry and splitter states are opaque QByteArrays, so
# they are base64'd into the ini; the dialog sizes below are plain "WxH" text
# because they can be, and a value a maintainer can read and edit is worth more
# than one they cannot.
#
# A machine's screen layout is not portable even when the config is, so
# _restore_window_layout re-centres a window that would land off-screen. That is
# the failure this design invites, and it is handled rather than hoped about.

def encode_qt_state(byte_array):
    """QByteArray -> an ini-safe string. Empty string if there is nothing."""
    try:
        raw = bytes(byte_array)
        return base64.b64encode(raw).decode("ascii") if raw else ""
    except Exception as e:
        log_diagnostic("encoding a Qt layout state for config.ini", e)
        return ""


def decode_qt_state(text):
    """The inverse. Returns None for anything unusable rather than raising.

    A hand-edited or truncated value must not stop the window from opening, so
    every failure here is the same as having no saved layout at all.
    """
    if not text:
        return None
    try:
        return QByteArray(base64.b64decode(text.encode("ascii"), validate=True))
    except Exception as e:
        log_diagnostic("decoding a saved layout from config.ini", e,
                       value_length=len(text))
        return None


# First-run sizes for the dialogs that remember theirs. Chosen against real
# content rather than guessed: the changelog and the update notes are wide HTML
# that wrapped into a scrolling sliver at the old minimums.
DIALOG_DEFAULT_SIZES = {
    "update": (820, 640),
    "changelog": (900, 720),
    "help": (1250, 800),
}


def _layout_owner(widget):
    """The main window behind a dialog -- whoever holds the config.

    Walks up rather than assuming `parent()` is the window, and returns None if
    there is no config in sight, which is the case in a few of the harnesses.
    """
    while widget is not None:
        if hasattr(widget, "config") and hasattr(widget, "_write_config_file"):
            return widget
        widget = widget.parent() if hasattr(widget, "parent") else None
    return None


class SizeRememberingDialog(QDialog):
    """
    A QDialog that opens at whatever size the user last left it.

    Subclasses set SIZE_KEY; the size is stored in config.ini's [Dialogs]
    section as "WxH". Position is deliberately NOT stored -- a dialog belongs
    centred on its parent, and a remembered position is what puts one on a
    monitor that is no longer attached.

    Every path out of a dialog reaches done(), including the window's X button
    and Escape (both go through reject()), so that is where the size is saved.
    """

    SIZE_KEY = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._size_owner = _layout_owner(parent)
        self._restore_size()

    def _restore_size(self):
        width, height = DIALOG_DEFAULT_SIZES.get(self.SIZE_KEY, (800, 600))
        owner = getattr(self, "_size_owner", None)
        if owner is not None and self.SIZE_KEY:
            try:
                stored = owner.config.get("Dialogs", self.SIZE_KEY, fallback="")
                if "x" in stored:
                    saved_w, saved_h = (int(v) for v in stored.lower().split("x", 1))
                    if saved_w > 200 and saved_h > 150:
                        width, height = saved_w, saved_h
            except Exception as e:
                log_diagnostic("reading a saved dialog size", e, dialog=self.SIZE_KEY)

        # Never larger than the screen it is about to open on. A size saved on a
        # 4K monitor must not open past the edge of a 1080p one -- exactly what
        # carrying config.ini between machines does.
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, available.width() - 40)
            height = min(height, available.height() - 60)
        self.resize(max(width, 200), max(height, 150))

    def _store_size(self):
        owner = getattr(self, "_size_owner", None)
        if owner is None or not self.SIZE_KEY:
            return
        try:
            if not owner.config.has_section("Dialogs"):
                owner.config.add_section("Dialogs")
            owner.config.set("Dialogs", self.SIZE_KEY,
                             "{}x{}".format(self.width(), self.height()))
            owner._write_config_file()
        except Exception as e:
            log_diagnostic("saving a dialog size", e, dialog=self.SIZE_KEY)

    def done(self, result):
        self._store_size()
        super().done(result)


# ---------------------------------------------------------------------------
# CHANGELOG-01 -- the changelog is data; the dialog is presentation
# ---------------------------------------------------------------------------
# changelog.txt used to BE the HTML: a `<pre>` block carrying its own hex
# colours, its own font stack, `&amp;` escapes and hard tabs, handed straight to
# setHtml(). That had three costs, and the third is the one that bit:
#
#   * a `<pre>` does not wrap, so long entries scrolled sideways -- the alignment
#     was being paid for with readability,
#   * every release meant hand-writing HTML in a file that is otherwise a list
#     of sentences,
#   * its colours could not follow the theme, and duly did not: after UI-02 it
#     was the last thing in the product still painted in the old Nord palette,
#     and it had to be found and fixed by hand.
#
# The file is now plain text -- a version line at column 0, entries indented
# beneath it -- and this function renders it. Wrapping comes free, the hanging
# indent comes from a real list rather than from monospaced padding, and the
# colours come from Glass, so they cannot drift again.

def _escape_changelog(text):
    """The four characters that would otherwise be read as markup.

    Deliberately not `html.escape`: STR-01 removed the shadowed imports from
    this file, and `html` is already used as a local name in the log formatter.
    A four-line helper is cheaper than reintroducing that class of confusion.
    """
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


def render_changelog_html(raw_text):
    """
    Turns the plain-text changelog into the HTML the dialog displays.

    Format, which is the whole specification:

        v3.3.0 - Interface & Reporting Release      <- column 0: version heading
            Security & Stability                    <- indented, no dash: section heading
            - NOTE: something worth knowing         <- indented, dashed: entry
            - FIXED: something that was broken

    A line at column 0 is a version heading. An indented line is a section
    heading if it carries no dash and an entry if it does. Entries become real
    list items, so Qt gives them a hanging indent and wrapped text lines up
    under the text instead of under the bullet -- which is what the old `<pre>`
    was buying with its refusal to wrap.

    CHANGELOG-02: section headings used to be missing from that list, and an
    indented line was an entry whatever it looked like -- so `Security &
    Stability` rendered as a bullet, sitting in the same list as the fixes it
    was supposed to be introducing. Three levels of structure arrived as two.

    Blank lines are separators, not content: every one of them in changelog.txt
    precedes a heading, so the spacing they encode is carried by the headings'
    own `margin-top` rather than by emitting anything for the blank itself. A
    stray `<br>` around a `<ul>` is rendered inconsistently by Qt's rich text;
    a margin is not.
    """
    # A changelog.txt from before CHANGELOG-01 is already a complete HTML
    # document. Rendering it again would double-escape it, so it is passed
    # through untouched. This matters for a build directory holding an older
    # copy of the file beside a newer executable.
    if "<pre" in raw_text[:400].lower():
        return raw_text

    parts = [
        '<div style="font-family: \'Segoe UI\', Arial, sans-serif; '
        'font-size: 10pt; color: {text};">'.format(text=Glass.TEXT)
    ]
    in_list = False

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # A dash makes it an entry wherever it sits: an indented line is one by
        # position, and an unindented one is a bullet that lost its leading tab
        # -- kinder to render it as the bullet it plainly is than to promote it
        # to a version heading. Indentation alone decides the other two.
        if stripped.startswith("-"):
            if not in_list:
                parts.append('<ul style="margin-top: 2px; margin-bottom: 10px;">')
                in_list = True
            parts.append("<li style=\"margin-bottom: 4px;\">{}</li>".format(
                _escape_changelog(stripped.lstrip("-").strip())))
            continue

        if in_list:
            parts.append("</ul>")
            in_list = False

        if line[:1] in (" ", "\t"):
            parts.append(
                '<div style="color: {accent}; font-weight: bold; font-size: 10pt; '
                'margin-top: 12px; margin-bottom: 2px;">{heading}</div>'.format(
                    accent=Glass.ACCENT_BRIGHT, heading=_escape_changelog(stripped)))
        else:
            parts.append(
                '<div style="color: {accent}; font-weight: bold; font-size: 11pt; '
                'margin-top: 16px; margin-bottom: 2px;">{heading}</div>'.format(
                    accent=Glass.ACCENT, heading=_escape_changelog(stripped)))

    if in_list:
        parts.append("</ul>")
    parts.append("</div>")
    return "".join(parts)


class RecentGroup(Enum):
    """Defines constant identifiers for recent item categories."""
    COMPILE_FILES = 'compile_files'
    COMPILE_FOLDERS = 'compile_folders'
    DECOMPILE_FILES = 'decompile_files'
    DECOMPILE_FOLDERS = 'decompile_folders'


class PathSlot(Enum):
    """
    The four path selections the UI tracks.

    STR-05: eight methods -- `_handle_*_path` and `_open_recent_*`, four of each
    -- were the same ~15 lines repeated with different attribute names. They had
    already drifted apart: the recent-path variants set the tooltip twice (the
    first call immediately overwritten) and never applied the "runtimes missing"
    tooltip that the handle-path variants did. One slot identifier plus the
    descriptor table in TextureToolApp.PATH_SLOTS now drives all of them.
    """
    DECOMPILE_INPUT = 'decompile_input'
    DECOMPILE_OUTPUT = 'decompile_output'
    COMPILE_INPUT = 'compile_input'
    COMPILE_OUTPUT = 'compile_output'


class Worker(QObject):
    finished = Signal(int, str)
    error = Signal(str)
    progress_updated = Signal(int, str)  # Emits progress percentage and message
    # Emits one parsed info line and its filename (empty for detail lines).
    #
    # BUG-20: this was batched into a single `Signal(list)` per reader batch,
    # cutting deliveries from 22,757 to 1,214 for a 7,584-texture archive. Paired
    # measurement showed that bought **nothing** -- 0.81 s of phase 2 either way
    # -- so the batching was reverted rather than kept for looking principled.
    # The signal volume is not the cost; see AUDIT.md BUG-20.
    info_line_parsed = Signal(str, str)

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
        # BUG-01: one reader thread per stream so stdout and stderr drain
        # concurrently. A single shared thread deadlocked on stderr-heavy jobs.
        self.reader_threads = []
        self.stdout_thread = None
        self.stderr_thread = None
        self.stdout_reader = None
        self.stderr_reader = None
        self.full_stdout = []
        self.full_stderr = []
        # BUG-14: TextureExtractor.exe and TextureCompiler.exe write "ERROR: ..."
        # and still exit 0, so the exit code alone cannot distinguish success
        # from failure. Every error line seen on either stream is collected here
        # and treated as a failure signal in _finalize_process.
        self.error_lines = []
        self.stdout_finished = False
        self.stderr_finished = False
        self.last_emitted_progress = -1  # Initialize progress tracker

    def run(self):
        try:
            # SEC-02: never hand a command string to a shell. The previous
            # implementation wrapped everything in `cmd.exe /c "chcp 65001 && ..."`
            # with shell=True, quoting arguments with double quotes only. Shell
            # metacharacters (& | ^ < > ") in user-chosen paths were interpreted,
            # so a file or folder named `foo & calc.exe` executed arbitrary code.
            # Paths reach here from file dialogs AND from drag-and-drop.
            if isinstance(self.command, str):
                command_list = shlex.split(self.command)
            else:
                command_list = list(self.command)

            if not command_list:
                self._emit_error("Empty command; nothing to execute.")
                return

            # The child inherits the console output code page. Setting it here
            # replaces what `chcp 65001` was doing inside the shell wrapper,
            # without needing a shell. No-op in a windowed build with no console.
            if sys.platform == "win32":
                try:
                    ctypes.windll.kernel32.SetConsoleOutputCP(65001)
                except Exception as e:
                    # STR-07: harmless in a windowed build, but if this fails in
                    # a console build the child's output encoding is wrong and
                    # the symptom shows up as mojibake much later. Worth knowing.
                    log_diagnostic("setting the console output code page to UTF-8", e)

            child_env = dict(os.environ)
            child_env["PYTHONIOENCODING"] = "utf-8"

            self.process = subprocess.Popen(
                command_list,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=child_env,
                creationflags=0 if self.show_window else (subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            )

            # BUG-01: stdout and stderr each get their OWN thread.
            #
            # They previously shared one QThread, with BOTH run() slots connected
            # to that thread's started signal. Qt invokes such slots sequentially
            # on the one thread, and StreamReader.run() blocks in
            # iter(stream.readline, '') until EOF -- so stderr was never drained
            # until stdout had already closed. Any child writing more than the
            # ~64 KB pipe buffer to stderr blocked forever on write; it then never
            # exited, never closed stdout, and the reader never returned. The app
            # hung with the UI locked, because _set_ui_task_active(True) disables
            # the menu bar for the duration of a task.
            #
            # Draining both pipes concurrently is the only correct fix.
            self.reader_threads = []

            if self.process.stdout:
                self.stdout_thread = QThread(self)
                self.stdout_reader = self.StreamReader(self.process.stdout)
                self.stdout_reader.moveToThread(self.stdout_thread)
                # BATCHED SIGNAL CONNECTION
                self.stdout_reader.lines_ready.connect(self._on_stdout_batch)
                self.stdout_reader.finished.connect(self._on_stream_finished)
                self.stdout_thread.started.connect(self.stdout_reader.run)
                self.reader_threads.append(self.stdout_thread)
            else:
                self.stdout_finished = True

            if self.process.stderr:
                self.stderr_thread = QThread(self)
                self.stderr_reader = self.StreamReader(self.process.stderr)
                self.stderr_reader.moveToThread(self.stderr_thread)
                # BATCHED SIGNAL CONNECTION
                self.stderr_reader.lines_ready.connect(self._on_stderr_batch)
                self.stderr_reader.finished.connect(self._on_stream_finished)
                self.stderr_thread.started.connect(self.stderr_reader.run)
                self.reader_threads.append(self.stderr_thread)
            else:
                self.stderr_finished = True

            if self.reader_threads:
                for thread in self.reader_threads:
                    thread.start()
            else:
                QTimer.singleShot(100, self._finalize_process)

        except Exception as e:
            self._emit_error(f"Failed to start process: {e}")

    # BUG-14: line prefixes that mean the child failed, whatever it exits with.
    ERROR_PREFIXES = ("ERROR:", "ERROR ", "FATAL:", "FATAL ")

    def _note_if_error(self, line):
        """Records a child error line so _finalize_process can fail the task."""
        stripped = line.strip()
        if stripped.upper().startswith(self.ERROR_PREFIXES):
            self.error_lines.append(stripped)

    def _on_stdout_batch(self, lines):
        # Process a batch of lines to prevent signal flooding
        for line in lines:
            self._note_if_error(line)
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
                    self.info_line_parsed.emit(clean_line, "")  # No filename

    def _on_stderr_batch(self, lines):
        self.full_stderr.extend(lines)
        for line in lines:
            self._note_if_error(line)

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
            except subprocess.TimeoutExpired as e:
                # STR-07: killing the child is the right escalation, but a
                # TexturePacker process that will not exit within 2 seconds of
                # its pipes closing is worth knowing about after the fact.
                log_diagnostic("waiting for the child process to exit before killing it",
                               e, pid=getattr(self.process, 'pid', None))
                self.process.kill()

        # BUG-01: both reader threads are shut down, with a bounded wait so a
        # wedged reader can never hang the caller indefinitely.
        for thread in self.reader_threads:
            if thread and thread.isRunning():
                thread.quit()
                if not thread.wait(5000):
                    thread.terminate()
                    thread.wait(1000)

        # BUG-22: both reader threads have stopped by this point, so the worker
        # (and the QThread children parented to it) can safely change thread
        # affinity. Doing it here means the destructor runs on the GUI thread.
        self._retire_to_gui_thread()

        # The 'output' is now just stderr, since stdout was handled live.
        # This prevents the entire log from being re-processed at the end.
        stderr_str = "\n".join(self.full_stderr)

        # BUG-14: exit code alone is not trustworthy here. Both TexturePacker
        # executables report "ERROR: Cannot open file ..." / "ERROR: Failed to
        # save image file ..." on a stream and then exit 0. Reporting that as
        # success is what produced the "process complete, empty output folder"
        # symptom. Any collected error line fails the task.
        return_code = self.process.returncode

        if self.error_lines:
            detail = "\n".join(self.error_lines[:20])
            if len(self.error_lines) > 20:
                detail += f"\n... and {len(self.error_lines) - 20} more error line(s)"
            if return_code == 0:
                error_message = (
                    "The operation reported success (exit code 0) but emitted errors, "
                    "so no usable output was produced:\n" + detail
                )
            else:
                error_message = f"Process failed with exit code {return_code}:\n{detail}"
            self.error.emit(error_message)
        elif return_code == 0:
            self.finished.emit(return_code, stderr_str) # Pass empty string for stdout
        else:
            error_message = f"Process failed with exit code {return_code}:\n{stderr_str.strip()}"
            self.error.emit(error_message)

    def _retire_to_gui_thread(self):
        """
    BUG-22: hand this worker back to the GUI thread before it finishes, so that
    its eventual destruction runs there.

    Destroying a QObject that lives in a worker thread makes shiboken acquire
    the GIL from that thread, inside `~QObject`, while it already holds the
    object's Qt signal/slot mutex. If the GUI thread is meanwhile inside
    `QObject::connect` -- which holds the GIL and wants that same mutex -- the
    two deadlock. Qt draws signal/slot mutexes from a fixed pool hashed by
    object pointer, so the two objects need not even be related.

    Captured with `py-spy dump --native` (handoff/bug22_captures/):

        worker : QObject::~QObject -> PyGILState_Ensure   [holds mutex, wants GIL]
        main   : QObject::connectImpl -> QBasicMutex::lockInternal
                                                          [holds GIL, wants mutex]

    Moving to the GUI thread first means the destructor runs on the thread that
    already owns the GIL, so the cross-thread acquisition never happens. This is
    called from the worker's own thread, which is where `moveToThread` is legal,
    and only once both reader threads have stopped.
    """
        try:
            app = QApplication.instance()
            if app is not None and self.thread() is not app.thread():
                self.moveToThread(app.thread())
        except RuntimeError as e:
            # Never let a cleanup nicety break the task that just succeeded.
            log_diagnostic("moving the finished worker back to the GUI thread", e)

    def _emit_error(self, message):
        tb_str = traceback.format_exc()
        error_msg = f"An unexpected fatal error occurred in the worker thread: {message}\n\nTraceback:\n{tb_str}"
        self._retire_to_gui_thread()
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
                # LOG-01: the handle was closed without ever asking what the
                # process returned, so a runtime installer that failed and one
                # that succeeded finished identically here -- the outcome was
                # inferred minutes later from a re-check, with nothing in the
                # log to say the installer itself had refused. The code is
                # carried on `finished` so the caller can report it.
                self.finished.emit(self._exit_code())
            else:
                self.error.emit(f"WaitForSingleObject failed with code: {wait_result}")
        except Exception as e:
            self.error.emit(f"An unexpected error occurred in the monitor thread: {e}")
        finally:
            ctypes.windll.kernel32.CloseHandle(self.process_handle)

    def _exit_code(self):
        """The process's exit code as text, or "" if it could not be read."""
        try:
            code = wintypes.DWORD()
            if ctypes.windll.kernel32.GetExitCodeProcess(self.process_handle, ctypes.byref(code)):
                return str(code.value)
        except Exception as e:
            log_diagnostic("reading the installer's exit code", e)
        return ""


class UpdateCheckWorker(QObject):
    finished = Signal(dict); error = Signal(str)
    
    def __init__(self, url): super().__init__(); self.url = url

    def run(self):
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(5)  # Set a shorter, more responsive global timeout.
        try:
            # SEC-01: verification restored. A default context validates the
            # certificate chain and the hostname, which is the point.
            ctx = ssl.create_default_context()

            req = urllib.request.Request(self.url, headers={'User-Agent': 'KodiTextureTool-Update-Checker'})

            with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
                if response.status == 200:
                    self.finished.emit(json.loads(response.read().decode('utf-8')))
                else:
                    self.error.emit(f"Server returned status {response.status}")
        except Exception as e:
            self.error.emit(f"Failed to check for updates: {e}")
        finally:
            socket.setdefaulttimeout(original_timeout)

class DownloadWorker(QObject):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)
    warning = Signal(str)

    def __init__(self, url, dest_folder, expected_sha256=None):
        super().__init__()
        self.url = url
        self.dest_folder = dest_folder
        # SEC-01: SHA-256 from version.json, or None when the manifest omits it.
        self.expected_sha256 = (expected_sha256 or "").strip().lower() or None

    def run(self):
        temp_path = None
        try:
            os.makedirs(self.dest_folder, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(suffix=".zip", dir=self.dest_folder)
            os.close(fd)

            # SEC-01: verification restored. This payload gets extracted over the
            # installation directory and relaunched, so an unverified channel here
            # is a remote code execution path.
            ctx = ssl.create_default_context()

            req = urllib.request.Request(self.url, headers={'User-Agent': 'KodiTextureTool-Update-Downloader'})

            digest = hashlib.sha256()
            with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                total_size = int(response.getheader('Content-Length', 0))
                bytes_read = 0
                with open(temp_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        digest.update(chunk)
                        bytes_read += len(chunk)
                        if total_size > 0:
                            percent = int((bytes_read / total_size) * 100)
                            self.progress.emit(percent)

            actual_sha256 = digest.hexdigest()

            if self.expected_sha256:
                if actual_sha256 != self.expected_sha256:
                    self._discard(temp_path)
                    self.error.emit(
                        "Update package failed integrity verification and was discarded.\n\n"
                        f"Expected SHA-256: {self.expected_sha256}\n"
                        f"Actual SHA-256:   {actual_sha256}\n\n"
                        "The download was corrupted or tampered with. Installation aborted."
                    )
                    return
            else:
                # Per the agreed migration policy: warn loudly, then continue.
                # TLS verification above is still enforced, so this is not an
                # unauthenticated channel -- only an unpinned artifact.
                self.warning.emit(
                    "Update manifest contains no 'sha256' field, so the package could not be "
                    f"integrity-checked. Computed SHA-256: {actual_sha256}"
                )

            self.finished.emit(temp_path)
        except Exception as e:
            self._discard(temp_path)
            self.error.emit(f"Download failed: {e}")

    @staticmethod
    def _discard(temp_path):
        """Removes a partial or rejected download so it can never be installed."""
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as e:
                # STR-07: this one matters. A payload that failed its SHA-256
                # check but could not be deleted is still sitting on disk, and
                # silence here means nobody would ever know.
                log_diagnostic("discarding a rejected or partial update download",
                               e, path=temp_path)

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
    """
    Writes the session log, keeping the handle open so a write is cheap.

    LOG-01: the log used to be opened "w" on construction and again on every
    Clear Log, and that was the whole retention policy -- the previous session
    was simply gone. It made the log useless for the case it exists to serve:
    the tool crashes, the user reopens it to fetch the log, and reopening it is
    what erased the crash. Clear Log had the same edge, with the added surprise
    that it truncated the file on disk while appearing to clear only the view.

    One generation is kept instead. The outgoing log is rotated to
    `<name>.prev.txt` before the new one is opened, so the evidence survives
    exactly one relaunch while the live log stays short enough to paste into a
    support thread. An empty or missing log is not rotated -- otherwise the
    first relaunch after a crash would overwrite the crash with nothing.
    """

    def __init__(self, log_path="TextureTool_Log.txt"):
        self.log_path = os.path.abspath(log_path)
        base, ext = os.path.splitext(self.log_path)
        self.prev_path = f"{base}.prev{ext or '.txt'}"
        self.log_file = None
        self.reset()
        atexit.register(self.close)

    def _rotate(self):
        """Moves the outgoing log aside, replacing the older generation."""
        try:
            if os.path.isfile(self.log_path) and os.path.getsize(self.log_path) > 0:
                os.replace(self.log_path, self.prev_path)
        except Exception as e:
            # Not fatal: the new log still opens, only the history is lost.
            print(f"Failed to rotate previous log: {e}")

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
        """Starts a fresh log, keeping the outgoing one as the .prev generation."""
        self.close()
        self._rotate()
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

# STR-03: PdfExportWorker was defined inside TextureToolApp for no reason -- it
# takes no outer state, and being nested meant it could only be reached as
# `self.PdfExportWorker`. It is a module-level class now, like every other worker
# and dialog in this file.
class PdfExportWorker(QObject):
    """A worker to generate a PDF report in a background thread."""
    # STR-03: the signals were split in two -- `finished` and `error` here, and
    # `progress` and `finished_with_path` at the very bottom of the class body,
    # below run(). All four are declared together now. `finished` was removed
    # entirely: it was never emitted and never connected; the real completion
    # signal is finished_with_path.
    progress = Signal(int)
    finished_with_path = Signal(str, str)
    error = Signal(str)
    # LOG-01: a non-fatal problem worth telling the user about -- currently a
    # tally of images that failed to render. `error` is the wrong channel: the
    # export succeeded, and reporting it there would abort a usable PDF.
    warning = Signal(str)

    def __init__(self, info_data, output_path, paper="light"):
        super().__init__()
        self.info_data = info_data
        self.output_path = output_path
        # PDF-01: "light" or "dark". Defaults to light so every existing caller
        # -- and every harness -- keeps the behaviour it had.
        self.paper = paper if paper in PDF_THEMES else "light"

    def run(self):
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.utils import ImageReader
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            # STR-01: `from datetime import datetime`, `import gc` and
            # `from PySide6.QtGui import QImageReader` were re-imported here,
            # shadowing the module-scope names with identical ones. Only the
            # reportlab imports need to be lazy -- reportlab is an optional
            # dependency and its absence is handled below.
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

        # --- Color & Font Definitions -------------------------------------
        # PDF-01: one of the two papers in PDF_THEMES. The checkerboard mat is
        # the same in both -- see the note there.
        theme = PDF_THEMES[self.paper]
        COLOR_PAGE = colors.HexColor(theme["page"])
        COLOR_HEADER_BG = colors.HexColor(theme["band"])
        COLOR_TEXT_LIGHT = colors.HexColor(theme["band_text"])
        COLOR_RULE = colors.HexColor(theme["rule"])
        COLOR_TEXT_DARK = colors.HexColor(theme["title"])
        COLOR_TEXT_LABEL = colors.HexColor(theme["label"])
        COLOR_BORDER = colors.HexColor(theme["card_border"])
        COLOR_CELL_BG = colors.HexColor(theme["card"])
        COLOR_CHECK_A = colors.HexColor(CHECKER_LIGHT)
        COLOR_CHECK_B = colors.HexColor(CHECKER_DARK)
        PAGE_WIDTH, PAGE_HEIGHT = letter

        c = None
        try:
            c = canvas.Canvas(self.output_path, pagesize=letter)
            # PDF-01: the checkerboard is a few thousand small rectangles per
            # page. Compressed, that is a rounding error on the file size;
            # uncompressed it is not.
            c.setPageCompression(1)
            total_images = len(self.info_data)
            failed_images = []  # LOG-01: cells that rendered as "[Image Error]"
            logo_path = get_resource_path("assets/kodi_logo_96.png")

            IMAGES_PER_PAGE = 9
            total_gallery_pages = (total_images + IMAGES_PER_PAGE - 1) // IMAGES_PER_PAGE
            total_doc_pages = 1 + total_gallery_pages

            # --- REVISED: Define header/footer heights as constants ---
            HEADER_HEIGHT = 0.5 * inch
            FOOTER_HEIGHT = 0.20 * inch

            def draw_checkerboard(canvas_obj, box_x, box_y, box_w, box_h):
                """
                PDF-01: the transparency mat.

                Drawn as clipped vector squares rather than a tiled image: a
                PDF viewer interpolates a scaled bitmap, which turns an 8pt
                checker into flat grey at exactly the sizes that matter. Roughly
                20x18 squares per cell, so a full gallery page is a few thousand
                rectangles -- which is why page compression is on.
                """
                canvas_obj.saveState()
                clip = canvas_obj.beginPath()
                clip.rect(box_x, box_y, box_w, box_h)
                canvas_obj.clipPath(clip, stroke=0, fill=0)

                canvas_obj.setFillColor(COLOR_CHECK_A)
                canvas_obj.rect(box_x, box_y, box_w, box_h, fill=1, stroke=0)

                canvas_obj.setFillColor(COLOR_CHECK_B)
                rows = int(box_h // CHECKER_SQUARE) + 1
                cols = int(box_w // CHECKER_SQUARE) + 1
                for r in range(rows):
                    for col in range(cols):
                        if (r + col) % 2:
                            canvas_obj.rect(box_x + col * CHECKER_SQUARE,
                                            box_y + r * CHECKER_SQUARE,
                                            CHECKER_SQUARE, CHECKER_SQUARE,
                                            fill=1, stroke=0)
                canvas_obj.restoreState()

            def draw_page_chrome(canvas_obj, page_num):
                canvas_obj.saveState()
                # PDF-01: the sheet itself. White paper needs no fill, but the
                # dark paper does, and it has to go down before anything else.
                if self.paper != "light":
                    canvas_obj.setFillColor(COLOR_PAGE)
                    canvas_obj.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
                # Header
                canvas_obj.setFillColor(COLOR_HEADER_BG)
                canvas_obj.rect(0, PAGE_HEIGHT - HEADER_HEIGHT, PAGE_WIDTH, HEADER_HEIGHT, fill=1, stroke=0)
                try:
                    logo = ImageReader(logo_path)
                    canvas_obj.drawImage(logo, 0.25 * inch, PAGE_HEIGHT - 0.45 * inch, width=0.4 * inch, height=0.4 * inch, preserveAspectRatio=True, mask='auto')
                except Exception: pass
                # A hairline of the accent under the band, so the header
                # reads as a masthead rather than as a block of navy.
                canvas_obj.setFillColor(COLOR_RULE)
                canvas_obj.rect(0, PAGE_HEIGHT - HEADER_HEIGHT, PAGE_WIDTH, 1.2, fill=1, stroke=0)
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

            # PDF-01: the title page was three lines in a box on an otherwise
            # blank sheet. It now carries the summary the report already
            # implies -- what formats and sizes are in here, and how much of it
            # there is -- because that is the question someone opens a texture
            # report to answer, and every value is already in hand.
            def tally(key):
                counts = {}
                for entry in self.info_data:
                    value = str(entry.get(key) or "N/A")
                    counts[value] = counts.get(value, 0) + 1
                return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

            def summarise(pairs, limit=3):
                shown = ", ".join("{} x{}".format(name, n) for name, n in pairs[:limit])
                if len(pairs) > limit:
                    shown += "  (+{} more)".format(len(pairs) - limit)
                return shown or "N/A"

            total_bytes = 0
            for entry in self.info_data:
                try:
                    total_bytes += int(entry.get('size') or 0)
                except (TypeError, ValueError):
                    pass
            total_size = "{:.2f} MB".format(total_bytes / (1024.0 * 1024.0)) \
                if total_bytes >= 1024 * 1024 else "{:.2f} KB".format(total_bytes / 1024.0)

            source_file = os.path.basename(self.info_data[0]['path'].split('_cache_')[0]) if self.info_data else "Unknown"
            summary_rows = [
                ("Source File", source_file),
                ("Total Images", str(total_images)),
                ("Total Size", total_size),
                ("Formats", summarise(tally('format'))),
                ("Dimensions", summarise(tally('dimensions'))),
                ("Report Date", datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ]

            BOX_LEFT = 1.25 * inch
            BOX_WIDTH = PAGE_WIDTH - (2 * BOX_LEFT)
            ROW_HEIGHT = 22
            BOX_HEIGHT = (len(summary_rows) * ROW_HEIGHT) + 24
            info_box_y = PAGE_HEIGHT - 4.0 * inch

            c.setStrokeColor(COLOR_BORDER)
            c.setFillColor(COLOR_CELL_BG)
            c.roundRect(BOX_LEFT, info_box_y - BOX_HEIGHT, BOX_WIDTH, BOX_HEIGHT, 4, stroke=1, fill=1)

            LABEL_X = BOX_LEFT + 18
            VALUE_X = BOX_LEFT + 108
            VALUE_WIDTH = BOX_WIDTH - (VALUE_X - BOX_LEFT) - 18
            row_y = info_box_y - 30
            for label, value in summary_rows:
                c.setFont("Helvetica", 10)
                c.setFillColor(COLOR_TEXT_LABEL)
                c.drawString(LABEL_X, row_y, "{}:".format(label))
                c.setFont("Helvetica-Bold", 10)
                c.setFillColor(COLOR_TEXT_DARK)
                # The same middle-trim the cells use: a long source name loses
                # its middle rather than running out of the box.
                shown = value
                if c.stringWidth(shown, "Helvetica-Bold", 10) > VALUE_WIDTH:
                    left, right = shown[:len(shown) // 2], shown[len(shown) // 2:]
                    while (left or right) and c.stringWidth(
                            left + "..." + right, "Helvetica-Bold", 10) > VALUE_WIDTH:
                        if len(left) > len(right):
                            left = left[:-1]
                        else:
                            right = right[1:]
                    shown = left + "..." + right
                c.drawString(VALUE_X, row_y, shown)
                row_y -= ROW_HEIGHT
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

            # PDF-01: the image area used to be a hardcoded 60% of the cell,
            # which left 27.5pt of nothing below the last line of text in all
            # nine cells on every page. It is derived from what the text
            # actually occupies instead, so the picture takes whatever is left
            # and the dead space cannot come back if a line is added or removed.
            CELL_PAD = 6
            TITLE_LEADING = 12          # filename (Helvetica-Bold 7)
            DETAIL_LEADING = 10         # the metadata lines (Helvetica 7)
            DETAIL_LINES = 4            # index, dimensions, format, size/alpha
            TEXT_BLOCK_HEIGHT = TITLE_LEADING + (DETAIL_LINES * DETAIL_LEADING)
            IMG_AREA_HEIGHT = CELL_HEIGHT - TEXT_BLOCK_HEIGHT - (3 * CELL_PAD)

            # PDF-01: a texture smaller than the mat is drawn at its own size
            # rather than blown up to fill it. Capped rather than forbidden:
            # anything that already fits (these assets mostly do) is untouched,
            # while a 32x32 icon stops being magnified 5x into an interpolated
            # smear. Relative sizes across a mixed gallery become honest too.
            MAX_MAGNIFY = 2.0

            def fit_label(text, font, size, max_width):
                """
                PDF-01: shorten from the MIDDLE, not the tail.

                The old code did `text[:-4] + "..."`, which throws away the end
                of the name. These paths share long prefixes
                (`subfolder/subfolder/...`), so the end is the part that
                identifies the file -- and the extension went with it.
                """
                if c.stringWidth(text, font, size) <= max_width:
                    return text
                left, right = text[:len(text) // 2], text[len(text) // 2:]
                while (left or right) and c.stringWidth(
                        left + "..." + right, font, size) > max_width:
                    if len(left) > len(right):
                        left = left[:-1]
                    else:
                        right = right[1:]
                return left + "..." + right

            def human_size(num_bytes):
                """Bytes as the previewer already shows them, e.g. '13.62 KB'."""
                try:
                    size = float(num_bytes)
                except (TypeError, ValueError):
                    return None
                for unit in ("B", "KB", "MB", "GB"):
                    if size < 1024 or unit == "GB":
                        return "{:.2f} {}".format(size, unit) if unit != "B" \
                            else "{:.0f} B".format(size)
                    size /= 1024.0
                return None

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

                img_x = x + CELL_PAD
                img_w = CELL_WIDTH - (2 * CELL_PAD)
                img_h = IMG_AREA_HEIGHT
                img_y = y + CELL_HEIGHT - CELL_PAD - img_h

                has_alpha = None
                try:
                    img_reader = ImageReader(data['path'])

                    # PDF-01: fit to the frame, but never magnify past
                    # MAX_MAGNIFY. drawImage's own preserveAspectRatio always
                    # fills the box, which is what blew small icons up.
                    src_w, src_h = img_reader.getSize()
                    scale = min(img_w / float(src_w), img_h / float(src_h),
                                MAX_MAGNIFY)
                    draw_w, draw_h = src_w * scale, src_h * scale
                    draw_x = img_x + (img_w - draw_w) / 2.0
                    draw_y = img_y + (img_h - draw_h) / 2.0

                    # PDF-01: the mat covers the ARTWORK, not the frame around
                    # it. This was the other way round until the pages were
                    # rendered and looked at: a 32x32 icon sat in a full-size
                    # slab of checker, which read as though the asset filled the
                    # frame, and put a heavy blue-grey block in all nine cells.
                    # In an image editor the checker IS the canvas -- so here it
                    # marks the texture's own extent, which is also what makes
                    # the magnification cap visible rather than merely correct.
                    draw_checkerboard(c, draw_x, draw_y, draw_w, draw_h)
                    c.setStrokeColor(COLOR_BORDER)
                    c.rect(draw_x, draw_y, draw_w, draw_h, fill=0, stroke=1)

                    c.drawImage(img_reader, draw_x, draw_y,
                                width=draw_w, height=draw_h,
                                preserveAspectRatio=True, anchor='c', mask='auto')

                    # Best-effort, and free: reportlab has already decoded the
                    # file, so this reads what it holds rather than opening the
                    # image a second time just to ask. Unknown stays unknown --
                    # the line is simply omitted rather than guessed.
                    try:
                        pil_image = getattr(img_reader, "_image", None)
                        if pil_image is not None:
                            has_alpha = (pil_image.mode in ("RGBA", "LA", "PA")
                                         or "transparency" in getattr(pil_image, "info", {}))
                    except Exception:
                        has_alpha = None

                    del img_reader
                except Exception as e:
                    c.setFont("Helvetica", 10)
                    c.setFillColor(colors.red)
                    c.drawCentredString(img_x + img_w / 2, img_y + img_h / 2, "[Image Error]")
                    # LOG-01: the failure was drawn into the PDF and nowhere
                    # else, so a report full of red "[Image Error]" cells came
                    # with a clean log and no way to tell which images failed.
                    failed_images.append(data.get('filename', '<unknown>'))
                    log_diagnostic("rendering an image into the PDF export", e,
                                   filename=data.get('filename'),
                                   path=data.get('path'))

                text_x = x + CELL_PAD
                text_y = img_y - CELL_PAD - TITLE_LEADING + 4

                c.setFont("Helvetica-Bold", 7)
                c.setFillColor(COLOR_TEXT_DARK)
                available_width = CELL_WIDTH - (2 * CELL_PAD)
                c.drawString(text_x, text_y,
                             fit_label(data['filename'], "Helvetica-Bold", 7, available_width))

                text_y -= TITLE_LEADING
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

                text_y -= DETAIL_LEADING
                c.drawString(text_x, text_y, "Dimensions: {}".format(formatted_dims))
                text_y -= DETAIL_LEADING
                c.drawString(text_x, text_y,
                             fit_label("Format: {}".format(data.get('format', 'N/A')),
                                       "Helvetica", 7, available_width))

                # PDF-01: the record already carries the byte size -- the
                # previewer shows it and the report did not. Alpha matters more
                # than either for a texture, and pairing them costs one line.
                text_y -= DETAIL_LEADING
                detail_bits = []
                size_text = human_size(data.get('size'))
                if size_text:
                    detail_bits.append("Size: {}".format(size_text))
                if has_alpha is not None:
                    detail_bits.append("Alpha: {}".format("Yes" if has_alpha else "No"))
                if detail_bits:
                    c.drawString(text_x, text_y, "  |  ".join(detail_bits))

                if (i + 1) % IMAGES_PER_PAGE == 0 and (i + 1) < total_images:
                    c.showPage()

                if i > 0 and i % 100 == 0:
                    gc.collect()

            c.save()
            if failed_images:
                # Surfaced on the main log channel, not just [DIAG]: a report
                # the user is about to send someone has visible holes in it.
                shown = ", ".join(failed_images[:10])
                more = f" (+{len(failed_images) - 10} more)" if len(failed_images) > 10 else ""
                self.warning.emit(
                    f"[WARN] {len(failed_images)} of {total_images} image(s) could not be "
                    f"rendered and appear as '[Image Error]' in the PDF: {shown}{more}")
            self.finished_with_path.emit("Successfully exported {} items to PDF.".format(len(self.info_data)), self.output_path)
        except Exception as e:
            tb_str = traceback.format_exc()
            self.error.emit("ERROR: Failed to generate PDF. Details: {}\n{}".format(e, tb_str))
        finally:
            del c
            if hasattr(self, 'info_data'):
                del self.info_data
            gc.collect()


# STR-03: UpdateDialog was defined inside TextureToolApp for no reason -- it
# takes no outer state, and being nested meant it could only be reached as
# `self.UpdateDialog`. It is a module-level class now, like every other worker
# and dialog in this file.
class UpdateDialog(SizeRememberingDialog):
    SIZE_KEY = "update"

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
        update_icon = qta.icon('fa5s.cloud-download-alt', color=Glass.ACCENT) # Use theme accent color
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
        scroll_area.setStyleSheet(STYLE_SCROLL_AREA)

        # LAYOUT-01: this was setMaximumHeight(400), which is why the release
        # notes clipped no matter how tall the user made the dialog -- the
        # dialog grew and the notes did not. A minimum instead of a maximum: it
        # keeps the notes from collapsing to a sliver, and lets them take
        # whatever height the user gives the window.
        scroll_area.setMinimumHeight(220)

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

        # LAYOUT-01: stretch factor 1, so extra height goes HERE. Without it
        # QVBoxLayout shared the growth with the icon/title block above -- of
        # 240px added to the dialog the notes received 82, which is why making
        # the window bigger barely helped the clipping it was making room for.
        main_layout.addWidget(scroll_area, 1)

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


class TextureToolApp(QMainWindow):
    """
    The main class for the Kodi TextureTool application.
    It encapsulates the UI, state, and business logic.
    """

    # STR-03: this docstring, the colour palette below, and __init__ all used to
    # sit roughly 200 lines further down, after ~20 methods. The docstring was a
    # no-op string expression mid-class -- the class had no docstring at all --
    # and each colour's comment had drifted onto the line below the constant it
    # described. Every comment here was re-derived from where the constant is
    # actually used, not from guessing the intended offset.

    # STR-08: log-line colours, named for their role. The values come from the
    # single Glass palette rather than being spelled out as hex a second time.
    # The names below are the roles the log grammar uses; the palette names are
    # the colours themselves, which is why COLOR_CYAN now holds a sky blue.
    COLOR_CYAN = Glass.INFO_BLUE        # The '[INFO]' tag
    COLOR_GREEN = Glass.OK_GREEN        # '-----' headers, '[Complete]', '[Started]', '[Passed]', '[Installed]'
    COLOR_RED = Glass.ERROR_RED         # The '[ERROR]' tag and '[Failed]'
    COLOR_YELLOW = Glass.WARN_YELLOW    # The '[WARN]' tag
    COLOR_MAGENTA = Glass.DATA_PURPLE   # The '[DATA]' tag
    COLOR_ORANGE = Glass.LOAD_ORANGE    # The '[LOAD]' tag
    COLOR_DEFAULT = Glass.TEXT          # Body text of every log line
    COLOR_SOFT_GOLD = Glass.SOFT_GOLD   # The 'checking for updates' notification icon
    COLOR_NUMERIC = Glass.NUMERIC       # Versions, timestamps, dates, sizes, highlighted literals

    # BUG-20: the numeric-highlight replacement was rebuilt as an f-string on
    # every `re.sub` call inside `_format_log_message` -- three per `[DATA]`
    # line, and a Get Info over a large archive pushes ~22,750 lines through it
    # in one blocking pass. Built once here instead.
    SPAN_NUMERIC = f'<span style="color:{COLOR_NUMERIC};">\\1</span>'

    # STR-08: the inline styles below were the fourth copy of the palette. They
    # remain inline because they are per-widget state, not global rules -- but
    # they no longer carry their own hex literals.
    # The mat the texture sits on. A well rather than a film: a preview needs
    # the darkest ground in the window behind it so the artwork -- which is
    # frequently pale, and frequently transparent -- reads against something
    # that is not competing with it.
    STYLE_PREVIEW_NORMAL = (f"border: 1px solid {FILM_LINE}; border-radius: 8px; "
                            f"background-color: {WELL_DEEP};")
    STYLE_PREVIEW_ERROR = (f"border: 1px solid {Glass.ERROR_RED}; border-radius: 8px; "
                           f"background-color: {WELL_DEEP}; "
                           f"color: {Glass.ERROR_RED}; font-weight: bold;")
    STYLE_SEARCH_NO_MATCH = f"background-color: {_rgba(Glass.ERROR_RED, 0.45)};"

    # Maximum number of recent items to track
    MAX_RECENT = 8
    update_check_complete = Signal(dict, bool)

    # STR-05: the descriptor table behind _apply_path_selection and _open_recent.
    # Everything that used to differ between the eight copy-pasted methods lives
    # here as data. `config_stores_parent` records that a *file* selection stores
    # its parent directory as the config path, which is why two slots differ.
    # `data_log` wording is preserved verbatim from the original methods -- these
    # strings appear in users' log files.
    PATH_SLOTS = {
        PathSlot.DECOMPILE_INPUT: {
            'state_attr': 'decompile_input_file',
            'label_attr': 'decompile_input_label',
            'config_key': 'decompileinput',
            'config_stores_parent': True,
            'data_log': 'Decompile input file: "{}"',
            'info_log': 'Input selection loaded successfully.',
            'recent_group': RecentGroup.DECOMPILE_FILES,
            'clear_gallery': True,
            'start_btn_attr': None,
            'noun': 'decompile file',
        },
        PathSlot.DECOMPILE_OUTPUT: {
            'state_attr': 'decompile_output_folder',
            'label_attr': 'decompile_output_label',
            'config_key': 'decompileoutput',
            'config_stores_parent': False,
            'data_log': 'Decompile output directory: "{}"',
            'info_log': 'Output folder destination loaded successfully.',
            'recent_group': RecentGroup.DECOMPILE_FOLDERS,
            'clear_gallery': False,
            'start_btn_attr': 'decompile_start_btn',
            'noun': 'decompile folder',
        },
        PathSlot.COMPILE_INPUT: {
            'state_attr': 'compile_input_folder',
            'label_attr': 'compile_input_label',
            'config_key': 'compileinput',
            'config_stores_parent': False,
            'data_log': 'Path to directory: "{}"',
            'info_log': 'Image folder input selection loaded successfully.',
            'recent_group': RecentGroup.COMPILE_FOLDERS,
            'clear_gallery': False,
            'start_btn_attr': None,
            'noun': 'compile folder',
        },
        PathSlot.COMPILE_OUTPUT: {
            'state_attr': 'compile_output_file',
            'label_attr': 'compile_output_label',
            'config_key': 'compileoutput',
            'config_stores_parent': True,
            'data_log': 'Path to output file: "{}"',
            'info_log': 'Output folder destination loaded successfully.',
            'recent_group': RecentGroup.COMPILE_FILES,
            'clear_gallery': False,
            'start_btn_attr': 'compile_start_btn',
            'noun': 'compile file',
        },
    }

    RUNTIMES_MISSING_TOOLTIP = "Disabled. Required C++ Runtimes are missing. See Display menu."

    # STR-03: __init__ was the 15th method in this class body, roughly 190
    # lines below the class constants it initialises. Constants first, then
    # the constructor, then the methods.
    def __init__(self):
        # STR-03: super() genuinely is first now. It used to sit below five
        # attribute assignments, directly under a comment claiming it had been
        # moved first as the "CRITICAL FIX".
        super().__init__()

        self.main_splitter = None
        self.last_displayed_index = -1 # Track for zoom reset logic.
        self.is_image_zoomed = False   # Track for zoom reset logic.
        self.current_zoom_level = 1.0  # Track zoom factor for overlay display
        # BUG-11: the full-resolution pixmap for the image on display, plus the
        # size it occupies at zoom 1.0 ("fit"). Every zoom step rescales from
        # this source, so detail is never destroyed. Zooming used to rescale the
        # already-scaled label pixmap, which threw away pixels on the way out and
        # could not recover them on the way back in.
        self._preview_source_pixmap = None
        self._preview_fit_size = None



        self.log_lock = threading.RLock()

        # BUG-17: default OFF. These default to ON historically, but the
        # feature never actually ran (see BUG-16: _delayed_open_folder armed
        # its QTimer on the worker thread, whose event loop was torn down
        # microseconds later by the finished->quit connection, so the timer
        # never fired). Fixing the threading made it work for the first time,
        # which would have given every upgrading user surprise Explorer
        # windows after every compile and decompile.
        self.open_decompile_on_complete = False
        self.open_compile_on_complete = False
        self.open_pdf_on_complete = True
        self.pdf_paper = 'light'   # PDF-01; _load_settings overrides
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
                log_diagnostic("creating the initial config.ini", e, path=self.config_path)

        # STR-06: the single parse of config.ini. Every accessor below reads from
        # self.config in memory from here on, and writes go straight back to disk.
        self._read_config_file()

        self.workspace_dir = None
        # SEC-03: update artifacts are staged here, outside the application tree.
        self.update_staging_dir = None
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
        # LOG-01: a `log_batch_timer` QTimer was built here and wired to
        # _process_log_message_buffer, but never started -- three lines that
        # looked like the buffer drained on a 10ms tick when it only ever
        # drained once, on completion (the singleShot in _on_process_finished).
        # Removed rather than started: BUG-20 batched this path precisely to
        # stop per-line GUI work during a large parse, and a 10ms tick would
        # walk that back. The failure paths now drain a bounded tail instead,
        # via _drain_log_buffer_tail.
        self.log_message_buffer = deque() # Use deque for efficient pop
        self._task_start_times = {}  # LOG-01: operation key -> monotonic start
        # --- END STATE ---

        self.REQUIRED_FILES = ["utils/TexturePacker_Compile/gif.dll", "utils/TexturePacker_Compile/jpeg62.dll", "utils/TexturePacker_Compile/libpng16.dll", "utils/TexturePacker_Compile/lzo2.dll", "utils/TexturePacker_Compile/TextureCompiler.exe", "utils/TexturePacker_Compile/zlib1.dll", "utils/TexturePacker_Decompile/getopt.dll", "utils/TexturePacker_Decompile/gif.dll", "utils/TexturePacker_Decompile/jpeg62.dll", "utils/TexturePacker_Decompile/libpng16.dll", "utils/TexturePacker_Decompile/lzo2.dll", "utils/TexturePacker_Decompile/squish.dll", "utils/TexturePacker_Decompile/TextureExtractor.exe", "utils/TexturePacker_Decompile/zlib1.dll"]
        self._init_recent()

        self.file_logger = FileLogger(log_path=os.path.join(config_dir, 'TextureTool_Log.txt'))
        # STR-07: from here on, log_diagnostic() writes to the same file. Anything
        # recorded before this point was buffered and is flushed now.
        bind_diagnostic_logger(self.file_logger)
        self.app_icon = QIcon(get_resource_path("assets/fav.ico"))
        self.tray_icon = QSystemTrayIcon(QIcon(get_resource_path("assets/fav.ico")), None)
        self.tray_icon.setToolTip(APP_TITLE)
        self.tray_icon.show()
        self.decompile_thread, self.decompile_worker = None, None
        self.compile_thread, self.compile_worker = None, None
        self.installer_thread, self.installer_worker = None, None
        self.info_thread, self.info_worker = None, None

        self.decompile_input_file, self.decompile_output_folder, self.compile_input_folder, self.compile_output_file = "", "", "", ""
        # BUG-16: carried for the bound-method adapters that replaced the
        # lambda/partial connections; set again at each task start.
        self.decompile_task_name = "decompile"
        self.update_check_manual = False
        # BUG-02: staged compile output, swapped into place only on success.
        self.compile_temp_output = None
        self.compile_final_output = None
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
        # STR-06: served from the in-memory config; no re-read.
        if not self.config.has_section('Recent'):
            return
        for group in RecentGroup:
            try:
                # Dynamically get the list from config and set the instance attribute
                recent_items = json.loads(self.config.get('Recent', group.value, fallback='[]'))
                # GUI-02: existing config files can already hold the same path in
                # both spellings. Canonicalise on load and collapse the duplicates,
                # preserving order, so the menus clean themselves up on next start.
                seen = set()
                deduped = []
                for item in recent_items:
                    canonical = self._normalize_path(item)
                    if canonical not in seen:
                        seen.add(canonical)
                        deduped.append(canonical)
                setattr(self, f'recent_{group.value}', deduped)
            except Exception as e:
                # On failure, set an empty list for that specific group.
                # STR-07: the user silently loses that recent list and is told
                # nothing. Record what was in the file so it can be explained.
                log_diagnostic("loading a recent-items list from config.ini", e,
                               group=group.value, config_path=self.config_path,
                               raw=self.config.get('Recent', group.value, fallback='')[:200])
                setattr(self, f'recent_{group.value}', [])
    
    def _save_recent(self):
        # STR-06: no re-read. _add_recent calls this on every path the user
        # picks, so this was a full parse plus a full rewrite per selection.
        if not self.config.has_section('Recent'):
            self.config.add_section('Recent')
        for group in RecentGroup:
            # Dynamically get the instance attribute and save it to config
            recent_list = getattr(self, f'recent_{group.value}')
            self.config.set('Recent', group.value, json.dumps(recent_list))
        self._write_config_file()

    @staticmethod
    def _normalize_path(path):
        """
    GUI-02: canonical spelling for any path that will be stored or compared.

    Drag-and-drop delivers forward slashes (`QUrl.toLocalFile` returns
    `C:/Users/...`) while the file dialogs deliver backslashes. Without this the
    same folder shows up twice in a Recent menu -- once per route -- because
    _add_recent's de-duplication compares the strings and they never match.
    """
        if not path:
            return path
        try:
            return os.path.normpath(path)
        except (TypeError, ValueError) as e:
            log_diagnostic("normalising a selected path", e, path=path)
            return path

    def _add_recent(self, group: RecentGroup, path):
        # Get the string value from the enum member for dynamic attribute access
        group_name = group.value
        path = self._normalize_path(path)          # GUI-02
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
        # LOG-01: this discards persisted data on a single menu click, and said
        # nothing. The count is what makes it recognisable afterwards as the
        # reason a list the user expected to be populated is empty.
        removed = len(getattr(self, f'recent_{group_name}', []) or [])
        setattr(self, f'recent_{group_name}', [])
        self._save_recent()
        self._update_recent_menus()
        self._log_message(f"[INFO] Cleared recent '{group_name}' list ({removed} item(s)).")

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

    def _apply_path_selection(self, slot: PathSlot, path):
        """
    STR-05: the single implementation behind all four `_handle_*_path` methods
    and the found-branch of all four `_open_recent_*` methods -- eight
    copy-pasted bodies before. Everything that varies comes from PATH_SLOTS.
    """
        spec = self.PATH_SLOTS[slot]
        # GUI-02: canonicalise once, here, so the stored state, the label tooltip,
        # the config entry and the recent list all agree regardless of whether the
        # path arrived from a file dialog, a drop, or a Recent menu.
        path = self._normalize_path(path)

        if spec['clear_gallery']:
            self._clear_gallery()

        setattr(self, spec['state_attr'], path)

        label = getattr(self, spec['label_attr'])
        label.setText("..\\{}".format(os.path.basename(path)))
        # The recent-path copies used to call setToolTip twice, the first call
        # (with the basename) immediately overwritten by the second. Only the
        # full path was ever visible; that is what is kept.
        label.setToolTip(path)
        label.setProperty("state", "selected")
        label.style().unpolish(label)
        label.style().polish(label)

        config_value = os.path.dirname(path) if spec['config_stores_parent'] else path
        self._set_config_path(spec['config_key'], config_value)

        # Previously applied only by the _handle_*_path copies, never by the
        # recent-path ones. Applying it consistently is the point of the merge:
        # a disabled Start button now always explains why.
        if spec['start_btn_attr'] and not self.vcredist_checks_passed:
            getattr(self, spec['start_btn_attr']).setToolTip(self.RUNTIMES_MISSING_TOOLTIP)

        self._log_message('[DATA] ' + spec['data_log'].format(os.path.normpath(path)))
        self._log_message('[INFO] ' + spec['info_log'])
        self._add_recent(spec['recent_group'], path)
        self._update_button_states()
        self._update_status_label()

    def _open_recent(self, slot: PathSlot, path):
        """
    STR-05: opens a path chosen from a Recent submenu, or drops it from the list
    if it has since been moved or deleted.
    """
        # GUI-02: normalise before the existence check, so a stale entry stored in
        # the other spelling still matches when it has to be pruned below.
        path = self._normalize_path(path)

        if os.path.exists(path):
            self._apply_path_selection(slot, path)
            return

        spec = self.PATH_SLOTS[slot]
        noun = spec['noun']                       # e.g. "decompile folder"
        kind = noun.split()[-1].capitalize()      # "File" or "Folder"
        recent_attr = 'recent_{}'.format(spec['recent_group'].value)

        self._log_message("[WARN] Recent {} not found, removing from list: {}".format(noun, path))
        # BUG-09: an unguarded remove() raises ValueError if the entry is already
        # gone (two menu clicks on the same stale path, or a list rewritten
        # between the menu being built and the action firing).
        recent_list = getattr(self, recent_attr)
        if path in recent_list:
            recent_list.remove(path)
        self._save_recent()
        self._update_recent_menus()
        QMessageBox.warning(
            self, "Recent {} Not Found".format(kind),
            "The recent {} could not be found and has been removed from the list:\n\n{}".format(noun, path))

    # Named wrappers: these are what the Recent submenus connect to, and they
    # keep the call sites self-describing.
    def _open_recent_compile_file(self, path):
        self._open_recent(PathSlot.COMPILE_OUTPUT, path)

    def _open_recent_compile_folder(self, path):
        self._open_recent(PathSlot.COMPILE_INPUT, path)

    def _open_recent_decompile_file(self, path):
        self._open_recent(PathSlot.DECOMPILE_INPUT, path)

    def _open_recent_decompile_folder(self, path):
        self._open_recent(PathSlot.DECOMPILE_OUTPUT, path)


    def _open_last_decompile_input(self):
        """Opens the most recent decompile input file."""
        if self.recent_decompile_files:
            self._open_recent_decompile_file(self.recent_decompile_files[0])
    
    def _open_last_compile_input(self):
        """Opens the most recent compile input folder."""
        if self.recent_compile_folders:
            self._open_recent_compile_folder(self.recent_compile_folders[0])

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
    
    # -----------------------------------------------------------------------
    # STR-06 -- config.ini access
    # -----------------------------------------------------------------------
    # Every one of the six accessors used to begin with self.config.read(...),
    # re-parsing the whole ini from disk on each call -- and _add_recent runs a
    # read *and* a write for every path the user picks. Nothing outside this
    # process writes the file, so self.config is already the authority: it is
    # read once at startup and served from memory thereafter.
    #
    # Writes still go straight to disk on every change. That is deliberate --
    # the app is expected to survive being killed, and the write is small.

    def _read_config_file(self):
        """STR-06: the one place config.ini is parsed from disk."""
        try:
            self.config.read(self.config_path, encoding='utf-8')
        except (OSError, configparser.Error) as e:
            # STR-07: a config file that will not parse means every setting
            # silently falls back to its default, which looks to the user like
            # the app forgot everything.
            log_diagnostic("reading config.ini", e, path=self.config_path)

    def _write_config_file(self):
        """STR-06: the one place config.ini is written back."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)
            return True
        except (OSError, configparser.Error) as e:
            # STR-07: previously this raised out of a settings toggle. Now the
            # setting simply does not persist, and the reason is on record.
            log_diagnostic("writing config.ini", e, path=self.config_path)
            return False

    def _get_config_path(self, key):
        """Reads a path from the in-memory config (see _read_config_file)."""
        return self.config.get('Paths', key, fallback=self.app_dir)

    def _set_config_path(self, key, path):
        """Writes a path to the config.ini file."""
        if not self.config.has_section('Paths'):
            self.config.add_section('Paths')
        self.config.set('Paths', key, path)
        self._write_config_file()

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

        # BUG-06: this used to be a single exact-match comparison against
        #   "Microsoft Visual C++ 2010  x86 Redistributable - 10.0.40219"
        # including the double space and that exact build number. Any localized
        # Windows, or any serviced build (10.0.40219 is the SP1 release; other
        # builds exist), reported "not installed" -- and this flag gates compile,
        # decompile AND updates. Two locale-independent strategies now run first,
        # with the old string kept only as a last-resort exact match.

        # Strategy 1: the VCRedist key the installer itself writes. Values are
        # numeric, so no display string and no localization is involved.
        vcredist_keys = [
            r"SOFTWARE\Microsoft\VisualStudio\10.0\VC\VCRedist\x86",
            r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\10.0\VC\VCRedist\x86",
        ]
        for key_path in vcredist_keys:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    installed, _ = winreg.QueryValueEx(key, "Installed")
                    if int(installed) == 1:
                        self._add_diagnostic_message(f"[INFO] VC++ 2010 x86 found via {key_path}.")
                        return True
            except (FileNotFoundError, OSError, ValueError, TypeError):
                continue

        # Strategy 2: scan the uninstall keys, but match on the stable tokens
        # rather than the whole localized string. The product name segment
        # "Visual C++ 2010" and the "x86" architecture marker survive
        # localization on every sample seen; the trailing version does not.
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
                                # Collapse runs of whitespace so the notorious
                                # double space in "2010  x86" stops mattering.
                                normalized = " ".join(str(display_name).split()).lower()
                                if "visual c++ 2010" in normalized and "x86" in normalized:
                                    self._add_diagnostic_message(f"[INFO] VC++ 2010 x86 found: {display_name}")
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

    def _sweep_stale_update_staging(self):
        """
    SEC-03: removes abandoned update staging directories left by a crash or a
    cancelled update, so downloaded payloads do not linger in %TEMP%.

    Only directories older than 24 hours are touched. A freshly relaunched app
    can still be racing its own updater's self-cleanup, and deleting that dir
    out from under a running batch script would be worse than leaving it.
    """
        prefix = "ktt_update_"
        cutoff = datetime.now() - timedelta(hours=24)
        temp_root = tempfile.gettempdir()
        try:
            for item_name in os.listdir(temp_root):
                if not item_name.startswith(prefix):
                    continue
                item_path = os.path.join(temp_root, item_name)
                if not os.path.isdir(item_path):
                    continue
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(item_path))
                    if mtime < cutoff:
                        shutil.rmtree(item_path, ignore_errors=True)
                        self._add_diagnostic_message(
                            f"[INFO] Removed stale update staging directory: {item_path}")
                except OSError as e:
                    # STR-07: a staging directory that cannot be swept keeps
                    # accumulating in %TEMP% on every run, unnoticed.
                    log_diagnostic("sweeping a stale update staging directory", e,
                                   path=item_path)
                    continue
        except Exception as e:
            self._add_diagnostic_message(f"[WARN] Update staging sweep failed: {e}")
            log_diagnostic("sweeping stale update staging directories", e,
                           temp_root=tempfile.gettempdir())

    def _cleanup_workspace(self):
        '''Removes the temporary workspace directory upon application exit.'''
        # STR-07: both handlers below still fail silently as far as the user is
        # concerned -- nothing useful can be shown during exit, and that is the
        # right call. But a workspace that will not delete is a real symptom:
        # it usually means a child process still holds a file open, which is
        # exactly the kind of thing BUG-04 was about. It is now on record.

        # Clean up main temp workspace
        if self.workspace_dir and os.path.exists(self.workspace_dir):
            try:
                shutil.rmtree(self.workspace_dir)
            except Exception as e:
                log_diagnostic("removing the temporary workspace on exit", e,
                               path=self.workspace_dir)

        # Clean up info cache directory
        if self.info_cache_dir and os.path.exists(self.info_cache_dir):
            try:
                shutil.rmtree(self.info_cache_dir)
            except Exception as e:
                log_diagnostic("removing the info cache directory on exit", e,
                               path=self.info_cache_dir)

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

    def _log_environment(self):
        """
        Records the machine and build the session is running on (LOG-01).

        A support log used to open with the version and nothing else, so every
        question that turned on the environment -- which Windows, was this the
        frozen build or a source run, where is it installed, which config did it
        read, was the disk full -- had to be asked in a round trip, and often
        went unanswered. All of it is cheap and known at startup, so it is
        written once here rather than requested later.
        """
        self._add_diagnostic_message(f'[DATA] Build Date: {BUILD_DATE}')
        frozen = getattr(sys, 'frozen', False)
        self._add_diagnostic_message(
            f'[DATA] Running: {"frozen build" if frozen else "from source"} | {sys.executable}')
        self._add_diagnostic_message(f'[DATA] Install Dir: {self.app_dir}')
        # None when _setup_temp_workspace failed -- which it logs, and which is
        # worth seeing spelled out here rather than as an empty field.
        self._add_diagnostic_message(
            f'[DATA] Workspace Dir: {self.workspace_dir or "UNAVAILABLE (workspace setup failed)"}')
        self._add_diagnostic_message(f'[DATA] Config File: {self.config_path}')
        self._add_diagnostic_message(f'[DATA] Log File: {self.file_logger.log_path}')

        self._add_diagnostic_message(
            f'[DATA] OS: {platform.platform()} | {platform.machine()}')
        self._add_diagnostic_message(
            f'[DATA] Python: {platform.python_version()} | Qt: {qVersion()} | PySide6: {PySide6.__version__}')

        probe_dir = self.workspace_dir or self.app_dir
        try:
            usage = shutil.disk_usage(probe_dir)
            self._add_diagnostic_message(
                f'[DATA] Disk ({probe_dir}): {usage.free // (1024 * 1024):,} MB free '
                f'of {usage.total // (1024 * 1024):,} MB')
        except Exception as e:
            log_diagnostic("reading free disk space for the startup banner", e, path=probe_dir)

    def _perform_startup_checks(self):
        self._add_diagnostic_message('[INFO] ----- Program Start -----')
        self._add_diagnostic_message(f'[INFO] Current Time: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}')
        self._add_diagnostic_message(f'[INFO] Running Version: {APP_VERSION}')
        self._log_environment()
        self._sweep_stale_update_staging()
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
        # LAYOUT-01: kept only to migrate a layout saved by an older version --
        # see _migrate_registry_layout. Nothing is written to it any more.
        self.settings = QSettings("KodiTextureTool", "TextureTool")
        self._migrate_registry_layout()
        self._restore_window_layout()
        shortcut_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        shortcut_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        shortcut_up = QShortcut(QKeySequence(Qt.Key.Key_Up), self)
        shortcut_down = QShortcut(QKeySequence(Qt.Key.Key_Down), self)
        
        shortcut_left.activated.connect(self._nav_prev)
        shortcut_right.activated.connect(self._nav_next)
        shortcut_up.activated.connect(self._zoom_in)
        shortcut_down.activated.connect(self._zoom_out)
    # BUG-04: every QThread this window owns. closeEvent used to kill the child
    # processes but never quit() or wait() on the threads driving them, so Qt
    # tore down running QThreads during shutdown -- the classic
    # "QThread: Destroyed while thread is still running" abort. SEC-03 made this
    # reachable on the update path too: the updater now exits through
    # QApplication.quit() instead of os._exit(0), so closeEvent actually runs.
    _OWNED_THREADS = [
        ('compile_thread', 'compile_worker'),
        ('decompile_thread', 'decompile_worker'),
        ('info_thread', 'info_worker'),
        ('installer_thread', 'installer_worker'),
        ('decompile_for_info_thread', 'decompile_for_info_worker'),
        ('pdf_export_thread', 'pdf_export_worker'),
        ('update_thread', 'update_worker'),
        ('download_thread', 'download_worker'),
    ]

    # Milliseconds to wait for a thread to unwind before giving up on it. The
    # child process has already been killed by then, so the reader loops are
    # unblocked and this is expected to return almost immediately.
    THREAD_SHUTDOWN_TIMEOUT_MS = 5000

    def closeEvent(self, event):
        # LOG-01: the log had no closing line, so a log that simply stopped was
        # indistinguishable from one cut off by a crash -- and with the log now
        # kept for a second session, telling those apart is the point.
        self._log_message('[INFO] ----- Shutdown Requested -----')

        # STABILITY FIX: Ensure any running subprocess is terminated before exiting.
        # This prevents orphaned processes and potential file-locking issues.
        for thread_attr, worker_attr in self._OWNED_THREADS:
            worker = getattr(self, worker_attr, None)
            if worker and getattr(worker, 'process', None):
                if worker.process.poll() is None: # Check if process is still running
                    try:
                        self._log_message(f"[WARN] Terminating active '{thread_attr}' process before exit.")
                        worker.process.kill()
                    except Exception as e:
                        self._log_message(f"[ERROR] Could not terminate process on exit: {e}")

        # BUG-04: now stop the threads themselves. Killing the process above is
        # what lets the blocked reader loops return, so this must come second.
        for thread_attr, _worker_attr in self._OWNED_THREADS:
            thread = getattr(self, thread_attr, None)
            if thread is None:
                continue
            try:
                if not thread.isRunning():
                    continue
                thread.quit()
                if not thread.wait(self.THREAD_SHUTDOWN_TIMEOUT_MS):
                    # Last resort. terminate() is unsafe in general, but the
                    # alternative here is Qt aborting the process on teardown.
                    self._log_message(f"[WARN] '{thread_attr}' did not stop in time; forcing termination.")
                    thread.terminate()
                    thread.wait(1000)
            except RuntimeError:
                # The underlying C++ object was already deleted (deleteLater ran).
                # Nothing to stop.
                continue
            except Exception as e:
                self._log_message(f"[ERROR] Could not stop '{thread_attr}' on exit: {e}")

        # LAYOUT-01: the layout goes to config.ini now, not the registry.
        # BUG-04's lesson still applies -- this runs while handling the close,
        # so it must not be able to raise and trap the user in the window.
        try:
            self._save_window_layout()
        except Exception as e:
            log_diagnostic("saving the window layout on close", e)

        # The preferences that are only known at exit -- the zoom the previewer
        # was left at, and the search criterion. Everything else in [Settings]
        # is already written when the user changes it.
        try:
            self._save_settings()
        except Exception as e:
            log_diagnostic("saving preferences on close", e)

        # Last line written this session: reaching it is the proof the shutdown
        # ran to completion. Its absence in a .prev log is the crash signature.
        self._log_message('[INFO] ----- Program Exit (clean) -----')

        super().closeEvent(event)

    def _migrate_registry_layout(self):
        """
        LAYOUT-01: one-time import of a layout saved by v3.2.0 or earlier.

        Those versions wrote to QSettings -- the Windows registry. Users who
        have a layout there should not lose it just because the store moved, so
        it is copied into config.ini once and the fact recorded. The registry
        keys are then removed: leaving two copies is how they drift apart, and
        the reason the layout was invisible in config.ini in the first place.
        """
        try:
            if self.config.getboolean('Settings', 'layout_migrated', fallback=False):
                return
            if not self.config.has_section('Window'):
                self.config.add_section('Window')

            moved = []
            for registry_key, ini_key in (("geometry", "geometry"),
                                          ("mainSplitter", "main_splitter"),
                                          ("rightPanelSplitter", "right_splitter")):
                value = self.settings.value(registry_key)
                if value:
                    encoded = encode_qt_state(value)
                    if encoded:
                        self.config.set('Window', ini_key, encoded)
                        moved.append(ini_key)
                self.settings.remove(registry_key)

            if not self.config.has_section('Settings'):
                self.config.add_section('Settings')
            self.config.set('Settings', 'layout_migrated', 'True')
            self._write_config_file()
            if moved:
                log_diagnostic("LAYOUT-01: migrated window layout from the registry "
                               "into config.ini", moved=", ".join(moved))
        except Exception as e:
            # A failed migration must never stop the window from opening. The
            # worst case is a layout that falls back to the defaults.
            log_diagnostic("migrating the window layout out of the registry", e)

    def _restore_window_layout(self):
        """LAYOUT-01: geometry and both splitters, from config.ini."""
        geometry = decode_qt_state(self.config.get('Window', 'geometry', fallback=''))
        if geometry is not None:
            self.restoreGeometry(geometry)
            self._ensure_on_screen()

        main_state = decode_qt_state(self.config.get('Window', 'main_splitter', fallback=''))
        if main_state is not None and getattr(self, 'main_splitter', None):
            self.main_splitter.restoreState(main_state)

        right_state = decode_qt_state(self.config.get('Window', 'right_splitter', fallback=''))
        if right_state is not None and getattr(self, 'right_panel_splitter', None):
            self.right_panel_splitter.restoreState(right_state)

    def _ensure_on_screen(self):
        """
        LAYOUT-01: drags a restored window back onto a screen that exists.

        This is the cost of making the layout portable, and it is the whole
        reason it is handled rather than assumed: a config.ini carried from a
        three-monitor desk to a laptop holds coordinates for a screen that is
        not there, and Qt will happily honour them.
        """
        screen = QApplication.screenAt(self.frameGeometry().center())
        if screen is not None:
            return                      # its centre is on a real screen; fine.

        primary = QApplication.primaryScreen()
        if primary is None:
            return
        available = primary.availableGeometry()
        frame = self.frameGeometry()
        self.resize(min(self.width(), available.width() - 40),
                    min(self.height(), available.height() - 60))
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())
        log_diagnostic("LAYOUT-01: saved window position was off-screen; recentred")

    def _save_window_layout(self):
        """LAYOUT-01: the inverse of _restore_window_layout."""
        if not self.config.has_section('Window'):
            self.config.add_section('Window')
        self.config.set('Window', 'geometry', encode_qt_state(self.saveGeometry()))
        if getattr(self, 'main_splitter', None):
            self.config.set('Window', 'main_splitter',
                            encode_qt_state(self.main_splitter.saveState()))
        if getattr(self, 'right_panel_splitter', None):
            self.config.set('Window', 'right_splitter',
                            encode_qt_state(self.right_panel_splitter.saveState()))
        self._write_config_file()

    def _reset_window_geometry(self):
        """Resets the window to the center of the screen and clears the saved geometry."""
        # LAYOUT-01: clears the dialog sizes too. "Reset Window Size & Position"
        # is where a user goes when something is off-screen or absurdly sized,
        # and a remembered dialog size is exactly as capable of both.
        for section, key in (('Window', 'geometry'),
                             ('Window', 'main_splitter'),
                             ('Window', 'right_splitter')):
            if self.config.has_option(section, key):
                self.config.remove_option(section, key)
        if self.config.has_section('Dialogs'):
            self.config.remove_section('Dialogs')
        self._write_config_file()
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
        self.decompile_start_btn = QPushButton(qta.icon('fa5s.play', color=Glass.BRIGHT), " Start")
        # UI-01: the object name the global sheet fills with Frost. Both Start
        # buttons carry it; nothing else in the window does.
        self.decompile_start_btn.setObjectName("PrimaryButton")
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
        self.compile_start_btn = QPushButton(qta.icon('fa5s.play', color=Glass.BRIGHT), " Start")
        self.compile_start_btn.setObjectName("PrimaryButton")  # UI-01, see above
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
        self.image_display_label.setStyleSheet(self.STYLE_PREVIEW_NORMAL)

        # BUG-11b: the label lives inside a scroll area so a magnified pixmap can
        # be panned instead of centre-cropped -- and, just as importantly, so the
        # label's sizeHint stops driving the layout. A QLabel reports the pixmap
        # size as its hint, so past roughly 6x the preview was wide enough to
        # fight the splitter for space and the whole left-hand control column
        # visibly jumped sideways on every zoom step. The scroll area is what the
        # layout measures now, and its Ignored size policy means it takes the
        # space it is given no matter how large the label inside it grows.
        self.image_scroll_area = QScrollArea()
        self.image_scroll_area.setObjectName("PreviewScrollArea")
        self.image_scroll_area.setWidget(self.image_display_label)
        self.image_scroll_area.setWidgetResizable(True)
        self.image_scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.image_scroll_area.setMinimumHeight(200)
        self.image_scroll_area.setSizePolicy(QSizePolicy.Policy.Ignored,
                                             QSizePolicy.Policy.Ignored)
        self.image_scroll_area.viewport().setStyleSheet("background: transparent;")
        image_container_layout.addWidget(self.image_scroll_area, 0, 0)

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
        # UI-01: this is the only button in the window with setMenu(), so it is
        # the only one that needs padding cleared for the drop-down indicator.
        self.export_pdf_btn.setObjectName("MenuButton")
        self.export_pdf_btn.setToolTip("Export the retrieved image info to a PDF gallery")
        self.export_pdf_btn.setEnabled(False)
        self.export_pdf_menu = QMenu(self)
        self.export_all_action = QAction("Export All...", self)
        self.export_filtered_action = QAction("Export Filtered...", self)
        self.export_selected_action = QAction("Export Selected...", self)
        self.export_pdf_menu.addAction(self.export_all_action)
        self.export_pdf_menu.addAction(self.export_filtered_action)
        self.export_pdf_menu.addAction(self.export_selected_action)

        # PDF-01: which paper the report is printed on, remembered in
        # config.ini. A submenu rather than three more top-level entries: the
        # three above are the *actions*, this is a property of the output, and
        # putting them on one level would read as six things to choose between.
        self.export_pdf_menu.addSeparator()
        self.pdf_paper_menu = self.export_pdf_menu.addMenu("Paper")
        self.pdf_paper_group = QActionGroup(self)
        self.pdf_paper_group.setExclusive(True)
        self.pdf_light_action = QAction("Light (white)", self)
        self.pdf_light_action.setToolTip("White paper. Prints cleanly and photocopies well.")
        self.pdf_dark_action = QAction("Dark (midnight navy)", self)
        self.pdf_dark_action.setToolTip("Navy paper, matching the app. Higher contrast on screen; heavy on toner.")
        for action, value in ((self.pdf_light_action, "light"),
                              (self.pdf_dark_action, "dark")):
            action.setCheckable(True)
            action.setData(value)
            self.pdf_paper_group.addAction(action)
            self.pdf_paper_menu.addAction(action)
        self.pdf_light_action.setChecked(self.pdf_paper != "dark")
        self.pdf_dark_action.setChecked(self.pdf_paper == "dark")
        self.pdf_paper_group.triggered.connect(self._set_pdf_paper)

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
        # LAYOUT-01: back to whatever the user last searched by. Set before the
        # currentIndexChanged connection below, so restoring a preference does
        # not fire the handler as though the user had just changed it.
        remembered = getattr(self, 'search_criteria', 'Filename')
        if remembered in ("Filename", "Index", "Dimensions"):
            self.search_criteria_combo.setCurrentText(remembered)
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
        self.search_criteria_combo.setFixedWidth(122)  # UI-01: padding + arrow
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
        # UI-01: 84 -> 66. This row was already over-constrained before the
        # restyle -- it needs more width than the previewer pane ever gets at
        # the window's own 1410px minimum -- and the roomier button padding
        # took another 17px off the Export label. The spacer here is pure
        # visual shift with nothing depending on its value, so the 17px comes
        # out of it rather than out of the button.
        bottom_controls_layout.addSpacing(66)
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
        # STR-08: colours from the single Glass palette, not hex literals.
        self.right_panel_splitter.setStyleSheet(SPLITTER_STYLESHEET)
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

    def _mark_task_start(self, key):
        """Stamps the start of a timed operation (LOG-01)."""
        self._task_start_times[key] = time.monotonic()

    def _task_duration(self, key):
        """
        How long `key` ran, as text, consuming the stamp.

        Monotonic rather than wall clock: the log already carries timestamps for
        "when", and this has to stay correct across a DST shift or a clock
        correction mid-compile. Returns "unknown" if the start was never marked,
        which is better in a support log than a plausible wrong number.
        """
        start = self._task_start_times.pop(key, None)
        if start is None:
            return "unknown"
        return f"{time.monotonic() - start:.1f}s"

    def _log_task_paths(self, task_name):
        """The input and output a task was working on, for its outcome line."""
        if task_name == "decompile":
            self._log_message(f"[DATA] Input: {self.decompile_input_file}")
            self._log_message(f"[DATA] Output: {self.decompile_output_folder}")
        elif task_name == "compile":
            self._log_message(f"[DATA] Input: {self.compile_input_folder}")
            self._log_message(f"[DATA] Output: {self.compile_output_file}")

    def _log_task_output_summary(self, task_name):
        """
        What a successful task actually produced (LOG-01).

        "Complete" was the whole record, so the two questions that follow every
        support report -- did it write anything, and was it everything -- had no
        answer in the log. Counting is a directory listing and a stat; the cost
        is paid once, at the end of a job the user already waited on.
        """
        self._log_task_paths(task_name)
        try:
            if task_name == "decompile":
                folder = self.decompile_output_folder
                if folder and os.path.isdir(folder):
                    count = sum(len(files) for _root, _dirs, files in os.walk(folder))
                    self._log_message(f"[DATA] Files written: {count:,}")
            elif task_name == "compile":
                out = self.compile_output_file
                if out and os.path.isfile(out):
                    size = os.path.getsize(out)
                    self._log_message(
                        f"[DATA] Archive size: {size:,} bytes ({size / (1024 * 1024):.2f} MB)")
                expected = getattr(self, 'compile_expected_count', None)
                if expected is not None:
                    self._log_message(f"[DATA] Images offered to the compiler: {expected:,}")
        except Exception as e:
            # A summary is not worth failing a completed task over.
            log_diagnostic("summarising task output", e, task=task_name)

    def _log_command(self, command):
        """
        Records the exact command line handed to a bundled tool.

        LOG-01: decompile and compile each built this string inline, and Get
        Info -- the operation with two child processes and the most reported
        failures -- logged neither of its two. One helper, four call sites, and
        the support log can now state what was actually run in every case.
        """
        log_command = " ".join([f'"{arg}"' if " " in arg else arg for arg in command])
        self._log_message(
            f'[DATA] {datetime.now().strftime("%H:%M:%S")}: Running command: {log_command}')

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
        else:
            # LOG-01: only the Yes branch was recorded, so the most common
            # cause of "compile and decompile are greyed out" -- the user
            # declined this prompt -- left no trace at all.
            self._log_message(
                "[WARN] User declined the runtime installation prompt. "
                "Compile and Decompile remain disabled until the runtimes are installed.")

    def _select_decompile_input(self):
        self._log_message("[INFO] ----- Decompile Mode Selected -----")
        last_path = self._get_config_path('decompileinput')
        file_path, _ = QFileDialog.getOpenFileName(self, "Browse .xbt file to extract...", last_path, "Kodi Texture File (*.xbt)")
        if file_path:
            self._handle_decompile_input_path(file_path)
        else:
            # LOG-01: a cancelled dialog left the mode-selected header above
            # with nothing under it, which reads like the selection failed.
            self._log_message("[INFO] Decompile input selection cancelled by user.")



    # STR-04: _open_decompile_input_folder and _open_decompile_folder were removed
    # here. Two near-identical methods, both opening the decompile input file's
    # parent folder, neither with a single call site anywhere in the file.

    def _open_decompile_output_folder(self):
        """Opens the folder selected as the decompile output directory."""
        # LOG-01: this open-the-folder logic was written out a second time here
        # (and a third in the compile twin) without the try/except or the two
        # log lines _open_folder already had -- so this button, unlike every
        # other route to the same action, could fail or do nothing in silence.
        self._open_folder(self.decompile_output_folder)

    def _select_decompile_output(self):
        last_path = self._get_config_path('decompileoutput')
        folder_path = QFileDialog.getExistingDirectory(self, "Select save location folder...", last_path)
        if folder_path:
            self._handle_decompile_output_path(folder_path)
        else:
            self._log_message("[INFO] Decompile output selection cancelled by user.")

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

        self._log_command(command)
        self._mark_task_start("decompile")

        self.decompile_thread = QThread(self)
        self.decompile_worker = Worker(command, process_cwd, show_window=False)
        self.decompile_worker.moveToThread(self.decompile_thread)

        # BUG-16: bound method, so this is a queued connection to the GUI thread.
        self.decompile_task_name = task_name
        self.decompile_worker.progress_updated.connect(self._on_decompile_progress)

        self.decompile_thread.started.connect(self.decompile_worker.run)
        self.decompile_worker.finished.connect(self._on_decompile_finished)
        self.decompile_worker.error.connect(self._on_decompile_error)
        # BUG-21: the worker is deleted on the THREAD's finished, never on its
        # own. Both were queued to the worker's thread, so `quit` could stop the
        # event loop before `deleteLater` was delivered -- stranding a worker
        # that owns two running reader QThreads, and aborting the process when
        # Qt eventually destroyed them. `error` must quit too, or a failed task
        # leaves the thread running and the worker is never collected.
        self.decompile_worker.finished.connect(self.decompile_thread.quit)
        self.decompile_worker.error.connect(self.decompile_thread.quit)
        self.decompile_thread.finished.connect(self.decompile_worker.deleteLater)
        self.decompile_thread.finished.connect(self.decompile_thread.deleteLater)
        self.decompile_thread.start()

    def _start_get_info(self):
        '''Orchestrates the two-stage Get Info process: silent extract, then info scan.'''
        if any(t is not None for t in (self.decompile_thread, self.compile_thread, self.info_thread, self.installer_thread, self.decompile_for_info_thread)):
            self._log_message("[WARN] Another task is already in progress. Please wait.")
            return

        if not self.workspace_dir:
            self._log_message("[ERROR] Cannot start task, workspace not available.")
            return
        # BUG-12: an `assert self.workspace_dir is not None` used to sit here.
        # asserts are stripped under `python -O`, so it was never a real guard --
        # the explicit check above is. Removed rather than made load-bearing.

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
        self._log_message("[INFO] Get Info step 1/2: extracting images to the cache.")
        self._log_command(decompile_command)
        self._mark_task_start("decompile_info")

        self.decompile_for_info_thread = QThread(self)
        self.decompile_for_info_worker = Worker(decompile_command, decompile_cwd, show_window=False)
        self.decompile_for_info_worker.moveToThread(self.decompile_for_info_thread)

        self.decompile_for_info_worker.progress_updated.connect(self._on_get_info_cache_progress)

        # BUG-21: delete the worker on the thread's finished, not its own, and
        # quit on error as well. Get Info builds two workers back to back, so
        # this teardown overlaps the next setup -- it is where the abort was
        # captured.
        self.decompile_for_info_worker.finished.connect(self.decompile_for_info_thread.quit)
        self.decompile_for_info_worker.error.connect(self.decompile_for_info_thread.quit)
        self.decompile_for_info_thread.finished.connect(self.decompile_for_info_worker.deleteLater)
        self.decompile_for_info_thread.finished.connect(self.decompile_for_info_thread.deleteLater)
        self.decompile_for_info_thread.finished.connect(self._clear_extract_refs)

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
        else:
            self._log_message("[INFO] Compile input selection cancelled by user.")

    def _select_compile_output(self):
        last_path = self._get_config_path('compileoutput')
        # Combine the last used directory with the desired default filename.
        default_file_path = os.path.join(last_path, "Textures.xbt")
        file_path, _ = QFileDialog.getSaveFileName(self, "Select save location for .xbt file...", default_file_path, "Kodi Texture File (*.xbt)")
        if file_path:
            self._handle_compile_output_path(file_path)
        else:
            self._log_message("[INFO] Compile output selection cancelled by user.")


    # STR-04: _open_compile_folder and _open_compile_input_folder were removed
    # here -- the compile-side mirror of the pair above, same duplication, also
    # with zero call sites.

    def _open_compile_output_folder(self):
        """Opens the folder containing the selected compile output file."""
        self._open_folder(
            os.path.dirname(self.compile_output_file) if self.compile_output_file else "")

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

        # BUG-18/BUG-19: establish what the compiler will actually pack before
        # anything is created or replaced. Done first so a cancel here leaves no
        # temporary file behind.
        self._cleanup_compile_staging()
        compile_source_folder = norm_input_folder
        try:
            packable, miscased = self._scan_compile_sources(norm_input_folder)
        except OSError as e:
            self._log_message(f"[ERROR] Could not read the source folder: {e}")
            return

        if miscased:
            self._log_message(
                "[WARN] {} image(s) have an uppercase file extension. "
                "TextureCompiler skips these silently.".format(len(miscased))
            )
            detail = "\n".join(
                os.path.relpath(f, norm_input_folder) for f in sorted(miscased)
            )

            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Uppercase file extensions found")
            box.setText(
                "{} image file(s) in this folder have an uppercase extension, "
                "for example .PNG instead of .png.".format(len(miscased))
            )
            box.setInformativeText(
                "The texture compiler only recognises lowercase extensions. It "
                "will skip these files without reporting an error, and they will "
                "be missing from the finished .xbt.\n\n"
                "\"Fix and compile\" compiles from a temporary copy with the "
                "extensions lowercased. Your source folder is not changed."
            )
            box.setDetailedText(detail)
            fix_btn = box.addButton("Fix and compile", QMessageBox.ButtonRole.AcceptRole)
            anyway_btn = box.addButton("Compile anyway", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(fix_btn)
            box.exec()
            clicked = box.clickedButton()

            if clicked is fix_btn:
                staged = self._stage_lowercased_sources(
                    norm_input_folder, packable, miscased
                )
                if staged is None:
                    self._log_message(
                        "[ERROR] Compile aborted: the source images could not be staged."
                    )
                    return
                compile_source_folder = staged
                packable, miscased = self._scan_compile_sources(staged)
            elif clicked is anyway_btn:
                self._log_message(
                    "[WARN] Proceeding at the user's request. {} image(s) will be "
                    "missing from the output.".format(len(miscased))
                )
            else:
                self._log_message("[INFO] Compile cancelled by the user.")
                return

        # BUG-19: what the compiler is expected to announce. Anything less is a
        # partial pack and must not be promoted over the user's existing file.
        self.compile_expected_count = len(packable)
        self.compile_skipped_sources = [
            os.path.relpath(f, norm_input_folder) for f in sorted(miscased)
        ]

        # BUG-02: the previous code truncated the destination with open(..., 'w')
        # before the compiler ran, so any failure destroyed the user's existing
        # .xbt and left a 0-byte file. Compile to a temporary file in the same
        # directory (same volume, so the later os.replace is atomic) and only
        # swap it into place once the compile has genuinely succeeded.
        out_dir = os.path.dirname(norm_output_file) or "."
        try:
            os.makedirs(out_dir, exist_ok=True)
            fd, temp_output = tempfile.mkstemp(prefix=".ktt_compile_", suffix=".xbt.part", dir=out_dir)
            os.close(fd)
        except OSError as e:
            self._log_message(f"[ERROR] Could not create output file: {e}")
            return

        self.compile_temp_output = temp_output
        self.compile_final_output = norm_output_file
        self.compile_texture_count = None  # BUG-02: set from the compiler's own output

        self._set_ui_task_active(True)
        process_cwd = os.path.join(self.workspace_dir, "utils", "TexturePacker_Compile")
        exe_path = os.path.join(process_cwd, "TextureCompiler.exe")

        command_parts = [exe_path]
        if self.dupecheck_cb.isChecked():
            command_parts.append("-dupecheck")

        command_parts.extend(["-input", compile_source_folder, "-output", temp_output])

        # --- DEV MODE LOGIC ---
        if self.dev_mode_cb.isChecked():
            log_command = " ".join([f'"{arg}"' if " " in arg else arg for arg in command_parts])
            QMessageBox.information(self, "Dev Mode: Command Preview", f"The following command will be executed:\n\n{log_command}")
            self._log_message(f"[DEV] Displayed command preview to user.")
        # --- END DEV MODE ---

        self.progress_bar.setValue(0)
        self.status_label.setText("Compile in progress... Please wait")
        self._show_tray_message(APP_TITLE, "Compile in progress...")

        self._log_command(command_parts)
        self._mark_task_start("compile")

        self.compile_thread = QThread(self)
        self.compile_worker = Worker(command_parts, process_cwd)
        self.compile_worker.moveToThread(self.compile_thread)

        # BUG-16: bound method, so this is a queued connection to the GUI thread.
        self.compile_worker.progress_updated.connect(self._on_compile_progress)
        self.compile_worker.progress_updated.connect(self._track_compile_texture_count)

        self.compile_thread.started.connect(self.compile_worker.run)
        self.compile_worker.finished.connect(self._on_compile_finished)
        self.compile_worker.error.connect(self._on_compile_error)
        # BUG-21: worker deleted on the thread's finished, and error quits too.
        self.compile_worker.finished.connect(self.compile_thread.quit)
        self.compile_worker.error.connect(self.compile_thread.quit)
        self.compile_thread.finished.connect(self.compile_worker.deleteLater)
        self.compile_thread.finished.connect(self.compile_thread.deleteLater)
        self.compile_thread.start()

    def _submit_log(self):
        self._log_message("[INFO] Help/Support button selected.")
        dialog = CustomHelpDialog(self)
        if dialog.exec():
            webbrowser.open("https://forum.kodi.tv/showthread.php?tid=382565")
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
    
    def _open_external_link(self, url, description):
        """Opens a URL in the default browser, recording it (LOG-01)."""
        try:
            webbrowser.open(url)
            self._log_message(f"[INFO] Opened the {description} in the default browser.")
        except Exception as e:
            # A browser that will not launch is otherwise indistinguishable
            # from a menu item that does nothing.
            self._log_message(f"[ERROR] Could not open the {description} ({url}): {e}")

    def _open_folder(self, path):
        """Opens a given folder path in the system's file explorer."""
        if not path:
            self._log_message("[WARN] Open folder requested, but no folder is selected.")
            return
        if not os.path.exists(path):
            # The button appears to do nothing; say why, or the user reports
            # a dead button and the log agrees with them.
            self._log_message(f"[WARN] Cannot open folder — it no longer exists: {path}")
            return
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
        # BUG-18: the staged source copy, if one was built, is dead the moment
        # the task ends -- on success, failure and error alike.
        self._cleanup_compile_staging()

        # Clear ALL possible task handles to allow a new task to start.
        #
        # BUG-21: these assignments used to drop the last Python reference to a
        # worker that could still be winding down. That destroys it there and
        # then, from the GUI thread, and Worker.run parents both stream-reader
        # QThreads to it -- Qt destroying a running QThread is qFatal, which
        # aborts the process with no catchable error. The handles are still
        # released immediately, so the task lock behaves exactly as before, but
        # any object whose thread is still running is parked in _retired_tasks
        # and released once that thread has actually stopped.
        self._retire_task_objects(
            (self.decompile_thread, self.decompile_worker),
            (self.compile_thread, self.compile_worker),
            (self.info_thread, self.info_worker),
            (self.installer_thread, self.installer_worker),
            (self.decompile_for_info_thread, self.decompile_for_info_worker),
            (self.pdf_export_thread, self.pdf_export_worker),
        )
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

    # BUG-16: Qt derives a slot's thread affinity from the RECEIVING QObject. A
    # lambda or functools.partial is a plain Python callable owning no QObject,
    # so PySide6 cannot resolve a receiver thread and invokes it DIRECTLY in the
    # emitting thread. For a worker signal that means GUI code ran on the worker
    # thread. Proven by a faulthandler trace from a frozen build:
    #
    #     Windows fatal exception: access violation
    #     Thread 0x0000331c (most recent call first):
    #       File "Kodi TextureTool.py", line 4061 in _update_progress_from_worker
    #       File "Kodi TextureTool.py", line 495 in _on_stdout_batch
    #
    # -- self.progress_bar.setValue() executing on the worker thread, one frame
    # above Worker._on_stdout_batch. Every adapter below replaces such a
    # connection with a bound method of this QObject, which lives on the GUI
    # thread, so the connection resolves to Qt.QueuedConnection and the slot
    # runs where the widgets are. The pattern was already correct at exactly one
    # site (_on_update_check_finished, which bounced through a Qt signal).

    def _on_compile_progress(self, percentage, message):
        self._update_progress_from_worker(percentage, message, prefix="Compiling")

    def _on_compile_finished(self, return_code, output):
        self._on_process_finished("compile", return_code, output)

    def _on_compile_error(self, error):
        self._on_process_finished("compile", -1, error)

    def _on_decompile_progress(self, percentage, message):
        self._update_progress_from_worker(percentage, message, prefix="Decompiling")

    def _on_decompile_finished(self, return_code, output):
        self._on_process_finished(self.decompile_task_name, return_code, output)

    def _on_decompile_error(self, error):
        self._on_process_finished(self.decompile_task_name, -1, error)

    def _on_info_task_finished(self, return_code, output):
        self._on_process_finished("decompile_info", return_code, output)

    def _on_info_task_error(self, error):
        self._on_process_finished("decompile_info", -1, error)

    def _on_download_warning(self, message):
        self._log_message(f"[WARN] {message}")

    def _on_pdf_export_error(self, message):
        self._on_pdf_export_finished(message, pdf_path=None)

    def _on_update_worker_finished(self, data):
        self._on_update_check_finished(data, self.update_check_manual)

    def _on_update_worker_error(self, error):
        self._on_update_check_error(error, self.update_check_manual)

    def _on_process_finished(self, task_name, return_code, output):
        if task_name == "decompile_info":
            if return_code != 0:
                self._log_message("[ERROR] Get Info task failed with code: {}.".format(return_code))
                if output: self._log_message("[ERROR] {}".format(output))
                # LOG-01: this used to clear the buffer outright, so the [DATA]
                # lines parsed from the compiler before it failed reached
                # neither the log file nor the window -- discarding precisely
                # the output that explains the failure. Keep a bounded tail:
                # enough to see how far it got, not the ~22k lines a healthy
                # run produces.
                self._log_message("[DATA] Get Info failed | Exit code: {} | Duration: {} | Source: {}".format(
                    return_code, self._task_duration("decompile_info"), self.decompile_input_file))
                self._drain_log_buffer_tail(
                    limit=self.FAILED_TASK_LOG_TAIL,
                    reason="Get Info failed; last {} parsed line(s) before the failure")
                self._reset_ui_after_task()
                return

            self._log_message("[INFO] ----- Get Info Complete (Data Parsed) -----")
            self._log_message("[DATA] Exit code: 0 | Duration: {} | Source: {}".format(
                self._task_duration("decompile_info"), self.decompile_input_file))

            # --- FALLBACK SCAN START ---
            try:
                if not self.preview_images:
                    self._scan_cache_dir_fallback()
            except Exception as e:
                self._log_message("[ERROR] Fallback scan failed: {}".format(e))
            # --- FALLBACK SCAN END ---

            # BUG-20: sizes are resolved here, in one directory scan, rather
            # than two stats per texture on the GUI thread during parsing.
            self._resolve_preview_sizes()

            # A zero here is the signature of the empty-previewer reports, and
            # it was never written down: the log said Complete either way.
            self._log_message(f"[DATA] Textures available for preview: {len(self.preview_images):,}")
            if not self.preview_images:
                self._log_message(
                    "[WARN] Get Info completed but no textures were recovered — "
                    "the previewer will be empty.")

            if self.preview_images:
                self.current_preview_index = 0

            # Update UI safely
            self._update_previewer_ui()
            self._populate_dimensions_filter()

            # --- RESET UI LOGIC ---
            # BUG-21: this pair is released the same way as every other, so a
            # worker whose thread is still winding down is not destroyed here.
            self._retire_task_objects((self.info_thread, self.info_worker))
            self.info_thread, self.info_worker = None, None
            self._set_ui_task_active(False)
            self._update_button_states()

            self.status_label.setText("Info retrieval complete. Rendering log to window...")

            QTimer.singleShot(0, self._process_log_message_buffer)
            return

        # Generic completion logic
        self.progress_bar.setValue(100)

        # BUG-02: a failed compile must leave the user's existing .xbt untouched.
        if task_name == "compile" and return_code != 0:
            self._discard_compile_temp()

        if return_code == 0:
            # BUG-02: promote the staged temp file only on genuine success.
            if task_name == "compile" and not self._promote_compile_output():
                return
            final_message = "{} process complete".format(task_name.capitalize())
            self.status_label.setText(final_message)
            self._log_message("[INFO] ----- {} Complete -----".format(task_name.capitalize()))
            # LOG-01: the outcome used to end at "Complete". None of what a
            # support request actually turns on -- how long it took, what it
            # produced, and where -- was recorded anywhere.
            self._log_message("[DATA] Exit code: 0 | Duration: {}".format(
                self._task_duration(task_name)))
            self._log_task_output_summary(task_name)
            if task_name == "decompile" and self.open_decompile_on_complete:
                self._delayed_open_folder(self.decompile_output_folder)
            elif task_name == "compile" and self.open_compile_on_complete:
                self._delayed_open_folder(os.path.dirname(self.compile_output_file))
            self._show_tray_message(APP_TITLE, "{} complete!".format(task_name.capitalize()))
        else:
            self._log_message("[ERROR] {}".format(output))
            # The parameters that produced the failure, recorded with it: a
            # failure line on its own cannot be acted on without them.
            self._log_message("[DATA] {} failed | Exit code: {} | Duration: {}".format(
                task_name.capitalize(), return_code, self._task_duration(task_name)))
            self._log_task_paths(task_name)
            self.status_label.setText("Error during {} (Code: {})".format(task_name, return_code))
            self._show_tray_message(APP_TITLE, "Error during {}".format(task_name), QSystemTrayIcon.MessageIcon.Warning)

        self._reset_ui_after_task()
    # BUG-02: an XBT containing no textures is 9 bytes of header. Measured
    # against TextureCompiler.exe: empty folder -> 9 bytes, one small PNG ->
    # 4,636 bytes. Anything at or below this is structurally empty.
    MIN_PLAUSIBLE_XBT_BYTES = 64

    # BUG-18: the extensions TextureCompiler.exe actually packs. Measured
    # against the bundled binary rather than inferred: .png .jpg .jpeg .gif are
    # packed; .bmp .tbn .tga .dds are ignored whatever their case; and the match
    # is CASE-SENSITIVE, so "Beta.PNG" is dropped without a word. Deliberately
    # narrower than the list used by the cache scan, which is the app's own.
    COMPILER_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif")

    def _scan_compile_sources(self, folder):
        """
    BUG-18/BUG-19: walks the source tree the way TextureCompiler.exe does and
    reports what it will and will not pack.

    Returns (packable, miscased), both lists of absolute paths:
      packable -- extension is one the compiler accepts, in lowercase
      miscased -- extension is one it accepts but not in lowercase, so the
                  compiler skips the file and says nothing
    Anything else is ignored by the compiler and by this scan, and is not a
    problem.
    """
        packable, miscased = [], []
        for root, _dirs, files in os.walk(folder):
            for name in files:
                ext = os.path.splitext(name)[1]
                if ext.lower() not in self.COMPILER_IMAGE_EXTENSIONS:
                    continue
                full = os.path.join(root, name)
                if ext == ext.lower():
                    packable.append(full)
                else:
                    miscased.append(full)
        return packable, miscased

    def _stage_lowercased_sources(self, folder, packable, miscased):
        """
    BUG-18: builds a copy of the source images in the workspace with every
    extension lowercased, so the compiler sees the files it would otherwise
    skip. The user's own folder is never modified and nothing is renamed in
    place.

    Only image files are staged -- the compiler ignores everything else -- and
    each is hardlinked where the filesystem allows it, so the common case costs
    no disk space and no copy time. Returns the staged folder, or None if it
    could not be built.
    """
        try:
            staging = tempfile.mkdtemp(prefix="ktt_srcfix_", dir=self.workspace_dir)
        except OSError as e:
            self._log_message(f"[ERROR] Could not create a staging folder: {e}")
            return None

        claimed = {}
        linked = copied = 0
        try:
            for src in packable + miscased:
                rel = os.path.relpath(src, folder)
                head, tail = os.path.split(rel)
                stem, ext = os.path.splitext(tail)
                dest_rel = os.path.join(head, stem + ext.lower())

                # Two source names collapsing onto one staged name would lose a
                # file just as silently as the bug being fixed. Refuse instead.
                key = dest_rel.lower()
                if key in claimed:
                    raise OSError(
                        'both "{}" and "{}" would become "{}"'.format(
                            os.path.relpath(claimed[key], folder), rel, dest_rel
                        )
                    )
                claimed[key] = src

                dest = os.path.join(staging, dest_rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                try:
                    os.link(src, dest)
                    linked += 1
                except (OSError, AttributeError, NotImplementedError):
                    shutil.copy2(src, dest)
                    copied += 1
        except (OSError, shutil.Error) as e:
            self._log_message(f"[ERROR] Could not stage the source images: {e}")
            shutil.rmtree(staging, ignore_errors=True)
            return None

        self.compile_staging_dir = staging
        self._log_message(
            "[INFO] Staged {} image(s) with lowercased extensions ({} linked, {} "
            "copied). Your source folder was not modified.".format(
                linked + copied, linked, copied
            )
        )
        return staging

    def _cleanup_compile_staging(self):
        """BUG-18: removes the staged source copy, if one was built."""
        staging = getattr(self, "compile_staging_dir", None)
        if staging and os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)
        self.compile_staging_dir = None

    def _track_compile_texture_count(self, percentage, message):
        """
    BUG-02: TextureCompiler.exe treats "nothing to pack" as success. Given an
    empty or unreadable source folder it prints 'Starting to pack 0 textures',
    writes a 9-byte header-only archive and exits 0 with no error output.
    Promoting that over the user's existing .xbt would destroy it, so the
    announced texture count is captured here for _promote_compile_output.
    """
        match = re.search(r'pack\s+(\d+)\s+textures', message, re.IGNORECASE)
        if match:
            self.compile_texture_count = int(match.group(1))

    def _discard_compile_temp(self):
        """BUG-02: removes the staged compile output, leaving any existing file alone."""
        temp = getattr(self, 'compile_temp_output', None)
        if temp and os.path.exists(temp):
            try:
                os.remove(temp)
                self._log_message("[INFO] Discarded incomplete compile output; existing file left untouched.")
            except OSError as e:
                self._log_message(f"[WARN] Could not remove temporary compile output '{temp}': {e}")
        self.compile_temp_output = None
        self.compile_final_output = None

    def _promote_compile_output(self) -> bool:
        """
    BUG-02: atomically moves the staged compile output onto the path the user
    chose. Returns False if the swap could not be done, in which case the UI has
    already been reset and the original file is still intact.
    """
        temp = getattr(self, 'compile_temp_output', None)
        final = getattr(self, 'compile_final_output', None)
        if not temp or not final:
            return True  # Nothing was staged (e.g. a non-compile task).

        try:
            if not os.path.exists(temp):
                raise OSError("the compiler produced no output file")

            # BUG-02: refuse to promote a structurally empty archive. The
            # compiler reports success for this case, so the guard is semantic
            # (the announced texture count) with a size check as a backstop.
            count = getattr(self, 'compile_texture_count', None)
            if count == 0:
                raise OSError(
                    "the compiler packed 0 textures - the input folder contained no "
                    "usable images, or its path could not be read"
                )

            # BUG-19: zero was the only case BUG-02 guarded. A *partial* pack
            # reads as success too -- the compiler drops what it does not
            # recognise, announces the smaller number and exits 0. Reconcile
            # the announced count against what the source folder actually
            # holds, so nothing silently missing reaches the user as complete.
            expected = getattr(self, 'compile_expected_count', None)
            if expected is not None and count is not None and count < expected:
                shortfall = expected - count
                detail = (
                    "the compiler packed {} of {} images - {} were dropped "
                    "without an error".format(count, expected, shortfall)
                )
                skipped = getattr(self, 'compile_skipped_sources', None)
                if skipped:
                    shown = ", ".join(skipped[:5])
                    if len(skipped) > 5:
                        shown += ", and {} more".format(len(skipped) - 5)
                    detail += (
                        "; {} of them have uppercase file extensions ({})".format(
                            len(skipped), shown
                        )
                    )
                raise OSError(detail)
            size = os.path.getsize(temp)
            if size <= self.MIN_PLAUSIBLE_XBT_BYTES:
                raise OSError(
                    f"the compiler produced a {size}-byte file, which contains no textures"
                )

            os.replace(temp, final)
            self.compile_temp_output = None
            self.compile_final_output = None
            self._log_message('[DATA] Output file written: "{}"'.format(final))
            return True
        except Exception as e:
            self._log_message(f"[ERROR] Compile finished but the output file could not be written: {e}")
            self._discard_compile_temp()
            self.status_label.setText("Compile failed: output file could not be written.")
            self._show_tray_message(APP_TITLE, "Compile failed", QSystemTrayIcon.MessageIcon.Warning)
            self._reset_ui_after_task()
            return False

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
        self.installer_worker.error.connect(self._on_installer_error)
        # BUG-21: worker deleted on the thread's finished. ProcessMonitorWorker
        # owns no reader threads, so this one cannot abort the process, but it
        # is the same lifetime bug and is fixed the same way for consistency.
        # `error` is already wired to _on_installer_finished; it must quit the
        # thread as well or the worker is never collected.
        self.installer_worker.finished.connect(self.installer_thread.quit)
        self.installer_worker.error.connect(self.installer_thread.quit)
        self.installer_thread.finished.connect(self.installer_worker.deleteLater)
        self.installer_thread.finished.connect(self.installer_thread.deleteLater)
        self.installer_thread.start()

    def _on_installer_finished(self, exit_code=""):
        """
        The installer exited on its own; `exit_code` is what it returned.

        LOG-01: this slot used to serve both the worker's `finished` and its
        `error`, telling them apart with `if error_msg:`. That could not survive
        `finished` carrying a real exit code -- "0" is a true string, so a
        clean install would have been reported as a failure. The two outcomes
        are separate slots now, which is what they always were in substance.
        """
        if exit_code == "":
            self._log_message("[INFO] Runtime installer finished (exit code unavailable).")
        elif exit_code == "0":
            self._log_message("[INFO] Runtime installer finished successfully (exit code 0).")
        else:
            # Not fatal on its own -- the re-check below is the real verdict --
            # but it is the first place a refused install becomes visible.
            self._log_message(
                f"[WARN] Runtime installer returned exit code {exit_code}. "
                "The install may not have completed.")

        self.status_label.setText("Installer finished.")
        self._show_tray_message(APP_TITLE, "Runtime Installation Complete", QSystemTrayIcon.MessageIcon.Information)

        # Re-check vcredist status after installation
        self._log_message("[INFO] Re-checking Visual C++ Redistributable status after installation.")
        self.vcredist_checks_passed = self._check_vcredist_installed()
        if self.vcredist_checks_passed:
            self._log_message("[INFO] Visual C++ Redistributable check: [Passed] after installation.")
        else:
            self._log_message("[ERROR] Visual C++ Redistributable check: [Failed] after installation. Please check log for details.")

        self._finish_installer_task()

    def _on_installer_error(self, error_msg):
        """The monitor thread could not wait on the installer process."""
        self._log_message(f"[ERROR] Installer monitoring failed: {error_msg}")
        self.status_label.setText("Installer finished with an error.")
        self._show_tray_message(APP_TITLE, "Runtime Installation Failed", QSystemTrayIcon.MessageIcon.Warning)
        self._finish_installer_task()

    def _finish_installer_task(self):
        """UI teardown shared by both installer outcomes."""
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

    # STR-05: these four were the other half of the eightfold duplication. They
    # now name the slot and delegate; the shared body is _apply_path_selection.
    def _handle_decompile_input_path(self, file_path):
        self._apply_path_selection(PathSlot.DECOMPILE_INPUT, file_path)

    def _handle_decompile_output_path(self, folder_path):
        self._apply_path_selection(PathSlot.DECOMPILE_OUTPUT, folder_path)

    def _handle_compile_input_path(self, folder_path):
        self._apply_path_selection(PathSlot.COMPILE_INPUT, folder_path)

    def _handle_compile_output_path(self, file_path):
        self._apply_path_selection(PathSlot.COMPILE_OUTPUT, file_path)

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

    # STR-04: _on_decompile_folder_dropped was removed here. It was superseded by
    # _on_decompile_file_dropped above, which is what DropGroupBox.fileDropped is
    # actually connected to and which handles both the file and folder cases.

    def _on_compile_folder_dropped(self, path):
        if os.path.isdir(path):
            self._log_message(f"[INFO] Compile input folder dropped: {os.path.basename(path)}")
            self._handle_compile_input_path(path)
        elif os.path.isfile(path):
            self._log_message(f"[INFO] Compile output file dropped: {os.path.basename(path)}")
            self._handle_compile_output_path(path)
        else:
            self._log_message(f"[WARN] Invalid item dropped on Compile box: {path}")

    # STR-04: _on_compile_file_dropped was removed here -- superseded by
    # _on_compile_folder_dropped above, the slot actually wired to the compile
    # box's fileDropped signal.
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
        kodi_forum_action.triggered.connect(
            lambda: self._open_external_link("https://forum.kodi.tv/showthread.php?tid=382565",
                                             "Kodi support forum"))
        help_menu.addAction(kodi_forum_action)
        github_action = QAction(qta.icon('fa5b.github'), "GitHub Link", self)
        github_action.setToolTip("Open the project's GitHub repository")
        github_action.triggered.connect(
            lambda: self._open_external_link("https://github.com/kittmaster/KodiTextureTool",
                                             "project GitHub page"))
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
            try:
                return [int(p) for p in v.lstrip('v').split('.')]
            except (ValueError, AttributeError) as e:
                # STR-07: a version string that will not parse normalises to [0],
                # which makes any comparison against it meaningless. If the
                # published manifest ever carries a malformed version, this is
                # the only place it would show.
                log_diagnostic("parsing a version string for comparison", e, value=v)
                return [0]
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
        self._retire_task_objects((self.update_thread, self.update_worker))  # BUG-23
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
        # BUG-23: released the same way as every other pair, so a thread that
        # is still winding down keeps a reference until it reports finished.
        # Dropping it outright left the window owning a running QThread that
        # closeEvent could no longer find, and Qt aborted on teardown.
        self._retire_task_objects((self.update_thread, self.update_worker))
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
            update_available_icon = qta.icon('fa5s.cloud-download-alt', color=Glass.ACCENT)
            self._show_tray_message("Update Available", f"Version {latest_version} is ready to download.", update_available_icon)
            # --- PATCH END ---
            download_url_raw = data.get("update_package_url", "https://github.com/kittmaster/KodiTextureTool/releases/latest")
            # CHANGELOG-02: version.json's changelog carries three shapes, and
            # this used to render two of them. An entry with no "- " prefix is a
            # section heading ("Security & Stability"), and an empty entry is a
            # group break; before the manifest carried either, both a section
            # heading and the fixes beneath it arrived as the same indented
            # line, and the blank lines that separated the groups in
            # changelog.txt never survived the trip. An older manifest has
            # neither shape in it and still renders exactly as it did.
            changelog_items = data.get("changelog", ["No changelog available."])
            changelog_html_parts = []
            for item in changelog_items:
                clean_item = item.strip()
                if not clean_item:
                    changelog_html_parts.append("")
                    continue
                safe_item = _escape_changelog(clean_item)
                if clean_item.startswith("- v"):
                    # A manifest predating CHANGELOG-02 has no explicit breaks,
                    # so one is still opened here -- unless the manifest already
                    # supplied it, which would otherwise double the gap.
                    if changelog_html_parts and changelog_html_parts[-1] != "":
                        changelog_html_parts.append("")
                    changelog_html_parts.append(f"<b>{safe_item}</b>")
                elif clean_item.startswith("-"):
                    changelog_html_parts.append(f"&nbsp;&nbsp;{safe_item}")
                else:
                    changelog_html_parts.append(
                        '<b><span style="color: {accent};">{heading}</span></b>'.format(
                            accent=Glass.ACCENT_BRIGHT, heading=safe_item))
            changelog_html = "<br>".join(changelog_html_parts)
            self._log_message("[INFO] Prompting user to download new version.")
            dialog = UpdateDialog(latest_version, changelog_html, self)
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
                # SEC-03: stage outside the application tree. The old code
                # downloaded into app_dir/_temp, i.e. inside the very directory
                # the updater then overwrites, and that also made a clean
                # atexit workspace wipe impossible.
                try:
                    self.update_staging_dir = tempfile.mkdtemp(prefix="ktt_update_")
                    self._log_message(f"[INFO] Update staging directory: {self.update_staging_dir}")
                except Exception as e:
                    self._log_message(f"[ERROR] Could not create update staging directory: {e}")
                    QMessageBox.critical(self, "Update Error",
                                         f"Could not prepare a staging folder for the update:\n\n{e}")
                    self._reset_ui_state()
                    return

                expected_sha256 = data.get("sha256") or data.get("sha256sum")
                if expected_sha256:
                    self._log_message("[INFO] Update manifest supplies a SHA-256; package will be verified.")
                else:
                    self._log_message("[WARN] Update manifest has no 'sha256' field; package integrity cannot be verified.")

                self.update_progress_dialog = UpdateProgressDialog(self)
                self.update_progress_dialog.show()
                # BUG-05: this QThread was the only one in the file created without
                # a parent. Every other site uses QThread(self). Unparented, its
                # lifetime depended entirely on the Python reference, so a cleared
                # handle could collect the thread object mid-download.
                self.download_thread = QThread(self)
                self.download_worker = DownloadWorker(download_url, self.update_staging_dir, expected_sha256)
                self.download_worker.moveToThread(self.download_thread)
                self.download_worker.progress.connect(self.update_progress_dialog.update_progress)
                self.download_worker.warning.connect(self._on_download_warning)
                self.download_worker.finished.connect(self._trigger_install)
                self.download_worker.error.connect(self._on_download_error)
                self.download_thread.started.connect(self.download_worker.run)
                # BUG-05: this was `download_thread.finished -> download_thread.quit`,
                # a no-op self-connection (a thread that has already finished cannot
                # be asked to quit). The intent was to stop the thread when the
                # worker is done, so the event loop actually exits.
                self.download_worker.finished.connect(self.download_thread.quit)
                self.download_worker.error.connect(self.download_thread.quit)
                # BUG-21: worker deleted on the thread's finished. Both quit
                # connections above were already correct.
                self.download_thread.finished.connect(self.download_worker.deleteLater)
                self.download_thread.finished.connect(self.download_thread.deleteLater)
                self.download_thread.start()
                self._mark_task_start("download")
            else:
                # LOG-01: declining the update was the one outcome of this
                # dialog that went unrecorded, so a user still on an old build
                # looked identical to one who never saw the prompt.
                self._log_message(f"[INFO] User declined the update to {latest_version}.")
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

    @staticmethod
    def _is_batch_safe(value: str) -> bool:
        """
    SEC-03: the updater template interpolates these values into `set "X=..."`
    statements. A double quote closes the assignment early and everything after
    it is executed as batch. A percent sign is expanded as a variable reference.
    Neither is legal in a Windows path anyway, so reject rather than escape.
    """
        return isinstance(value, str) and '"' not in value and '%' not in value

    def _trigger_install(self, zip_path):
        if not self.update_staging_dir or not os.path.isdir(self.update_staging_dir):
            self._log_message("[ERROR] Cannot install update: staging directory is not available.")
            return
        # LOG-01: the download's own outcome was never stated -- only that
        # verification was going to happen. With the log rotated rather than
        # truncated, this is now the last thing the .prev log records before
        # the relaunch, and the only place to see what was actually installed.
        try:
            self._log_message("[DATA] Update package: {} | {:,} bytes | Downloaded in {}".format(
                zip_path, os.path.getsize(zip_path), self._task_duration("download")))
        except Exception as e:
            log_diagnostic("sizing the downloaded update package", e, path=zip_path)
        self._log_message("Starting update installation process...")

        app_dir = self.app_dir
        key_file_to_find = "Kodi TextureTool.exe"

        # Determine the correct exe to kill and the full command to relaunch
        executable_path = sys.executable
        app_exe_to_kill = os.path.basename(executable_path)

        # SEC-03: validate every value before it reaches the batch template.
        for label, value in (("update package path", zip_path),
                             ("application directory", app_dir),
                             ("executable name", app_exe_to_kill)):
            if not self._is_batch_safe(value):
                self._log_message(
                    f"[ERROR] Refusing to build the updater script: {label} contains a quote "
                    f"or percent character that cannot be safely embedded: {value}"
                )
                QMessageBox.critical(
                    self, "Update Aborted",
                    f"The update cannot proceed because the {label} contains an unsafe "
                    f"character (\" or %):\n\n{value}\n\nPlease report this path."
                )
                DownloadWorker._discard(zip_path)
                return

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

:: Self-destruct. This script is running FROM the staging folder, so cmd holds
:: update.bat open and "rd" cannot remove the directory itself -- it would strip
:: the contents and leave an empty folder behind. Hand the removal to a detached
:: shell that waits for this one to exit and release the file first.
cd /d "%TEMP%"
start "" /min cmd /c timeout /t 3 /nobreak ^>NUL ^& rd /s /q "{staging_dir}"
exit
"""
        staging_dir = os.path.normpath(self.update_staging_dir)
        if not self._is_batch_safe(staging_dir):
            self._log_message(f"[ERROR] Staging directory contains an unsafe character: {staging_dir}")
            DownloadWorker._discard(zip_path)
            return

        batch_script_content = batch_script_template.format(
            zip_path=zip_path,
            app_dir=app_dir,
            key_file_to_find=key_file_to_find,
            app_exe_to_kill=app_exe_to_kill,
            staging_dir=staging_dir
        )
        # SEC-03: the updater lives in the staging directory, not in app_dir/_temp.
        # textwrap.dedent() was removed here: the template is not indented, so the
        # call did nothing and implied a sanitising step that was never happening.
        updater_path = os.path.join(staging_dir, "update.bat")
        with open(updater_path, "w", encoding="utf-8") as f:
            f.write(batch_script_content)
        self._log_message(f"Updater script created at: {updater_path}")

        # SEC-03: no shell. `start` was only being used to detach the console
        # window; DETACHED_PROCESS does the same without a command interpreter.
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen([updater_path], cwd=staging_dir, shell=False,
                         close_fds=True, creationflags=creation_flags)

        # SEC-03: os._exit(0) skipped every atexit handler, so _cleanup_workspace
        # never ran and app_dir/_temp was left behind for the updater to copy over.
        # Run the cleanup explicitly, then leave through the normal Qt path.
        try:
            self._cleanup_workspace()
        except Exception as e:
            self._log_message(f"[WARN] Workspace cleanup before update failed: {e}")

        QApplication.quit()

    def _load_settings(self):
        """Loads settings from the in-memory config (see _read_config_file)."""
        # STR-06: no re-read.
        if not self.config.has_section('Settings'):
            self.config.add_section('Settings')
        self.open_decompile_on_complete = self.config.getboolean('Settings', 'open_decompile_on_complete', fallback=False)
        self.open_compile_on_complete = self.config.getboolean('Settings', 'open_compile_on_complete', fallback=False)
        self.open_pdf_on_complete = self.config.getboolean('Settings', 'open_pdf_on_complete', fallback=True)
        self.check_for_updates_on_startup = self.config.getboolean('Settings', 'check_for_updates_on_startup', fallback=True)
        self.log_on_top = self.config.getboolean('Settings', 'log_on_top', fallback=True)
        self.decompile_on_top = self.config.getboolean('Settings', 'decompile_on_top', fallback=False)
        self.dev_update_url = self.config.get('Settings', 'dev_update_url', fallback='https://raw.githubusercontent.com/kittmaster/KodiTextureTool/main/version.json')
        # PDF-01: light unless the user has chosen otherwise. An unrecognised
        # value falls back rather than reaching the worker, so a hand-edited
        # config cannot produce a KeyError three threads away from the typo.
        paper = self.config.get('Settings', 'pdf_paper', fallback='light').strip().lower()
        self.pdf_paper = paper if paper in PDF_THEMES else 'light'
        # LAYOUT-01: two more things worth remembering between runs.
        self.search_criteria = self.config.get('Settings', 'search_criteria',
                                               fallback='Filename')
        # The zoom the previewer opens at. Navigating to another texture still
        # resets to fit -- that is existing behaviour and not something to
        # change quietly -- so this seeds the FIRST image of the session with
        # whatever magnification the user was last working at.
        try:
            self.startup_zoom_level = float(
                self.config.get('Settings', 'preview_zoom', fallback='1.0'))
        except (TypeError, ValueError):
            self.startup_zoom_level = 1.0
        self.startup_zoom_level = max(0.1, min(self.startup_zoom_level, 8.0))

        # BUG-17: a one-time reset of the two auto-open options.
        # Every existing config.ini already stores these as True, because
        # _save_settings has always written the ON default back out. That
        # stored True is not a choice anybody made -- the feature was dead
        # (BUG-16), so no user has ever seen it do anything. Changing the
        # fallback alone would therefore reach new installs only. This clears
        # the value once, records that it has been done, and never touches it
        # again, so a user who deliberately turns it on afterwards keeps it.
        if not self.config.getboolean('Settings', 'autoopen_reset_v320', fallback=False):
            self.open_decompile_on_complete = False
            self.open_compile_on_complete = False
            self.autoopen_reset_v320 = True
            log_diagnostic('BUG-17: auto-open folder options reset to off (one time)')
        else:
            self.autoopen_reset_v320 = True

    def _save_settings(self):
        """Saves current settings to the config file."""
        # STR-06: no re-read.
        if not self.config.has_section('Settings'):
            self.config.add_section('Settings')
        self.config.set('Settings', 'autoopen_reset_v320',
                        str(getattr(self, 'autoopen_reset_v320', True)))
        self.config.set('Settings', 'open_decompile_on_complete', str(self.open_decompile_on_complete))
        self.config.set('Settings', 'open_compile_on_complete', str(self.open_compile_on_complete))
        self.config.set('Settings', 'open_pdf_on_complete', str(self.open_pdf_on_complete))
        self.config.set('Settings', 'check_for_updates_on_startup', str(self.check_for_updates_on_startup))
        self.config.set('Settings', 'log_on_top', str(self.log_on_top))
        self.config.set('Settings', 'decompile_on_top', str(self.decompile_on_top))
        self.config.set('Settings', 'dev_update_url', str(self.dev_update_url))
        self.config.set('Settings', 'pdf_paper', str(getattr(self, 'pdf_paper', 'light')))
        if hasattr(self, 'search_criteria_combo'):
            self.config.set('Settings', 'search_criteria',
                            self.search_criteria_combo.currentText())
        self.config.set('Settings', 'preview_zoom',
                        "{:.4f}".format(getattr(self, 'current_zoom_level', 1.0)))
        self._write_config_file()

    def _set_pdf_paper(self, action):
        """PDF-01: records the chosen paper. Applies to the next export."""
        self.pdf_paper = action.data() or "light"
        self._save_settings()
        self._log_message("[INFO] PDF report paper is now {}.".format(
            "Dark (midnight navy)" if self.pdf_paper == "dark" else "Light (white)"))

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

            # LAYOUT-02: navigating to another texture used to reset the zoom
            # to fit. It no longer does -- the level is a multiple of each
            # image's OWN fit size, so 3x means "three times as large as this
            # one would be" for every texture in the archive, and stepping
            # through a set at a fixed magnification is the thing the previewer
            # is for. Fit to Window is how you get back to 1.0.
            self.last_displayed_index = self.current_preview_index
            self._update_zoom_overlay()

            self.previewer_box.setVisible(True)
            is_search_active = bool(self.search_results) and self.current_search_index != -1

            if not self.preview_images or self.current_preview_index == -1:
                placeholder_icon = qta.icon('fa5s.ban', color=Glass.EDGE_LIT)
                placeholder_pixmap = placeholder_icon.pixmap(QSize(128, 128))
                self.image_display_label.setPixmap(placeholder_pixmap)
                self._reset_preview_label_bounds()
                # BUG-11: drop the cached source so a later zoom cannot act on the
                # pixmap of an image that is no longer on display.
                self._preview_source_pixmap = None
                self._preview_fit_size = None
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
                    # STR-07: the reason is shown in the previewer, but the
                    # traceback -- which says whether this was the reader, the
                    # file, or the decode -- was being thrown away.
                    log_diagnostic("loading a texture for the previewer", e,
                                   path=image_data.get('path'))

                # --- UI UPDATE ---
                if original_pixmap is None or original_pixmap.isNull():
                    fail_msg = "Preview Unavailable\n\nReason: {}\n({})".format(error_reason, os.path.basename(image_data['path']))
                    self.image_display_label.setText(fail_msg)
                    self.image_display_label.setStyleSheet(self.STYLE_PREVIEW_ERROR)
                    self._reset_preview_label_bounds()
                    # BUG-11: nothing to zoom from once the load failed.
                    self._preview_source_pixmap = None
                    self._preview_fit_size = None
                else:
                    self.image_display_label.setStyleSheet(self.STYLE_PREVIEW_NORMAL)
                    # BUG-11b: the viewport, not the label -- once a zoomed
                    # label has grown past the pane, its own size is no longer
                    # the space available to fit into.
                    label_size = self.image_scroll_area.viewport().size()
                    if label_size.width() > 0 and label_size.height() > 0:
                        # BUG-11: keep the full-resolution pixmap and the size it
                        # occupies at zoom 1.0. _render_preview_at_zoom scales from
                        # this source every time instead of compounding scalings.
                        self._preview_source_pixmap = original_pixmap
                        if original_pixmap.width() > label_size.width() or original_pixmap.height() > label_size.height():
                            self._preview_fit_size = original_pixmap.size().scaled(
                                label_size, Qt.AspectRatioMode.KeepAspectRatio)
                        else:
                            self._preview_fit_size = original_pixmap.size()

                        # LAYOUT-02: this used to be guarded by
                        # `if not pixmap or is_image_zoomed is False`, which
                        # skipped the render whenever the user was zoomed in --
                        # harmless only because the level was being reset to 1.0
                        # a few lines above. With the zoom persisting, the new
                        # image has to be drawn at the level in force, so the
                        # render is unconditional.
                        self.current_zoom_level = self._initial_zoom_level()

                        # A level that was fine for the last texture can exceed
                        # what this one allows: the ceiling is computed from the
                        # image's own fit size and the pixel budget. Clamp, so
                        # walking onto a much larger texture cannot ask for a
                        # pixmap that will not fit in memory.
                        self.current_zoom_level = max(
                            self.MIN_ZOOM_LEVEL,
                            min(self.current_zoom_level,
                                self._max_zoom_for_current_image()))
                        self._render_preview_at_zoom()

                        self.is_image_zoomed = abs(self.current_zoom_level - 1.0) > 0.001
                        self.btn_fit_to_window.setEnabled(self.is_image_zoomed)
                        self._update_zoom_overlay()

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

        # BUG-10: a latin-1 -> utf-8 round-trip used to sit here, compensating
        # for the double encoding caused by the old `cmd.exe /c chcp 65001`
        # shell wrapper. SEC-02 removed that wrapper, so the child's output now
        # arrives byte-accurate and this "repair" actively re-corrupted it.
        # Verified against a real texture name containing non-ASCII characters:
        # pre-SEC-02 the pipeline reported 'co.Ã¢Â€Âš ltd..png' while the file on
        # disk was 'co.\xe2\x80\x9a ltd..png'; it now matches the disk exactly.
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

            # BUG-21: the extract worker and its thread are deliberately NOT
            # cleared here. This slot runs on `worker.finished`, while the
            # worker's own QThread is still winding down. Dropping the last
            # Python reference to the worker destroys it immediately, from the
            # GUI thread -- and Worker.run parents both stream-reader QThreads
            # to it, so Qt destroys those too. Destroying a running QThread is
            # qFatal, and qFatal aborts the process (0xc0000409). Measured: with
            # these two assignments the harness aborts within 1-4 Get Info
            # cycles; without them, 25 cycles run clean.
            # `_clear_extract_refs` does the clearing on the THREAD's finished
            # signal instead, by which point the thread has genuinely stopped.

            if not self.info_cache_dir or not self.workspace_dir:
                self._on_get_info_extract_failed("Cache or workspace directory does not exist. Cannot proceed.")
                return

            # BUG-12: redundant assert removed -- the explicit check above is the
            # real guard, and asserts vanish under `python -O`.

            self._log_message("[INFO] Image cache created successfully.")
            self.status_label.setText("Step 2/2: Reading texture information...")
            self.progress_bar.setRange(0, 100)

            process_cwd = os.path.join(self.workspace_dir, "utils", "TexturePacker_Compile")
            exe_path = os.path.join(process_cwd, "TextureCompiler.exe")
            command = [exe_path, "-info", os.path.normpath(self.decompile_input_file)]
            self._log_message("[INFO] Get Info step 2/2: parsing texture metadata.")
            self._log_command(command)

            self.info_thread = QThread(self)
            self.info_worker = Worker(command, process_cwd, show_window=False)
            self.info_worker.moveToThread(self.info_thread)

            # Clear buffers again to be safe
            self.preview_images.clear()
            self.log_message_buffer.clear()

            self.info_worker.progress_updated.connect(self._on_info_progress_updated)
            # BUG-20: batched — one signal per reader batch, not one per line.
            self.info_worker.info_line_parsed.connect(self._on_info_line_received)

            # BUG-21: worker deleted on the thread's finished, and error quits
            # too. This is the second of Get Info's two workers.
            self.info_worker.finished.connect(self.info_thread.quit)
            self.info_worker.error.connect(self.info_thread.quit)
            self.info_thread.finished.connect(self.info_worker.deleteLater)
            self.info_thread.finished.connect(self.info_thread.deleteLater)

            self.info_thread.started.connect(self.info_worker.run)
            self.info_worker.finished.connect(self._on_info_task_finished)
            self.info_worker.error.connect(self._on_info_task_error)

            self.info_thread.start()
        except Exception as e:
             self._log_message("[ERROR] Exception during Phase 2 start: {}".format(e))
             self._on_get_info_extract_failed(str(e))

    def _retire_task_objects(self, *pairs):
        """
    BUG-21: releases worker/thread handles without destroying them early.

    A worker whose QThread is still running must not lose its last Python
    reference: Qt destroys the reader QThreads parented to it, and destroying a
    running QThread is qFatal -- an abort the process cannot catch. Anything
    still running is held in `_retired_tasks` until its thread reports finished,
    at which point `deleteLater` has already been queued and the handle can go.

    Pairs whose thread has already stopped are not retained at all, so the list
    stays empty in the normal case.
    """
        if not hasattr(self, "_retired_tasks"):
            self._retired_tasks = []

        for thread, worker in pairs:
            if thread is None:
                continue
            try:
                running = thread.isRunning()
            except RuntimeError:
                # The C++ object is already gone; nothing to hold on to.
                continue
            if not running:
                continue
            self._retired_tasks.append((thread, worker))
            thread.finished.connect(self._drain_retired_tasks)

        self._drain_retired_tasks()

    def _drain_retired_tasks(self):
        """BUG-21: forgets retired pairs whose thread has genuinely stopped."""
        if not getattr(self, "_retired_tasks", None):
            return
        still_running = []
        for thread, worker in self._retired_tasks:
            try:
                if thread.isRunning():
                    still_running.append((thread, worker))
            except RuntimeError:
                continue  # already destroyed by deleteLater; drop it
        self._retired_tasks = still_running

    def _clear_extract_refs(self):
        """
    BUG-21: drops the Get Info extract worker and thread references once the
    thread has actually finished.

    Clearing them any earlier destroys a worker that still owns two running
    reader QThreads, which Qt treats as a fatal error and turns into an abort.
    Bound to the thread's `finished` signal, so by the time this runs the thread
    has stopped and the objects are safe to release. `deleteLater` on the same
    signal owns the actual destruction; this only releases our own handles so
    the next Get Info is not refused by the task-in-progress guard.
    """
        self.decompile_for_info_thread = None
        self.decompile_for_info_worker = None

    def _on_get_info_cache_progress(self, percentage, message):
        '''Handles progress updates specifically for the Phase 1 caching process.'''
        self.progress_bar.setValue(percentage)
        self.status_label.setText(f"Step 1/2: {message}")

    def _on_pdf_export_finished(self, result_message, pdf_path=None):
        """Handles the completion or failure of the PDF export background task."""
        duration = self._task_duration("pdf")
        if pdf_path:
            self._log_message(f"[INFO] {result_message}")
            try:
                size = os.path.getsize(pdf_path)
                self._log_message(
                    f"[DATA] PDF written: {pdf_path} | {size:,} bytes | Duration: {duration}")
            except Exception as e:
                self._log_message(f"[DATA] PDF written: {pdf_path} | Duration: {duration}")
                log_diagnostic("sizing the exported PDF", e, path=pdf_path)
            self.status_label.setText("PDF export complete.")
            self._show_tray_message("Export Complete", result_message)
            if self.open_pdf_on_complete:
                self._delayed_open_folder(pdf_path)
        else:
            self._log_message(f"[ERROR] {result_message}")
            self._log_message(f"[DATA] PDF export failed after {duration}.")
            self.status_label.setText("PDF export failed.")
            self._show_tray_message("Export Failed", result_message, QSystemTrayIcon.MessageIcon.Warning)

        self._reset_ui_after_task()
    
    def _on_pdf_export_progress(self, percentage):
        '''Updates the progress bar during the PDF export process.'''
        self.progress_bar.setValue(percentage)
        self.status_label.setText(f"Generating PDF... {percentage}% complete.")

    def _clear_decompile_selections(self):
        '''Clears only the decompile mode file and folder selections.'''
        self._log_message("[INFO] Decompile selections cleared by user.")
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
        self._log_message("[INFO] Compile selections cleared by user.")
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
                active_search_widget.setStyleSheet(self.STYLE_SEARCH_NO_MATCH)

            self.btn_find_prev.setEnabled(False)
            self.btn_find_next.setEnabled(False)
            return False
    
    def _find_first_match(self):
        """Triggered by Enter key. Finds results and jumps to the first one."""
        found = self._perform_search()
        # LOG-01: logged here rather than in _perform_search, which re-runs on
        # every keystroke -- this is the committed search, one line per Enter.
        # "I searched for X and got nothing" is otherwise unreproducible.
        query, criterion = self.last_search_query if self.last_search_query else ("", "")
        if found:
            self.current_search_index = 0
            self._log_message(
                f"[INFO] Search ({criterion}) for '{query}': {len(self.search_results):,} match(es).")
            self._jump_to_search_result()
        elif query:
            self._log_message(f"[WARN] Search ({criterion}) for '{query}': no matches.")

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

    def _resolve_preview_sizes(self):
        """
    BUG-20: fills in the `size` of every parsed texture record from one scan of
    the cache directory.

    Replaces two `os.path` stats per texture performed on the GUI thread while
    the log was still streaming. `os.scandir` reports size from the directory
    entry the OS has already read, so the whole set costs roughly one stat
    instead of two per file, and it happens once, after parsing, rather than
    interleaved with it.
    """
        if not self.preview_images or not self.info_cache_dir:
            return
        sizes = {}
        try:
            with os.scandir(self.info_cache_dir) as entries:
                for entry in entries:
                    if entry.is_file():
                        try:
                            sizes[entry.name] = entry.stat().st_size
                        except OSError:
                            pass
        except OSError as e:
            # STR-07: a missing or unreadable cache leaves every size at 0,
            # which the previewer already renders as unknown. Worth a line in
            # the log rather than a silent zero.
            log_diagnostic("scanning the info cache for texture sizes", e,
                           cache_dir=self.info_cache_dir)
            return

        for record in self.preview_images:
            if not record.get('size'):
                record['size'] = sizes.get(record.get('filename'), 0)

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

            # BUG-20: `size` is deliberately left at 0 here. This used to call
            # os.path.exists AND os.path.getsize on every Texture: line -- two
            # disk stats per texture, on the GUI thread, 15,170 of them for a
            # 7,584-texture archive. `_resolve_preview_sizes` fills them in
            # afterwards from a single directory scan.
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

    # How many buffered lines to keep when a task dies holding a full buffer.
    # A healthy Get Info buffers ~22k [DATA] lines; the tail is what shows how
    # far it got, and the whole point is to stay pasteable in a support thread.
    FAILED_TASK_LOG_TAIL = 50

    def _drain_log_buffer_tail(self, limit, reason):
        """
        Emits the last `limit` buffered lines, then empties the buffer (LOG-01).

        For the failure paths: the buffer holds the task's own output, and
        dropping it unseen is what made "it just failed" unanswerable. `reason`
        is a format string taking the number of lines actually shown.
        """
        with self.log_lock:
            pending = list(self.log_message_buffer)
            self.log_message_buffer.clear()

        if not pending:
            return

        tail = pending[-limit:]
        dropped = len(pending) - len(tail)
        self._log_message("[DATA] " + reason.format(len(tail))
                          + (f" ({dropped} earlier line(s) omitted)" if dropped else ""))
        for line in tail:
            self._log_message(line)

    def _format_log_message(self, message: str) -> tuple[str, str]:
        """
    Centralized log message formatter. Takes a raw string and returns (html, plain_text).
    This is the single source of truth for log appearance.
    """
        # BUG-20: `now_str = datetime.now().strftime(...)` stood here and was
        # never read -- dead, but not free: this function runs once per log
        # message, and a Get Info over a 7,584-texture archive queues 22,757 of
        # them, so it was 22,757 wasted datetime formats inside the single
        # blocking render pass.

        # Capitalize drive letter for any Windows path in the message.
        # BUG-20: guarded. Only a message containing a "<letter>:\" sequence can
        # match, and almost no info line does, so the cheap containment test
        # skips the regex for the overwhelming majority of them.
        if sys.platform == "win32" and ":\\" in message:
            message = _DRIVE_LETTER_RE.sub(lambda m: m.group(1).upper() + ':\\', message)

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
            # BUG-07: this pattern was `\d{{2}}` -- leftover .format() escaping in a
            # raw string that is never .format()ed, so it looked for the literal
            # text "{2}" and timestamps were never colorised.
            html_content = re.sub(r'(\d{2}:\d{2}:\d{2})', f'<span style="color:{self.COLOR_NUMERIC};">\\1</span>', html_content)
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
            # BUG-20: precompiled patterns, prebuilt replacement, and a cheap
            # containment test before each. Every one of these ran on every
            # [DATA] line; a texture line ("Texture: foo.png", "Dimensions:
            # 161x109", "Format: A8R8G8B8") matches none of them, and that is
            # the overwhelming majority of the traffic during Get Info.
            if "v" in html_content:
                html_content = _VERSION_RE.sub(self.SPAN_NUMERIC, html_content)
            if "KB" in html_content:
                html_content = _KB_RE.sub(self.SPAN_NUMERIC, html_content)
            # BUG-07: same dead `{{2}}` escaping as the timestamp pattern above.
            if "-" in html_content:
                html_content = _DATE_RE.sub(self.SPAN_NUMERIC, html_content)
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
    
    def _resolve_missing_dimensions(self):
        """
    Fills in any 'N/A' dimensions by reading image headers.

    GUI-01: `_scan_cache_dir_fallback` deliberately records every image as 'N/A'
    and defers the real read until the image is viewed -- a sound trade for load
    speed, and not something to undo. But the Dimensions search filter is built
    from those values, so after a fallback scan the entire Dimensions criterion
    was empty and that search mode did nothing at all.

    `QImageReader.size()` reads the header only; it does not decode the image.
    This runs once per gallery load, not per frame.
    """
        resolved = 0
        for record in self.preview_images:
            if record.get('dimensions') and record['dimensions'] != 'N/A':
                continue
            try:
                reader = QImageReader(record['path'])
                reader.setAllocationLimit(0)
                size = reader.size()
                if size.isValid() and size.width() > 0 and size.height() > 0:
                    record['dimensions'] = "{}x{}".format(size.width(), size.height())
                    resolved += 1
            except Exception as e:
                log_diagnostic("reading image dimensions for the Dimensions filter",
                               e, path=record.get('path'))
        return resolved

    def _populate_dimensions_filter(self):
        """Populates the dimensions combo box with unique dimensions from the image data."""
        # GUI-01: resolve anything still 'N/A' first, or the filter comes up empty
        # after a fallback scan. Silent when there is nothing to resolve, which is
        # the normal case -- TextureCompiler's -info output already carries them.
        if self.preview_images:
            resolved = self._resolve_missing_dimensions()
            if resolved:
                self._log_message(
                    "[INFO] Read dimensions for {} image(s) to build the Dimensions filter.".format(resolved))

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
        self.update_check_manual = manual
        self.update_worker.finished.connect(self._on_update_worker_finished)
        self.update_worker.error.connect(self._on_update_worker_error)
        self.update_thread.started.connect(self.update_worker.run)
        # BUG-23: without these two the thread's event loop never exits, so
        # `finished` never fires and neither deleteLater below it ever runs.
        # Every other thread site in this file has had both since BUG-21; this
        # one was missed because the update check is the only task that is not
        # started by the user, so nothing in the test suite ever closed the
        # window after one had run. `error` must quit too, or a failed check
        # leaves the thread running just the same.
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.error.connect(self.update_thread.quit)
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

        # SEC-03: a failed or rejected download must not leave a staged payload
        # sitting on disk where a later run could pick it up.
        if self.update_staging_dir and os.path.exists(self.update_staging_dir):
            try:
                shutil.rmtree(self.update_staging_dir, ignore_errors=True)
                self._log_message("[INFO] Removed update staging directory after failed download.")
            except Exception as e:
                self._log_message(f"[WARN] Could not remove update staging directory: {e}")
        self.update_staging_dir = None

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
        # BUG-03: this used to build a bare socket that was never closed (one
        # leaked descriptor per update check) and call socket.setdefaulttimeout(2)
        # without ever restoring it, silently imposing a 2-second deadline on
        # every later network call in the process. create_connection takes a
        # per-call timeout and the context manager closes the socket on both the
        # success and the failure path.
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.error, OSError) as ex:
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
    # BUG-11: zoom bounds, expressed as a multiple of the fit-to-window size.
    MIN_ZOOM_LEVEL = 0.1
    MAX_ZOOM_LEVEL = 8.0
    # Ceiling on the rendered pixmap so magnifying a large texture cannot
    # allocate hundreds of MB (24M px is ~96 MB at 4 bytes per pixel).
    MAX_PREVIEW_PIXELS = 24_000_000

    def _render_preview_at_zoom(self):
        """
    BUG-11: renders the preview at self.current_zoom_level, always scaling from
    the full-resolution source pixmap.

    The old _zoom_in / _zoom_out each rescaled whatever was already in the label,
    so every step compounded on the last: zooming out to 51% and back to 100%
    left a permanently softened image, because the discarded pixels were gone.
    Scaling from the source each time makes zoom non-destructive and exactly
    reversible.
    """
        source = self._preview_source_pixmap
        fit_size = self._preview_fit_size
        if source is None or source.isNull() or fit_size is None:
            return False

        new_width = max(int(fit_size.width() * self.current_zoom_level), 1)
        new_height = max(int(fit_size.height() * self.current_zoom_level), 1)

        # Magnifying past the source resolution invents pixels, but a texture
        # small enough to fit the pane is exactly the case where the user needs
        # a closer look, so serve it through _upscale_pixmap instead of refusing
        # to grow. Downscaling stays a single smooth pass from the source.
        if new_width == source.width() and new_height == source.height():
            scaled_pixmap = source
        elif new_width <= source.width() and new_height <= source.height():
            scaled_pixmap = source.scaled(
                new_width, new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
        else:
            scaled_pixmap = self._upscale_pixmap(source, new_width, new_height)

        self.image_display_label.setPixmap(scaled_pixmap)

        # BUG-11b: with setWidgetResizable(True) the label tracks the viewport,
        # which is what fit-to-window wants. A minimum size larger than the
        # viewport is what makes it overflow instead, which is what brings the
        # scroll bars up and makes the magnified image pannable.
        viewport_size = self.image_scroll_area.viewport().size()
        if (scaled_pixmap.width() > viewport_size.width()
                or scaled_pixmap.height() > viewport_size.height()):
            self.image_display_label.setMinimumSize(scaled_pixmap.size())
        else:
            self._reset_preview_label_bounds()
        return True

    def _reset_preview_label_bounds(self):
        """
        Drops the panning minimum so the label collapses back to the viewport.

        Called whenever the label stops holding an oversized pixmap - fitting,
        stepping back down, or swapping in the placeholder or an error message -
        because a stale minimum leaves scroll bars on a picture that no longer
        needs them.
        """
        if hasattr(self, 'image_display_label'):
            self.image_display_label.setMinimumSize(0, 200)

    def _upscale_pixmap(self, source, target_width, target_height):
        """
        Magnify past the source resolution as cleanly as invented pixels allow.

        A plain bilinear (SmoothTransformation) blow-up of a small texture turns
        to mush well before 2x. Stepping up by the largest whole-number factor
        with nearest-neighbour first keeps the edges hard, then one smooth pass
        covers the fractional remainder so the result is not blocky at 2.5x,
        3.7x and the like. Artifacts are unavoidable - the detail is not in the
        file - but the image stays readable.
        """
        source_width = max(source.width(), 1)
        source_height = max(source.height(), 1)
        ratio = max(target_width / source_width, target_height / source_height)

        staged = source
        integer_factor = int(ratio)
        if integer_factor >= 2:
            staged = source.scaled(
                source_width * integer_factor, source_height * integer_factor,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation)

        if staged.width() == target_width and staged.height() == target_height:
            return staged
        return staged.scaled(
            target_width, target_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)

    def _max_zoom_for_current_image(self):
        """
        MAX_ZOOM_LEVEL, further capped by MAX_PREVIEW_PIXELS for this image.

        The cap is applied to the zoom level rather than to the rendered size so
        the overlay never claims a magnification the pixmap does not actually
        have - the old code silently clamped the pixmap to the source size, which
        is why the label kept counting past 1.2x while the picture stopped
        growing.
        """
        fit_size = self._preview_fit_size
        if fit_size is None or fit_size.width() <= 0 or fit_size.height() <= 0:
            return self.MAX_ZOOM_LEVEL
        fit_pixels = fit_size.width() * fit_size.height()
        budget_zoom = math.sqrt(self.MAX_PREVIEW_PIXELS / fit_pixels)
        return max(self.MIN_ZOOM_LEVEL, min(self.MAX_ZOOM_LEVEL, budget_zoom))

    def _apply_zoom_step(self, factor):
        """Shared body of _zoom_in / _zoom_out. Clamps, renders, updates state."""
        if not self.preview_images or self.current_preview_index == -1:
            return
        if self._preview_source_pixmap is None or self._preview_fit_size is None:
            return

        new_level = self.current_zoom_level * factor
        new_level = max(self.MIN_ZOOM_LEVEL,
                        min(new_level, self._max_zoom_for_current_image()))
        if new_level == self.current_zoom_level:
            return  # Already at the limit; nothing to redraw.

        previous_level = self.current_zoom_level
        # BUG-11b: remember what the viewport was centred on before the pixmap
        # changes size, so a zoom step magnifies about the middle of what is on
        # screen instead of dumping the view back at the top-left corner.
        focus = self._capture_preview_focus()
        self.current_zoom_level = new_level
        if not self._render_preview_at_zoom():
            self.current_zoom_level = previous_level
            return
        self._restore_preview_focus(focus)

        self.is_image_zoomed = True
        self.btn_fit_to_window.setEnabled(True)
        self._update_zoom_overlay()

    def _initial_zoom_level(self):
        """
        The zoom a freshly-loaded image is drawn at.

        Normally that is simply the level already in force -- LAYOUT-02 keeps it
        across navigation. The exception is the first image of a session, which
        takes the level restored from config.ini; that value is consumed here,
        at first use, rather than being cleared at startup, so a session that
        never opens the previewer does not silently discard it.
        """
        pending = getattr(self, 'startup_zoom_level', None)
        if pending is not None:
            self.startup_zoom_level = None
            if pending > 0 and abs(pending - 1.0) >= 0.01:
                return pending
        return getattr(self, 'current_zoom_level', 1.0)

    def _capture_preview_focus(self):
        """Returns the scroll position as a fraction of the content, or None."""
        if not hasattr(self, 'image_scroll_area'):
            return None
        viewport = self.image_scroll_area.viewport().size()
        content = self.image_display_label.size()
        if content.width() <= 0 or content.height() <= 0:
            return None
        h_bar = self.image_scroll_area.horizontalScrollBar()
        v_bar = self.image_scroll_area.verticalScrollBar()
        return ((h_bar.value() + viewport.width() / 2) / content.width(),
                (v_bar.value() + viewport.height() / 2) / content.height())

    def _restore_preview_focus(self, focus):
        """
        Puts the fraction captured by _capture_preview_focus back on screen.

        Deferred by a zero-delay timer because the scroll bar ranges only widen
        once the layout has acted on the label's new minimum size; setting the
        value now would just clamp it against the old range.
        """
        if focus is None or not hasattr(self, 'image_scroll_area'):
            return
        focus_x, focus_y = focus

        def apply_focus():
            viewport = self.image_scroll_area.viewport().size()
            content = self.image_display_label.size()
            h_bar = self.image_scroll_area.horizontalScrollBar()
            v_bar = self.image_scroll_area.verticalScrollBar()
            h_bar.setValue(int(focus_x * content.width() - viewport.width() / 2))
            v_bar.setValue(int(focus_y * content.height() - viewport.height() / 2))

        QTimer.singleShot(0, apply_focus)

    def _zoom_out(self):
        """Reduces the zoom level of the displayed image."""
        self._apply_zoom_step(0.8)

    def _zoom_in(self):
        """Increases the zoom level of the displayed image."""
        self._apply_zoom_step(1.2)

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
    
    def _pdf_export_directory(self):
        """
        Where the Save dialog should open for a PDF report.

        PDF-02: it used to seed from `decompileoutput` -- a different setting,
        for a different job -- and `_get_config_path` falls back to the app's
        own directory when that is unset, which is the folder the maintainer
        kept landing in. The folder a report was last actually saved to is
        remembered now and preferred whenever it still exists.

        "Still exists" is the whole reason this is a loop rather than a lookup:
        a remembered folder can be deleted, renamed, or sit on a drive that is
        not currently attached, and a Save dialog opened on a path like that is
        worse than one opened somewhere merely uninteresting.
        """
        candidates = (self.config.get('Paths', 'pdfexport', fallback=''),
                      self._get_config_path('decompileoutput'))
        for candidate in candidates:
            try:
                if candidate and os.path.isdir(candidate):
                    return candidate
            except Exception as e:
                # A malformed path can raise on some filesystems rather than
                # simply answering False.
                log_diagnostic("checking a remembered PDF export folder", e,
                               path=candidate)
        return self.app_dir

    def _start_pdf_export_worker(self, image_data: list, export_description: str):
        """Gets a save path from the user and starts the PDF export worker thread."""
        base_name = os.path.basename(self.decompile_input_file)
        pdf_name = os.path.splitext(base_name)[0] + "_Report.pdf"

        last_path = self._pdf_export_directory()
        save_path, _ = QFileDialog.getSaveFileName(self, "Save PDF Report", os.path.join(last_path, pdf_name), "PDF Files (*.pdf)")

        if not save_path:
            self._log_message("[INFO] PDF export cancelled by user.")
            return

        # PDF-02: recorded on SELECTION, not on success. The user has told us
        # where reports belong; whether reportlab then failed is a separate
        # matter, and making them navigate back there after an error would be
        # punishing them for it.
        chosen_directory = os.path.dirname(os.path.abspath(save_path))
        if os.path.isdir(chosen_directory):
            self._set_config_path('pdfexport', chosen_directory)

        self._log_message(f"[INFO] ----- Starting PDF Export of {export_description} to {os.path.basename(save_path)} -----")
        # The basename alone does not identify the file the user ends up with,
        # and the paper choice changes the output but was never recorded.
        self._log_message(f"[DATA] Destination: {save_path}")
        self._log_message(f"[DATA] Images: {len(image_data):,} | Paper: {getattr(self, 'pdf_paper', 'light')}")
        self._mark_task_start("pdf")
        self.status_label.setText("Exporting to PDF... Please wait.")
        self.progress_bar.setValue(0)
        self._set_ui_task_active(True)

        self.pdf_export_thread = QThread(self)
        self.pdf_export_worker = PdfExportWorker(image_data, save_path,
                                                paper=getattr(self, 'pdf_paper', 'light'))
        self.pdf_export_worker.moveToThread(self.pdf_export_thread)

        self.pdf_export_worker.progress.connect(self._on_pdf_export_progress)
        self.pdf_export_thread.started.connect(self.pdf_export_worker.run)

        self.pdf_export_worker.finished_with_path.connect(self._on_pdf_export_finished)
        self.pdf_export_worker.error.connect(self._on_pdf_export_error)
        # Emitted from the worker thread; _log_message is lock-guarded and this
        # is a queued connection to the GUI thread, as with every other signal here.
        self.pdf_export_worker.warning.connect(self._log_message)

        # BUG-21: the seventh site. Its completion signal is named
        # `finished_with_path` rather than `finished`, which is why it did not
        # show up alongside the other six. Both quit connections were already
        # correct; only the deleteLater was racing.
        self.pdf_export_worker.finished_with_path.connect(self.pdf_export_thread.quit)
        self.pdf_export_worker.error.connect(self.pdf_export_thread.quit)
        self.pdf_export_thread.finished.connect(self.pdf_export_worker.deleteLater)
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
                        except Exception as e:
                            # STR-07: the record survives with size 0, which the
                            # UI shows as "0 B" -- indistinguishable from a real
                            # empty file without this.
                            log_diagnostic("reading a cached image's size during the fallback scan",
                                           e, path=image_path)

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
        """
        Re-fits the preview after the window has finished being resized.

        LAYOUT-02 dropped the `and not self.is_image_zoomed` guard. That existed
        because _update_previewer_ui used to reset the zoom, so refreshing a
        zoomed preview would have thrown the user's magnification away; the
        cost was that a zoomed image kept the size it had before the resize,
        while the pane around it changed. Now that the level survives a refresh,
        the refresh can happen every time -- so a zoomed preview re-fits to the
        new pane and STAYS at the same multiple of it.
        """
        if self.preview_images:
            self._update_previewer_ui()
    
class ChangelogDialog(SizeRememberingDialog):
    SIZE_KEY = "changelog"

    def __init__(self, changelog_text, parent=None):
        super().__init__(parent)
        #self.setWindowTitle("Changelog")
        self.setWindowTitle(f"{APP_TITLE} - {APP_VERSION} - Changelog")
        self.setWindowIcon(parent.app_icon if parent else QIcon())
        # LAYOUT-01: the minimum stays a minimum. The dialog used to OPEN at it,
        # because nothing ever called resize() -- the changelog is wide HTML and
        # 600x500 wrapped it into a scrolling column.
        self.setMinimumSize(600, 500)
        layout = QVBoxLayout(self)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        # CHANGELOG-01: the file is plain text now; the markup is built here.
        text_edit.setHtml(render_changelog_html(changelog_text))
        # Long entries wrap instead of scrolling sideways, so there is nothing
        # left for a horizontal scroll bar to do.
        text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        text_edit.document().setDocumentMargin(8)
        layout.addWidget(text_edit)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        
class HelpDialog(SizeRememberingDialog):
    SIZE_KEY = "help"

    def __init__(self, markdown_file_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_TITLE} - {APP_VERSION} - Help")
        self.setMinimumSize(800, 600)
        # LAYOUT-01: the old unconditional resize(1250, 800) is now the
        # first-run default in DIALOG_DEFAULT_SIZES -- unconditional, it
        # overwrote whatever size the user had chosen last time.

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
        # STR-08: this was the third stylesheet carrying its own hex literals.
        self.content_browser.document().setDefaultStyleSheet(HELP_STYLESHEET)

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




# STR-08: the global stylesheet was a 131-line local variable inside the
# `if __name__ == "__main__"` block, which made it unreachable from any test
# and invisible to anything else in the file. It is a module constant now,
# and its colours come from QSS_VARS rather than being spelled
# out again as hex literals.
APP_STYLESHEET = """

/* =======================================================================
   UI-02 -- the Glass Midnight Navy sheet
   -----------------------------------------------------------------------
   This replaces the UI-01 Nord sheet. UI-01's job was to give the window a
   surface hierarchy it did not have: ground -> panel -> control, wells cut
   below, one accent-filled primary action. That hierarchy is kept intact
   here -- the sections below are the same sections, in the same order --
   but it is now expressed in glass rather than in flat Nord greys.

   The three mechanics, and what breaks if one of them is dropped:

     gradient   QMainWindow / QDialog paint a diagonal
                GROUND -> PANEL -> GROUND. This is the only opaque fill in
                the window; everything else sits on it.
     transparency
                QWidget is transparent by default so that gradient shows
                through every container. This is why each opaque-by-nature
                widget below (menus, popups, item views, tooltips) has to
                re-declare a background of its own -- without that they
                render see-through and unreadable.
     films      panels are white at 4.5-11% alpha with a brighter hairline
                along the top edge only; wells are black at 28-36%. Alpha,
                not solid colour, is what makes the depth survive on top of
                a gradient that is a different brightness at each corner.

   Two ordering rules this sheet depends on, both load-bearing:

     1. `QWidget` must come BEFORE `QMainWindow`. Both are plain type
        selectors, so Qt scores them equally and the last one wins -- with
        the order reversed, the blanket transparency repaints the gradient
        away and the whole theme renders flat.
     2. Later rules override earlier ones at equal specificity, so the
        section order (ground, containers, controls, accent layer) is
        deliberate and not incidental.
   ======================================================================= */


/* -- 1. Ground ---------------------------------------------------------
   The gradient, and the blanket transparency that lets it be seen. */
        QWidget {{
            background: transparent;
            color: {glass_text};
            font-size: 10pt;
        }}
        QMainWindow, QDialog {{
            background-color: {glass_window};
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 {glass_ground},
                                        stop:0.5 {glass_panel},
                                        stop:1 {glass_ground});
            color: {glass_text};
        }}
        /* These have no surface of their own and must not punch holes
           through the panel they sit on. */
        QLabel, QCheckBox, QRadioButton, QSplitter {{
            background: transparent;
        }}
        QFrame {{
            margin-top: 5px;
            margin-bottom: 5px;
        }}


/* -- 2. Menu bar and menus ---------------------------------------------
   The bar rides on the gradient; the menus themselves cannot -- a popup
   extends past the window, so it needs an opaque fill of its own or it
   shows the desktop through. PANEL is that fill. */
        QMenuBar {{
            background: transparent;
            border-bottom: 1px solid {film_line};
            padding: 3px 4px;
        }}
        QMenuBar::item {{
            color: {glass_text}; /* Fix for black text/icons on Win10/7 */
            background: transparent;
            padding: 5px 11px;
            border-radius: 6px;
        }}
        QMenuBar::item:selected {{
            background-color: {glass_accent_hover};
            color: {glass_bright};
        }}
        QMenuBar::item:pressed {{
            background-color: {glass_accent_press};
            color: {glass_bright};
        }}
        QMenu {{
            background-color: {glass_panel};
            border: 1px solid {film_line_lit};
            border-radius: 8px;
            padding: 6px;
        }}
        QMenu::item {{
            color: {glass_text}; /* Fix for black text/icons on Win10/7 */
            background: transparent;
            padding: 6px 22px 6px 34px;
            border-radius: 6px;
        }}
        QMenu::item:selected {{
            background-color: {glass_accent_soft};
            color: {glass_bright};
        }}
        QMenu::item:disabled {{
            color: {glass_disabled};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {film_line};
            margin: 5px 10px;
        }}
        QMenu::icon {{
            left: 11px;
        }}

        /* FINAL CHECKMARK FIX -- the ticked entries under Display/Options */
        QMenu::indicator {{
            width: 13px;
            height: 13px;
            left: 9px;
        }}
        QMenu::indicator:non-exclusive:checked {{
            image: url({checkmark_svg_path});
        }}


/* -- 3. Panels ---------------------------------------------------------
   A group box is a pane of glass: a barely-there white film, a hairline
   border that is brighter along the top edge, and a title in the accent
   sitting on the frame. The title has no background of its own now -- on
   a gradient, a filled title pill would be a visible patch of the wrong
   navy wherever the gradient underneath it had moved on. */
        QGroupBox {{
            background-color: {film_panel};
            border: 1px solid {film_line};
            border-top: 1px solid {film_line_lit};
            border-radius: 10px;
            margin-top: 12px;
            padding: 18px 7px 10px 7px;
            font-weight: bold;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 14px;
            padding: 2px 9px;
            color: {glass_accent};
            background: transparent;
        }}
        /* Drag-and-drop target, lit along its whole edge rather than by a
           2px border that shifted the layout as it appeared. */
        DropGroupBox[dragging="true"] {{
            border: 1px solid {glass_accent};
            border-top: 1px solid {glass_accent};
            background-color: {glass_accent_hover};
        }}
        DropGroupBox[dragging="true"]::title {{
            color: {glass_accent_bright};
        }}


/* -- 4. Buttons --------------------------------------------------------
   Raised glass: a white film, lit along the top edge. Hover blooms the
   accent through it and lights the border; pressed deepens the bloom and
   shifts the label a pixel down. */
        QPushButton {{
            background-color: {film_raised};
            color: {glass_text}; /* This ensures icons are white on Win10/7 */
            border: 1px solid {film_line};
            border-top: 1px solid {film_line_lit};
            border-radius: 8px;
            padding: 6px 7px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {glass_accent_hover};
            border: 1px solid {glass_accent};
            color: {glass_bright};
        }}
        QPushButton:pressed {{
            background-color: {glass_accent_press};
            border: 1px solid {glass_accent};
            color: {glass_bright};
            padding-top: 8px;
            padding-bottom: 6px;
        }}
        QPushButton:focus {{
            border: 1px solid {glass_accent};
            outline: none;
        }}
        QPushButton:disabled {{
            background-color: {film_disabled};
            color: {glass_disabled};
            border: 1px solid {film_line_soft};
        }}
        QPushButton#MenuButton {{
            padding-right: 20px;
        }}
        QPushButton::menu-indicator {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            right: 8px;
        }}

        /* The primary action. Both START buttons carry this object name; it
           is the one control in the window filled with solid accent rather
           than a film, which is what makes it findable at a glance. The
           deep end of the ramp, not ACCENT itself -- the qtawesome glyphs
           are drawn light and a pale fill would swallow them. */
        QPushButton#PrimaryButton {{
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                              stop:0 {glass_accent_deep},
                                              stop:1 {glass_accent_shade});
            border: 1px solid {glass_accent};
            border-top: 1px solid {glass_accent_bright};
            color: {glass_bright};
            font-weight: bold;
        }}
        QPushButton#PrimaryButton:hover {{
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                              stop:0 {glass_accent},
                                              stop:1 {glass_accent_deep});
            border: 1px solid {glass_accent_bright};
            color: {glass_bright};
        }}
        QPushButton#PrimaryButton:pressed {{
            background-color: {glass_accent_shade};
            border: 1px solid {glass_accent};
            color: {glass_bright};
        }}
        QPushButton#PrimaryButton:disabled {{
            background-color: {film_disabled};
            color: {glass_disabled};
            border: 1px solid {film_line_soft};
        }}


/* -- 5. Wells: text entry, text views, item views ----------------------
   Everything the user reads out of or types into is cut *into* the glass
   -- black at alpha rather than a lighter fill -- so input reads as
   recessed and controls as raised. */
        QLineEdit, QComboBox, QAbstractSpinBox {{
            background-color: {well};
            color: {glass_text};
            border: 1px solid {film_line};
            border-radius: 8px;
            padding: 6px 9px;
            selection-background-color: {glass_accent_soft};
            selection-color: {glass_bright};
        }}
        QLineEdit:hover, QComboBox:hover, QAbstractSpinBox:hover {{
            border: 1px solid {film_line_lit};
        }}
        QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus {{
            border: 1px solid {glass_accent};
            background-color: {well_deep};
        }}
        QLineEdit:disabled, QComboBox:disabled {{
            background-color: {film_disabled};
            color: {glass_disabled};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;
            border: none;
            background: transparent;
        }}
        QComboBox::down-arrow {{
            image: url(__CHEVRON_SVG__);
            width: 12px;
            height: 12px;
        }}
        /* A popup list, so opaque -- see the note on QMenu. */
        QComboBox QAbstractItemView {{
            background-color: {glass_panel};
            border: 1px solid {film_line_lit};
            border-radius: 8px;
            padding: 4px;
            selection-background-color: {glass_accent_soft};
            selection-color: {glass_bright};
            outline: none;
        }}

        QTextEdit, QPlainTextEdit, QTextBrowser {{
            background-color: {well};
            color: {glass_text};
            border: 1px solid {film_line};
            border-radius: 8px;
            padding: 6px;
            selection-background-color: {glass_accent_soft};
            selection-color: {glass_bright};
        }}
        /* The log. The deepest well in the window: it is dense coloured
           text, and every one of those colours was chosen against a near
           black rather than against the middle of the gradient. */
        QTextEdit#LogWidget {{
            background-color: {well_deep};
            border: 1px solid {film_line};
            border-radius: 8px;
            padding: 8px;
        }}

        QAbstractItemView {{
            background-color: {well};
            border: 1px solid {film_line};
            border-radius: 8px;
            padding: 4px;
            outline: none;
            selection-background-color: {glass_accent_soft};
            selection-color: {glass_bright};
        }}
        QListView::item, QTreeView::item {{
            padding: 5px 7px;
            border-radius: 6px;
        }}
        QListView::item:hover, QTreeView::item:hover {{
            background-color: {film_hover};
        }}
        /* Fusion's own selection is a Windows blue that belongs to no part
           of this palette. It was the loudest off-tone colour in the app. */
        QListView::item:selected, QTreeView::item:selected {{
            background-color: {glass_accent_soft};
            color: {glass_bright};
        }}

        /* Only QScrollArea -- the plain scrolling container. NOT
           QAbstractScrollArea, which is also the base of QTextEdit and the
           item views above and would win the specificity tie against them.
           The previewer's scroll area is transparent so the texture sits on
           the label's own mat (STYLE_PREVIEW_NORMAL), not on a second one;
           the update dialog's changelog scroller styles itself locally
           through STYLE_SCROLL_AREA. */
        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}


/* -- 6. Scroll bars ----------------------------------------------------
   Slim, arrowless, transparent track. Fusion's own steppers were the
   single most dated thing on screen. */
        QScrollBar:vertical {{
            background: transparent;
            border: none;
            width: 12px;
            margin: 4px 2px 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {film_line_lit};
            border-radius: 4px;
            min-height: 28px;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            border: none;
            height: 12px;
            margin: 2px 4px 2px 4px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {film_line_lit};
            border-radius: 4px;
            min-width: 28px;
        }}
        QScrollBar::handle:hover {{
            background-color: {glass_accent_soft};
        }}
        QScrollBar::handle:pressed {{
            background-color: {glass_accent};
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            height: 0px;
            width: 0px;
            border: none;
            background: none;
        }}
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: none;
        }}


/* -- 7. Check boxes and sliders ---------------------------------------- */
        QCheckBox {{
            spacing: 8px;
            padding: 2px 0px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {film_line_lit};
            border-radius: 5px;
            background-color: {well};
        }}
        QCheckBox::indicator:hover {{
            border: 1px solid {glass_accent};
        }}
        QCheckBox::indicator:checked {{
            background-color: {glass_accent_soft};
            border: 1px solid {glass_accent};
            image: url({checkmark_svg_path});
        }}
        QCheckBox:disabled {{
            color: {glass_disabled};
        }}
        QCheckBox::indicator:disabled {{
            background-color: {film_line_soft};
            border: 1px solid {film_line};
        }}

        QSlider::groove:horizontal {{
            background-color: {well};
            border: 1px solid {film_line};
            height: 5px;
            border-radius: 3px;
        }}
        QSlider::sub-page:horizontal {{
            background-color: {glass_accent};
            border: 1px solid {glass_accent};
            height: 5px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background-color: {glass_bright};
            border: 2px solid {glass_accent};
            width: 12px;
            height: 12px;
            margin: -6px 0px;
            border-radius: 8px;
        }}
        QSlider::handle:horizontal:hover {{
            background-color: {glass_accent_bright};
            border: 2px solid {glass_accent_bright};
        }}


/* -- 8. Splitters ------------------------------------------------------
   A hairline that turns accent when the pointer is on it, so the panes
   read as separated rather than merely adjacent. */
        QSplitter::handle:horizontal {{
            background-color: transparent;
            border-left: 1px solid {film_line};
            width: 1px;
            margin: 4px 4px;
        }}
        QSplitter::handle:horizontal:hover {{
            border-left: 1px solid {glass_accent};
        }}
        QSplitter::handle:vertical {{
            background-color: transparent;
            border-top: 1px solid {film_line};
            height: 1px;
            margin: 4px 4px;
        }}
        QSplitter::handle:vertical:hover {{
            border-top: 1px solid {glass_accent};
        }}


/* -- 9. Progress -------------------------------------------------------
   Sunken track, accent fill running deep-to-bright left to right, so the
   bar reads as filling rather than as a block that grows. */
        QProgressBar {{
            background-color: {well};
            border: 1px solid {film_line};
            border-radius: 8px;
            min-height: 16px;
            text-align: center;
            color: {glass_bright};
            font-weight: bold;
        }}
        QProgressBar::chunk {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                              stop:0 {glass_accent_deep},
                                              stop:1 {glass_accent});
            border-radius: 7px;
            margin: 1px;
        }}


/* -- 10. Named labels and tooltips ------------------------------------- */
        QLabel#StatusLabel {{
            color: {glass_accent};
            font-weight: bold;
        }}
        /* The path readouts under each step. Unselected stays quiet;
           selected is accent rather than body text, so "this one is set"
           carries across the panel without having to be read. */
        QLabel[state="unselected"] {{
            color: {glass_dim};
            font-style: italic;
        }}
        QLabel[state="selected"] {{
            color: {glass_accent_bright};
            font-weight: bold;
        }}

        /* Zoom Level Overlay -- floats over the previewed texture, so it
           is opaque-ish glass in its own right rather than a film: what is
           behind it is the user's artwork, not the window. */
        QLabel#ZoomLevelLabel {{
            background-color: rgba(7, 12, 26, 0.82); /* GROUND at 82% */
            color: {glass_accent};
            border: 1px solid {film_line_lit};
            font-weight: bold;
            font-size: 9pt;
            padding: 4px 9px;
            border-radius: 6px;
            margin: 10px; /* Give it some space from the corner */
        }}

        /* Tooltips leave the window, so they are opaque -- see QMenu. */
        QToolTip {{
            background-color: {glass_panel};
            color: {glass_text};
            border: 1px solid {glass_accent};
            padding: 6px 9px;
            border-radius: 6px;
        }}
"""

APP_STYLESHEET = APP_STYLESHEET.replace(
    "__CHEVRON_SVG__",
    get_resource_path('assets/chevron-down.svg').replace('\\', '/'))


if __name__ == "__main__":
    # Set application name and organization name
    app = QApplication(sys.argv)
    # Removes the default limit (128MB/256MB) on image loading to allow large filmstrips
    QImageReader.setAllocationLimit(0)     
    app.setStyle("Fusion")
    # BUG-13: this ran unguarded, so the app died on import on any non-Windows
    # platform despite the `sys.platform == "win32"` checks used everywhere else.
    # The AppUserModelID only exists on Windows; elsewhere it is simply skipped.
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Kittmaster's Kodi TextureTool")
        except Exception:
            pass  # Taskbar grouping is cosmetic; never block startup for it.
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("KodiTextureTool")

    # 1. Get the correct, absolute path to the SVG using your helper function
    checkmark_path = get_resource_path('assets/checkmark.svg').replace('\\', '/')

    # 2. Your stylesheet with ALL CSS braces escaped ({{ and }})
    # STR-08: the stylesheet now lives in the module-level APP_STYLESHEET.

    # 3. Format the stylesheet string, injecting the correct path
    formatted_stylesheet = APP_STYLESHEET.format(checkmark_svg_path=checkmark_path, **QSS_VARS)

    # 4. Apply the fully formatted stylesheet
    app.setStyleSheet(formatted_stylesheet)

    window = TextureToolApp()
    window.show()
    sys.exit(app.exec())