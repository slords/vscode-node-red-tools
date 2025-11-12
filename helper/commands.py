"""
General command implementations for vscode-node-red-tools

Contains commands for statistics, benchmarking, and verification.
"""

import difflib
import json
import tempfile
import time
from pathlib import Path

from .logging import log_info, log_success, log_warning, log_error
from .exit_codes import (
    SUCCESS,
    GENERAL_ERROR,
    FILE_NOT_FOUND,
    EXPLODE_ERROR,
    REBUILD_ERROR,
    VERIFICATION_FAILED,
)
from .utils import compute_file_hash, compute_dir_hash
from .explode import explode_flows
from .rebuild import rebuild_flows


def stats_command(
    flows_path: Path,
    src_path: Path,
    plugins_dict: dict,
    config: dict,
) -> int:
    """Display comprehensive flow and source statistics

    Args:
        flows_path: Path to flows.json
        src_path: Path to source directory
        plugins_dict: Pre-loaded plugins dictionary
        config: Pre-loaded configuration dictionary
    """
    if plugins_dict is None or config is None:
        log_error("stats_command requires pre-loaded plugins_dict and config. None was provided.", code=GENERAL_ERROR)
        return GENERAL_ERROR
    try:
        log_info("=== Flow Statistics ===")

        stats = {}

        # Flow statistics
        if flows_path.exists():
            log_info(f"\nFlows file: {flows_path}")
            with open(flows_path, "r") as f:
                flow_data = json.load(f)

            # Count node types
            node_types = {}
            tabs = []
            subflows = []
            config_nodes = []

            for node in flow_data:
                node_type = node.get("type", "unknown")
                node_types[node_type] = node_types.get(node_type, 0) + 1

                if node_type == "tab":
                    tabs.append(node)
                elif node_type == "subflow":
                    subflows.append(node)
                elif "z" not in node and node_type not in ["tab", "subflow"]:
                    config_nodes.append(node)

            stats["total_nodes"] = len(flow_data)
            stats["tabs"] = len(tabs)
            stats["subflows"] = len(subflows)
            stats["config_nodes"] = len(config_nodes)
            stats["regular_nodes"] = (
                len(flow_data) - len(tabs) - len(subflows) - len(config_nodes)
            )

            log_info(f"  Total nodes: {stats['total_nodes']}")
            log_info(f"  Tabs: {stats['tabs']}")
            log_info(f"  Subflows: {stats['subflows']}")
            log_info(f"  Config nodes: {stats['config_nodes']}")
            log_info(f"  Regular nodes: {stats['regular_nodes']}")

            # Most common node types
            log_info("\n  Most common node types:")
            sorted_types = sorted(node_types.items(), key=lambda x: x[1], reverse=True)
            for node_type, count in sorted_types[:10]:
                log_info(f"    {node_type}: {count}")

            # File size
            file_size = flows_path.stat().st_size
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            log_info(f"\n  File size: {size_str}")

            # Hash
            hash_value = compute_file_hash(flows_path)
            log_info(f"  Hash (first 16 chars): {hash_value[:16]}")

        else:
            log_warning(f"Flows file not found: {flows_path}", code=FILE_NOT_FOUND)

        # Source statistics
        if src_path.exists():
            log_info(f"\nSource directory: {src_path}")

            # Count files by extension
            file_counts = {}
            total_size = 0

            for file_path in src_path.rglob("*"):
                if file_path.is_file():
                    ext = file_path.suffix or "(no extension)"
                    file_counts[ext] = file_counts.get(ext, 0) + 1
                    total_size += file_path.stat().st_size

            stats["total_files"] = sum(file_counts.values())
            stats["total_size"] = total_size

            log_info(f"  Total files: {stats['total_files']}")

            if total_size < 1024:
                size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.1f} KB"
            else:
                size_str = f"{total_size / (1024 * 1024):.1f} MB"
            log_info(f"  Total size: {size_str}")

            # Files by extension
            log_info("\n  Files by extension:")
            sorted_exts = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
            for ext, count in sorted_exts:
                log_info(f"    {ext}: {count}")

            # Directory hash (all files)
            hash_value = compute_dir_hash(src_path, ["**/*"])
            log_info(f"\n  Directory hash (first 16 chars): {hash_value[:16]}")

        else:
            log_warning(f"Source directory not found: {src_path}", code=FILE_NOT_FOUND)

        # Plugin statistics (use pre-loaded plugins only)
        log_info("\n=== Plugin Statistics ===")
        total_plugins = sum(len(plugins_dict[key]) for key in plugins_dict)
        log_info(f"  Total loaded plugins: {total_plugins}")

        for plugin_type, plugins in plugins_dict.items():
            if plugins:
                log_info(f"    {plugin_type}: {len(plugins)}")
                for plugin in plugins:
                    log_info(f"      - {plugin.get_name()}")

        return SUCCESS

    except Exception as e:
        log_error(f"Stats failed: {e}", code=GENERAL_ERROR)
        import traceback

        traceback.print_exc()
        return GENERAL_ERROR


