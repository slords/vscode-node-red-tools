"""
Explode operations for vscode-node-red-tools

Handles decomposition of flows.json into individual source files with:
- Plugin-based node extraction
- Parallel processing for large flows
- Per-node round-trip verification
- Pre/post-explode plugin stages
"""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .config import load_config
from .file_ops import find_orphaned_files, handle_orphaned_files
from .logging import (
    create_progress_context,
    log_error,
    log_info,
    log_success,
    log_warning,
    show_progress_bar,
)
from .plugin_loader import load_plugins
from .rebuild import rebuild_single_node
from .skeleton import create_skeleton, get_node_directory, save_skeleton
from .utils import create_backup

# Constants
DEFAULT_MAX_WORKERS = None  # None = use os.cpu_count()
PARALLEL_THRESHOLD = 20  # Min nodes to enable parallel processing


def _load_flows_for_explode(flows_path: Path, backup: bool) -> tuple[list, Path]:
    """Load and validate flows file for exploding

    Args:
        flows_path: Path to flows.json file
        backup: Whether to create a timestamped backup

    Returns:
        tuple of (flow_data, repo_root)

    Raises:
        ValueError: If flows file has invalid format
    """
    # Create backup if requested
    if backup:
        create_backup(flows_path)

    # Load flows
    with open(flows_path, "r") as f:
        flow_data = json.load(f)

    # Validate flow data structure
    if not isinstance(flow_data, list):
        raise ValueError(
            f"Invalid flows.json format: expected array, got {type(flow_data).__name__}"
        )

    if not flow_data:
        log_warning("Flows file is empty (contains empty array)")

    # Get repo root for plugins
    repo_root = flows_path.parent.parent

    return flow_data, repo_root


def _run_pre_explode_stage(
    flow_data: list,
    pre_explode_plugins: list,
    repo_root: Path,
    quiet_plugins: bool,
    progress_task: tuple = None,
) -> list:
    """Run pre-explode plugins to modify flow JSON

    Args:
        flow_data: Flow data array
        pre_explode_plugins: List of pre-explode plugins
        repo_root: Repository root directory
        quiet_plugins: Whether to suppress plugin messages
        progress_task: Optional (progress, task_id) tuple

    Returns:
        Modified flow_data
    """
    if pre_explode_plugins:
        log_info("Stage 1: Running pre-explode plugins...")
        for plugin in pre_explode_plugins:
            if not quiet_plugins:
                log_info(f"  {plugin.get_name()}")
            flow_data = plugin.process_flows_pre_explode(flow_data, repo_root)
            if progress_task:
                progress, task_id = progress_task
                progress.update(task_id, advance=1)
    else:
        log_info("Stage 1: No pre-explode plugins")

    return flow_data


