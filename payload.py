# PATCHED_BY_SCRIPT_VERSION: v2.2.0 | Implemented AUTO versioning to dynamically increment patch versions.
from __future__ import annotations
from typing import Dict, List, Optional

import difflib
import os
import re
import shutil
import textwrap
from typing import Any, Dict, List, Optional, Tuple, Mapping

import libcst as cst
from colorama import Fore, Style, init

init(autoreset=True)


# ==============================================================================
# ====== SCRIPT CONFIGURATION (EDIT FOR EACH PATCH) ============================
# ==============================================================================

TARGET_FILE: str = "Kodi TextureTool.py"

# SET TO "AUTO" to automatically increment the patch version from the target file.
# OR, set to a specific version string like "v4.0.0" to override.
BACKUP_VERSION: str = "AUTO"

PATCH_DESCRIPTION: str = "Fixed a crash that could occur during the transition between Phase 1 and Phase 2 of the 'Get Info' process by improving thread handle cleanup."
INTERACTIVE_MODE: bool = False # SET TO True to see a diff and approve changes before writing to the file.

# ==============================================================================
# ====== PYLANCE DEVELOPMENT STUBS (FOR STATIC ANALYSIS) =======================
# ==============================================================================
# This section helps your editor (e.g., VS Code with Pylance) understand the
# code in the directives below, reducing false-positive errors.
# It has NO effect on the patching process itself.
# To use, define dummy versions of the classes/functions you are patching.

if False:
    # Example Stubs:
    class MyClass:
        """A dummy class to provide context for Pylance."""
        some_attribute: str = ""
        def __init__(self): ...
        def method_to_replace(self, old_args): ...
        def method_to_inject_into(self, data): ...
        def obsolete_method(self): ...

    # A dummy top-level variable
    stylesheet: str = ""

# ==============================================================================
# ### NEW ### AI DEVELOPMENT PHILOSOPHY (DO NOT MODIFY)
# ==============================================================================
# 1. CONTEXT IS KEY: The user's request is only the starting point. The primary
#    source of truth is the existing code in the target file.
# 2. PRESERVE AND ENHANCE: Your goal is to integrate changes seamlessly. This
#    means preserving existing comments, docstrings, and architectural patterns.
# 3. CAUTION OVER SPEED: It is better to ask for clarification or refuse a
#    dangerous change than to generate code that breaks existing functionality.
#    The stability of the application is the highest priority.
# ==============================================================================

# ==============================================================================
# ====== SURGICAL PATCH DIRECTIVES (AI-POPULATED SECTION) ======================
# ==============================================================================
# ### MODIFIED ### INSTRUCTIONS FOR AI:
# 1. READ AND PRESERVE COMMENTS: When replacing code, you MUST review the
#    original function for existing developer comments (especially those marked
#    with `!!` or `FIX:`). PRESERVE their intent and placement in your new code.
#
# 2. ### NEW ### CHECK FOR IMPORTS: After generating any new code block
#    (e.g., for METHODS_TO_ADD or TOP_LEVEL_CODE_TO_ADD), you MUST perform a
#    secondary review of that code to identify all imported classes used and ensure
#    a corresponding `IMPORTS_TO_ADD` directive is created. This is a critical
#    step to prevent `NameError` exceptions.
#
# 3. FOLLOW EXISTING PATTERNS: Before writing code, review the target file to
#    understand and use established patterns (e.g., using `_set_busy_state` for
#    UI updates, using `.state([...])` for ttk widgets).
# 4. Populate the dictionaries below to patch the target file.
# 5. ALWAYS use triple-quoted strings for any multi-line string or code block.
# 6. If a section is not needed, leave it as an empty dictionary {}.
# 7. AVOID COMPLEX F-STRINGS: For multi-line strings that also
#    contain characters like curly braces ({}) used by other languages (e.g.,
#    CSS, QSS, HTML), do not use a single large f-string. The patcher's code
#    parser can fail on this complex case. Instead, use regular string
#    concatenation (+) or the .format() method to insert variables.

# Use to ADD or ENSURE import statements exist.
# Key: The module to import (e.g., "os", "typing").
# Value: A list of specific names (for 'from x import y') or None (for 'import x').
IMPORTS_TO_ADD: Dict[str, Optional[List[str]]] = {
    # "logging": None,              # -> import logging
    # "typing": ["List", "Dict"], # -> from typing import List, Dict
}

