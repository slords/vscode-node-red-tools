"""
Prettier Post-Explode Plugin

Post-explode plugin that formats all source files after explode.
Only signals "change" if non-.json files were modified.
"""

import importlib.util
from pathlib import Path

# Load plugin helpers module
_helpers_path = Path(__file__).parent / "plugin_helpers.py"
_spec = importlib.util.spec_from_file_location("plugin_helpers", _helpers_path)
_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers)
run_prettier = _helpers.run_prettier
run_prettier_parallel = _helpers.run_prettier_parallel


class PrettierExplodePlugin:
    """Plugin for formatting source files after explode"""

    def get_name(self) -> str:
        return "prettier-explode"

    def get_priority(self):
        return None  # Use filename prefix (60)

    def get_plugin_type(self) -> str:
        return "post-explode"

    def process_directory_post_explode(
        self, src_dir: Path, flows_path: Path, repo_root: Path
    ) -> bool:
        """Format src directory and flows.json after explode

        Uses parallel formatting with flows.json bundled with root files.
        Returns False because JSON formatting shouldn't trigger re-upload.
        """
        # Format src directory + flows.json in parallel
        # Root files + flows.json in one thread, each subdirectory in its own thread
        result = run_prettier_parallel(
            src_dir, repo_root, additional_files=[flows_path]
        )

        if result:
            print(f"   Formatted src directory and {flows_path.name}")

        # Always return False - JSON formatting doesn't trigger re-upload
        # Only non-JSON code changes should trigger uploads
        return False