def benchmark_command(
    flows_path: Path,
    src_path: Path,
    plugins_dict: dict = None,
    config: dict = None,
    iterations: int = 3,
) -> int:
    """Benchmark explode and rebuild performance

    Args:
        flows_path: Path to flows.json
        src_path: Path to source directory
        plugins_dict: Pre-loaded plugins dictionary
        config: Pre-loaded configuration dictionary
        iterations: Number of iterations
    """
    try:
        log_info(f"Benchmarking with {iterations} iterations...")

        # Load original flows once
        with open(flows_path, "r") as f:
            original_flows = json.load(f)

        log_info(f"Flow size: {len(original_flows)} nodes")

        explode_times = []
        rebuild_times = []

        for i in range(iterations):
            log_info(f"\nIteration {i + 1}/{iterations}")

            # Create temp directory for each iteration
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                temp_src = temp_path / "src"
                temp_flows = temp_path / "flows.json"

                # Write flows to temp
                temp_flows.write_text(
                    json.dumps(
                        original_flows, separators=(",", ":"), ensure_ascii=False
                    )
                    + "\n"
                )

                # Benchmark explode
                start = time.time()
                result = explode_flows(
                    temp_flows,
                    temp_src,
                    quiet_plugins=True,
                    plugins_dict=plugins_dict,
                )
                explode_time = time.time() - start
                explode_times.append(explode_time)

                if result != SUCCESS:
                    log_error("Explode failed", code=EXPLODE_ERROR)
                    return EXPLODE_ERROR

                log_info(f"  Explode: {explode_time:.3f}s")

                # Benchmark rebuild
                start = time.time()
                result = rebuild_flows(
                    temp_flows,
                    temp_src,
                    quiet_plugins=True,
                    plugins_dict=plugins_dict,
                )
                rebuild_time = time.time() - start
                rebuild_times.append(rebuild_time)

                if result != SUCCESS:
                    log_error("Rebuild failed", code=REBUILD_ERROR)
                    return REBUILD_ERROR

                log_info(f"  Rebuild: {rebuild_time:.3f}s")
                log_info(f"  Total: {explode_time + rebuild_time:.3f}s")

        # Calculate statistics
        log_info("\n=== Benchmark Results ===")

        explode_avg = sum(explode_times) / len(explode_times)
        explode_min = min(explode_times)
        explode_max = max(explode_times)

        rebuild_avg = sum(rebuild_times) / len(rebuild_times)
        rebuild_min = min(rebuild_times)
        rebuild_max = max(rebuild_times)

        total_avg = explode_avg + rebuild_avg
        total_min = explode_min + rebuild_min
        total_max = explode_max + rebuild_max

        log_info(
            f"Explode:  avg={explode_avg:.3f}s  min={explode_min:.3f}s  max={explode_max:.3f}s"
        )
        log_info(
            f"Rebuild:  avg={rebuild_avg:.3f}s  min={rebuild_min:.3f}s  max={rebuild_max:.3f}s"
        )
        log_info(
            f"Total:    avg={total_avg:.3f}s  min={total_min:.3f}s  max={total_max:.3f}s"
        )

        # Nodes per second
        nodes_per_sec_explode = len(original_flows) / explode_avg
        nodes_per_sec_rebuild = len(original_flows) / rebuild_avg

        log_info(f"\nThroughput:")
        log_info(f"  Explode: {nodes_per_sec_explode:.1f} nodes/sec")
        log_info(f"  Rebuild: {nodes_per_sec_rebuild:.1f} nodes/sec")

        return SUCCESS

    except Exception as e:
        log_error(f"Benchmark failed: {e}", code=GENERAL_ERROR)
        import traceback

        traceback.print_exc()
        return GENERAL_ERROR


