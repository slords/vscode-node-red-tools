"""
Centralized initialization for command dispatch

Handles config loading, credential resolution, authentication, and plugin loading.
"""

from pathlib import Path
import json
from .logging import log_error, log_info, log_warning
from .auth import resolve_credentials
from .plugin_loader import load_plugins


def initialize_system(args):
    """
    Centralized initialization and command dispatch: loads config, resolves credentials,
    authenticates (if needed), loads plugins, determines repo_root.

    Returns:
        tuple: (config, plugins_dict, credentials, repo_root) or (None, None, None, None) on failure
    """

    def parse_plugin_list(value: str):
        """Parse comma-separated plugin list from CLI argument"""
        if not value:
            return []
        return [name.strip() for name in value.split(",") if name.strip()]

    flows_path = Path(args.flows).resolve()
    config_path = (
        Path(args.config).resolve() if hasattr(args, "config") and args.config else None
    )
    repo_root = (
        Path(args.flows).parent.parent
        if Path(args.flows).parent.name == "flows"
        else Path.cwd()
    )

    # Load configuration
    config_filename = ".vscode-node-red-tools.json"
    config = None

    if config_path is not None:
        config_file = Path(config_path)
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                log_info(f"Using config from: {config_file}")
                config["_config_path"] = str(config_file.resolve())
            except Exception as e:
                log_warning(f"Failed to load config from {config_file}: {e}")
        else:
            log_warning(f"Config file not found: {config_file}")

    if config is None:
        # Search locations in priority order
        search_paths = [
            Path.cwd() / config_filename,
            Path.home() / config_filename,
            Path(__file__).parent.parent / config_filename,
        ]
        for config_file in search_paths:
            if config_file.exists():
                try:
                    with open(config_file, "r") as f:
                        config = json.load(f)
                    log_info(f"Using config from: {config_file}")
                    config["_config_path"] = str(config_file.resolve())
                    break
                except Exception as e:
                    log_warning(f"Failed to load config from {config_file}: {e}")

        if config is None:
            log_info("No config file found, using defaults")
            config = {
                "flows": "flows/flows.json",
                "src": "src",
                "plugins": {
                    "enabled": [],
                    "disabled": [],
                    "order": [],
                },
                "server": {
                    "url": "http://127.0.0.1:1880",
                    "username": None,
                    "password": None,
                    "token": None,
                    "tokenFile": None,
                    "verifySSL": True,
                },
                "_config_path": None,
            }

    # Resolve credentials
    credentials = resolve_credentials(args, config)
    if credentials is None:
        log_error("Failed to resolve credentials")
        return None, None, None, None

    # Check if this command needs server authentication
    needs_server = False
    if args.command == "watch":
        needs_server = True
    elif args.command == "diff" and (
        getattr(args, "source", None) == "server"
        or getattr(args, "target", None) == "server"
    ):
        needs_server = True

    # Authenticate if needed
    if needs_server:
        from .watcher_server import authenticate
        from .dashboard import WatchConfig

        # Create a minimal WatchConfig for authentication testing
        test_config = WatchConfig(args, flows_path, Path(args.src).resolve())

        if not authenticate(test_config, credentials):
            log_error("Failed to connect to Node-RED server")
            log_error(f"Server URL: {credentials.url}")
            log_error(f"Auth type: {credentials.auth_type}")
            return None, None, None, None

    # Load plugins
    enabled_override = (
        parse_plugin_list(getattr(args, "enable", None))
        if hasattr(args, "enable") and args.enable
        else None
    )
    disabled_override = (
        parse_plugin_list(getattr(args, "disable", None))
        if hasattr(args, "disable") and args.disable
        else None
    )

    plugins_dict = load_plugins(
        repo_root,
        config,
        enabled_override=enabled_override,
        disabled_override=disabled_override,
        quiet=False,
    )

    return config, plugins_dict, credentials, repo_root
