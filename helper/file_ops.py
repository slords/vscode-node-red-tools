"""
File operations for vscode-node-red-tools

Handles discovery, classification, and management of node files including:
- Orphaned file detection and handling
- New file discovery and node creation
- Node type inference from file patterns
"""

import json5 as json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from .logging import log_info, log_success, log_warning, log_error
from .skeleton import get_node_directory
from .utils import validate_safe_path, sanitize_filename


def find_orphaned_files(
    src_dir: Path, flow_data: list, tab_ids: set, skeleton_data: list = None
) -> List[Path]:
    """Find files in src_dir that don't correspond to any node in flow_data

    Uses metadata from skeleton if available for perfect accuracy.
    Falls back to heuristic detection if skeleton is not provided.

    Args:
        src_dir: Source directory
        flow_data: Flow data (list of nodes)
        tab_ids: Set of tab/subflow IDs
        skeleton_data: Optional skeleton data with metadata

    Returns:
        List of orphaned file paths

    Notes:
        - Skips .orphaned/ directory
        - Skips .flow-skeleton.json
        - With skeleton: Uses _explode_meta for perfect detection
        - Without skeleton: Infers from filename and location
    """
    # If skeleton data is provided, use metadata for perfect detection
    if skeleton_data:
        # Ensure src_dir is resolved for consistent path comparison
        src_dir = src_dir.resolve()

        # Build map of expected files from metadata
        expected_files = set()
        node_dirs = {}

        for node in skeleton_data:
            node_id = node.get("id")
            if not node_id:
                continue

            # Get expected directory for this node (returns resolved path)
            node_dir = get_node_directory(node, src_dir, tab_ids)
            node_dirs[node_id] = node_dir

            # Get files from metadata (new format: {plugin: [files], stable: bool})
            meta = node.get("_explode_meta", {})
            for key, value in meta.items():
                if key == "stable":
                    continue  # Skip the stable flag
                # value is the list of files for this plugin
                if isinstance(value, list):
                    for filename in value:
                        # Add resolved path for consistent comparison
                        expected_files.add((node_dir / filename).resolve())

        # Find all actual files
        orphaned = []
        for item in src_dir.rglob("*"):
            if not item.is_file():
                continue

            # Skip .orphaned directory
            if ".orphaned" in item.parts:
                continue

            # Skip skeleton file
            if item.name == ".flow-skeleton.json":
                continue

            # Check if this file is expected (resolve for consistent comparison)
            if item.resolve() not in expected_files:
                orphaned.append(item)

        return orphaned

    # Fallback to heuristic detection (old behavior)
    # Build map of node_id -> expected_directory_path
    node_locations = {}
    for node in flow_data:
        node_id = node.get("id")
        if node_id:
            expected_dir = get_node_directory(node, src_dir, tab_ids)
            node_locations[node_id] = expected_dir

    orphaned = []

    # Check all files in src_dir
    for item in src_dir.rglob("*"):
        if not item.is_file():
            continue

        # Skip .orphaned directory
        if ".orphaned" in item.parts:
            continue

        # Skip skeleton file
        if item.name == ".flow-skeleton.json":
            continue

        # Extract node ID from filename (base name before first dot)
        name_parts = item.name.split(".")
        if len(name_parts) > 0:
            base_name = name_parts[0]
        else:
            continue

        # Check if this node ID exists in flow
        if base_name not in node_locations:
            # Node ID doesn't exist - orphaned
            orphaned.append(item)
        elif item.parent != node_locations[base_name]:
            # Node ID exists but file is in wrong directory - orphaned
            orphaned.append(item)

    return orphaned


def handle_orphaned_files(
    orphaned: List[Path], src_dir: Path, delete: bool = False
) -> None:
    """Handle orphaned files - move to .orphaned/ or delete

    Args:
        orphaned: List of orphaned file paths
        src_dir: Source directory root
        delete: If True, delete files; if False, move to .orphaned/

    Notes:
        - Preserves directory structure in .orphaned/
        - Adds timestamp to destination filename if it already exists
        - Logs all operations for visibility
    """
    if not orphaned:
        return

    log_warning(f"Found {len(orphaned)} orphaned file(s):")
    for f in orphaned:
        log_warning(f"  - {f.relative_to(src_dir)}")

    if delete:
        log_info("Deleting orphaned files...")
        for f in orphaned:
            f.unlink()
        log_success("Orphaned files deleted")
    else:
        # Move to .orphaned/ directory
        orphaned_dir = src_dir / ".orphaned"

        log_info(f"Moving orphaned files to {orphaned_dir.relative_to(src_dir)}/...")
        for f in orphaned:
            # Preserve directory structure
            rel_path = f.relative_to(src_dir)
            dest = orphaned_dir / rel_path

            # Create destination directory
            dest.parent.mkdir(parents=True, exist_ok=True)

            # If destination exists, add timestamp
            if dest.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = dest.parent / f"{dest.stem}.{timestamp}{dest.suffix}"

            f.rename(dest)

        log_success(f"Moved {len(orphaned)} orphaned file(s) to .orphaned/")