# Use to REPLACE the base class(es) of a class definition.
# Key: The fully-qualified class name (e.g., "MyClass" or "OuterClass.InnerClass").
# Value: A string containing the new base class(es), comma-separated.
CLASS_BASE_REPLACEMENTS: Dict[str, str] = {
    # "MyClass": "NewBaseClass1, NewBaseClass2",
}

# ### NEW ### Use to REPLACE an ENTIRE class definition.
# This is the most powerful directive and will override any other
# directives targeting the same class (e.g., METHODS_TO_ADD).
# Key: The fully-qualified class name to replace (e.g., "MyClass" or "OuterClass.InnerClass").
# Value: A string containing the new, complete class definition.
CLASS_REPLACEMENTS: Dict[str, str] = {
    # "OldClass": """
    # class OldClass(NewBase):
    #     # This is the new, complete class implementation.
    #     def __init__(self, config):
    #         self.config = config
    # """,
}

# Use to REPLACE a top-level variable's assigned value.
# Key: The name of the variable.
# Value: A string representing the new value's code.
MODULE_LEVEL_DIRECTIVES: Dict[str, str] = {
    # "stylesheet": """'body { color: #000; }'""",
}

# ### NEW ### Use to ADD new functions, classes, or constants at the module level.
# The code will be inserted after all imports, following PEP 8 conventions.
# This is the ideal way to add helper functions or new dialog classes.
# Key: Not applicable, this is a single string.
# Value: A string containing the raw Python code to add.
TOP_LEVEL_CODE_TO_ADD: str = """
"""

# Use to inject code at the BEGINNING of a function's body.
# Key: The fully-qualified function/method name (e.g., "MyClass.my_method").
# Value: The code string to prepend.
CODE_TO_PREPEND: Dict[str, str] = {
    # "MyClass.method_to_inject_into": """
    # print(f"DEBUG: Entering method with data: {data}")
    # """,
}

# Use to inject code at the END of a function's body (just before it returns).
# Key: The fully-qualified function/method name.
# Value: The code string to append.
CODE_TO_APPEND: Dict[str, str] = {
    # "MyClass.method_to_inject_into": """
    # print("DEBUG: Method finished execution.")
    # """,
}

