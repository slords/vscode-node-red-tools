"""
Configuration management for vscode-node-red-tools

Handles loading and validating the .vscode-node-red-tools.json configuration file.
"""

import json
import traceback
from pathlib import Path

from .logging import log_info, log_success, log_warning, log_error


def load_config(repo_root: Path, config_path: Path = None) -> dict:
    """Load configuration from .vscode-node-red-tools.json

    Searches for config file in the following order (unless config_path is specified):
    1. Specified config_path (if provided via --config flag)
    2. Current working directory (project-specific config)
    3. User's home directory (~/.vscode-node-red-tools.json)
    4. Tool installation directory (default config)

    Args:
        repo_root: Repository root directory (not used, kept for API compatibility)
        config_path: Optional explicit path to config file (overrides search)

    Returns:
        Configuration dictionary with default values for missing keys

    Notes:
        - First found config file is used
        - Returns default configuration if no config file found or has errors
    """
    config_filename = ".vscode-node-red-tools.json"

    # If explicit config path provided, use it exclusively
    if config_path is not None:
        config_file = Path(config_path)
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                log_info(f"Using config from: {config_file}")
                return config
            except Exception as e:
                log_warning(f"Failed to load config from {config_file}: {e}")
                # Fall through to defaults
        else:
            log_warning(f"Config file not found: {config_file}")
            # Fall through to defaults

    # Search locations in priority order
    search_paths = [
        Path.cwd() / config_filename,  # 1. Current working directory
        Path.home() / config_filename,  # 2. User home directory
        Path(__file__).parent.parent / config_filename,  # 3. Tool directory
    ]

    # Try each location
    for config_file in search_paths:
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                log_info(f"Using config from: {config_file}")
                return config
            except Exception as e:
                log_warning(f"Failed to load config from {config_file}: {e}")
                # Continue to next location

    # No config file found or all failed to load - return defaults
    log_info("No config file found, using defaults")
    return {
        "flows": "flows/flows.json",
        "src": "src",
        "plugins": {
            "enabled": [],  # Empty = all enabled
            "disabled": [],
            "order": [],  # Empty = use priority/filename
        },
        "watch": {"pollInterval": 1, "debounce": 2.0},
        "server": {
            "url": "http://127.0.0.1:1880",
            "username": None,
            "password": None,
            "token": None,
            "tokenFile": None,
            "verifySSL": True,
        },
    }


