"""
Stage processing for watch mode

Handles high-level download/explode orchestration:
- Pre-explode stage processing
- Explode stage processing
- Post-explode stage processing
- Download and explode orchestration
- Stability checking
- Rebuild and deploy
"""

import json
from datetime import datetime
from pathlib import Path

# Watch-specific imports (conditional)
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .logging import (
    log_info,
    log_success,
    log_warning,
    log_error,
    create_progress_context,
)
from .utils import clear_watch_state_after_failure
from .rebuild import rebuild_flows
from .explode import (
    _run_pre_explode_stage,
    _explode_nodes_stage,
    _run_post_explode_stage,
)
from .file_ops import find_orphaned_files, handle_orphaned_files
from .dashboard import WatchConfig
# Legacy watcher_server functions replaced by ServerClient usage


def _run_pre_explode_download_stage(
    watch_config: WatchConfig,
    plugins_dict: dict,
    repo_root: Path,
    progress_task: tuple = None,
) -> bool:
    """Run pre-explode plugins and upload if modified

    Args:
        config: Watch configuration
        plugins_dict: Plugin dictionary
        repo_root: Repository root directory
        progress_task: Optional (progress, task_id) tuple for progress tracking

    Returns:
        True if successful, False on error
    """
    pre_explode_plugins = plugins_dict["pre-explode"]

    if pre_explode_plugins:
        # Load flows
        with open(watch_config.flows_file, "r") as f:
            flow_data = json.load(f)

        # Save original for comparison
        original_flow = json.dumps(flow_data, separators=(",", ":"), ensure_ascii=False)

        # Run pre-explode plugins using the shared function (handles logging and progress)
        flow_data = _run_pre_explode_stage(
            flow_data,
            pre_explode_plugins,
            repo_root,
            quiet_plugins=True,  # Suppress plugin names in watch mode
            progress_task=progress_task,
        )

        # Check if anything changed
        modified_flow = json.dumps(flow_data, separators=(",", ":"), ensure_ascii=False)
        flows_modified = original_flow != modified_flow

        # Write modified flows
        watch_config.flows_file.write_text(modified_flow + "\n")

        # Upload if any pre-explode plugin modified flows (don't count - automated)
        if flows_modified:
            log_info("Flows modified by pre-explode plugins, uploading...")
            sc = getattr(watch_config, "server_client", None)
            if not sc or not sc.deploy_flows(flow_data, count_stats=False):
                clear_watch_state_after_failure(watch_config, "upload modified flows")
                return False
            log_success("Modified flows uploaded to Node-RED")

        return True
    else:
        log_info("Stage 1: No pre-explode plugins")
        return True


def _run_explode_download_stage(
    watch_config: WatchConfig,
    plugins_dict: dict,
    repo_root: Path,
    progress_task: tuple = None,
) -> tuple:
    """Explode flows to src/

    Args:
        config: Watch configuration
        plugins_dict: Plugin dictionary
        repo_root: Repository root directory
        progress_task: Optional (progress, task_id) tuple for progress tracking

    Returns:
        Tuple of (success, files_changed) where success is True if no errors,
        files_changed is True if any node was unstable (files differ from flows.json)
    """
    # Pause watching during explode
    watch_config.pause_watching = True
    try:
        # Load flows (modified by pre-explode stage)
        with open(watch_config.flows_file, "r") as f:
            flow_data = json.load(f)

        # Get explode plugins from dict
        explode_plugins = plugins_dict["explode"]

        # Create src directory
        watch_config.src_dir.mkdir(parents=True, exist_ok=True)

        # Get all tab/subflow IDs for directory organization
        tab_ids = {
            node["id"] for node in flow_data if node.get("type") in ["tab", "subflow"]
        }

        # Create directories for tabs/subflows
        for tab_id in tab_ids:
            (watch_config.src_dir / tab_id).mkdir(exist_ok=True)

        # Run explode stage using shared function (handles logging and progress)
        skeleton_data, any_node_unstable = _explode_nodes_stage(
            flow_data,
            explode_plugins,
            watch_config.src_dir,
            tab_ids,
            repo_root,
            quiet_plugins=True,  # Suppress plugin names in watch mode
            progress_task=progress_task,
        )

        # Detect and handle orphaned files
        orphaned = find_orphaned_files(
            watch_config.src_dir, flow_data, tab_ids, skeleton_data
        )
        if orphaned:
            handle_orphaned_files(orphaned, watch_config.src_dir, delete=False)

        return (True, any_node_unstable)
    finally:
        watch_config.pause_watching = False


def _run_post_explode_download_stage(
    watch_config: WatchConfig,
    plugins_dict: dict,
    repo_root: Path,
    progress_task: tuple = None,
) -> tuple:
    """Run post-explode plugins

    Args:
        config: Watch configuration
        plugins_dict: Plugin dictionary
        repo_root: Repository root directory
        progress_task: Optional (progress, task_id) tuple for progress tracking

    Returns:
        Tuple of (success, changes_made) where success is True if no errors,
        changes_made is True if plugins modified files
    """
    # Pause watching during post-explode processing
    watch_config.pause_watching = True
    try:
        # Get post-explode plugins from dict
        post_explode_plugins = plugins_dict["post-explode"]

        # Run post-explode stage using shared function (handles logging and progress)
        post_explode_modified = _run_post_explode_stage(
            post_explode_plugins,
            watch_config.src_dir,
            watch_config.flows_file,
            repo_root,
            quiet_plugins=True,  # Suppress plugin names in watch mode
            progress_task=progress_task,
        )

        # Just return whether files changed - don't upload here
        return (True, post_explode_modified)
    finally:
        watch_config.pause_watching = False


