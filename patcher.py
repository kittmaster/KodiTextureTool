import os
import shutil
import libcst as cst
from colorama import init, Fore, Style
import textwrap

init(autoreset=True)

# --- SCRIPT CONFIGURATION ---
TARGET_FILE = "Kodi TextureTool.py"
BACKUP_VERSION = "v3.5.6" # The new version you are applying
PATCH_DESCRIPTION = "Ensures short paths are converted to long paths before deletion for accurate logging." # (NEW) A summary of the patch's changes.
BACKUP_FILE = f"{TARGET_FILE}.bak.{BACKUP_VERSION}"

# The generic prefix is used for checking if a patch from ANY version exists.
PATCH_ID_PREFIX = "# PATCHED_BY_SCRIPT_VERSION:"
# The current, version-specific marker is used for writing the new patch version and description.
CURRENT_PATCH_MARKER = f"{PATCH_ID_PREFIX} {BACKUP_VERSION} | {PATCH_DESCRIPTION}" # (MODIFIED) Now includes the description.


# --- SURGICAL PATCH DIRECTIVES (AI-POPULATED SECTION) ---

# (NEW) Use this to REPLACE a top-level variable assignment.
MODULE_LEVEL_DIRECTIVES = {
}

# Use this to REPLACE the entire body of an existing function.
REPLACEMENT_DIRECTIVES = {
    "TextureToolApp._start_get_info": """
    def _start_get_info(self):
        '''Orchestrates the two-stage Get Info process: silent extract, then info scan.'''
        if any(t is not None for t in (self.decompile_thread, self.compile_thread, self.info_thread, self.installer_thread, self.decompile_for_info_thread)):
            self._log_message("[WARN] Another task is already in progress. Please wait.")
            return

        if not self.workspace_dir:
            self._log_message("[ERROR] Cannot start task, workspace not available.")
            return
        assert self.workspace_dir is not None # Hint for Pylance

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
                        # --- FIX: Convert path to long name BEFORE deleting it ---
                        long_item_path = item_path
                        if sys.platform == "win32":
                            buffer = ctypes.create_unicode_buffer(512)
                            # This API call only works if the path exists.
                            if ctypes.windll.kernel32.GetLongPathNameW(item_path, buffer, 512):
                                long_item_path = buffer.value
                        # --- END FIX ---
                        try:
                            shutil.rmtree(item_path)
                            self._log_message(f"[INFO] Removed orphaned cache directory: {long_item_path}")
                            found_and_cleaned += 1
                        except Exception as e:
                            self._log_message(f"[WARN] Could not remove old cache directory '{long_item_path}': {e}")
            if found_and_cleaned == 0:
                self._log_message("[INFO] No old info caches found to clean up.")
        except Exception as e:
            self._log_message(f"[WARN] An error occurred during temp folder cleanup: {e}")
        # --- End Garbage Collection ---

        # --- PHASE 1: SILENT DECOMPILATION ---
        self._log_message("[INFO] ----- Starting Get Info -----")

        # Reset search state on new info retrieval
        self._reset_search_state()

        if self.info_cache_dir and os.path.exists(self.info_cache_dir):
            shutil.rmtree(self.info_cache_dir, ignore_errors=True)

        self.preview_images.clear()
        self.current_preview_index = -1
        self._update_previewer_ui()

        try:
            # Create the temp directory; path may be short on some systems.
            short_path_cache_dir = tempfile.mkdtemp(prefix="ktt_info_cache_")

            # --- COSMETIC FIX: Convert to long path for logging and internal use ---
            long_path_cache_dir = short_path_cache_dir
            if sys.platform == "win32":
                # Create a buffer to hold the long path.
                buffer = ctypes.create_unicode_buffer(512)
                # Call the Windows API function to get the long path name.
                if ctypes.windll.kernel32.GetLongPathNameW(short_path_cache_dir, buffer, 512):
                    long_path_cache_dir = buffer.value

            self.info_cache_dir = long_path_cache_dir
            # --- END COSMETIC FIX ---

            self._log_message(f"[INFO] Created temporary image cache: {self.info_cache_dir}")
        except Exception as e:
            self._log_message(f"[ERROR] Could not create temporary cache directory: {e}")
            self.info_cache_dir = None
            return

        self._set_ui_task_active(True)
        # --- MODIFICATION: Set progress bar to determinate for Phase 1 ---
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText("Step 1/2: Caching images...")

        decompile_cwd = os.path.join(self.workspace_dir, "utils", "TexturePacker_Decompile")
        decompile_exe = os.path.join(decompile_cwd, "TextureExtractor.exe")
        decompile_command = [decompile_exe, "-o", self.info_cache_dir, "-c", os.path.normpath(self.decompile_input_file)]

        self.decompile_for_info_thread = QThread(self)
        self.decompile_for_info_worker = Worker(decompile_command, decompile_cwd, show_window=False)
        self.decompile_for_info_worker.moveToThread(self.decompile_for_info_thread)

        # --- CRITICAL FIX: Connect the progress signal to its handler ---
        self.decompile_for_info_worker.progress_updated.connect(self._on_get_info_cache_progress)

        self.decompile_for_info_worker.finished.connect(self.decompile_for_info_thread.quit)
        self.decompile_for_info_worker.finished.connect(self.decompile_for_info_worker.deleteLater)
        self.decompile_for_info_thread.finished.connect(self.decompile_for_info_thread.deleteLater)

        self.decompile_for_info_thread.started.connect(self.decompile_for_info_worker.run)
        self.decompile_for_info_worker.finished.connect(self._start_get_info_phase2)
        self.decompile_for_info_worker.error.connect(self._on_get_info_extract_failed)

        self.decompile_for_info_thread.start()
""",
}

