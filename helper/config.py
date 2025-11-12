"""
Configuration management for vscode-node-red-tools

Handles loading and validating the .vscode-node-red-tools.json configuration file.
"""

import json
import traceback
from pathlib import Path

from .logging import log_info, log_success, log_warning, log_error




def validate_config(config: dict, server_client=None) -> int:
    """Validate configuration structure and values

    Args:
        config: Configuration dictionary to validate
        server_client: Optional ServerClient instance (for testing auth resolution)

    Returns:
        Exit code (0 = valid, 1 = invalid)
    """
    # Helper: recursively display config values and their sources
    def display_config_with_sources(config, defaults, prefix=""):
        for key in sorted(defaults.keys()):
            val = config.get(key, None)
            default_val = defaults[key]
            if isinstance(default_val, dict):
                log_info(f"{prefix}{key}:")
                display_config_with_sources(val or {}, default_val, prefix + "  ")
            else:
                if key in config:
                    source = "config file"
                else:
                    source = "default"
                log_info(f"{prefix}{key}: {val!r}  [source: {source}]")

    # Determine paths
    repo_root = Path.cwd()

    log_info("Validating configuration...")
    errors = []
    warnings = []

    # Validate structure
    if not isinstance(config, dict):
        errors.append("Config must be a JSON object")
        log_error("✗ Config must be a JSON object")
    else:
        log_info("✓ Valid config structure")

        # Validate flows path
        if "flows" in config:
            if not isinstance(config["flows"], str):
                errors.append("'flows' must be a string path")
            else:
                flows_path = repo_root / config["flows"]
                if flows_path.exists():
                    log_info(f"✓ Flows path exists: {config['flows']}")
                else:
                    warnings.append(f"Flows path does not exist: {config['flows']}")
                    log_warning(f"⚠ Flows path does not exist: {config['flows']}")

        # Validate src path
        if "src" in config:
            if not isinstance(config["src"], str):
                errors.append("'src' must be a string path")
            else:
                src_path = repo_root / config["src"]
                if src_path.exists():
                    log_info(f"✓ Source path exists: {config['src']}")
                else:
                    warnings.append(f"Source path does not exist: {config['src']}")
                    log_warning(f"⚠ Source path does not exist: {config['src']}")

        # Validate plugins section
        if "plugins" in config:
            if not isinstance(config["plugins"], dict):
                errors.append("'plugins' must be an object")
            else:
                plugins = config["plugins"]

                # Check enabled
                if "enabled" in plugins:
                    if not isinstance(plugins["enabled"], list):
                        errors.append("'plugins.enabled' must be an array")
                    elif all(isinstance(p, str) for p in plugins["enabled"]):
                        log_info(
                            f"✓ plugins.enabled is valid ({len(plugins['enabled'])} plugins)"
                        )
                    else:
                        errors.append("'plugins.enabled' must contain only strings")

                # Check disabled
                if "disabled" in plugins:
                    if not isinstance(plugins["disabled"], list):
                        errors.append("'plugins.disabled' must be an array")
                    elif all(isinstance(p, str) for p in plugins["disabled"]):
                        log_info(
                            f"✓ plugins.disabled is valid ({len(plugins['disabled'])} plugins)"
                        )
                    else:
                        errors.append("'plugins.disabled' must contain only strings")

                # Check order
                if "order" in plugins:
                    if not isinstance(plugins["order"], list):
                        errors.append("'plugins.order' must be an array")
                    elif all(isinstance(p, str) for p in plugins["order"]):
                        log_info(
                            f"✓ plugins.order is valid ({len(plugins['order'])} plugins)"
                        )
                    else:
                        errors.append("'plugins.order' must contain only strings")

        # Validate watch section (if present, warn user these are no longer used)
        if "watch" in config:
            if not isinstance(config["watch"], dict):
                errors.append("'watch' must be an object")
            else:
                watch = config["watch"]

                # Warn about deprecated settings
                deprecated_watch_settings = ["pollInterval", "debounce", "convergenceLimit", "convergenceWindow"]
                found_deprecated = [key for key in deprecated_watch_settings if key in watch]

                if found_deprecated:
                    warnings.append(
                        f"watch.{', watch.'.join(found_deprecated)} are no longer configurable - "
                        "these are runtime constants. Modify helper/constants.py to change these values."
                    )
                    log_warning(
                        f"⚠ watch.{', watch.'.join(found_deprecated)} settings ignored "
                        "(now constants - see helper/constants.py)"
                    )

        # Validate server section
        if "server" in config:
            if not isinstance(config["server"], dict):
                errors.append("'server' must be an object")
            else:
                server = config["server"]

                # Check url
                if "url" in server:
                    if not isinstance(server["url"], str):
                        errors.append("'server.url' must be a string")
                    else:
                        log_info(f"✓ server.url is valid: {server['url']}")

                # Check username
                if "username" in server:
                    if server["username"] is not None and not isinstance(
                        server["username"], str
                    ):
                        errors.append("'server.username' must be a string or null")
                    elif server["username"]:
                        log_info(f"✓ server.username is set")

                # Check password
                if "password" in server:
                    if server["password"] is not None and not isinstance(
                        server["password"], str
                    ):
                        errors.append("'server.password' must be a string or null")
                    elif server["password"]:
                        log_info("✓ server.password is set")

                # Check token
                if "token" in server:
                    if server["token"] is not None and not isinstance(
                        server["token"], str
                    ):
                        errors.append("'server.token' must be a string or null")
                    elif server["token"]:
                        log_info("✓ server.token is set")

                # Check tokenFile
                if "tokenFile" in server:
                    if server["tokenFile"] is not None:
                        if not isinstance(server["tokenFile"], str):
                            errors.append("'server.tokenFile' must be a string or null")
                        else:
                            token_file_path = Path(server["tokenFile"]).expanduser()
                            if token_file_path.exists():
                                log_info(f"✓ server.tokenFile exists: {server['tokenFile']}")
                            else:
                                warnings.append(
                                    f"Token file does not exist: {server['tokenFile']}"
                                )
                                log_warning(
                                    f"⚠ Token file does not exist: {server['tokenFile']}"
                                )

                # Check verifySSL
                if "verifySSL" in server:
                    if not isinstance(server["verifySSL"], bool):
                        errors.append("'server.verifySSL' must be a boolean")
                    else:
                        log_info(
                            f"✓ server.verifySSL is valid ({server['verifySSL']})"
                        )

        # Check for unknown top-level keys
        known_keys = {"flows", "src", "plugins", "watch", "backup", "server", "_config_path"}
        unknown_keys = set(config.keys()) - known_keys
        if unknown_keys:
            warnings.append(
                f"Unknown config keys (will be ignored): {', '.join(unknown_keys)}"
            )
            log_warning(f"⚠ Unknown config keys: {', '.join(unknown_keys)}")

        # Summary
        if errors:
            log_error(f"\n✗ Configuration is invalid ({len(errors)} error(s))")
            for error in errors:
                log_error(f"  - {error}")
            return 1

        if warnings:
            log_success(f"\n✓ Configuration is valid (with {len(warnings)} warning(s))")
        else:
            log_success("\n✓ Configuration is valid")

        return 0

