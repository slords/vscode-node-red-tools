"""
Centralized initialization for command dispatch

Handles config loading, credential resolution, authentication, and plugin loading.
"""

from pathlib import Path
import json
from .logging import log_error, log_info, log_warning
from .exit_codes import SERVER_CONNECTION_ERROR, CONFIG_ERROR

# Legacy credential resolution removed; ServerClient now handles all auth/path logic
from .plugin_loader import load_plugins
from .server_client import ServerClient


def initialize_system(args):
    """
    Centralized initialization and command dispatch: loads config, builds ServerClient,
    authenticates (if needed), loads plugins.

    Returns:
        tuple: (config, plugins_dict, server_client) or (None, None, None) on failure
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
                log_warning(
                    f"Failed to load config from {config_file}: {e}", code=CONFIG_ERROR
                )
        else:
            log_warning(f"Config file not found: {config_file}", code=CONFIG_ERROR)

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
                    log_warning(
                        f"Failed to load config from {config_file}: {e}",
                        code=CONFIG_ERROR,
                    )

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

    # Build ServerClient directly from args + config (auth + paths encapsulated)
    server_client = ServerClient(args, config)

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
        if not server_client.connect():
            log_error(
                "Failed to connect to Node-RED server", code=SERVER_CONNECTION_ERROR
            )
            log_error(f"Server URL: {server_client.url}")
            log_error(f"Auth type: {server_client.auth_type}")
            return None, None, None

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
        config,
        enabled_override=enabled_override,
        disabled_override=disabled_override,
        quiet=False,
    )

    # Return server_client in place of legacy credentials (call sites expecting .url/.auth_type still work)
    return config, plugins_dict, server_client
