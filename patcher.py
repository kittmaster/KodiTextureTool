import os
import shutil
import libcst as cst
from colorama import init, Fore, Style
import textwrap

init(autoreset=True)

# --- SCRIPT CONFIGURATION ---
TARGET_FILE = "Kodi TextureTool.py"
BACKUP_VERSION = "v3.3.97" # The new version you are applying
PATCH_DESCRIPTION = "Fix jagged icon scaling in UpdateDialog by matching QLabel size to the smooth-scaled QPixmap." # (NEW) A summary of the patch's changes.
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
    "TextureToolApp.UpdateDialog.__init__": '''
    def __init__(self, version, changelog_html, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QScrollArea, QSizePolicy

        self.setWindowTitle("Update Available")
        self.setWindowIcon(parent.app_icon if parent else QIcon())
        self.setMinimumWidth(550)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # --- Top Section (Icon + Title) ---
        top_container_widget = QWidget()
        top_container_widget.setMinimumHeight(85) # Ensure container is tall enough

        container_v_layout = QVBoxLayout(top_container_widget)
        container_v_layout.setContentsMargins(0, 0, 0, 0)
        
        content_h_layout = QHBoxLayout()
        
        icon_label = QLabel()
        # 1. Scale the pixmap with high quality
        icon_pixmap = QPixmap(get_resource_path("assets/kodi_logo_96.png")).scaled(
            64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        icon_label.setPixmap(icon_pixmap)
        # 2. Force the label to the exact same size as the pixmap to prevent jagged re-scaling
        icon_label.setFixedSize(64, 64)

        title_label = QLabel("A new version is available!")
        title_label.setStyleSheet("font-size: 14pt;")
        
        content_h_layout.addWidget(icon_label)
        content_h_layout.addSpacing(15)
        content_h_layout.addWidget(title_label)
        content_h_layout.addStretch()

        # 3. Use stretches to vertically center the content_h_layout within the container
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
    ''',
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