"""
Prettier Post-Rebuild Plugin

Post-rebuild plugin that formats flows.json after rebuild.
"""

import importlib.util
from pathlib import Path

# Load plugin helpers module
_helpers_path = Path(__file__).parent / "plugin_helpers.py"
_spec = importlib.util.spec_from_file_location("plugin_helpers", _helpers_path)
_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers)
run_prettier = _helpers.run_prettier


class PrettierPostRebuildPlugin:
    """Plugin for formatting flows.json after rebuild"""

    def get_name(self) -> str:
        return "prettier-post-rebuild"

    def get_priority(self):
        return None  # Use filename prefix (500)

    def get_plugin_type(self) -> str:
        return "post-rebuild"

    def process_flows_post_rebuild(self, flows_path: Path, repo_root: Path) -> bool:
        """Format flows.json after rebuild"""
        # Format flows.json
        result = run_prettier(flows_path, repo_root)

        if result:
            print(f"   Formatted {flows_path.name}")

        return result