def _explode_single_node(
    idx: int,
    node: dict,
    explode_plugins: list,
    src_dir: Path,
    tab_ids: set,
    repo_root: Path,
    quiet_plugins: bool,
) -> tuple[int, dict, bool]:
    """Process a single node for exploding (thread-safe worker function)

    Args:
        idx: Node index (for ordering results)
        node: Node data
        explode_plugins: List of explode plugins
        src_dir: Source directory
        tab_ids: Set of tab/subflow IDs
        repo_root: Repository root directory
        quiet_plugins: Whether to suppress plugin messages

    Returns:
        tuple of (idx, skeleton, is_unstable)
    """
    node_id = node.get("id")
    if not node_id:
        return (idx, None, False)

    node_dir = get_node_directory(node, src_dir, tab_ids)
    node_dir.mkdir(parents=True, exist_ok=True)

    # Create skeleton entry
    skeleton = create_skeleton(node)

    # Track claimed fields to prevent conflicts
    claimed_fields = set()

    # Track metadata for this node: {plugin_name: [files]}
    plugin_files_map = {}

    # Let plugins handle node-specific files
    for plugin in explode_plugins:
        if plugin.can_handle_node(node):
            # Check for field conflicts
            plugin_fields = set(plugin.get_claimed_fields(node))
            if plugin_fields & claimed_fields:
                # Skip this plugin - another plugin already claimed these fields
                continue

            # Claim fields and process node
            claimed_fields.update(plugin_fields)
            plugin_files = plugin.explode_node(node, node_dir, repo_root)

            # Collect metadata - map plugin name to files it created
            if plugin_files:
                plugin_files_map[plugin.get_name()] = sorted(plugin_files)

    # Write base .json file (exclude structural fields and claimed fields)
    structural_fields = {"id", "type", "z", "x", "y", "wires"}
    excluded_fields = structural_fields | claimed_fields

    json_file = node_dir / f"{node_id}.json"
    node_json = {k: v for k, v in node.items() if k not in excluded_fields}

    # Only write .json file if there are functional fields to save
    if node_json:
        json_file.write_text(
            json.dumps(node_json, separators=(",", ":"), ensure_ascii=False) + "\n"
        )
        # Base .json is created internally, not by a plugin
        plugin_files_map["internal"] = [f"{node_id}.json"]

    # Empty claimed functional fields in skeleton (preserve type-appropriate placeholders)
    for field in claimed_fields:
        if field in skeleton and field not in structural_fields:
            # Keep type-appropriate empty placeholder
            value = skeleton[field]
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

    # Store metadata in skeleton: {plugin_name: [files], stable: bool}
    skeleton["_explode_meta"] = plugin_files_map.copy()
    skeleton["_explode_meta"]["stable"] = None  # Will be set after verification

    # Per-node round-trip verification
    base_json_exists = "internal" in plugin_files_map
    is_unstable = False
    try:
        rebuilt_node = rebuild_single_node(
            node_id, node_dir, skeleton, base_json_exists, explode_plugins, repo_root
        )

        # Compare original node to rebuilt node (excluding metadata)
        original_compare = {k: v for k, v in node.items() if k != "_explode_meta"}
        rebuilt_compare = {
            k: v for k, v in rebuilt_node.items() if k != "_explode_meta"
        }

        # Serialize to JSON for accurate comparison
        original_json = json.dumps(
            original_compare, separators=(",", ":"), ensure_ascii=False
        )
        rebuilt_json = json.dumps(
            rebuilt_compare, separators=(",", ":"), ensure_ascii=False
        )

        if original_json == rebuilt_json:
            skeleton["_explode_meta"]["stable"] = True
        else:
            skeleton["_explode_meta"]["stable"] = False
            is_unstable = True
            if not quiet_plugins:
                log_warning(
                    f"Node {node_id} changed during round-trip - will trigger rebuild/upload"
                )

    except Exception as e:
        skeleton["_explode_meta"]["stable"] = False
        is_unstable = True
        log_warning(f"Failed to verify node {node_id}: {e}")

    return (idx, skeleton, is_unstable)


