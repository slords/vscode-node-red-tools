"""Slim authentication config and resolution.

Provides minimal AuthConfig dataclass + resolve_auth_config function used by ServerClient.
No legacy ServerCredentials class anymore - all server interaction is now via ServerClient.

Priority (URL): args.server > config.server.url > default
Priority (verify_ssl): args.no_verify_ssl overrides (False) > config.server.verifySSL > True
Priority (auth):
 1. args.token_file
 2. args.token
 3. args.username/password (CLI + resolution chain for password)
 4. config.server.tokenFile
 5. config.server.token
 6. config.server.username/password
 7. standard token file locations (./.nodered-token, ~/.nodered-token)
 8. NODERED_TOKEN env var
 9. anonymous
"""

from __future__ import annotations

import os
import getpass
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

from .logging import log_info, log_warning, log_error


@dataclass(slots=True)
class AuthConfig:
    url: str
    auth_type: str  # 'none' | 'basic' | 'bearer'
    verify_ssl: bool
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None


def _read_token_file(path: Path) -> Optional[str]:
    try:
        if path.exists():
            token = path.read_text().strip()
            if token:
                log_info(f"Loaded token from: {path}")
                return token
    except Exception as e:  # pragma: no cover - filesystem edge
        log_warning(f"Failed to read token file {path}: {e}")
    return None


def _find_standard_token() -> Optional[str]:
    for p in [Path.cwd() / ".nodered-token", Path.home() / ".nodered-token"]:
        t = _read_token_file(p)
        if t:
            return t
    return None


def _resolve_password(param: Optional[str], cfg: Optional[str], username: str) -> Optional[str]:
    if param:
        log_warning(
            "⚠️  WARNING: Passing password via CLI is insecure; prefer NODERED_PASSWORD env variable."
        )
        return param
    if cfg:
        log_info("Using password from config file")
        return cfg
    env_pw = os.environ.get("NODERED_PASSWORD")
    if env_pw:
        log_info("Using password from NODERED_PASSWORD environment variable")
        return env_pw
    try:
        log_info(f"Prompting for password for user '{username}'")
        pw = getpass.getpass(f"Enter password for '{username}': ")
        if pw:
            return pw
    except (KeyboardInterrupt, EOFError):
        log_error("Password input cancelled")
        return None
    return None


def resolve_auth_config(args: Any, config: dict) -> AuthConfig:
    server_cfg = config.get("server", {})

    # URL
    param_url = getattr(args, "server", None)
    if param_url:
        url = param_url
    elif server_cfg.get("url"):
        url = server_cfg["url"]
    else:
        url = "http://127.0.0.1:1880"
    log_info(f"Server URL: {url}")

    # verify_ssl
    if getattr(args, "no_verify_ssl", False) is True:
        verify_ssl = False
    elif "verifySSL" in server_cfg:
        verify_ssl = bool(server_cfg.get("verifySSL", True))
    else:
        verify_ssl = True

    # Token chain
    token: Optional[str] = None

    token_file_param = getattr(args, "token_file", None)
    if token_file_param:
        token = _read_token_file(Path(token_file_param))

    if not token:
        token_param = getattr(args, "token", None)
        if token_param:
            token = token_param
            log_warning(
                "⚠️  WARNING: Passing token via CLI is insecure; prefer NODERED_TOKEN env or token file."
            )

    username_param = getattr(args, "username", None)
    has_username_param = username_param is not None

    if not token and not has_username_param:
        token_file_cfg = server_cfg.get("tokenFile")
        if token_file_cfg:
            token = _read_token_file(Path(token_file_cfg))

    if not token and not has_username_param:
        token_cfg = server_cfg.get("token")
        if token_cfg:
            token = token_cfg

    has_username_cfg = server_cfg.get("username") is not None

    if not token and not has_username_param and not has_username_cfg:
        token = _find_standard_token()

    if not token and not has_username_param and not has_username_cfg:
        env_token = os.environ.get("NODERED_TOKEN")
        if env_token:
            token = env_token

    if token:
        log_info("Using bearer token authentication")
        return AuthConfig(
            url=url,
            auth_type="bearer",
            verify_ssl=verify_ssl,
            token=token,
        )

    # Username/password chain
    username: Optional[str] = None
    password: Optional[str] = None

    if username_param:
        username = username_param
    elif server_cfg.get("username") is not None:
        username = server_cfg.get("username")

    if username:
        pw_param = getattr(args, "password", None)
        pw_cfg = server_cfg.get("password")
        password = _resolve_password(pw_param, pw_cfg, username)
        if not password:
            raise ValueError("Failed to resolve password")
        return AuthConfig(
            url=url,
            auth_type="basic",
            verify_ssl=verify_ssl,
            username=username,
            password=password,
        )

    log_info("Using anonymous access (no authentication)")
    return AuthConfig(
        url=url,
        auth_type="none",
        verify_ssl=verify_ssl,
    )
