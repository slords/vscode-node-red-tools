"""
Prettier Pre-Rebuild Plugin

Pre-rebuild plugin that formats all source files before rebuild.
Ensures that local changes are properly formatted before being rebuilt and uploaded.
"""

import importlib.util
from pathlib import Path

# Load plugin helpers module
_helpers_path = Path(__file__).parent / "plugin_helpers.py"
_spec = importlib.util.spec_from_file_location("plugin_helpers", _helpers_path)
_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers)
run_prettier_parallel = _helpers.run_prettier_parallel


class PrettierPreRebuildPlugin:
    """Plugin for formatting source files before rebuild"""

    def get_name(self) -> str:
        return "prettier-pre-rebuild"

    def get_priority(self):
        return None  # Use filename prefix (400)

    def get_plugin_type(self) -> str:
        return "pre-rebuild"

    def process_directory_pre_rebuild(
        self, src_dir: Path, continued_from_explode: bool = False
    ) -> None:
        """Format src directory before rebuild

        Uses parallel formatting for directories (groups by subdirectory).
        Ensures local changes are formatted before being built and uploaded.

        Args:
            src_dir: Source directory to format
            continued_from_explode: If True, skip formatting (post-explode just ran)
        """
        # Skip if we just ran post-explode prettier
        if continued_from_explode:
            return

        # Format src directory in parallel (groups by subdirectory)
        run_prettier_parallel(src_dir)


# Export plugin
Plugin = PrettierPreRebuildPlugin
