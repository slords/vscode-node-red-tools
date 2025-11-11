#!/usr/bin/env python3
"""
vscode-node-red-tools.py - Unified Node-RED development tool

Combines explode, rebuild, and watch functionality into a single tool
with plugin support for extensibility.

Usage:
    # Explode flows to source files
    python vscode-node-red-tools.py explode flows/flows.json

    # Rebuild flows from source files
    python vscode-node-red-tools.py rebuild flows/flows.json

    # Watch mode (bidirectional sync)
    python vscode-node-red-tools.py watch --server https://server:1880 --username admin --password pass
"""

__version__ = "2.0.0"

import argparse
import difflib
import json
import sys
import tempfile
import time
import importlib.util
from pathlib import Path
from typing import List

# Import from helper modules
from helper import (
    # Logging
    log_error,
    # Config
    validate_config,
    # Rebuild
    rebuild_flows,
    # Explode
    explode_flows,
    # Diff
    diff_flows,
    # Watcher
    WATCH_AVAILABLE,
    watch_mode,
)

# Import command implementations
from helper.commands import (
    stats_command,
    benchmark_command,
    verify_flows,
)

from helper.commands_plugin import (
    new_plugin_command,
    list_plugins_command,
)

# Import constants
from helper import DEFAULT_POLL_INTERVAL

# CLI-specific constant (not in helper/constants.py as it's CLI-only)
DEFAULT_DEBOUNCE = 2.0  # seconds


# ============================================================================
# Helper Functions
# ============================================================================


def parse_plugin_list(value: str) -> List[str]:
    """Parse comma-separated plugin list from CLI argument

    Args:
        value: Comma-separated string like "plugin1,plugin2" or "all"

    Returns:
        List of plugin names, with whitespace stripped
    """
    if not value:
        return []
    return [name.strip() for name in value.split(",") if name.strip()]


def preload_plugins(args, repo_root: Path = None):
    """Preload plugins once for all commands

    Args:
        args: Parsed command line arguments
        repo_root: Repository root (inferred from flows path if not provided)

    Returns:
        tuple: (plugins_dict, plugin_config, repo_root)
    """
    from helper import load_config, load_plugins

    # Infer repo root from flows path if not provided
    if repo_root is None:
        flows_path = Path(args.flows)
        repo_root = (
            flows_path.parent.parent
            if flows_path.parent.name == "flows"
            else Path.cwd()
        )

    # Load config
    config_path = Path(args.config).resolve() if hasattr(args, 'config') and args.config else None
    plugin_config = load_config(repo_root, config_path)

    # Parse enable/disable lists
    enabled_override = parse_plugin_list(args.enable) if args.enable else None
    disabled_override = parse_plugin_list(args.disable) if args.disable else None

    # Load plugins
    plugins_dict = load_plugins(
        repo_root,
        plugin_config,
        enabled_override=enabled_override,
        disabled_override=disabled_override,
        quiet=False,  # Show plugins on first load
    )

    return (plugins_dict, plugin_config, repo_root)