# Use to REPLACE the ENTIRE body of an existing function or method.
# Key: The fully-qualified function/method name.
# Value: A string containing the complete new function definition.
#
# !! BEST PRACTICE !!
# This is the most robust option for complex methods where code injection
# (prepend/append) is difficult. Use this for methods with:
#   - Early returns or complex conditional logic.
#   - Deferred calls (e.g., `self.after()` in Tkinter) that hide execution flow.
#
# ### MODIFIED ###
# !! CAUTION !!
# When you replace a function, you are replacing EVERYTHING, including its
# original docstring and comments. It is CRITICAL that you:
#   a) Copy the original docstring into your new function definition.
#   b) Preserve any important developer comments (especially `!!` notes).
REPLACEMENT_DIRECTIVES: Dict[str, str] = {
    "TextureToolApp._on_process_finished": """
    def _on_process_finished(self, task_name, return_code, output):
        if task_name == "decompile_info":
            if return_code != 0:
                self._log_message(f"[ERROR] Get Info task failed with code: {return_code}.")
                if output: self._log_message(f"[ERROR] {output}")
                self.log_message_buffer.clear()
                self._reset_ui_after_task() # Reset immediately on failure
                return

            # THE FIX: Log the completion message IMMEDIATELY to give the user feedback.
            self._log_message("[INFO] ----- Get Info Complete (Data Parsed) -----")

            if self.preview_images:
                self.current_preview_index = 0
            self._update_previewer_ui()
            self._populate_dimensions_filter()

            # The background process is done. Clean up its handles and unlock the UI.
            self.info_thread, self.info_worker = None, None
            # self.decompile_for_info_thread, self.decompile_for_info_worker = None, None # This is now handled at the start of Phase 2
            self._set_ui_task_active(False)
            self._update_button_states()

            self.status_label.setText("Info retrieval complete. Rendering log to window...")
            # Trigger the batch processor for the thousands of DATA lines.
            # It will handle the final UI reset when it's done.
            QTimer.singleShot(0, self._process_log_message_buffer)
            return

        self.progress_bar.setValue(100)
        if return_code == 0:
            final_message = f"{task_name.capitalize()} process complete"
            self.status_label.setText(final_message)
            self._log_message(f"[INFO] ----- {task_name.capitalize()} Complete -----")
            if task_name == "decompile" and self.open_decompile_on_complete:
                self._delayed_open_folder(self.decompile_output_folder)
            elif task_name == "compile" and self.open_compile_on_complete:
                self._delayed_open_folder(os.path.dirname(self.compile_output_file))
            self._show_tray_message(APP_TITLE, f"{task_name.capitalize()} complete!")
        else:
            self._log_message(f"[ERROR] {output}")
            self.status_label.setText(f"Error during {task_name} (Code: {return_code})")
            self._show_tray_message(APP_TITLE, f"Error during {task_name}", QSystemTrayIcon.MessageIcon.Warning)        
        self._reset_ui_after_task()
""",
    "TextureToolApp._start_get_info_phase2": """
    def _start_get_info_phase2(self, return_code, output):
        '''The second phase of Get Info: scanning the file for texture names.'''
        if return_code != 0:
            self._on_get_info_extract_failed(f"TextureExtractor exited with code {return_code}.\\n{output}")
            return

        # --- BUG FIX: Clear Phase 1 handles immediately upon its success ---
        # The Phase 1 worker is done, so we release its lock on the UI state.
        self.decompile_for_info_thread = None
        self.decompile_for_info_worker = None
        # --- END BUG FIX ---

        if not self.info_cache_dir or not self.workspace_dir:
            self._on_get_info_extract_failed("Cache or workspace directory does not exist. Cannot proceed.")
            return

        assert self.workspace_dir is not None # Hint for Pylance

        self._log_message("[INFO] Image cache created successfully.")
        self.status_label.setText("Step 2/2: Reading texture information...")
        self.progress_bar.setRange(0, 100)

        process_cwd = os.path.join(self.workspace_dir, "utils", "TexturePacker_Compile")
        exe_path = os.path.join(process_cwd, "TextureCompiler.exe")
        command = [exe_path, "-info", os.path.normpath(self.decompile_input_file)]

        self.info_thread = QThread(self)
        self.info_worker = Worker(command, process_cwd, show_window=False)
        self.info_worker.moveToThread(self.info_thread)

        # Clear buffers before starting
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
""",
}

# Use to ADD one or more brand new methods to a class.
# Key: The fully-qualified name of the target class (e.g., "MyClass" or "OuterClass.InnerClass").
# Value: A string containing the full definition of one or more new methods.
METHODS_TO_ADD: Dict[str, str] = {
    # "MyClass": """
    # def newly_added_method(self):
    #     return "I am new!"
    #
    # def another_new_method(self, value):
    #     self.some_attribute = value
    # """,
}

# Use to DELETE one or more methods from a class by name.
# Key: The fully-qualified name of the target class (e.g., "MyClass" or "OuterClass.InnerClass").
# Value: A list of method name strings to remove.
METHODS_TO_DELETE: Dict[str, List[str]] = {
    # "MyClass": ["obsolete_method"],
}


# ==============================================================================
# ====== AUTO-VERSIONING AND SAFETY (DO NOT MODIFY) ============================
# ==============================================================================
# --- Internal Constants ---
PATCH_ID_PREFIX = "# PATCHED_BY_SCRIPT_VERSION:"