def find_new_files(src_dir: Path, skeleton_data: list, plugins: list) -> List[Path]:
    """Find new node definition files that don't have corresponding skeleton entries

    Args:
        src_dir: Source directory root
        skeleton_data: List of skeleton nodes
        plugins: List of explode plugins (for metadata file detection)

    Returns:
        List of new node definition file paths

    Notes:
        - Searches for .json files as they are the canonical node definition format
        - Skips .flow-skeleton.json (internal use only)
        - Skips files in .orphaned/
        - Asks plugins if file is metadata generated by plugins
    """
    # Get all node IDs from skeleton
    skeleton_ids = {node.get("id") for node in skeleton_data if "id" in node}

    new_files = []

    # Find all .json files (excluding skeleton and special files)
    for json_file in src_dir.rglob("*.json"):
        if json_file.name == ".flow-skeleton.json":
            continue

        # Skip files in .orphaned directory
        if ".orphaned" in json_file.parts:
            continue

        # Ask plugins if this is a metadata file (not a primary node definition)
        is_metadata = False
        for plugin in plugins:
            if hasattr(plugin, "is_metadata_file") and plugin.is_metadata_file(
                json_file.name
            ):
                is_metadata = True
                break

        if is_metadata:
            continue

        # Extract node ID from filename
        node_id = json_file.stem

        # Check if this node exists in skeleton
        if node_id not in skeleton_ids:
            new_files.append(json_file)

    return new_files


def detect_node_type(json_file: Path, plugins: list) -> str:
    """Detect node type from associated files using plugins

    Args:
        json_file: Path to node's .json file
        plugins: List of explode plugins (for type inference)

    Returns:
        Detected node type string (defaults to "comment" if unknown)

    Notes:
        - Asks plugins via can_infer_node_type() method
        - Plugins inspect associated files to determine node type
        - Defaults to "comment" if type cannot be determined
    """
    node_dir = json_file.parent
    node_id = json_file.stem

    # Ask plugins if they can infer the node type
    for plugin in plugins:
        if hasattr(plugin, "can_infer_node_type"):
            node_type = plugin.can_infer_node_type(node_dir, node_id)
            if node_type:
                return node_type

    # Default to comment node if plugins can't determine type
    return "comment"


def create_node_from_files(
    json_file: Path,
    next_position: Tuple[int, int],
    src_dir: Path,
    plugins: list,
) -> dict:
    """Create a new node entry from files with smart defaults

    Infers tab/subflow from directory structure.

    Args:
        json_file: Path to node's .json file
        next_position: (x, y) position for new node
        src_dir: Source directory root
        plugins: List of explode plugins (for type inference)

    Returns:
        Node dictionary with smart defaults

    Raises:
        ValueError: If path traversal is detected

    Notes:
        - Loads base data from node definition file
        - Infers z field from directory (tab_*/ or subflow_*/)
        - Adds layout fields (x, y) if missing
        - Creates empty wires array if missing
        - Uses detect_node_type() for type inference via plugins
        - All file paths are validated to prevent path traversal
    """
    # Validate that json_file is within src_dir (security check)
    json_file = validate_safe_path(src_dir, json_file)

    with open(json_file, "r") as f:
        node_data = json.load(f)

    # Sanitize node ID for filesystem safety (especially Windows)
    raw_node_id = node_data.get("id", json_file.stem)
    node_id = sanitize_filename(raw_node_id)
    node_type = detect_node_type(json_file, plugins)

    # Start with data from JSON file
    new_node = node_data.copy()

    # Ensure id is set
    if "id" not in new_node:
        new_node["id"] = node_id

    # Infer z (tab/subflow) from directory structure
    if "z" not in new_node:
        relative_path = json_file.relative_to(src_dir)
        parts = relative_path.parts

        # Check if in a subdirectory (tab or subflow)
        if len(parts) > 1:
            parent_dir = parts[0]

            # Infer z from directory name
            if parent_dir.startswith("tab_") or parent_dir.startswith("subflow_"):
                new_node["z"] = parent_dir

    # Add layout fields if missing
    if "x" not in new_node:
        new_node["x"] = next_position[0]
    if "y" not in new_node:
        new_node["y"] = next_position[1]

    # Add wires if missing (empty, unwired)
    if "wires" not in new_node:
        outputs = new_node.get("outputs", 1)
        new_node["wires"] = [[] for _ in range(outputs)]

    # Ensure type is set
    if "type" not in new_node:
        new_node["type"] = node_type

    return new_node


def handle_new_files(
    new_files: List[Path],
    src_dir: Path,
    plugins: list,
    orphan: bool = False,
    delete: bool = False,
) -> List[dict]:
    """Handle new files - create nodes, orphan, or delete

    Args:
        new_files: List of new .json file paths
        src_dir: Source directory root
        plugins: List of explode plugins (for type inference)
        orphan: If True, move to .orphaned/
        delete: If True, delete files

    Returns:
        List of newly created node dictionaries (empty if orphaned/deleted)

    Notes:
        - delete takes precedence over orphan
        - When deleting, also deletes all associated files for the node
        - When creating nodes, positions them vertically starting at (100, 100)
        - Logs all operations for visibility
    """
    if not new_files:
        return []

    log_warning(f"Found {len(new_files)} new file(s) not in skeleton:")
    for f in new_files:
        log_warning(f"  - {f.relative_to(src_dir)}")

    if delete:
        log_info("Deleting new files...")
        for f in new_files:
            # Delete all associated files for this node
            for ext_file in f.parent.glob(f"{f.stem}.*"):
                ext_file.unlink()
        log_success("New files deleted")
        return []

    elif orphan:
        # Move to .orphaned/
        handle_orphaned_files(new_files, src_dir, delete=False)
        return []

    else:
        # Create nodes from files
        log_info("Creating nodes from new files...")
        new_nodes = []
        next_position = [100, 100]  # Starting position for new nodes

        for json_file in new_files:
            try:
                new_node = create_node_from_files(
                    json_file, tuple(next_position), src_dir, plugins
                )
                new_nodes.append(new_node)

                # Increment position for next node
                next_position[1] += 50  # Stack vertically

                log_success(
                    f"  Created node: {new_node['id']} (type: {new_node.get('type', 'unknown')})"
                )
            except Exception as e:
                log_error(f"  Failed to create node from {json_file.name}: {e}")

        return new_nodes