# Use this to ADD one or more brand new methods to a class.
METHODS_TO_ADD = {
}

# Use this to DELETE one or more methods from a class by name.
METHODS_TO_DELETE = {
}


# --- LibCST Surgical Engine (UPGRADED - DO NOT MODIFY FURTHER) ---
class SurgicalTransformer(cst.CSTTransformer):
    def __init__(self):
        super().__init__()
        self.change_made = False
        self.class_scope_stack = []

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self.class_scope_stack.append(node.name.value)
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.BaseStatement:
        class_name = original_node.name.value
        self.class_scope_stack.pop()
        final_node = updated_node
        
        methods_to_delete = METHODS_TO_DELETE.get(class_name, [])
        if methods_to_delete:
            self.change_made = True
            print(f"{Fore.CYAN}INFO: Deleting methods from '{class_name}': {methods_to_delete}")
            def is_not_deleted(stmt):
                if isinstance(stmt, cst.FunctionDef):
                    return stmt.name.value not in methods_to_delete
                return True
            new_body_statements = [stmt for stmt in final_node.body.body if is_not_deleted(stmt)]
            final_node = final_node.with_changes(body=final_node.body.with_changes(body=new_body_statements))

        methods_to_add_str = METHODS_TO_ADD.get(class_name)
        if methods_to_add_str:
            self.change_made = True
            print(f"{Fore.CYAN}INFO: Adding new methods to '{class_name}'")
            new_methods_str = textwrap.dedent(methods_to_add_str).strip()
            new_methods_ast = cst.parse_module(new_methods_str)
            new_body_statements = list(final_node.body.body) + list(new_methods_ast.body)
            final_node = final_node.with_changes(body=final_node.body.with_changes(body=new_body_statements))
            
        return final_node

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.BaseStatement | cst.RemovalSentinel:
        fully_qualified_name = ".".join(self.class_scope_stack + [original_node.name.value])
        if fully_qualified_name in REPLACEMENT_DIRECTIVES:
            self.change_made = True
            print(f"{Fore.CYAN}INFO: Replacing method '{fully_qualified_name}'.")
            new_code_str = textwrap.dedent(REPLACEMENT_DIRECTIVES[fully_qualified_name]).strip()
            try:
                new_method_ast = cst.parse_module(new_code_str)
                return new_method_ast.body[0]
            except Exception as e:
                print(f"{Fore.RED}FATAL: Failed to parse replacement code for '{fully_qualified_name}'. Aborting. Error: {e}")
                raise
        return updated_node

    # (NEW) This method handles module-level variable replacements.
    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        if len(original_node.targets) == 1:
            target = original_node.targets[0].target
            if isinstance(target, cst.Name):
                variable_name = target.value
                if variable_name in MODULE_LEVEL_DIRECTIVES:
                    self.change_made = True
                    print(f"{Fore.CYAN}INFO: Replacing module-level variable '{variable_name}'.")
                    new_value_str = textwrap.dedent(MODULE_LEVEL_DIRECTIVES[variable_name]).strip()
                    # We create a new SimpleString node. The quotes (''' or \"\"\") are preserved from the directive.
                    new_value_node = cst.SimpleString(f"{new_value_str}")
                    return updated_node.with_changes(value=new_value_node)
        return updated_node