def verify_flows(
    flows_path: Path,
    plugins_dict: dict,
    config: dict,
) -> int:
    """Verify round-trip stability: explode → rebuild → compare

    Args:
        flows_path: Path to flows.json
        plugins_dict: Pre-loaded plugins dictionary
        config: Pre-loaded configuration dictionary
    """
    if plugins_dict is None or config is None:
        log_error("verify_flows requires pre-loaded plugins_dict and config. None was provided.", code=GENERAL_ERROR)
        return GENERAL_ERROR
    log_info(f"Verifying round-trip stability for {flows_path}")

    try:
        # Load original flows
        if not flows_path.exists():
            log_error(f"File not found: {flows_path}", code=FILE_NOT_FOUND)
            log_error("Provide a valid flows.json file path with --flows, or use watch mode to sync from server")
            return FILE_NOT_FOUND

        with open(flows_path, "r") as f:
            original_flows = json.load(f)

        # Create temp directory for verification
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            temp_src = temp_path / "src"
            temp_flows = temp_path / "flows.json"

            # Copy original flows to temp
            temp_flows.write_text(
                json.dumps(original_flows, separators=(",", ":"), ensure_ascii=False)
                + "\n"
            )

            # Step 1: Explode (pass pre-loaded plugins)
            log_info("Step 1: Exploding flows...")
            result = explode_flows(
                temp_flows,
                temp_src,
                plugins_dict=plugins_dict,
            )
            if result != SUCCESS:
                log_error("Explode failed during verification", code=EXPLODE_ERROR)
                return EXPLODE_ERROR

            # Step 2: Rebuild (pass pre-loaded plugins)
            log_info("Step 2: Rebuilding flows...")
            result = rebuild_flows(
                temp_flows,
                temp_src,
                continued_from_explode=True,
                plugins_dict=plugins_dict,
            )
            if result != SUCCESS:
                log_error("Rebuild failed during verification", code=REBUILD_ERROR)
                return REBUILD_ERROR

            # Step 3: Compare
            log_info("Step 3: Comparing original vs rebuilt...")
            with open(temp_flows, "r") as f:
                rebuilt_flows = json.load(f)

            # Serialize both with same settings to check field order AND content
            # Using compact format (no sort_keys to preserve order)
            original_json = json.dumps(
                original_flows, separators=(",", ":"), ensure_ascii=False
            )
            rebuilt_json = json.dumps(
                rebuilt_flows, separators=(",", ":"), ensure_ascii=False
            )

            # Compare serialized JSON (catches order differences)
            if original_json == rebuilt_json:
                log_success(
                    "\u2713 Round-trip verification passed - flows are identical (content and order)"
                )
                return SUCCESS
            else:
                log_error("\u2717 Round-trip verification failed - flows differ", code=VERIFICATION_FAILED)

                # Check if content is same but order differs
                if original_flows == rebuilt_flows:
                    log_warning(
                        "Content is identical but field ORDER differs (critical for Node-RED!)",
                        code=VERIFICATION_FAILED
                    )
                else:
                    log_error("Content differs (not just field order)", code=VERIFICATION_FAILED)

                # Show differences (use indented format for readability, but no sort_keys)
                original_pretty = json.dumps(
                    original_flows, indent=2, ensure_ascii=False
                )
                rebuilt_pretty = json.dumps(rebuilt_flows, indent=2, ensure_ascii=False)

                diff = list(
                    difflib.unified_diff(
                        original_pretty.splitlines(keepends=True),
                        rebuilt_pretty.splitlines(keepends=True),
                        fromfile="original",
                        tofile="rebuilt",
                        lineterm="",
                    )
                )

                # Show first 50 lines of diff
                print("\nFirst 50 lines of diff:")
                for line in diff[:50]:
                    print(line.rstrip())

                if len(diff) > 50:
                    print(f"\n... ({len(diff) - 50} more lines)")

                return VERIFICATION_FAILED

    except Exception as e:
        log_error(f"Verification failed: {e}", code=VERIFICATION_FAILED)
        import traceback

        traceback.print_exc()
        return VERIFICATION_FAILED