def _explode_nodes_stage(
    flow_data: list,
    explode_plugins: list,
    src_dir: Path,
    tab_ids: set,
    repo_root: Path,
    quiet_plugins: bool,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_task: tuple = None,
) -> tuple[list, bool]:
    """Process each node and build skeleton (with optional parallel processing)

    Args:
        flow_data: Flow data array
        explode_plugins: List of explode plugins
        src_dir: Source directory
        tab_ids: Set of tab/subflow IDs
        repo_root: Repository root directory
        quiet_plugins: Whether to suppress plugin messages
        max_workers: Max worker threads (None = cpu_count, 1 = sequential)
        progress_task: Optional (progress, task_id) tuple

    Returns:
        tuple of (skeleton_data, any_node_unstable)
    """
    log_info("Stage 2: Exploding nodes to src/...")

    total_nodes = len(flow_data)

    # Decide whether to use parallel processing
    use_parallel = max_workers != 1 and total_nodes >= PARALLEL_THRESHOLD

    if use_parallel and max_workers is None:
        max_workers = os.cpu_count() or 4

    # Shared state for thread-safe operations
    progress_lock = threading.Lock()
    progress_counter = [0]
    show_progress = total_nodes > 50

    def update_progress():
        """Thread-safe progress update"""
        with progress_lock:
            progress_counter[0] += 1
            if progress_task:
                progress, task_id = progress_task
                progress.update(task_id, advance=1)
            elif show_progress:
                show_progress_bar(progress_counter[0], total_nodes, "Exploding nodes")

    any_node_unstable = False

    # Process nodes
    if use_parallel:
        # Parallel processing with ThreadPoolExecutor
        skeleton_data = [None] * total_nodes  # Pre-allocate to maintain order

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    _explode_single_node,
                    idx,
                    node,
                    explode_plugins,
                    src_dir,
                    tab_ids,
                    repo_root,
                    quiet_plugins,
                ): idx
                for idx, node in enumerate(flow_data)
            }

            # Collect results as they complete
            for future in as_completed(futures):
                idx, skeleton, is_unstable = future.result()
                if skeleton:
                    skeleton_data[idx] = skeleton
                if is_unstable:
                    any_node_unstable = True

                update_progress()

        # Filter out None entries
        skeleton_data = [s for s in skeleton_data if s is not None]

    else:
        # Sequential processing
        skeleton_data = []

        for idx, node in enumerate(flow_data):
            idx_result, skeleton, is_unstable = _explode_single_node(
                idx,
                node,
                explode_plugins,
                src_dir,
                tab_ids,
                repo_root,
                quiet_plugins,
            )

            if skeleton:
                skeleton_data.append(skeleton)

            if is_unstable:
                any_node_unstable = True

            update_progress()

    # Write skeleton to .flow-skeleton.json
    save_skeleton(src_dir, skeleton_data)

    return skeleton_data, any_node_unstable


def _run_post_explode_stage(
    post_explode_plugins: list,
    src_dir: Path,
    flows_path: Path,
    repo_root: Path,
    quiet_plugins: bool,
    progress_task: tuple = None,
) -> bool:
    """Run post-explode plugins to format files

    Args:
        post_explode_plugins: List of post-explode plugins
        src_dir: Source directory
        flows_path: Flows file path
        repo_root: Repository root directory
        quiet_plugins: Whether to suppress plugin messages
        progress_task: Optional (progress, task_id) tuple for progress tracking

    Returns:
        True if any plugin modified files
    """
    if post_explode_plugins:
        log_info("Stage 3: Running post-explode plugins...")
        any_modified = False

        for plugin in post_explode_plugins:
            if not quiet_plugins:
                log_info(f"  {plugin.get_name()}")
            changed = plugin.process_directory_post_explode(
                src_dir, flows_path, repo_root
            )
            if changed:
                any_modified = True
            if progress_task:
                progress, task_id = progress_task
                progress.update(task_id, advance=1)

        return any_modified
    else:
        log_info("Stage 3: No post-explode plugins")
        return False


