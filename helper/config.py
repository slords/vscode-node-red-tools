"""
Configuration management for vscode-node-red-tools

Handles loading and validating the .vscode-node-red-tools.json configuration file.
"""

import json
import traceback
from pathlib import Path

from .logging import log_info, log_success, log_warning, log_error


def load_config(repo_root: Path) -> dict:
    """Load configuration from .vscode-node-red-tools.json (relative to this script)

    Args:
        repo_root: Repository root directory (not used, kept for API compatibility)

    Returns:
        Configuration dictionary with default values for missing keys

    Notes:
        - Config file lives with the tool (.vscode-node-red-tools.json), not the repo
        - Returns default configuration if file doesn't exist or has errors
    """
    # Config lives with the tool, not the repo
    script_dir = Path(__file__).parent.parent
    config_file = script_dir / ".vscode-node-red-tools.json"
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            log_warning(f"Failed to load config: {e}")

    # Default configuration
    return {
        "flows": "flows/flows.json",
        "src": "src",
        "plugins": {
            "enabled": [],  # Empty = all enabled
            "disabled": [],
            "order": [],  # Empty = use priority/filename
        },
        "watch": {"pollInterval": 1, "debounce": 2.0},
    }


def validate_config(config_path: Path = None, repo_root: Path = None) -> int:
    """Validate configuration file

    Args:
        config_path: Path to config file (optional, will auto-detect)
        repo_root: Repository root (optional, will use cwd)

    Returns:
        Exit code (0 = valid, 1 = invalid)
    """
    try:
        # Determine paths
        if repo_root is None:
            repo_root = Path.cwd()

        if config_path is None:
            # Config lives with the tool, not the repo
            script_dir = Path(__file__).parent.parent
            config_path = script_dir / ".vscode-node-red-tools.json"

        log_info("Validating configuration...")
        errors = []
        warnings = []

        # Check if config file exists
        if not config_path.exists():
            log_info(f"✓ No config file found at {config_path}")
            log_info("  Using default configuration")
            config = load_config(repo_root)
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

        # Check for unknown top-level keys
        known_keys = {"flows", "src", "plugins", "watch", "backup"}
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