def download_from_nodered(
    watch_config: WatchConfig, force: bool = False, count_stats: bool = True
) -> bool:
    """Download flows from Node-RED and explode

    Args:
        config: Watch configuration
        force: If True, skip ETag check and always download (for manual download command)
        count_stats: If True, count this download in statistics (False for convergence cycles)

    Returns:
        True if successful, False on error
    """
    try:
        sc = getattr(watch_config, "server_client", None)
        if not sc:
            log_error("No ServerClient attached to watch_config")
            return False

        changed, flows = sc.get_and_store_flows(force=force)
        if not changed:
            return True  # No change (304 or failure already logged inside)

        # Log revision change
        if sc.last_rev:
            log_info(f"Current server rev: {sc.last_rev}")

        # Ensure flows directory exists
        watch_config.flows_file.parent.mkdir(parents=True, exist_ok=True)

        # Write to flows file - compact format
        watch_config.flows_file.write_text(
            json.dumps(flows, separators=(",", ":"), ensure_ascii=False) + "\n"
        )

        # Use cached plugins (loaded once at startup)
        plugins_dict = watch_config.plugins_dict
        repo_root = watch_config.repo_root

        # STAGE 1: Run pre-explode plugins (with its own progress context)
        pre_explode_plugins = plugins_dict["pre-explode"]
        if pre_explode_plugins:
            with create_progress_context(True) as progress:
                pre_task = progress.add_task(
                    "Pre-explode plugins", total=len(pre_explode_plugins)
                )
                if not _run_pre_explode_download_stage(
                    watch_config, plugins_dict, repo_root, progress_task=(progress, pre_task)
                ):
                    return False

        # STAGE 2: Explode flows (with its own progress context)
        nodes_count = len(flows) if isinstance(flows, list) else 0
        explode_changed = False
        with create_progress_context(True) as progress:
            nodes_task = progress.add_task("Exploding nodes", total=nodes_count)
            success, explode_changed = _run_explode_download_stage(
                watch_config, plugins_dict, repo_root, progress_task=(progress, nodes_task)
            )
            if not success:
                return False

        # Log if explode detected file changes
        if explode_changed:
            log_info("Explode detected file changes (nodes unstable)")

        # STAGE 3: Run post-explode plugins (with its own progress context)
        post_explode_changed = False
        post_explode_plugins = plugins_dict["post-explode"]
        if post_explode_plugins:
            with create_progress_context(True) as progress:
                post_task = progress.add_task(
                    "Post-explode plugins", total=len(post_explode_plugins)
                )
                success, post_explode_changed = _run_post_explode_download_stage(
                    watch_config, plugins_dict, repo_root, progress_task=(progress, post_task)
                )
            # Log "No changes" after progress bar completes
            if not post_explode_changed:
                log_info("No changes from post-explode plugins")
            if not success:
                return False

        # If explode or post-explode detected changes, rebuild and upload
        upload_needed = explode_changed or post_explode_changed
        if upload_needed:
            log_info("Changes detected, rebuilding and uploading...")
            result = rebuild_flows(
                watch_config.flows_file,
                watch_config.src_dir,
                continued_from_explode=True,
                quiet_plugins=True,
                plugins_dict=watch_config.plugins_dict,
                repo_root=watch_config.repo_root,
            )
            if result != 0:
                log_error("Rebuild failed")
                return False

            if not deploy_to_nodered(watch_config, count_stats=False):
                clear_watch_state_after_failure(watch_config, "upload after changes")
                return False
            log_success("Changes uploaded to Node-RED")

        log_success("Download and explode complete")

        # Clear file watcher state to prevent false rebuild triggers
        # (explode/post-explode wrote files from server, not user edits)
        watch_config.clear_file_watcher_state()

        # Update statistics (only if this is a counted download, not a stability check)
        # Stats already tracked in ServerClient; dashboard may still log
        if count_stats and watch_config.dashboard:
            watch_config.dashboard.log_download()

        return True

    except requests.exceptions.RequestException as e:
        log_error(f"Download failed: {e}")
        if watch_config.dashboard:
            watch_config.dashboard.log_activity(f"Download failed: {e}", is_error=True)
        return False


def rebuild_and_deploy(watch_config: WatchConfig) -> bool:
    """Rebuild flows and deploy to Node-RED"""
    # Rebuild (pre-rebuild plugin may format src files)
    log_info("Rebuilding flows...")

    result = rebuild_flows(
        watch_config.flows_file,
        watch_config.src_dir,
        quiet_plugins=True,
        plugins_dict=watch_config.plugins_dict,
        repo_root=watch_config.repo_root,
    )
    if result != 0:
        log_error("Rebuild failed")
        return False

    # Deploy
    sc = getattr(watch_config, "server_client", None)
    if not sc or not sc.deploy_flows(json.loads(watch_config.flows_file.read_text())):
        return False

    # Clear file watcher state to prevent false rebuild triggers
    # (deploy completed successfully, already synced with server)
    watch_config.clear_file_watcher_state()

    # ETag cleared by deploy - next poll will download and check convergence
    log_success("Rebuild and deploy complete")
    return True
