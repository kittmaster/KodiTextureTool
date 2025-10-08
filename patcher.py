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

import difflib
import os
import re
import shutil
import textwrap

import libcst as cst
from colorama import Fore, Style, init

init(autoreset=True)
# ==============================================================================
# ====== LibCST SURGICAL ENGINE (DO NOT MODIFY) ================================
# ==============================================================================

# HELPER FUNCTION TO CORRECTLY PARSE DOTTED MODULE PATHS
def _parse_module_path(path: str) -> cst.Attribute | cst.Name:
    """
    Parses a simple or dotted module path string into a valid CST Name or
    Attribute node, raising an error if the path is invalid.
    """
    node = cst.parse_expression(path)
    if not isinstance(node, (cst.Name, cst.Attribute)):
        raise TypeError(f"Path '{path}' is not a valid module path for an import.")
    return node


class SurgicalTransformer(cst.CSTTransformer):
    def __init__(self):
        super().__init__()
        self.change_made = False
        self.class_scope_stack: list[str] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self.class_scope_stack.append(node.name.value)
        return True

    # MODIFIED leave_Module TO FIX THE DOTTED IMPORT BUG AND CORRECTLY SCAN EXISTING IMPORTS
    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        """Handles the addition of new import statements at the module level."""
        # ### MODIFIED ###: Also check for TOP_LEVEL_CODE_TO_ADD
        if not IMPORTS_TO_ADD and not TOP_LEVEL_CODE_TO_ADD.strip():
            return updated_node

        existing_imports = set()
        # FIX: Iterate through SimpleStatementLine to find the actual import nodes
        for statement_line in original_node.body:
            if isinstance(statement_line, cst.SimpleStatementLine):
                for node in statement_line.body:
                    if isinstance(node, cst.Import):
                        for name in node.names:
                            existing_imports.add(f"import {original_node.code_for_node(name.name)}")
                    elif isinstance(node, cst.ImportFrom):
                        module_name = original_node.code_for_node(node.module) if node.module else ''
                        if isinstance(node.names, cst.ImportStar):
                             existing_imports.add(f"from {module_name} import *")
                        else:
                            for name in node.names:
                                existing_imports.add(f"from {module_name} import {name.name.value}")

        imports_to_add: list[cst.BaseSmallStatement] = []
        for module, names in IMPORTS_TO_ADD.items():
            if names is None:  # Standard import: `import module`
                if f"import {module}" not in existing_imports:
                    self.change_made = True
                    print(f"{Fore.CYAN}INFO: Adding import: 'import {module}'")
                    # FIX: Use the helper to correctly handle dotted paths
                    imports_to_add.append(cst.Import(names=[cst.ImportAlias(name=_parse_module_path(module))]))
            else:  # From import: `from module import name1, name2`
                new_names_to_import = [
                    cst.ImportAlias(name=cst.Name(name))
                    for name in names if f"from {module} import {name}" not in existing_imports
                ]
                if new_names_to_import:
                    self.change_made = True
                    print(f"{Fore.CYAN}INFO: Adding import: 'from {module} import {', '.join([n.name.value for n in new_names_to_import])}'")
                    # FIX: Use the helper to correctly handle dotted paths
                    imports_to_add.append(cst.ImportFrom(module=_parse_module_path(module), names=new_names_to_import))

        # --- Start of new/modified section ---

        # Find the insertion point after the docstring and any existing imports.
        first_statement_idx = 0
        if updated_node.body:
            # Skip over a docstring if it exists
            if isinstance(updated_node.body[0], cst.SimpleStatementLine) and isinstance(updated_node.body[0].body[0], cst.Expr) and isinstance(updated_node.body[0].body[0].value, cst.SimpleString):
                first_statement_idx = 1

            # Scan forward to find the last import statement
            last_import_idx = -1
            for i in range(first_statement_idx, len(updated_node.body)):
                stmt = updated_node.body[i]
                is_import = False
                if isinstance(stmt, cst.SimpleStatementLine):
                    for node in stmt.body:
                        if isinstance(node, (cst.Import, cst.ImportFrom)):
                            is_import = True
                            break
                if is_import:
                    last_import_idx = i
            if last_import_idx != -1:
                first_statement_idx = last_import_idx + 1

        all_new_statements = [cst.SimpleStatementLine(body=[imp]) for imp in imports_to_add]

        # ### NEW ###: Handle adding top-level code blocks.
        if TOP_LEVEL_CODE_TO_ADD.strip():
            self.change_made = True
            print(f"{Fore.CYAN}INFO: Adding new top-level code definitions.")
            top_level_ast = safe_parse_module(TOP_LEVEL_CODE_TO_ADD, "top-level code")
            if all_new_statements: # If we also added imports, add spacing.
                all_new_statements.extend([cst.EmptyLine(), cst.EmptyLine()])
            all_new_statements.extend(top_level_ast.body)

        new_body = list(updated_node.body)
        new_body[first_statement_idx:first_statement_idx] = all_new_statements
        return updated_node.with_changes(body=new_body)

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.BaseStatement:
        # MODIFIED: Use the full scope to create a fully-qualified name for matching.
        fully_qualified_name = ".".join(self.class_scope_stack)

        # ### NEW ###: Handle full class replacement, which takes precedence.
        # MODIFIED: Check against the fully_qualified_name.
        if fully_qualified_name in CLASS_REPLACEMENTS:
            self.change_made = True
            print(f"{Fore.CYAN}INFO: Replacing class '{fully_qualified_name}' entirely.")

            # Warn if other directives for this class will be ignored.
            conflicting_directives = [
                d for d in (CLASS_BASE_REPLACEMENTS, METHODS_TO_DELETE, METHODS_TO_ADD)
                if fully_qualified_name in d
            ]
            if conflicting_directives:
                print(f"{Fore.YELLOW}WARNING: Other directives for '{fully_qualified_name}' are ignored due to full class replacement.")

            new_class_ast = safe_parse_module(CLASS_REPLACEMENTS[fully_qualified_name], f"replacement for class '{fully_qualified_name}'")
            if len(new_class_ast.body) != 1 or not isinstance(new_class_ast.body[0], cst.ClassDef):
                 print(f"{Fore.RED}ERROR: Replacement code for '{fully_qualified_name}' must contain exactly one class definition. Aborting modification.")
                 self.class_scope_stack.pop() # Pop scope before returning original node
                 return updated_node

            self.class_scope_stack.pop() # Pop scope before returning new node
            return new_class_ast.body[0]

        # If not replacing the whole class, apply other transformations.
        final_node = updated_node

        if fully_qualified_name in CLASS_BASE_REPLACEMENTS:
            self.change_made = True
            new_bases_str = CLASS_BASE_REPLACEMENTS[fully_qualified_name]
            print(f"{Fore.CYAN}INFO: Changing base classes of '{fully_qualified_name}' to '{new_bases_str}'.")
            base_names = [s.strip() for s in new_bases_str.split(',')]
            new_bases = [cst.Arg(value=safe_parse_expression(name, f"base class '{name}' for '{fully_qualified_name}'")) for name in base_names]
            final_node = final_node.with_changes(bases=new_bases)

        if fully_qualified_name in METHODS_TO_DELETE:
            self.change_made = True
            methods_to_delete = set(METHODS_TO_DELETE[fully_qualified_name])
            print(f"{Fore.CYAN}INFO: Deleting methods from '{fully_qualified_name}': {methods_to_delete}")
            new_body_statements = [
                stmt for stmt in final_node.body.body
                if not (isinstance(stmt, cst.FunctionDef) and stmt.name.value in methods_to_delete)
            ]
            final_node = final_node.with_changes(body=final_node.body.with_changes(body=new_body_statements))

        if fully_qualified_name in METHODS_TO_ADD:
            self.change_made = True
            print(f"{Fore.CYAN}INFO: Adding new methods to '{fully_qualified_name}'")
            new_methods_ast = safe_parse_module(METHODS_TO_ADD[fully_qualified_name], f"new methods for '{fully_qualified_name}'")
            new_body_statements = list(final_node.body.body) + list(new_methods_ast.body)
            final_node = final_node.with_changes(body=final_node.body.with_changes(body=new_body_statements))

        # IMPORTANT: Pop the scope stack AFTER all transformations for this class are done.
        self.class_scope_stack.pop()

        return final_node

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.BaseStatement | cst.RemovalSentinel:
        fully_qualified_name = ".".join(self.class_scope_stack + [original_node.name.value])

        if fully_qualified_name in REPLACEMENT_DIRECTIVES:
            self.change_made = True
            print(f"{Fore.CYAN}INFO: Replacing method '{fully_qualified_name}'.")
            if fully_qualified_name in CODE_TO_PREPEND or fully_qualified_name in CODE_TO_APPEND:
                print(f"{Fore.YELLOW}WARNING: Injection directives for '{fully_qualified_name}' ignored due to full replacement.")

            new_method_ast = safe_parse_module(REPLACEMENT_DIRECTIVES[fully_qualified_name], f"replacement for '{fully_qualified_name}'")
            return new_method_ast.body[0]

        final_node = updated_node

        if fully_qualified_name in CODE_TO_PREPEND:
            self.change_made = True
            print(f"{Fore.CYAN}INFO: Prepending code to '{fully_qualified_name}'.")
            prepended_ast = safe_parse_module(CODE_TO_PREPEND[fully_qualified_name], f"prepend code for '{fully_qualified_name}'")
            new_body_statements = list(prepended_ast.body) + list(final_node.body.body)
            final_node = final_node.with_changes(body=final_node.body.with_changes(body=new_body_statements))

        if fully_qualified_name in CODE_TO_APPEND:
            self.change_made = True
            print(f"{Fore.CYAN}INFO: Appending code to '{fully_qualified_name}'.")
            appended_ast = safe_parse_module(CODE_TO_APPEND[fully_qualified_name], f"append code for '{fully_qualified_name}'")

            insertion_point = len(final_node.body.body)
            for i, stmt in reversed(list(enumerate(final_node.body.body))):
                if isinstance(stmt, cst.Return):
                    insertion_point = i
                    break

            new_body_statements = list(final_node.body.body)
            new_body_statements[insertion_point:insertion_point] = appended_ast.body
            final_node = final_node.with_changes(body=final_node.body.with_changes(body=new_body_statements))

        return final_node

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        if not self.class_scope_stack and len(original_node.targets) == 1:
            target = original_node.targets[0].target
            if isinstance(target, cst.Name):
                variable_name = target.value
                if variable_name in MODULE_LEVEL_DIRECTIVES:
                    self.change_made = True
                    print(f"{Fore.CYAN}INFO: Replacing module-level variable '{variable_name}'.")
                    new_value_node = safe_parse_expression(MODULE_LEVEL_DIRECTIVES[variable_name], f"new value for '{variable_name}'")
                    return updated_node.with_changes(value=new_value_node)
        return updated_node