def determine_next_version(target_file: str, version_override: str) -> str:
    """
    Determines the next version number by reading the target file.
    If version_override is not "AUTO", it is returned directly.
    Otherwise, it reads the first line of target_file, finds a version
    string like "v3.0.19", increments the patch number, and returns "v3.0.20".
    """
    if version_override.upper() != "AUTO":
        print(f"{Fore.CYAN}INFO: Using manual version override: {version_override}")
        return version_override

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            first_line = f.readline()

        # Regex to find a version string like v<major>.<minor>.<patch>
        match = re.search(r"v(\d+)\.(\d+)\.(\d+)", first_line)

        if not match:
            print(f"{Fore.YELLOW}WARNING: Could not find version string in the first line of {target_file}. Defaulting to 'v0.0.1'.")
            return "v0.0.1"

        major, minor, patch = map(int, match.groups())
        new_patch = patch + 1
        new_version = f"v{major}.{minor}.{new_patch}"
        print(f"{Fore.CYAN}INFO: Auto-incremented version from {match.group(0)} to {new_version}")
        return new_version

    except FileNotFoundError:
        print(f"{Fore.YELLOW}WARNING: Target file {target_file} not found for auto-versioning. Defaulting to 'v0.0.1'.")
        return "v0.0.1"
    except Exception as e:
        print(f"{Fore.RED}ERROR: An unexpected error occurred during auto-versioning: {e}. Defaulting to 'v0.0.1'.")
        return "v0.0.1"

# --- Determine the final version for this patch run ---
final_patch_version = determine_next_version(TARGET_FILE, BACKUP_VERSION)

BACKUP_FILE = f"{TARGET_FILE}.bak.{final_patch_version}"
CURRENT_PATCH_MARKER = f"{PATCH_ID_PREFIX} {final_patch_version} | {PATCH_DESCRIPTION}"


def _check_dict(
    name: str,
    d: Mapping[Any, Any],
    key_type: Tuple[type, ...],
    val_type: Optional[Tuple[type, ...]] = None
):
    """Helper to validate the structure of a directive dictionary."""
    if not isinstance(d, dict):
        raise TypeError(f"Directive '{name}' must be a dict, but got {type(d).__name__}.")
    for k, v in d.items():
        if not isinstance(k, key_type):
            raise TypeError(f"Directive '{name}' key {k!r} must be of type {key_type}, but got {type(k).__name__}.")
        if val_type and v is not None and not isinstance(v, val_type):
            raise TypeError(f"Directive '{name}' value for key {k!r} must be of type {val_type}, but got {type(v).__name__}.")

def validate_directives() -> None:
    """Ensures all AI-populated directives match the expected schema before execution."""
    print(f"{Fore.CYAN}INFO: Validating directive schemas...")
    _check_dict("IMPORTS_TO_ADD", IMPORTS_TO_ADD, (str,), (list, type(None)))
    _check_dict("CLASS_BASE_REPLACEMENTS", CLASS_BASE_REPLACEMENTS, (str,), (str,))
    _check_dict("CLASS_REPLACEMENTS", CLASS_REPLACEMENTS, (str,), (str,)) # ### NEW ###
    _check_dict("MODULE_LEVEL_DIRECTIVES", MODULE_LEVEL_DIRECTIVES, (str,), (str,))
    if not isinstance(TOP_LEVEL_CODE_TO_ADD, str):
        raise TypeError(f"Directive 'TOP_LEVEL_CODE_TO_ADD' must be a str, but got {type(TOP_LEVEL_CODE_TO_ADD).__name__}.")
    _check_dict("CODE_TO_PREPEND", CODE_TO_PREPEND, (str,), (str,))
    _check_dict("CODE_TO_APPEND", CODE_TO_APPEND, (str,), (str,))
    _check_dict("REPLACEMENT_DIRECTIVES", REPLACEMENT_DIRECTIVES, (str,), (str,))
    _check_dict("METHODS_TO_ADD", METHODS_TO_ADD, (str,), (str,))
    _check_dict("METHODS_TO_DELETE", METHODS_TO_DELETE, (str,), (list,))
    print(f"{Fore.GREEN}SUCCESS: Directives are valid.")

def safe_parse_module(code: str, context: str) -> cst.Module:
    """Parses module-level code safely, providing context on failure."""
    try:
        return cst.parse_module(textwrap.dedent(code).strip())
    except Exception as e:
        print(f"{Fore.RED}FATAL: Failed to parse code for '{context}'. Aborting. Error: {e}")
        raise

def safe_parse_expression(expr: str, context: str) -> cst.BaseExpression:
    """Parses an expression safely, providing context on failure."""
    try:
        return cst.parse_expression(textwrap.dedent(expr).strip())
    except Exception as e:
        print(f"{Fore.RED}FATAL: Failed to parse expression for '{context}'. Aborting. Error: {e}")
        raise