# --- Main Execution Logic (Unchanged) ---
def is_newer_version(new_version, old_version):
    """Compares two version strings (e.g., 'v1.2.3') and returns True if new_version is greater."""
    def normalize(v):
        try:
            return [int(p) for p in v.lstrip('v').split('.')]
        except (ValueError, AttributeError):
            return [0]
    return normalize(new_version) > normalize(old_version)

def create_backup(file_path, backup_path):
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

def main():
    print(f"--- Running Patcher Script ({BACKUP_VERSION}) for {TARGET_FILE} ---")

    if not os.path.exists(TARGET_FILE):
        print(f"{Fore.RED}ERROR: Target file '{TARGET_FILE}' not found. Aborting.")
        return

    try:
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            source_code = f.read()
    except Exception as e:
        print(f"{Fore.RED}ERROR: Could not read target file '{TARGET_FILE}'. Error: {e}")
        return

    # (MODIFIED) Version checking logic is now more robust.
    first_line = source_code.splitlines()[0] if source_code else ""
    if first_line.startswith(PATCH_ID_PREFIX):
        # Isolate the content after the prefix, e.g., "v1.0.3 | Old description"
        content_after_prefix = first_line.replace(PATCH_ID_PREFIX, "").strip()
        # The version is always the first part, before any " | " separator.
        existing_version = content_after_prefix.split('|')[0].strip()
        
        if not is_newer_version(BACKUP_VERSION, existing_version):
            print(f"{Fore.YELLOW}SKIPPED: Target file is already at version {existing_version} (or newer). No action needed.")
            return
        else:
            print(f"{Fore.CYAN}INFO: Upgrading from {existing_version} to {BACKUP_VERSION}. Stripping old patch marker.")
            # Remove the old header line to be replaced later.
            source_code = '\n'.join(source_code.splitlines()[1:])

    if not create_backup(TARGET_FILE, BACKUP_FILE):
        print(f"{Fore.RED}FAILED: Backup creation failed. Aborting patch.")
        return

    try:
        original_tree = cst.parse_module(source_code)
    except Exception as e:
        print(f"{Fore.RED}ERROR: Failed to parse target file with LibCST: {e}. Aborting.")
        return

    transformer = SurgicalTransformer()
    try:
        modified_tree = original_tree.visit(transformer)
    except Exception as e:
        print(f"{Fore.RED}FAILED: Patching aborted during transformation: {e}")
        return

    if not transformer.change_made:
        print(f"{Fore.YELLOW}SKIPPED: No patch directives matched in '{TARGET_FILE}'. No changes made.")
        if os.path.exists(BACKUP_FILE):
            os.remove(BACKUP_FILE)
            print(f"{Fore.CYAN}INFO: Removed unnecessary backup file '{BACKUP_FILE}'.")
        return

    try:
        final_code = f"{CURRENT_PATCH_MARKER}\n{modified_tree.code}"
        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            f.write(final_code)
        print(f"{Fore.GREEN}SUCCESS: Changes applied and new patch marker added to '{TARGET_FILE}'.")
    except Exception as e:
        print(f"{Fore.RED}ERROR: Failed to write changes to target file: {e}.")
        print(f"{Fore.YELLOW}WARNING: The original file is preserved in the backup: '{BACKUP_FILE}'")


if __name__ == "__main__":
    main()