# ==============================================================================
# ====== MAIN EXECUTION LOGIC (DO NOT MODIFY) ==================================
# ==============================================================================
def is_newer_version(new_version: str, old_version: str) -> bool:
    """Compares two semantic version strings (e.g., 'v1.2.3')."""
    def normalize(v):
        try: return [int(p) for p in v.lstrip('v').split('.')]
        except (ValueError, AttributeError): return [0]
    return normalize(new_version) > normalize(old_version)

def create_backup(file_path: str, backup_path: str) -> bool:
    """Creates a backup of the target file if one for this version doesn't exist."""
    if os.path.exists(backup_path):
        print(f"{Fore.YELLOW}INFO: Backup '{backup_path}' for this version already exists.")
        return True
    try:
        shutil.copy2(file_path, backup_path)
        print(f"{Fore.GREEN}SUCCESS: Backup created at '{backup_path}'")
        return True
    except Exception as e:
        print(f"{Fore.RED}ERROR: Could not create backup: {e}")
        return False

def print_side_by_side_diff(original_code: str, new_code: str) -> None:
    """Generates and prints a two-column, side-by-side diff in the terminal."""
    try:
        terminal_width = os.get_terminal_size().columns
    except OSError:
        terminal_width = 120 # Default if terminal size can't be determined

    print(Style.BRIGHT + Fore.WHITE + "--- INTERACTIVE DIFF (Original vs. Patched) ---")
    print("Green = Added, Red = Removed, Yellow = Changed")
    print("-" * terminal_width)

    def get_visible_length(s: str) -> int:
        return len(re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', s))

    diff = list(difflib.ndiff(original_code.splitlines(), new_code.splitlines()))
    col_width = (terminal_width - 5) // 2

    lines = []
    i = 0
    while i < len(diff):
        line = diff[i]
        prefix = line[:2]
        content = line[2:]

        if prefix == '  ': # Unchanged
            lines.append((content, content))
            i += 1
        elif prefix == '- ':
            # Check if this is a change or a pure deletion
            if i + 1 < len(diff) and diff[i+1][:2] == '+ ':
                lines.append((Fore.YELLOW + content, Fore.YELLOW + diff[i+1][2:]))
                i += 2
            else:
                lines.append((Fore.RED + content, ''))
                i += 1
        elif prefix == '+ ': # Pure addition
            lines.append(('', Fore.GREEN + content))
            i += 1
        else: # Context lines from ndiff
            i += 1

    for left, right in lines:
        reset_left = Style.RESET_ALL + left
        reset_right = Style.RESET_ALL + right

        # Truncate long lines to fit the column view
        if get_visible_length(left) > col_width:
             reset_left = left[:col_width - 3] + Style.RESET_ALL + "..."
        if get_visible_length(right) > col_width:
             reset_right = right[:col_width - 3] + Style.RESET_ALL + "..."

        padding = " " * (col_width - get_visible_length(left))
        print(f"{reset_left}{padding} {Style.BRIGHT}|{Style.RESET_ALL} {reset_right}")

    print("-" * terminal_width)

def main(p_final_patch_version: str, p_backup_file: str, p_current_patch_marker: str) -> None:
    """Main orchestration logic for the patching process."""
    print(f"--- Running Patcher ({p_final_patch_version}) for {TARGET_FILE} ---")

    try:
        validate_directives()
    except TypeError as e:
        print(f"{Fore.RED}FAILED: Directive validation failed: {e}")
        return

    if not os.path.exists(TARGET_FILE):
        print(f"{Fore.RED}ERROR: Target file '{TARGET_FILE}' not found. Aborting.")
        return

    try:
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            source_code = f.read()
    except Exception as e:
        print(f"{Fore.RED}ERROR: Could not read target file '{TARGET_FILE}'. Error: {e}")
        return

    # Check for existing patch marker and decide whether to upgrade
    clean_source_code = source_code
    lines = source_code.splitlines()
    if lines and lines[0].startswith(PATCH_ID_PREFIX):
        content_after_prefix = lines[0].replace(PATCH_ID_PREFIX, "").strip()
        existing_version = content_after_prefix.split('|')[0].strip()

        if not is_newer_version(p_final_patch_version, existing_version):
            print(f"{Fore.YELLOW}SKIPPED: Target file is already at version {existing_version} (or newer). No action needed.")
            return
        else:
            print(f"{Fore.CYAN}INFO: Upgrading from {existing_version} to {p_final_patch_version}. Stripping old patch marker.")
            clean_source_code = '\n'.join(lines[1:])

    # Run the CST transformation
    try:
        original_tree = cst.parse_module(clean_source_code)
        transformer = SurgicalTransformer()
        modified_tree = original_tree.visit(transformer)
    except Exception as e:
        print(f"{Fore.RED}FAILED: Patching aborted during CST transformation: {e}")
        # Add detailed exception information for debugging
        import traceback
        traceback.print_exc()
        return

    if not transformer.change_made:
        print(f"{Fore.YELLOW}SKIPPED: No patch directives matched in '{TARGET_FILE}'. No changes made.")
        return

    final_code = f"{p_current_patch_marker}\n{modified_tree.code}"

    # Handle interactive mode approval
    if INTERACTIVE_MODE:
        print_side_by_side_diff(source_code, final_code)
        try:
            choice = input(Style.BRIGHT + Fore.WHITE + "Apply these changes? (y/n): ").lower().strip()
        except KeyboardInterrupt:
            print("\nAborted by user.")
            return

        if choice != 'y':
            print(f"{Fore.YELLOW}SKIPPED: Patch application cancelled by user.")
            return

        print(f"{Fore.CYAN}User approved. Applying changes...")

    # Create backup and write the new file
    if not create_backup(TARGET_FILE, p_backup_file):
        print(f"{Fore.RED}FAILED: Backup creation failed. Aborting patch.")
        return

    try:
        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            f.write(final_code)
        print(f"{Fore.GREEN}SUCCESS: Changes applied and new patch marker added to '{TARGET_FILE}'.")
    except Exception as e:
        print(f"{Fore.RED}ERROR: Failed to write changes to target file: {e}.")
        print(f"{Fore.YELLOW}WARNING: The original file is preserved in the backup: '{p_backup_file}'")


if __name__ == "__main__":
    main(final_patch_version, BACKUP_FILE, CURRENT_PATCH_MARKER)