# ============================================================================
# Main CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Unified Node-RED development tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"vscode-node-red-tools {__version__}",
    )

    # Global options (apply to all commands)
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config file (overrides standard locations)",
    )
    parser.add_argument(
        "--flows",
        default="flows/flows.json",
        help="Path to flows.json file (default: flows/flows.json)",
    )
    parser.add_argument(
        "--src",
        default="src",
        help="Path to source directory (default: src)",
    )

    # Global plugin control options
    parser.add_argument(
        "--enable",
        type=str,
        help="Comma-separated list of plugins to enable, or 'all' (overrides config)",
    )
    parser.add_argument(
        "--disable",
        type=str,
        help="Comma-separated list of plugins to disable, or 'all' to disable all",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Explode command
    explode_parser = subparsers.add_parser(
        "explode", help="Explode flows.json into source files"
    )
    explode_parser.add_argument(
        "--backup",
        action="store_true",
        help="Create timestamped backup before exploding",
    )
    explode_parser.add_argument(
        "--delete-orphaned",
        action="store_true",
        help="Delete orphaned files instead of moving to .orphaned/",
    )
    explode_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes",
    )

    # Rebuild command
    rebuild_parser = subparsers.add_parser(
        "rebuild", help="Rebuild flows.json from source files"
    )
    rebuild_parser.add_argument(
        "--backup",
        action="store_true",
        help="Create timestamped backup before rebuilding",
    )
    rebuild_parser.add_argument(
        "--orphan-new",
        action="store_true",
        help="Move new files (not in skeleton) to .orphaned/",
    )
    rebuild_parser.add_argument(
        "--delete-new", action="store_true", help="Delete new files (not in skeleton)"
    )
    rebuild_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )

    # Verify command
    verify_parser = subparsers.add_parser(
        "verify", help="Verify round-trip stability (explode → rebuild → compare)"
    )

    # List-plugins command
    list_plugins_parser = subparsers.add_parser(
        "list-plugins", help="List all available plugins with status and priority"
    )

    # Diff command
    diff_parser = subparsers.add_parser(
        "diff",
        help="Compare src, flow, or server",
        epilog="Security: Use NODERED_PASSWORD or NODERED_TOKEN environment variables instead of CLI parameters. "
        "Token files: ./.nodered-token or ~/.nodered-token",
    )
    diff_parser.add_argument(
        "source", choices=["src", "flow", "server"], help="Source to compare from"
    )
    diff_parser.add_argument(
        "target", choices=["src", "flow", "server"], help="Target to compare to"
    )
    diff_parser.add_argument(
        "--server",
        help="Node-RED server URL (default: http://127.0.0.1:1880 for server comparisons)",
    )
    diff_parser.add_argument(
        "--username",
        help="Node-RED username (for basic auth)",
    )
    diff_parser.add_argument(
        "--password",
        help="Node-RED password (INSECURE - use NODERED_PASSWORD env var instead)",
    )
    diff_parser.add_argument(
        "--token",
        help="Bearer token (INSECURE - use NODERED_TOKEN env var or token file instead)",
    )
    diff_parser.add_argument(
        "--token-file",
        help="Path to file containing bearer token",
    )
    diff_parser.add_argument(
        "--no-verify-ssl", action="store_true", help="Disable SSL verification"
    )
    diff_parser.add_argument(
        "--bcomp", action="store_true", help="Launch Beyond Compare for visual diff"
    )
    diff_parser.add_argument(
        "-C",
        "--context",
        type=int,
        default=3,
        help="Number of context lines to show in unified diff (default: 3)",
    )

    # Watch command
    watch_parser = subparsers.add_parser(
        "watch",
        help="Watch mode - bidirectional sync",
        epilog="Security: Use NODERED_PASSWORD or NODERED_TOKEN environment variables instead of CLI parameters. "
        "Token files: ./.nodered-token or ~/.nodered-token",
    )
    watch_parser.add_argument(
        "--server",
        help="Node-RED server URL (default: http://127.0.0.1:1880)",
    )
    watch_parser.add_argument(
        "--username",
        help="Node-RED username (for basic auth)",
    )
    watch_parser.add_argument(
        "--password",
        help="Node-RED password (INSECURE - use NODERED_PASSWORD env var instead)",
    )
    watch_parser.add_argument(
        "--token",
        help="Bearer token (INSECURE - use NODERED_TOKEN env var or token file instead)",
    )
    watch_parser.add_argument(
        "--token-file",
        help="Path to file containing bearer token",
    )
    watch_parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL})",
    )
    watch_parser.add_argument(
        "--debounce",
        type=float,
        default=DEFAULT_DEBOUNCE,
        help=f"Debounce time in seconds for local file changes (default: {DEFAULT_DEBOUNCE})",
    )
    watch_parser.add_argument(
        "--no-verify-ssl", action="store_true", help="Disable SSL verification"
    )
    watch_parser.add_argument(
        "--dashboard", action="store_true", help="Enable visual dashboard mode"
    )

    # Stats command
    stats_parser = subparsers.add_parser(
        "stats", help="Display comprehensive flow and source statistics"
    )

    # Benchmark command
    benchmark_parser = subparsers.add_parser(
        "benchmark", help="Benchmark explode and rebuild performance"
    )
    benchmark_parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=3,
        help="Number of iterations (default: 3)",
    )

    # New-plugin command
    new_plugin_parser = subparsers.add_parser(
        "new-plugin", help="Generate a new plugin scaffold"
    )
    new_plugin_parser.add_argument("name", help="Plugin name (e.g., MyPlugin)")
    new_plugin_parser.add_argument(
        "type",
        choices=[
            "pre-explode",
            "explode",
            "post-explode",
            "pre-rebuild",
            "post-rebuild",
        ],
        help="Plugin type",
    )
    new_plugin_parser.add_argument(
        "--priority",
        "-p",
        type=int,
        help="Plugin priority (default: auto based on type)",
    )

    # Validate-config command
    validate_config_parser = subparsers.add_parser(
        "validate-config",
        help="Validate configuration file and test credential resolution",
    )
    validate_config_parser.add_argument(
        "--test-auth",
        action="store_true",
        help="Test authentication credential resolution",
    )

    # Enable shell completion if argcomplete is available
    try:
        import argcomplete

        argcomplete.autocomplete(parser)
    except ImportError:
        pass  # Shell completion is optional

    args = parser.parse_args()

    try:
        # Commands that don't need plugins
        if args.command == "validate-config":
            config_path = Path(args.config).resolve() if args.config else None
            return validate_config(config_path)

        elif args.command == "new-plugin":
            priority = args.priority if hasattr(args, "priority") else None
            return new_plugin_command(args.name, args.type, priority)

        # All other commands need plugins - preload them once
        plugins_dict, plugin_config, repo_root = preload_plugins(args)

        if args.command == "list-plugins":
            return list_plugins_command(repo_root, plugins_dict, plugin_config)

        elif args.command == "watch":
            # Watch mode uses preloaded plugins
            flows_path = Path(args.flows).resolve()
            src_path = Path(args.src).resolve()
            return watch_mode(
                args,
                flows_path,
                src_path,
                plugins_dict=plugins_dict,
                plugin_config=plugin_config,
                repo_root=repo_root,
            )

        if args.command == "explode":
            flows_path = Path(args.flows).resolve()
            src_path = Path(args.src).resolve()

            return explode_flows(
                flows_path,
                src_path,
                backup=args.backup,
                delete_orphaned=args.delete_orphaned,
                dry_run=args.dry_run,
                plugins_dict=plugins_dict,
                repo_root=repo_root,
            )

        elif args.command == "rebuild":
            flows_path = Path(args.flows).resolve()
            src_path = Path(args.src).resolve()

            return rebuild_flows(
                flows_path,
                src_path,
                backup=args.backup,
                orphan_new=args.orphan_new,
                delete_new=args.delete_new,
                dry_run=args.dry_run,
                plugins_dict=plugins_dict,
                repo_root=repo_root,
            )

        elif args.command == "verify":
            flows_path = Path(args.flows).resolve()

            return verify_flows(
                flows_path,
                plugins_dict=plugins_dict,
                plugin_config=plugin_config,
                repo_root=repo_root,
            )

        elif args.command == "diff":
            flows_path = Path(args.flows).resolve()
            src_path = Path(args.src).resolve()
            verify_ssl = not args.no_verify_ssl

            return diff_flows(
                args.source,
                args.target,
                flows_path,
                src_path,
                args.server,
                args.username,
                args.password,
                verify_ssl,
                args.bcomp,
                plugins_dict=plugins_dict,
                repo_root=repo_root,
                context=args.context,
            )

        elif args.command == "stats":
            flows_path = Path(args.flows).resolve()
            src_path = Path(args.src).resolve()

            return stats_command(
                flows_path,
                src_path,
                plugins_dict=plugins_dict,
                plugin_config=plugin_config,
                repo_root=repo_root,
            )

        elif args.command == "benchmark":
            flows_path = Path(args.flows).resolve()
            src_path = Path(args.src).resolve()

            return benchmark_command(
                flows_path,
                src_path,
                plugins_dict=plugins_dict,
                plugin_config=plugin_config,
                repo_root=repo_root,
                iterations=args.iterations,
            )

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 1
    except Exception as e:
        log_error(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
