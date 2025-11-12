"""
Plugin loading and management for vscode-node-red-tools

Handles discovery, loading, filtering, and ordering of plugins.
"""

import importlib.util
import re
from pathlib import Path
from typing import Dict, List, Optional

from .logging import log_info, log_warning
from .constants import DEFAULT_PLUGIN_PRIORITY


class Plugin:
    """Base class for plugins

    All plugins must inherit from this class and implement at minimum:
    - get_name(): Return plugin name
    - get_plugin_type(): Return 'pre-explode', 'explode', 'post-explode', 'pre-rebuild', or 'post-rebuild'

    Plugin types:
    - pre-explode: Modifies flow JSON before explode (e.g., normalize-ids)
    - explode: Extracts node data to files (e.g., func, info)
    - post-explode: Formats files after explode (e.g., prettier on source files)
    - pre-rebuild: Processes files before rebuild (e.g., validation)
    - post-rebuild: Formats flows JSON after rebuild (e.g., prettier on flows.json)
    """

    def get_name(self) -> str:
        """Return plugin name"""
        raise NotImplementedError

    def get_priority(self) -> Optional[int]:
        """
        Return plugin priority (lower = runs first).
        None means use filename prefix or default.
        """
        return None

    def get_plugin_type(self) -> str:
        """
        Return plugin type: 'pre-explode', 'explode', 'post-explode', 'pre-rebuild', 'rebuild', 'post-rebuild'.
        - pre-explode: Modifies flow JSON before explode (e.g., normalize-ids)
        - explode: Extracts node data to files (e.g., func, info)
        - post-explode: Formats files after explode (e.g., prettier on source files)
        - pre-rebuild: Processes files before rebuild (e.g., validation)
        - rebuild: Same as explode (backward compat)
        - post-rebuild: Formats flows JSON after rebuild (e.g., prettier on flows.json)
        """
        return "explode"

    # Explode plugin methods
    def can_handle_node(self, node: dict) -> bool:
        """
        Return True if this plugin will actually process this node.
        Only return True if pattern matching succeeds.
        Only used by 'explode' type plugins.
        """
        return False

    def get_claimed_fields(self, node: dict) -> List[str]:
        """
        Return list of node fields this plugin will modify.
        Only called if can_handle_node returns True.
        Only used by 'explode' type plugins.
        """
        return []

    def explode_node(self, node: dict, node_dir: Path, repo_root: Path) -> List[str]:
        """
        Explode node-specific files.
        Only used by 'explode' type plugins.

        Returns:
            List of created filenames (relative to node_dir, not full paths)
            Example: ["node_id.js", "node_id.md"]
        """
        return []

    def rebuild_node(
        self, node_id: str, node_dir: Path, skeleton: dict, repo_root: Path
    ) -> dict:
        """
        Rebuild node-specific data. Returns dict to merge into node.
        Only used by 'explode' type plugins.
        """
        return {}

    # Pre-explode plugin methods
    def process_flows_pre_explode(self, flow_data: list, repo_root: Path) -> list:
        """
        Modify flow data before explode.
        Only used by 'pre-explode' type plugins.
        Returns modified flow_data.
        """
        return flow_data

    # Post-explode plugin methods
    def process_directory_post_explode(
        self, src_dir: Path, flows_path: Path, repo_root: Path
    ) -> bool:
        """
        Process files after explode (e.g., formatting).
        Only used by 'post-explode' type plugins.
        Can modify both src_dir files and flows_path.
        Returns True if changes were made.
        """
        return False

    # Pre-rebuild plugin methods
    def process_directory_pre_rebuild(self, src_dir: Path, repo_root: Path) -> bool:
        """
        Process files before rebuild (e.g., validation).
        Only used by 'pre-rebuild' type plugins.
        Returns True if changes were made.
        """
        return False

    # Post-rebuild plugin methods
    def process_flows_post_rebuild(self, flows_path: Path, repo_root: Path) -> bool:
        """
        Process flows.json after rebuild (e.g., formatting).
        Only used by 'post-rebuild' type plugins.
        Returns True if changes were made.
        """
        return False