def validate_config(config_path: Path = None, repo_root: Path = None) -> int:
    """Validate configuration file

    Args:
        config_path: Path to specific config file (optional, will search standard locations)
        repo_root: Repository root (optional, will use cwd)

    Returns:
        Exit code (0 = valid, 1 = invalid)
    """
    try:
        # Determine paths
        if repo_root is None:
            repo_root = Path.cwd()

        log_info("Validating configuration...")
        errors = []
        warnings = []

        if config_path is None:
            # Search for config file in standard locations
            config_filename = ".vscode-node-red-tools.json"
            search_paths = [
                Path.cwd() / config_filename,
                Path.home() / config_filename,
                Path(__file__).parent.parent / config_filename,
            ]

            # Find first existing config
            config_path = None
            for path in search_paths:
                if path.exists():
                    config_path = path
                    break

            if config_path is None:
                log_info("✓ No config file found in standard locations")
                log_info("  Locations checked:")
                for path in search_paths:
                    log_info(f"    - {path}")
                log_info("  Using default configuration")
                config = load_config(repo_root, config_path=None)
            else:
                log_info(f"✓ Config file found: {config_path}")
                # Check JSON validity
                try:
                    with open(config_path, "r") as f:
                        config = json.load(f)
                    log_info("✓ Valid JSON format")
                except json.JSONDecodeError as e:
                    errors.append(f"Invalid JSON: {e}")
                    log_error(f"✗ Invalid JSON format: {e}")
                    return 1
                except Exception as e:
                    errors.append(f"Failed to read config: {e}")
                    log_error(f"✗ Failed to read config: {e}")
                    return 1
        else:
            # Specific config path provided
            if not config_path.exists():
                log_error(f"✗ Config file not found: {config_path}")
                return 1

            log_info(f"✓ Config file found: {config_path}")

            # Check JSON validity
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                log_info("✓ Valid JSON format")
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON: {e}")
                log_error(f"✗ Invalid JSON format: {e}")
                return 1
            except Exception as e:
                errors.append(f"Failed to read config: {e}")
                log_error(f"✗ Failed to read config: {e}")
                return 1

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

        # Validate watch section
        if "watch" in config:
            if not isinstance(config["watch"], dict):
                errors.append("'watch' must be an object")
            else:
                watch = config["watch"]

                # Check pollInterval
                if "pollInterval" in watch:
                    if not isinstance(watch["pollInterval"], (int, float)):
                        errors.append("'watch.pollInterval' must be a number")
                    elif watch["pollInterval"] <= 0:
                        errors.append("'watch.pollInterval' must be positive")
                    else:
                        log_info(
                            f"✓ watch.pollInterval is valid ({watch['pollInterval']}s)"
                        )

                # Check debounce
                if "debounce" in watch:
                    if not isinstance(watch["debounce"], (int, float)):
                        errors.append("'watch.debounce' must be a number")
                    elif watch["debounce"] < 0:
                        errors.append("'watch.debounce' must be non-negative")
                    else:
                        log_info(f"✓ watch.debounce is valid ({watch['debounce']}s)")

                # Check convergenceLimit
                if "convergenceLimit" in watch:
                    if not isinstance(watch["convergenceLimit"], int):
                        errors.append("'watch.convergenceLimit' must be an integer")
                    elif watch["convergenceLimit"] <= 0:
                        errors.append("'watch.convergenceLimit' must be positive")
                    else:
                        log_info(
                            f"✓ watch.convergenceLimit is valid ({watch['convergenceLimit']} cycles)"
                        )
                else:
                    # Import default and show it
                    from .constants import DEFAULT_CONVERGENCE_LIMIT

                    log_info(
                        f"✓ watch.convergenceLimit using default ({DEFAULT_CONVERGENCE_LIMIT} cycles)"
                    )

                # Check convergenceWindow
                if "convergenceWindow" in watch:
                    if not isinstance(watch["convergenceWindow"], (int, float)):
                        errors.append("'watch.convergenceWindow' must be a number")
                    elif watch["convergenceWindow"] <= 0:
                        errors.append("'watch.convergenceWindow' must be positive")
                    else:
                        log_info(
                            f"✓ watch.convergenceWindow is valid ({watch['convergenceWindow']}s)"
                        )
                else:
                    # Import default and show it
                    from .constants import DEFAULT_CONVERGENCE_WINDOW

                    log_info(
                        f"✓ watch.convergenceWindow using default ({DEFAULT_CONVERGENCE_WINDOW}s)"
                    )
        else:
            # No watch section - show defaults
            from .constants import DEFAULT_CONVERGENCE_LIMIT, DEFAULT_CONVERGENCE_WINDOW

            log_info("✓ watch section using defaults:")
            log_info(f"  - convergenceLimit: {DEFAULT_CONVERGENCE_LIMIT} cycles")
            log_info(f"  - convergenceWindow: {DEFAULT_CONVERGENCE_WINDOW}s")

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
                        warnings.append(
                            "Storing passwords in config file is insecure. Use NODERED_PASSWORD environment variable instead."
                        )
                        log_warning(
                            "⚠ server.password is set (insecure - use environment variable instead)"
                        )

                # Check token
                if "token" in server:
                    if server["token"] is not None and not isinstance(
                        server["token"], str
                    ):
                        errors.append("'server.token' must be a string or null")
                    elif server["token"]:
                        warnings.append(
                            "Storing tokens in config file is insecure. Use NODERED_TOKEN environment variable or token file instead."
                        )
                        log_warning(
                            "⚠ server.token is set (insecure - use environment variable or token file instead)"
                        )

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
        known_keys = {"flows", "src", "plugins", "watch", "backup", "server"}
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

    except Exception as e:
        log_error(f"Validation failed: {e}")
        traceback.print_exc()
        return 1
