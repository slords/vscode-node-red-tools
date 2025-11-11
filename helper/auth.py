"""
Authentication and credential resolution for Node-RED server connections

Handles secure credential resolution from multiple sources with priority ordering.
"""

import os
import getpass
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

from .logging import log_info, log_warning, log_error


@dataclass
class ServerCredentials:
    """Resolved server credentials"""

    url: str
    auth_type: str  # 'none', 'basic', 'bearer'
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    verify_ssl: bool = True


def read_token_file(token_file_path: Path) -> Optional[str]:
    """Read token from file, stripping whitespace

    Args:
        token_file_path: Path to token file

    Returns:
        Token string or None if file doesn't exist or is empty
    """
    try:
        if token_file_path.exists():
            token = token_file_path.read_text().strip()
            if token:
                log_info(f"Loaded token from: {token_file_path}")
                return token
    except Exception as e:
        log_warning(f"Failed to read token file {token_file_path}: {e}")
    return None


def find_token_file() -> Optional[str]:
    """Search standard locations for token file

    Searches in priority order:
    1. ./.nodered-token (current directory)
    2. ~/.nodered-token (user home)

    Returns:
        Token string or None if not found
    """
    search_paths = [
        Path.cwd() / ".nodered-token",
        Path.home() / ".nodered-token",
    ]

    for path in search_paths:
        token = read_token_file(path)
        if token:
            return token

    return None


def resolve_password(
    password_param: Optional[str],
    password_config: Optional[str],
    username: str,
    show_param_warning: bool = True,
) -> Optional[str]:
    """Resolve password from multiple sources

    Priority order:
    1. CLI parameter (with warning)
    2. Config file
    3. NODERED_PASSWORD environment variable
    4. Secure prompt

    Args:
        password_param: Password from CLI parameter
        password_config: Password from config file
        username: Username (for prompt message)
        show_param_warning: Whether to show warning for CLI parameter

    Returns:
        Resolved password or None
    """
    # 1. CLI parameter (with warning)
    if password_param:
        if show_param_warning:
            log_warning(
                "⚠️  WARNING: Passing password via CLI parameter is insecure. "
                "Use NODERED_PASSWORD environment variable instead."
            )
        return password_param

    # 2. Config file
    if password_config:
        log_info("Using password from config file")
        return password_config

    # 3. Environment variable
    env_password = os.environ.get("NODERED_PASSWORD")
    if env_password:
        log_info("Using password from NODERED_PASSWORD environment variable")
        return env_password

    # 4. Secure prompt
    try:
        log_info(f"Password required for user '{username}'")
        password = getpass.getpass(f"Enter password for '{username}': ")
        if password:
            return password
    except (KeyboardInterrupt, EOFError):
        log_error("Password input cancelled")
        return None

    return None


def resolve_credentials(
    # CLI parameters
    server_param: Optional[str],
    username_param: Optional[str],
    password_param: Optional[str],
    token_param: Optional[str],
    token_file_param: Optional[str],
    verify_ssl_param: bool,
    # Config
    config: dict,
) -> Optional[ServerCredentials]:
    """Resolve server credentials from all sources

    Priority order for authentication:
    1. --token-file parameter
    2. --token parameter
    3. --username/--password parameters
    4. config.server.tokenFile
    5. config.server.token
    6. config.server.username/password
    7. Token file search (./.nodered-token, ~/.nodered-token)
    8. NODERED_TOKEN environment variable
    9. No authentication (local mode)

    Args:
        server_param: Server URL from CLI
        username_param: Username from CLI
        password_param: Password from CLI
        token_param: Token from CLI
        token_file_param: Token file path from CLI
        verify_ssl_param: Whether to verify SSL
        config: Configuration dictionary

    Returns:
        ServerCredentials or None if resolution fails
    """
    # Get server URL (parameter > config > default)
    server_url = server_param
    if not server_url:
        server_config = config.get("server", {})
        server_url = server_config.get("url", "http://127.0.0.1:1880")

    log_info(f"Server URL: {server_url}")

    # Get SSL verification setting (parameter overrides config)
    server_config = config.get("server", {})
    verify_ssl = verify_ssl_param
    if not verify_ssl and "verifySSL" in server_config:
        verify_ssl = server_config.get("verifySSL", True)

    # =========================================================================
    # Token Resolution Chain
    # =========================================================================

    token = None
    token_source = None

    # 1. --token-file parameter
    if token_file_param:
        token_path = Path(token_file_param)
        token = read_token_file(token_path)
        if token:
            token_source = "parameter (--token-file)"
            log_warning(
                "⚠️  WARNING: Passing token file via CLI parameter is insecure. "
                "Use config file or standard token file locations instead."
            )

    # 2. --token parameter
    if not token and token_param:
        token = token_param
        token_source = "parameter (--token)"
        log_warning(
            "⚠️  WARNING: Passing token via CLI parameter is insecure. "
            "Use NODERED_TOKEN environment variable or token file instead."
        )

    # 3. Check if we have username from parameter (skip to username/password auth)
    has_param_username = username_param is not None

    # 4. config.server.tokenFile
    if not token and not has_param_username:
        token_file_config = server_config.get("tokenFile")
        if token_file_config:
            token_path = Path(token_file_config)
            token = read_token_file(token_path)
            if token:
                token_source = "config (tokenFile)"

    # 5. config.server.token
    if not token and not has_param_username:
        token_config = server_config.get("token")
        if token_config:
            token = token_config
            token_source = "config (token)"
            log_info("Using token from config file")

    # 6. Check if we have username from config (skip to username/password auth)
    has_config_username = server_config.get("username") is not None

    # 7. Token file search
    if not token and not has_param_username and not has_config_username:
        token = find_token_file()
        if token:
            token_source = "token file"

    # 8. NODERED_TOKEN environment variable
    if not token and not has_param_username and not has_config_username:
        env_token = os.environ.get("NODERED_TOKEN")
        if env_token:
            token = env_token
            token_source = "NODERED_TOKEN environment variable"
            log_info("Using token from NODERED_TOKEN environment variable")

    # If we found a token, use bearer authentication
    if token:
        log_info(f"Using bearer token authentication (source: {token_source})")
        return ServerCredentials(
            url=server_url,
            auth_type="bearer",
            token=token,
            verify_ssl=verify_ssl,
        )

    # =========================================================================
    # Username/Password Resolution Chain
    # =========================================================================

    # Get username (parameter > config)
    username = username_param or server_config.get("username")

    if username:
        log_info(f"Using basic authentication for user: {username}")

        # Resolve password
        password_config = server_config.get("password")
        password = resolve_password(
            password_param,
            password_config,
            username,
            show_param_warning=True,
        )

        if not password:
            log_error("Failed to resolve password")
            return None

        return ServerCredentials(
            url=server_url,
            auth_type="basic",
            username=username,
            password=password,
            verify_ssl=verify_ssl,
        )

    # =========================================================================
    # No Authentication (Local Mode)
    # =========================================================================

    log_info("No authentication credentials found - using anonymous access")
    return ServerCredentials(
        url=server_url,
        auth_type="none",
        verify_ssl=verify_ssl,
    )