def explode_flows(
    flows_path: Path,
    src_dir: Path,
    backup: bool = False,
    delete_orphaned: bool = False,
    return_info: bool = False,
    quiet_plugins: bool = False,
    dry_run: bool = False,
    plugins_dict: dict = None,
    repo_root: Path = None,
):
    """Explode flows.json into individual source files

    Args:
        flows_path: Path to flows.json file
        src_dir: Output directory for source files
        backup: Create timestamped backup before exploding
        delete_orphaned: Delete orphaned files instead of moving to .orphaned/
        return_info: If True, return dict with detailed info instead of int
        quiet_plugins: Suppress plugin loading messages
        dry_run: Show what would happen without making changes
        plugins_dict: Pre-loaded plugins dictionary (required)
        repo_root: Repository root path (required)

    Returns:
        int: Exit code (0 = success, 1 = error) if return_info=False
        dict: {'exit_code': int, 'needs_rebuild': bool} if return_info=True
    """
    # Handle dry-run by using temp directory and comparing
    if dry_run:
        import tempfile
        import shutil

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_src = Path(temp_dir) / "src"
            temp_src.mkdir()

            # Run explode in temp directory
            result = explode_flows(
                flows_path,
                temp_src,
                backup=False,
                delete_orphaned=delete_orphaned,
                return_info=return_info,
                quiet_plugins=True,
                dry_run=False,
                plugins_dict=plugins_dict,
                repo_root=repo_root,
            )

            # Compare and report differences
            log_info(f"Dry run complete - would explode to {src_dir}/")

            return result

    try:
        log_info(f"Exploding {flows_path} to {src_dir}/")

        # STAGE 1: Load and validate flows
        try:
            flow_data, loaded_repo_root = _load_flows_for_explode(flows_path, backup)
            if repo_root is None:
                repo_root = loaded_repo_root
        except ValueError as e:
            log_error(str(e))
            log_error("Flows file should contain an array of node objects")
            if return_info:
                return {"exit_code": 1, "needs_rebuild": False}
            return 1

        # Require plugins_dict to be provided
        if plugins_dict is None:
            raise ValueError("plugins_dict is required - call preload_plugins() first")

        # Get plugins from loaded dict (already filtered by load_plugins)
        pre_explode_plugins = plugins_dict["pre-explode"]
        explode_plugins = plugins_dict["explode"]
        post_explode_plugins = plugins_dict["post-explode"]

        # STAGE 2: Run pre-explode plugins (with its own progress context)
        if pre_explode_plugins:
            with create_progress_context(True) as progress:
                task = progress.add_task(
                    "Pre-explode plugins", total=len(pre_explode_plugins)
                )
                flow_data = _run_pre_explode_stage(
                    flow_data,
                    pre_explode_plugins,
                    repo_root,
                    quiet_plugins,
                    progress_task=(progress, task),
                )
        else:
            flow_data = _run_pre_explode_stage(
                flow_data,
                pre_explode_plugins,
                repo_root,
                quiet_plugins,
                progress_task=None,
            )

        # Create src directory
        src_dir.mkdir(parents=True, exist_ok=True)

        # Get all tab/subflow IDs for directory organization
        tab_ids = {
            node["id"] for node in flow_data if node.get("type") in ["tab", "subflow"]
        }

        # Create directories for tabs/subflows
        for tab_id in tab_ids:
            (src_dir / tab_id).mkdir(exist_ok=True)

        # STAGE 3: Explode nodes and build skeleton (with its own progress context)
        with create_progress_context(True) as progress:
            nodes_task = progress.add_task("Exploding nodes", total=len(flow_data))
            skeleton_data, any_node_unstable = _explode_nodes_stage(
                flow_data,
                explode_plugins,
                src_dir,
                tab_ids,
                repo_root,
                quiet_plugins,
                progress_task=(progress, nodes_task),
            )

        # STAGE 4: Run post-explode plugins (with its own progress context, optional)
        post_explode_modified = False
        if post_explode_plugins:
            with create_progress_context(True) as progress:
                post_task = progress.add_task(
                    "Post-explode plugins", total=len(post_explode_plugins)
                )
                post_explode_modified = _run_post_explode_stage(
                    post_explode_plugins,
                    src_dir,
                    flows_path,
                    repo_root,
                    quiet_plugins,
                    progress_task=(progress, post_task),
                )

            if post_explode_modified:
                any_node_unstable = True  # Files changed, need rebuild

        # Detect and handle orphaned files (using metadata for perfect accuracy)
        orphaned = find_orphaned_files(src_dir, flow_data, tab_ids, skeleton_data)
        if orphaned:
            handle_orphaned_files(orphaned, src_dir, delete=delete_orphaned)

        log_success(f"Exploded {len(flow_data)} nodes to {src_dir}/")

        if return_info:
            return {
                "exit_code": 0,
                "needs_rebuild": any_node_unstable,
            }
        return 0

    except Exception as e:
        log_error(f"Explode failed: {e}")
        import traceback

        traceback.print_exc()

        if return_info:
            return {
                "exit_code": 1,
                "needs_rebuild": False,
            }
        return 1
