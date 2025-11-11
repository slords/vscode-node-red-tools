# Plugin Development Guide

This guide explains how to create custom plugins for vscode-node-red-tools.

## Table of Contents

- [Plugin Basics](#plugin-basics)
- [Plugin Types](#plugin-types)
- [Creating a Plugin](#creating-a-plugin)
- [Plugin Interface](#plugin-interface)
- [Examples](#examples)
- [Testing Plugins](#testing-plugins)
- [Best Practices](#best-practices)

## Plugin Basics

### What Plugins Do

Plugins extend the tool's functionality by:
- Transforming flows JSON before/after explode
- Extracting node-specific data to files
- Formatting source files and flows.json
- Adding custom processing logic

### Plugin Architecture

Plugins are Python classes that implement specific methods based on their type. They're loaded dynamically from the `plugins/` directory.

### Plugin Lifecycle

1. **Discovery** - Tool scans `plugins/` for `*_plugin.py` files
2. **Loading** - Classes implementing plugin interface are instantiated
3. **Priority Sorting** - Plugins ordered by priority (config, method, filename)
4. **Execution** - Plugins run in priority order during their stage

## Plugin Types

### Pre-Explode Plugins

Run **before** exploding flows to source files.

**Purpose:** Modify flows JSON before extraction

**Use Cases:**
- ID normalization
- Flow validation
- Adding metadata
- Cleaning up data

**Example:** `normalize-ids` plugin converts random IDs to functional names

### Explode Plugins

Run **during** explode to extract node-specific data.

**Purpose:** Extract node data to files

**Use Cases:**
- Extract function code
- Extract template content
- Extract documentation
- Handle custom node types

**Example:** `action` plugin extracts `.def.js` and `.execute.js` files

### Post-Explode Plugins

Run **after** exploding to format source files.

**Purpose:** Format and post-process source files

**Use Cases:**
- Code formatting (prettier)
- Linting
- Adding headers/comments
- Generating indexes

**Example:** `prettier-explode` plugin formats all source files

### Pre-Rebuild Plugins

Run **before** rebuilding flows from source files.

**Purpose:** Process source files before assembly

**Use Cases:**
- Pre-formatting source files
- Validation
- Pre-processing
- Adding metadata

**Example:** `prettier-pre-rebuild` plugin formats files before rebuild

### Post-Rebuild Plugins

Run **after** rebuilding to format flows.json.

**Purpose:** Format and post-process flows.json

**Use Cases:**
- JSON formatting
- Flow validation
- Adding metadata
- Cleanup

**Example:** `prettier-post-rebuild` plugin formats final flows.json

## Creating a Plugin

### Quick Start: Use the Plugin Generator

The easiest way to create a new plugin is to use the built-in generator:

```bash
# Generate a new plugin scaffold
python3 vscode-node-red-tools.py new-plugin my_custom explode

# With custom priority
python3 vscode-node-red-tools.py new-plugin my_formatter post-explode --priority 350
```

**Arguments:**
- `name`: Plugin name (lowercase with underscores)
- `type`: Plugin type (`pre-explode`, `explode`, `post-explode`, `pre-rebuild`, `post-rebuild`)
- `--priority`: Optional priority number (defaults based on type)

**What it creates:**
- File with correct naming convention (`300_my_custom_plugin.py`)
- Complete plugin class structure
- All required methods with TODO comments
- Helpful documentation and examples
- Ready to test immediately

**Example output:**
```
✓ Created plugin: plugins/200_my_custom_plugin.py
  Class name: MyCustomPlugin
  Type: explode
  Priority: 200

Next steps:
  1. Edit plugins/200_my_custom_plugin.py
  2. Implement the plugin logic
  3. Test with: python vscode-node-red-tools.py list-plugins
```

### Manual Creation (Alternative)

If you prefer to create plugins manually:

#### Step 1: Create File

Create a file in `plugins/` directory:
```bash
touch plugins/300_my_custom_plugin.py
```

**Naming Convention:**
- Prefix with priority number (e.g., `300_`)
- Suffix with `_plugin.py`
- Use lowercase with underscores

#### Step 2: Import Dependencies

```python
"""
My Custom Plugin

Description of what this plugin does.
"""

from pathlib import Path
from typing import Dict, Any
import json

# Import helper utilities if needed
from .plugin_helpers import read_node_file, write_node_file
```

#### Step 3: Implement Plugin Class

```python
class MyCustomPlugin:
    """My custom plugin description"""

    def get_name(self) -> str:
        """Return plugin name for identification"""
        return "my-custom"

    def get_priority(self):
        """Return priority (or None to use filename prefix)"""
        return None  # Uses 300 from filename

    def get_plugin_type(self) -> str:
        """Return plugin type"""
        return "post-explode"

    # Implement type-specific methods...
```

#### Step 4: Implement Type-Specific Methods

See [Plugin Interface](#plugin-interface) for required methods.

## Plugin Interface

### Common Methods

All plugins must implement:

```python
def get_name(self) -> str:
    """
    Return unique plugin name for identification.

    Used in:
    - Configuration (enabled/disabled lists)
    - Logging
    - Plugin ordering

    Returns:
        str: Plugin name (e.g., "my-plugin")
    """
    return "my-plugin"

def get_priority(self):
    """
    Return execution priority (or None to use filename).

    Lower numbers run first. Common ranges:
    - 100-199: Pre-explode (modifications)
    - 200-299: Explode (extraction)
    - 300-399: Post-explode (formatting)
    - 400-499: Pre-rebuild (processing)
    - 500-599: Post-rebuild (formatting)

    Returns:
        int or None: Priority number, or None to use filename prefix
    """
    return None  # Use filename prefix

def get_plugin_type(self) -> str:
    """
    Return plugin type.

    Valid types:
    - "pre-explode": Run before exploding
    - "explode": Run during explode (per node)
    - "post-explode": Run after exploding
    - "pre-rebuild": Run before rebuilding
    - "post-rebuild": Run after rebuilding

    Returns:
        str: Plugin type
    """
    return "explode"
```

### Pre-Explode Interface

Pre-explode plugins modify flows.json before it's exploded into individual files. Common uses include ID normalization, flow restructuring, and adding metadata.

```python
def pre_explode(self, flows: list, flows_file: Path) -> Dict[str, Any]:
    """
    Modify flows JSON before exploding.

    Called before flows.json is exploded to individual files.
    Common uses: ID normalization, metadata injection, flow validation.

    Args:
        flows: List of flow nodes (mutable - modify in place)
        flows_file: Path to flows.json

    Returns:
        dict: Status with optional keys:
            - "modified": bool, whether flows were modified
            - "message": str, description of changes

    Example:
        def pre_explode(self, flows, flows_file):
            # Normalize random IDs to functional names
            modified_count = 0
            for node in flows:
                if node.get("type") == "function" and len(node.get("id", "")) > 20:
                    old_id = node["id"]
                    node["id"] = self.generate_functional_name(node)
                    modified_count += 1

            return {
                "modified": modified_count > 0,
                "message": f"Normalized {modified_count} node IDs"
            }

    Notes:
        - Modify flows list in place
        - Return modified=True to trigger flows.json save
        - Changes are saved before explode begins
        - Used for normalizing Node-RED's random IDs to stable names
    """
    pass
```

### Explode Interface

Explode plugins process individual nodes during the explode phase. They implement multiple methods for different aspects of node handling.

#### Required Methods

```python
def can_handle_node(self, node: dict) -> bool:
    """
    Check if this plugin can handle the given node.

    Called before processing each node to determine if this plugin should handle it.

    Args:
        node: Node dictionary

    Returns:
        bool: True if plugin should process this node

    Example:
        def can_handle_node(self, node):
            return node.get("type") == "function" and "func" in node
    """
    pass

def explode_node(
    self,
    node: dict,
    node_dir: Path,
    node_id: str,
    claimed_fields: set
) -> Dict[str, Any]:
    """
    Extract node data to files during explode.

    Args:
        node: Node dictionary (mutable)
        node_dir: Directory for this node's files
        node_id: Node ID
        claimed_fields: Set of field names claimed by previous plugins

    Returns:
        dict: Status with optional keys:
            - "claimed_fields": list of field names this plugin handled
            - "files_created": list of file paths created
            - "message": str, description of actions

    Example:
        def explode_node(self, node, node_dir, node_id, claimed_fields):
            if "func" in claimed_fields:
                return {}  # Already handled

            func_code = node.get("func", "")
            func_file = node_dir / f"{node_id}.wrapped.js"
            func_file.write_text(self.wrap_function(func_code))

            return {
                "claimed_fields": ["func"],
                "files_created": [str(func_file)],
                "message": "Extracted function code"
            }
    """
    pass

def rebuild_node(
    self,
    node: dict,
    node_dir: Path,
    node_id: str
) -> Dict[str, Any]:
    """
    Inject data back into node during rebuild.

    Args:
        node: Node dictionary (mutable)
        node_dir: Directory with this node's files
        node_id: Node ID

    Returns:
        dict: Status with optional keys:
            - "message": str, description of actions
            - "files_read": list of file paths read

    Example:
        def rebuild_node(self, node, node_dir, node_id):
            func_file = node_dir / f"{node_id}.wrapped.js"
            if func_file.exists():
                wrapped_code = func_file.read_text()
                node["func"] = self.unwrap_function(wrapped_code)
                return {
                    "files_read": [str(func_file)],
                    "message": "Injected function code"
                }
            return {}
    """
    pass
```

#### Optional Methods (Highly Recommended)

```python
def get_claimed_fields(self, node: dict) -> list:
    """
    Return list of field names this plugin will claim.

    Called before explode_node() to pre-announce which fields will be handled.
    This allows early conflict detection and proper ordering.

    Args:
        node: Node dictionary

    Returns:
        list: Field names that will be claimed

    Example:
        def get_claimed_fields(self, node):
            # Claim func, initialize, and finalize fields
            return ["func", "initialize", "finalize"]

    Notes:
        - Fields listed here should match what explode_node() actually claims
        - Used to prevent multiple plugins from handling the same field
        - Helps with plugin priority ordering
    """
    return []

def can_infer_node_type(self, node_dir: Path, node_id: str) -> Optional[str]:
    """
    Infer node type from files in node directory.

    Called when new files are discovered to determine what type of node to create.
    Critical for auto-creating nodes from manually added files.

    Args:
        node_dir: Directory containing node files
        node_id: Node ID

    Returns:
        str: Node type if can infer, None otherwise

    Example:
        def can_infer_node_type(self, node_dir, node_id):
            # Check for wrapped function file
            if (node_dir / f"{node_id}.wrapped.js").exists():
                return "function"
            return None

    Notes:
        - Return None if plugin can't determine type
        - First plugin to return non-None wins
        - Used by new file detection system
    """
    return None

def is_metadata_file(self, filename: str) -> bool:
    """
    Check if filename is a metadata file generated by this plugin.

    Called during new file detection to distinguish between:
    - Primary node definition files (node_id.json)
    - Metadata files generated by plugins (node_id.action.json)

    Args:
        filename: Filename to check

    Returns:
        bool: True if this is a metadata file, False if primary definition

    Example:
        def is_metadata_file(self, filename):
            # Action plugin generates .action.json files (metadata)
            return filename.endswith(".action.json")

    Notes:
        - Metadata files don't create new nodes
        - Used to prevent duplicate node creation
        - Primary definition is typically node_id.json
    """
    return False
```

### Post-Explode Interface

Post-explode plugins process all files after the explode phase completes. Common uses include formatting, validation, and documentation generation.

```python
def process_directory_post_explode(
    self,
    src_dir: Path,
    flows_path: Path,
    repo_root: Path
) -> bool:
    """
    Process files after exploding.

    Called after all nodes have been exploded to individual files.
    Common uses: formatting (prettier), linting, documentation generation.

    Args:
        src_dir: Source directory with exploded files
        flows_path: Path to flows.json file
        repo_root: Repository root directory (for tool configuration files)

    Returns:
        bool: True if files were modified, False otherwise

    Example:
        def process_directory_post_explode(self, src_dir, flows_path, repo_root):
            # Format all source files
            changed_files = self.format_directory(src_dir, repo_root)

            # Format flows.json too
            if self.format_file(flows_path, repo_root):
                changed_files.append(flows_path)

            return len(changed_files) > 0

    Notes:
        - Return False if formatting shouldn't trigger re-upload (JSON-only changes)
        - Return True if code changes should trigger watch mode re-upload
        - This method runs in the main explode command
        - Also runs in watch mode after downloading from server
    """
    return False
```

### Pre-Rebuild Interface

Pre-rebuild plugins process files before they're rebuilt into flows.json. Common uses include formatting local changes, validation, and pre-processing.

```python
def process_directory_pre_rebuild(
    self,
    src_dir: Path,
    repo_root: Path,
    continued_from_explode: bool = False
) -> None:
    """
    Process files before rebuilding.

    Called before source files are rebuilt into flows.json.
    Common uses: formatting local changes, validation, pre-processing.

    Args:
        src_dir: Source directory with exploded files
        repo_root: Repository root directory (for tool configuration files)
        continued_from_explode: True if this rebuild immediately follows an explode
                                (allows skipping redundant work)

    Returns:
        None (or bool for future compatibility)

    Example:
        def process_directory_pre_rebuild(self, src_dir, repo_root, continued_from_explode=False):
            # Skip formatting if post-explode just ran
            if continued_from_explode:
                return

            # Format all source files before rebuild
            self.format_directory(src_dir, repo_root)

    Notes:
        - continued_from_explode=True means post-explode just ran
        - Use this flag to avoid duplicate formatting
        - This method runs in rebuild and watch mode (file changes)
        - Does NOT run when rebuild follows an explode (use post-explode instead)
    """
    pass
```

### Post-Rebuild Interface

Post-rebuild plugins process flows.json after it's been rebuilt from source files. Common uses include formatting flows.json, adding metadata, and validation.

```python
def process_flows_post_rebuild(
    self,
    flows_path: Path,
    repo_root: Path
) -> bool:
    """
    Process flows.json after rebuilding.

    Called after flows.json has been rebuilt from source files.
    Common uses: formatting flows.json, validation, metadata injection.

    Args:
        flows_path: Path to flows.json file
        repo_root: Repository root directory (for tool configuration files)

    Returns:
        bool: True if flows.json was modified, False otherwise

    Example:
        def process_flows_post_rebuild(self, flows_path, repo_root):
            # Format flows.json for consistent formatting
            return self.format_file(flows_path, repo_root)

    Notes:
        - This runs after rebuild completes
        - Typically used for formatting flows.json
        - Return value indicates whether file was modified
        - Runs in both rebuild command and watch mode (file changes)
    """
    return False
```

## Examples

### Example 1: Simple Pre-Explode Plugin

```python
"""Ensure flows have consistent version metadata"""

from pathlib import Path
from typing import Dict, Any

class VersionPlugin:
    """Add version metadata to flows if missing (stable after first run)"""

    def get_name(self) -> str:
        return "version"

    def get_priority(self):
        return 150  # Run after normalize-ids

    def get_plugin_type(self) -> str:
        return "pre-explode"

    def pre_explode(self, flows: list, flows_file: Path) -> Dict[str, Any]:
        modified = False

        # Add version field to tabs if missing
        for node in flows:
            if node.get("type") == "tab":
                # Only add if not present - becomes stable after first run
                if "_version" not in node:
                    node["_version"] = "1.0.0"
                    modified = True

        if modified:
            return {
                "modified": True,
                "message": "Added version metadata to tabs"
            }
        return {"modified": False}
```

**Note:** This plugin is **stable** - after the first run, it won't modify flows again unless new tabs are added. This is important for watch mode convergence.

### Example 2: Explode Plugin for Custom Node Type

```python
"""Handle custom widget nodes"""

from pathlib import Path
from typing import Dict, Any

class WidgetPlugin:
    """Extract widget configuration to separate files"""

    def get_name(self) -> str:
        return "widget"

    def get_priority(self):
        return 245  # Between template and info plugins

    def get_plugin_type(self) -> str:
        return "explode"

    def can_handle_node(self, node: dict) -> bool:
        return node.get("type", "").startswith("widget-")

    def explode_node(
        self,
        node: dict,
        node_dir: Path,
        node_id: str,
        claimed_fields: set
    ) -> Dict[str, Any]:
        files_created = []
        claimed = []

        # Extract widget configuration
        if "widgetConfig" in node and "widgetConfig" not in claimed_fields:
            config_file = node_dir / f"{node_id}.widget.json"
            config_file.write_text(json.dumps(node["widgetConfig"], indent=2))
            files_created.append(str(config_file))
            claimed.append("widgetConfig")
            del node["widgetConfig"]

        # Extract widget template
        if "widgetTemplate" in node and "widgetTemplate" not in claimed_fields:
            template_file = node_dir / f"{node_id}.widget.html"
            template_file.write_text(node["widgetTemplate"])
            files_created.append(str(template_file))
            claimed.append("widgetTemplate")
            del node["widgetTemplate"]

        return {
            "claimed_fields": claimed,
            "files_created": files_created,
            "message": f"Extracted widget files"
        }

    def rebuild_node(
        self,
        node: dict,
        node_dir: Path,
        node_id: str
    ) -> Dict[str, Any]:
        files_read = []

        # Inject widget configuration
        config_file = node_dir / f"{node_id}.widget.json"
        if config_file.exists():
            node["widgetConfig"] = json.loads(config_file.read_text())
            files_read.append(str(config_file))

        # Inject widget template
        template_file = node_dir / f"{node_id}.widget.html"
        if template_file.exists():
            node["widgetTemplate"] = template_file.read_text()
            files_read.append(str(template_file))

        return {
            "files_read": files_read,
            "message": "Injected widget files"
        }
```

### Example 3: Post-Explode Validation Plugin

```python
"""Validate exploded files"""

from pathlib import Path
from typing import Dict, Any

class ValidationPlugin:
    """Validate exploded files meet requirements"""

    def get_name(self) -> str:
        return "validation"

    def get_priority(self):
        return 350  # Run after prettier

    def get_plugin_type(self) -> str:
        return "post-explode"

    def post_explode(
        self,
        src_dir: Path,
        flows_file: Path
    ) -> Dict[str, Any]:
        issues = []

        # Check all .js files have valid syntax
        for js_file in src_dir.rglob("*.js"):
            if not self.validate_js_syntax(js_file):
                issues.append(f"Invalid syntax: {js_file}")

        # Check all functions have documentation
        for json_file in src_dir.rglob("*.json"):
            node_id = json_file.stem
            md_file = json_file.parent / f"{node_id}.md"
            if not md_file.exists():
                issues.append(f"Missing docs: {json_file}")

        if issues:
            print(f"Validation warnings:\n" + "\n".join(issues))

        return {
            "files_changed": False,
            "message": f"Validated files ({len(issues)} warnings)"
        }

    def validate_js_syntax(self, file_path: Path) -> bool:
        # Use Node.js to check syntax
        import subprocess
        try:
            subprocess.run(
                ["node", "--check", str(file_path)],
                capture_output=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
```

## Testing Plugins

### Manual Testing

```bash
# Test plugin loads
python3 vscode-node-red-tools.py list-plugins

# Test explode with your plugin
python3 vscode-node-red-tools.py explode flows/flows.json

# Test rebuild with your plugin
python3 vscode-node-red-tools.py rebuild flows/flows.json

# Verify round-trip
python3 vscode-node-red-tools.py verify flows/flows.json
```

### Enable Only Your Plugin

```json
{
  "plugins": {
    "enabled": ["my-custom"]
  }
}
```

### Skip Other Plugins

To test your plugin in isolation, disable all plugins then enable only yours:

```bash
# Test your plugin (e.g., "my-custom") in isolation
python3 vscode-node-red-tools.py --disable all --enable my-custom explode flows/flows.json
```

This ensures only your plugin runs, making it easier to debug and verify its behavior.

### Unit Testing

```python
# test_my_plugin.py
import pytest
from plugins.my_custom_plugin import MyCustomPlugin

def test_plugin_name():
    plugin = MyCustomPlugin()
    assert plugin.get_name() == "my-custom"

def test_plugin_handles_node():
    plugin = MyCustomPlugin()
    node = {"type": "function", "func": "return msg;"}
    assert plugin.can_handle_node(node)

def test_plugin_explode():
    plugin = MyCustomPlugin()
    node = {"type": "function", "func": "return msg;"}
    result = plugin.explode_node(node, Path("/tmp"), "test", set())
    assert "claimed_fields" in result
```

## Best Practices

### 1. Check Claimed Fields

Always check if fields are already claimed:

```python
def explode_node(self, node, node_dir, node_id, claimed_fields):
    if "func" in claimed_fields:
        return {}  # Skip, already handled
    # ... process node
```

### 2. Report What You Did

Return detailed status:

```python
return {
    "claimed_fields": ["func", "initialize"],
    "files_created": [str(func_file), str(init_file)],
    "message": "Extracted function with initialization"
}
```

### 3. Handle Missing Data

```python
func_code = node.get("func", "")  # Default to empty string
if not func_code:
    return {}  # Nothing to do
```

### 4. Preserve Data

Don't modify data unless necessary:

```python
# Good: Extract then remove
func_code = node.get("func", "")
write_file(func_file, func_code)
del node["func"]

# Bad: Modify without extracting
node["func"] = modified_func_code  # Lost original!
```

### 5. Use Helpers

```python
from .plugin_helpers import (
    read_node_file,
    write_node_file,
    run_prettier,
    safe_filename
)

# Use helper functions instead of reimplementing
write_node_file(node_dir / f"{node_id}.js", code)
```

### 6. Handle Errors Gracefully

```python
def explode_node(self, node, node_dir, node_id, claimed_fields):
    try:
        # ... processing
        return {"claimed_fields": ["func"]}
    except Exception as e:
        print(f"Warning: Failed to process {node_id}: {e}")
        return {}  # Don't crash the tool
```

### 7. Document Your Plugin

```python
"""
My Custom Plugin

Extracts custom widget configurations to separate files.

Files Created:
- <node_id>.widget.json: Widget configuration
- <node_id>.widget.html: Widget template

Configuration:
{
  "plugins": {
    "enabled": ["widget"]
  }
}
"""
```

### 8. Use Type Hints

```python
from pathlib import Path
from typing import Dict, Any, Set

def explode_node(
    self,
    node: dict,
    node_dir: Path,
    node_id: str,
    claimed_fields: Set[str]
) -> Dict[str, Any]:
    # ... implementation
```

## Plugin Helpers

Common utilities available in `plugin_helpers.py`:

```python
from .plugin_helpers import (
    # File operations
    read_node_file,      # Read file with error handling
    write_node_file,     # Write file with error handling
    safe_filename,       # Sanitize filename

    # Prettier integration
    run_prettier,        # Format file with prettier
    run_prettier_files,  # Format multiple files

    # JSON operations
    load_json,           # Load JSON with error handling
    save_json,           # Save JSON with formatting

    # Common patterns
    extract_field,       # Extract and claim field
    inject_field,        # Inject field if file exists
)
```

## Next Steps

- Review existing plugins in `plugins/` directory
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for design details
- See [CONFIGURATION.md](CONFIGURATION.md) for plugin configuration
- Test your plugin with [USAGE.md](USAGE.md) commands