def extract_numeric_prefix(filename: str) -> int:
    """Extract numeric prefix from filename (e.g., '10_action_plugin.py' -> 10)

    Args:
        filename: Plugin filename

    Returns:
        Priority number from filename prefix, or DEFAULT_PLUGIN_PRIORITY if no prefix
    """
    match = re.match(r"(\d+)_", filename)
    return int(match.group(1)) if match else DEFAULT_PLUGIN_PRIORITY


def load_plugins(
    repo_root: Path,
    config: Optional[dict] = None,
    enabled_override: Optional[List[str]] = None,
    disabled_override: Optional[List[str]] = None,
    quiet: bool = False,
) -> Dict[str, List[Plugin]]:
    """
    Load and order plugins based on priority resolution.
    Returns dict with keys: 'pre-explode', 'explode', 'post-explode', 'pre-rebuild', 'post-rebuild'

    Priority resolution (lowest number = runs first):
    1. Config file explicit order
    2. Plugin get_priority() method
    3. Filename numeric prefix (e.g., 10_plugin.py)
    4. Default (999)

    Args:
        repo_root: Repository root path (for reference, not used currently)
        config: Configuration dictionary
        enabled_override: Optional list of plugin names to enable, or ["all"] for all plugins
        disabled_override: Optional list of plugin names to disable, or ["all"] to disable all
        quiet: If True, suppress plugin loading messages

    Returns:
        Dictionary mapping plugin type to list of plugin instances:
        {
            'pre-explode': [plugin1, plugin2, ...],
            'explode': [plugin3, plugin4, ...],
            'post-explode': [plugin5, ...],
            'pre-rebuild': [plugin6, ...],
            'post-rebuild': [plugin7, ...],
        }

    Notes:
        - Plugins are loaded from plugins/ directory
        - Only files matching *_plugin.py are considered
        - Each file should contain exactly one class ending with "Plugin"
        - Plugins are filtered by enabled/disabled lists
        - Plugins are sorted by priority (lower runs first)
        - Config order takes precedence over priority
        - Warns about priority conflicts (same type, same priority)
    """
    # Get plugins directory (works in both development and installed modes)
    # For this project, plugins/ is at repo root, not in the package
    plugins_dir = Path(__file__).parent.parent / "plugins"

    if not plugins_dir.exists():
        return {
            "pre-explode": [],
            "explode": [],
            "post-explode": [],
            "pre-rebuild": [],
            "post-rebuild": [],
        }

    # Load all plugin modules
    loaded_plugins = []

    for plugin_file in sorted(plugins_dir.glob("*_plugin.py")):
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find plugin class (looks for class ending with "Plugin")
                for name in dir(module):
                    obj = getattr(module, name)
                    if (
                        isinstance(obj, type)
                        and name.endswith("Plugin")
                        and name not in ["Plugin"]
                    ):
                        # Instantiate plugin
                        plugin_instance = obj()
                        # Attach metadata needed for hot-reload without full rescan
                        try:
                            plugin_instance._source_path = str(plugin_file)  # type: ignore[attr-defined]
                            plugin_instance._class_name = obj.__name__  # type: ignore[attr-defined]
                        except Exception:
                            # Non-fatal – reload will fall back to runtime introspection
                            pass

                        # Validate required methods
                        required_methods = ["get_name", "get_plugin_type"]
                        missing = [
                            m
                            for m in required_methods
                            if not hasattr(plugin_instance, m)
                        ]
                        if missing:
                            log_warning(
                                f"Plugin {plugin_file.stem} missing required methods: {', '.join(missing)}"
                            )
                            continue

                        plugin_name = plugin_instance.get_name()
                        plugin_type = plugin_instance.get_plugin_type()

                        # Determine priority
                        priority = plugin_instance.get_priority()
                        if priority is None:
                            # Use filename prefix
                            priority = extract_numeric_prefix(plugin_file.name)

                        loaded_plugins.append(
                            {
                                "instance": plugin_instance,
                                "name": plugin_name,
                                "type": plugin_type,
                                "priority": priority,
                                "filename": plugin_file.name,
                            }
                        )
                        break  # Only load first Plugin class from each file

        except Exception as e:
            log_warning(f"Failed to load plugin {plugin_file.name}: {e}")

    # Apply enable/disable filters
    # Start with all loaded plugins
    plugin_names = {p["name"] for p in loaded_plugins}
    active_plugins = plugin_names.copy()
    plugins_section = (config or {}).get("plugins", {})

    # If no CLI overrides, use config
    if enabled_override is None and disabled_override is None:
        config_enabled = plugins_section.get("enabled", [])
        config_disabled = plugins_section.get("disabled", [])

        # Apply config filters
        if config_enabled:
            active_plugins = active_plugins & set(config_enabled)
        if config_disabled:
            active_plugins = active_plugins - set(config_disabled)
    else:
        # CLI overrides specified - apply in order: disable all, enable all, disable list, enable list

        # 1. Disable all (if "all" in disabled_override)
        if disabled_override and "all" in disabled_override:
            active_plugins = set()

        # 2. Enable all (if "all" in enabled_override)
        if enabled_override and "all" in enabled_override:
            active_plugins = plugin_names.copy()

        # 3. Disable specific plugins
        if disabled_override:
            specific_disables = set(disabled_override) - {"all"}
            active_plugins = active_plugins - specific_disables

        # 4. Enable specific plugins
        if enabled_override:
            specific_enables = set(enabled_override) - {"all"}
            active_plugins = active_plugins | specific_enables

    # Filter to active plugins only
    filtered_plugins = [p for p in loaded_plugins if p["name"] in active_plugins]

    # Apply ordering
    config_order = plugins_section.get("order", [])
    if config_order:
        # Config order takes precedence
        ordered_plugins = []
        # First, add plugins in config order
        for plugin_name in config_order:
            for p in filtered_plugins:
                if p["name"] == plugin_name:
                    ordered_plugins.append(p)
                    break
        # Then add remaining plugins sorted by priority
        remaining = [p for p in filtered_plugins if p not in ordered_plugins]
        remaining.sort(key=lambda x: x["priority"])
        ordered_plugins.extend(remaining)
    else:
        # Sort by priority (lower first)
        ordered_plugins = sorted(filtered_plugins, key=lambda x: x["priority"])

    # Detect priority conflicts
    priority_map = {}
    for p in ordered_plugins:
        priority = p["priority"]
        plugin_type = p["type"]
        if plugin_type == "rebuild":
            plugin_type = "explode"  # Normalize for conflict detection

        key = (plugin_type, priority)
        if key not in priority_map:
            priority_map[key] = []
        priority_map[key].append(p["name"])

    # Warn about conflicts (same type, same priority)
    for (plugin_type, priority), plugins in priority_map.items():
        if len(plugins) > 1:
            log_warning(
                f"Priority conflict: {len(plugins)} {plugin_type} plugins with priority {priority}: {', '.join(plugins)}"
            )
            log_warning(
                f"  Execution order will be: {', '.join(plugins)} (alphabetical by name)"
            )

    # Categorize by type
    result = {
        "pre-explode": [],
        "explode": [],
        "post-explode": [],
        "pre-rebuild": [],
        "post-rebuild": [],
    }

    for p in ordered_plugins:
        plugin_type = p["type"]
        # Treat 'rebuild' as 'explode' for backward compat
        if plugin_type == "rebuild":
            plugin_type = "explode"
        if plugin_type in result:
            result[plugin_type].append(p["instance"])
            if not quiet:
                log_info(
                    f"Loaded plugin: {p['name']} (type: {plugin_type}, priority: {p['priority']})"
                )
        else:
            if not quiet:
                log_warning(f"Plugin {p['name']} has unknown type: {plugin_type}")

    return result
