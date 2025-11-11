"""
Skeleton file management for vscode-node-red-tools

Handles creation, loading, and saving of .flow-skeleton.json files which
contain the structural metadata for Node-RED flows.
"""

import json
from pathlib import Path
from typing import Optional

from .logging import log_info, log_warning


def get_node_directory(node: dict, src_dir: Path, tab_ids: set) -> Path:
    """Get the directory where a node's files should be stored

    Args:
        node: Node dictionary
        src_dir: Source directory root
        tab_ids: Set of valid tab/subflow IDs

    Returns:
        Path to directory for this node's files

    Notes:
        - Nodes without z field go to root (src_dir)
        - Nodes with z pointing to non-existent tab go to root
        - Nodes in tabs/subflows go into subdirectories (src_dir/tab_id)
    """
    z = node.get("z")
    node_type = node.get("type", "")

    # Nodes without z or with z pointing to non-existent tab go to root
    if not z or z not in tab_ids:
        return src_dir

    # Nodes in tabs/subflows go into subdirectories
    return src_dir / z


def create_skeleton(node: dict) -> dict:
    """Create skeleton node (structure only, no functional data)

    Args:
        node: Complete node dictionary

    Returns:
        Skeleton dictionary with:
        - Structural fields with values: id, type, z, x, y, wires
        - Empty placeholders for functional fields to preserve order

    Notes:
        - Preserves field order from original node (Python 3.7+ dict ordering)
        - Functional fields get empty placeholders based on type
        - Used to maintain flow structure while separating functional code
    """
    structural_fields = {"id", "type", "z", "x", "y", "wires"}

    skeleton = {}

    # Process all fields in original order (Python 3.7+ preserves dict order)
    for field, value in node.items():
        if field in structural_fields:
            # Structural fields: keep actual value
            skeleton[field] = value
        else:
            # Functional fields: create empty placeholder based on type
            if isinstance(value, str):
                skeleton[field] = ""
            elif isinstance(value, list):
                skeleton[field] = []
            elif isinstance(value, int):
                skeleton[field] = 0
            elif isinstance(value, bool):
                skeleton[field] = False
            elif isinstance(value, dict):
                skeleton[field] = {}
            else:
                skeleton[field] = ""  # Default to empty string

    return skeleton


def load_skeleton(src_dir: Path, flows_path: Optional[Path] = None) -> tuple[list, dict]:
    """Load skeleton file for rebuilding

    Args:
        src_dir: Source directory containing .flow-skeleton.json
        flows_path: Optional flows file path (fallback if skeleton missing)

    Returns:
        tuple of (skeleton_data, skeleton_map):
        - skeleton_data: List of skeleton nodes
        - skeleton_map: Dictionary mapping node ID to skeleton node

    Raises:
        FileNotFoundError: If neither skeleton nor flows file exists

    Notes:
        - Primary source: src_dir/.flow-skeleton.json
        - Fallback: flows_path if provided and skeleton missing
        - Skeleton map enables O(1) lookup by node ID
    """
    skeleton_file = src_dir / ".flow-skeleton.json"

    if not skeleton_file.exists():
        # Fallback: try to load flows.json as skeleton if it exists
        log_warning(f"Skeleton file not found: {skeleton_file}")
        if flows_path and flows_path.exists():
            log_info(f"Using {flows_path} as skeleton fallback")
            with open(flows_path, "r") as f:
                skeleton_data = json.load(f)
        else:
            raise FileNotFoundError(f"Neither skeleton file nor flows.json found")
    else:
        with open(skeleton_file, "r") as f:
            skeleton_data = json.load(f)

    # Build skeleton map for O(1) lookup
    skeleton_map = {node["id"]: node for node in skeleton_data}

    return skeleton_data, skeleton_map


def save_skeleton(src_dir: Path, skeleton_data: list) -> None:
    """Save skeleton data to .flow-skeleton.json

    Args:
        src_dir: Source directory where skeleton file will be created
        skeleton_data: List of skeleton nodes to save

    Notes:
        - Writes compact JSON format (no spaces)
        - Adds trailing newline for git-friendly diffs
        - File: src_dir/.flow-skeleton.json
    """
    skeleton_file = src_dir / ".flow-skeleton.json"
    skeleton_json = json.dumps(skeleton_data, separators=(",", ":"), ensure_ascii=False)
    skeleton_file.write_text(skeleton_json + "\n")
