"""
Configuration management for vscode-node-red-tools

Handles loading and validating the .vscode-node-red-tools.json configuration file.
"""

import json
import os
import traceback
from pathlib import Path

from .logging import log_info, log_success, log_warning, log_error, get_log_level, LogLevel
from .exit_codes import SUCCESS, CONFIG_ERROR, CONFIG_INVALID




def validate_config(config: dict, server_client=None, args=None) -> int:
    """Validate configuration structure and values with comprehensive reporting

    Args:
        config: Configuration dictionary to validate
        server_client: Optional ServerClient instance (for testing auth resolution)
        args: Optional CLI args to check for overrides

    Returns:
        Exit code (SUCCESS = valid, CONFIG_ERROR = invalid)
    """
    # Determine paths
    repo_root = Path.cwd()

    # Helper function to get value source
    def get_value_source(cli_value, env_var_name, config_value, default_value):
        """Determine the source and effective value for a configuration item"""
        if cli_value is not None:
            return cli_value, "CLI arg"
        if env_var_name and os.environ.get(env_var_name):
            return os.environ.get(env_var_name), f"env var ({env_var_name})"
        if config_value is not None:
            return config_value, "config file"
        return default_value, "default"

    # ========================================================================
    # SECTION 1: CONFIGURATION REPORT
    # ========================================================================
    log_info("=" * 70)
    log_info("CONFIGURATION REPORT")
    log_info("=" * 70)

    # Configuration file location
    config_path = config.get("_config_path")
    if config_path:
        log_info(f"\nConfiguration file: {config_path}")
    else:
        log_info("\nConfiguration file: None (using defaults)")

    # --- Core Paths Section ---
    log_info("\n" + "-" * 70)
    log_info("CORE PATHS")
    log_info("-" * 70)

    # Flows path
    flows_cli = getattr(args, "flows", None) if args else None
    flows_config = config.get("flows")
    flows_default = "flows/flows.json"
    flows_value, flows_source = get_value_source(flows_cli, None, flows_config, flows_default)
    log_info(f"flows: {flows_value}")
    log_info(f"  Source: {flows_source}")
    flows_path = repo_root / flows_value
    log_info(f"  Resolved: {flows_path}")
    log_info(f"  Exists: {'Yes' if flows_path.exists() else 'No'}")

    # Src path
    src_cli = getattr(args, "src", None) if args else None
    src_config = config.get("src")
    src_default = "src"
    src_value, src_source = get_value_source(src_cli, None, src_config, src_default)
    log_info(f"\nsrc: {src_value}")
    log_info(f"  Source: {src_source}")
    src_path = repo_root / src_value
    log_info(f"  Resolved: {src_path}")
    log_info(f"  Exists: {'Yes' if src_path.exists() else 'No'}")

    # --- Logging Section ---
    log_info("\n" + "-" * 70)
    log_info("LOGGING")
    log_info("-" * 70)

    current_level = get_log_level()
    level_names = {LogLevel.DEBUG: "DEBUG", LogLevel.INFO: "INFO", LogLevel.WARNING: "WARNING", LogLevel.ERROR: "ERROR"}
    log_info(f"Current level: {level_names.get(current_level, 'UNKNOWN')}")

    # Determine logging source
    log_level_cli = getattr(args, "log_level", None) if args else None
    quiet_cli = getattr(args, "quiet", False) if args else False
    verbose_cli = getattr(args, "verbose", False) if args else False
    env_log_level = os.environ.get("NODERED_TOOLS_LOG_LEVEL")

    if log_level_cli:
        log_info(f"  Source: CLI arg (--log-level={log_level_cli})")
    elif quiet_cli:
        log_info("  Source: CLI arg (--quiet)")
    elif verbose_cli:
        log_info("  Source: CLI arg (--verbose)")
    elif env_log_level:
        log_info(f"  Source: env var (NODERED_TOOLS_LOG_LEVEL={env_log_level})")
    else:
        log_info("  Source: default")

    # --- Plugins Section ---
    log_info("\n" + "-" * 70)
    log_info("PLUGINS")
    log_info("-" * 70)

    plugins_config = config.get("plugins", {})

    # Enabled plugins
    enabled_cli = getattr(args, "enable", None) if args else None
    enabled_config = plugins_config.get("enabled", [])
    if enabled_cli:
        enabled_list = [p.strip() for p in enabled_cli.split(",") if p.strip()]
        log_info(f"enabled: {enabled_list}")
        log_info(f"  Source: CLI arg (--enable)")
    elif enabled_config:
        log_info(f"enabled: {enabled_config}")
        log_info(f"  Source: config file")
    else:
        log_info("enabled: []")
        log_info("  Source: default")

    # Disabled plugins
    disabled_cli = getattr(args, "disable", None) if args else None
    disabled_config = plugins_config.get("disabled", [])
    if disabled_cli:
        disabled_list = [p.strip() for p in disabled_cli.split(",") if p.strip()]
        log_info(f"\ndisabled: {disabled_list}")
        log_info(f"  Source: CLI arg (--disable)")
    elif disabled_config:
        log_info(f"\ndisabled: {disabled_config}")
        log_info(f"  Source: config file")
    else:
        log_info("\ndisabled: []")
        log_info("  Source: default")

    # Order plugins
    order_config = plugins_config.get("order", [])
    if order_config:
        log_info(f"\norder: {order_config}")
        log_info(f"  Source: config file")
    else:
        log_info("\norder: []")
        log_info("  Source: default")

    # --- Server Configuration Section ---
    log_info("\n" + "-" * 70)
    log_info("SERVER CONFIGURATION")
    log_info("-" * 70)

    server_config = config.get("server", {})

    # URL
    url_cli = getattr(args, "server", None) if args else None
    url_config = server_config.get("url")
    url_default = "http://127.0.0.1:1880"
    url_value, url_source = get_value_source(url_cli, None, url_config, url_default)
    log_info(f"url: {url_value}")
    log_info(f"  Source: {url_source}")

    # Username
    username_cli = getattr(args, "username", None) if args else None
    username_config = server_config.get("username")
    username_value, username_source = get_value_source(username_cli, "NODERED_USERNAME", username_config, None)
    if username_value:
        log_info(f"\nusername: {username_value}")
        log_info(f"  Source: {username_source}")
    else:
        log_info(f"\nusername: None")
        log_info(f"  Source: not configured")

    # Password
    password_cli = getattr(args, "password", None) if args else None
    password_config = server_config.get("password")
    password_env = os.environ.get("NODERED_PASSWORD")

    if password_cli:
        log_info(f"\npassword: [REDACTED]")
        log_info(f"  Source: CLI arg")
        log_warning(f"  WARNING: Password via CLI is visible in shell history!", code=CONFIG_INVALID)
    elif password_env:
        log_info(f"\npassword: [REDACTED]")
        log_info(f"  Source: env var (NODERED_PASSWORD)")
    elif password_config:
        log_info(f"\npassword: [REDACTED]")
        log_info(f"  Source: config file")
    else:
        log_info(f"\npassword: None")
        log_info(f"  Source: not configured (will prompt if username is set)")

    # Token
    token_cli = getattr(args, "token", None) if args else None
    token_config = server_config.get("token")
    token_env = os.environ.get("NODERED_TOKEN")

    if token_cli:
        log_info(f"\ntoken: [REDACTED]")
        log_info(f"  Source: CLI arg")
        log_warning(f"  WARNING: Token via CLI is visible in shell history!", code=CONFIG_INVALID)
    elif token_env:
        log_info(f"\ntoken: [REDACTED]")
        log_info(f"  Source: env var (NODERED_TOKEN)")
    elif token_config:
        log_info(f"\ntoken: [REDACTED]")
        log_info(f"  Source: config file")
    else:
        log_info(f"\ntoken: None")
        log_info(f"  Source: not configured")

    # Token File
    token_file_cli = getattr(args, "token_file", None) if args else None
    token_file_config = server_config.get("tokenFile")

    if token_file_cli:
        log_info(f"\ntokenFile: {token_file_cli}")
        log_info(f"  Source: CLI arg")
        token_file_path = Path(token_file_cli).expanduser()
        log_info(f"  Resolved: {token_file_path}")
        log_info(f"  Exists: {'Yes' if token_file_path.exists() else 'No'}")
    elif token_file_config:
        log_info(f"\ntokenFile: {token_file_config}")
        log_info(f"  Source: config file")
        token_file_path = Path(token_file_config).expanduser()
        log_info(f"  Resolved: {token_file_path}")
        log_info(f"  Exists: {'Yes' if token_file_path.exists() else 'No'}")
    else:
        log_info(f"\ntokenFile: None")
        log_info(f"  Source: not configured")

    # Verify SSL
    no_verify_ssl_cli = getattr(args, "no_verify_ssl", False) if args else False
    verify_ssl_config = server_config.get("verifySSL", True)

    if no_verify_ssl_cli:
        log_info(f"\nverifySSL: False")
        log_info(f"  Source: CLI arg (--no-verify-ssl)")
        log_warning(f"  WARNING: SSL verification disabled!", code=CONFIG_INVALID)
    elif not verify_ssl_config:
        log_info(f"\nverifySSL: False")
        log_info(f"  Source: config file")
        log_warning(f"  WARNING: SSL verification disabled!", code=CONFIG_INVALID)
    else:
        log_info(f"\nverifySSL: True")
        log_info(f"  Source: {'config file' if 'verifySSL' in server_config else 'default'}")

    # --- Resolved Authentication Section ---
    if server_client:
        log_info("\n" + "-" * 70)
        log_info("RESOLVED AUTHENTICATION")
        log_info("-" * 70)
        log_info(f"Server URL: {server_client.url}")
        log_info(f"Auth Type: {server_client.auth_type}")
        log_info(f"Verify SSL: {server_client.verify_ssl}")

        if server_client.auth_type == "bearer":
            log_info(f"Token: [REDACTED]")
        elif server_client.auth_type == "basic":
            log_info(f"Username: {server_client.username}")
            log_info(f"Password: [REDACTED]")
        else:
            log_info("Authentication: None (anonymous access)")


    # ========================================================================
    # SECTION 2: VALIDATION (Existing Logic)
    # ========================================================================
    log_info("\n" + "=" * 70)
    log_info("VALIDATION RESULTS")
    log_info("=" * 70)

    errors = []
    warnings = []

    # Validate structure
    if not isinstance(config, dict):
        errors.append("Config must be a JSON object")
        log_error("✗ Config must be a JSON object", code=CONFIG_INVALID)
    else:
        log_info("\n✓ Valid config structure")

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
                    log_warning(f"⚠ Flows path does not exist: {config['flows']}", code=CONFIG_INVALID)

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
                    log_warning(f"⚠ Source path does not exist: {config['src']}", code=CONFIG_INVALID)

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
                        "(now constants - see helper/constants.py)",
                        code=CONFIG_INVALID
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
                                    f"⚠ Token file does not exist: {server['tokenFile']}",
                                    code=CONFIG_INVALID
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
            log_warning(f"⚠ Unknown config keys: {', '.join(unknown_keys)}", code=CONFIG_INVALID)

        # Summary
        log_info("\n" + "=" * 70)
        if errors:
            log_error(f"✗ Configuration is invalid ({len(errors)} error(s))", code=CONFIG_INVALID)
            for error in errors:
                log_error(f"  - {error}", code=CONFIG_INVALID)
            log_info("=" * 70)
            return CONFIG_ERROR

        if warnings:
            log_success(f"✓ Configuration is valid (with {len(warnings)} warning(s))")
        else:
            log_success("✓ Configuration is valid")
        log_info("=" * 70)

        return SUCCESS

