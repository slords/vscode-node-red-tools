"""
Utility functions for vscode-node-red-tools

Provides JSON handling, hashing, backup management, and other utilities.
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
import urllib.parse

from .logging import log_info, log_warning

# Constants
HTTP_TIMEOUT = 30
FILE_BUFFER_SIZE = 65536  # 64KB for streaming hash computation
HASH_DIGEST_LENGTH = 16  # First N chars of SHA256 hex digest


def validate_safe_path(base_dir: Path, target_path: Path) -> Path:
    """Validate that target_path is within base_dir (prevent path traversal)

    Args:
        base_dir: Base directory that must contain the target
        target_path: Target path to validate

    Returns:
        Resolved safe path

    Raises:
        ValueError: If path traversal detected

    Example:
        base = Path("/home/user/project/src")
        target = Path("/home/user/project/src/node_123/file.json")
        safe_path = validate_safe_path(base, target)  # OK

        malicious = Path("/home/user/project/src/../../etc/passwd")
        validate_safe_path(base, malicious)  # Raises ValueError
    """
    base_dir = base_dir.resolve()
    target_path = target_path.resolve()

    # Check if target is within base
    try:
        target_path.relative_to(base_dir)
    except ValueError:
        raise ValueError(
            f"Security: Path traversal detected. '{target_path}' is outside '{base_dir}'"
        )

    return target_path


def validate_server_url(url: str) -> str:
    """Validate and normalize server URL with security checks

    Args:
        url: Server URL to validate

    Returns:
        Normalized URL (with scheme, without trailing slash)

    Raises:
        ValueError: If URL is invalid or uses prohibited schemes

    Notes:
        - Only http:// and https:// schemes are allowed
        - file://, ftp://, and other schemes are rejected for security
        - Localhost and private IPs are allowed (expected use case)
        - Validates hostname format and presence
        - Prevents malformed URLs that could cause unexpected behavior
    """
    if not url:
        raise ValueError("Server URL cannot be empty")

    # Check for dangerous schemes before adding default
    url_lower = url.lower()
    dangerous_schemes = ["file://", "ftp://", "data:", "javascript:", "about:"]
    for scheme in dangerous_schemes:
        if url_lower.startswith(scheme):
            raise ValueError(
                f"Invalid URL scheme: {scheme.rstrip(':/')} "
                f"(only http and https are allowed for Node-RED servers)"
            )

    # Add scheme if missing (default to https)
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    # Parse and validate URL structure
    try:
        parsed = urllib.parse.urlparse(url)

        # Validate scheme (should always be http/https at this point)
        if parsed.scheme not in ["http", "https"]:
            raise ValueError(
                f"Invalid URL scheme: {parsed.scheme} (must be http or https)"
            )

        # Validate netloc (hostname:port) exists
        if not parsed.netloc:
            raise ValueError("URL must include a hostname")

        # Extract hostname (without port) for validation
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL must include a valid hostname")

        # Validate hostname format (basic checks)
        # Allow: domain names, IPv4, IPv6, localhost
        if len(hostname) > 253:
            raise ValueError(f"Hostname too long: {len(hostname)} chars (max 253)")

        # Check for obviously invalid characters in hostname
        invalid_chars = [" ", "<", ">", '"', "{", "}", "|", "\\", "^", "`"]
        for char in invalid_chars:
            if char in hostname:
                raise ValueError(
                    f"Hostname contains invalid character: '{char}'"
                )

        # Validate port if present
        if parsed.port is not None:
            if not (1 <= parsed.port <= 65535):
                raise ValueError(
                    f"Invalid port number: {parsed.port} (must be 1-65535)"
                )

        # Remove trailing slash for consistency
        url = url.rstrip("/")

        return url

    except ValueError:
        # Re-raise ValueError as-is (our validation errors)
        raise
    except Exception as e:
        # Catch other parsing errors and wrap them
        raise ValueError(f"Invalid server URL '{url}': {e}")


def write_compact_json(path: Path, data: Any):
    """Write JSON in compact format with trailing newline

    Args:
        path: Path to write JSON file
        data: Data to serialize

    Example:
        write_compact_json(Path("flows.json"), flow_data)
    """
    json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    path.write_text(json_str + "\n")


def read_json(path: Path) -> Any:
    """Read and parse JSON file

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON data

    Example:
        data = read_json(Path("flows.json"))
    """
    with open(path, "r") as f:
        return json.load(f)


def format_compact_json(data: Any) -> str:
    """Format data as compact JSON string (no trailing newline)

    Args:
        data: Data to serialize

    Returns:
        Compact JSON string without trailing newline

    Example:
        json_str = format_compact_json({"key": "value"})
    """
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def compute_file_hash(filepath: Path, buffer_size: int = FILE_BUFFER_SIZE) -> str:
    """Compute SHA256 hash of a file using streaming

    Args:
        filepath: Path to file
        buffer_size: Buffer size for reading (default: 64KB)

    Returns:
        First N characters of SHA256 hex digest (where N = HASH_DIGEST_LENGTH)
    """
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(buffer_size):
            hasher.update(chunk)
    return hasher.hexdigest()[:HASH_DIGEST_LENGTH]


def compute_dir_hash(
    directory: Path, patterns: List[str], buffer_size: int = FILE_BUFFER_SIZE
) -> str:
    """Compute combined hash of all matching files in directory using streaming

    Args:
        directory: Directory to scan
        patterns: List of glob patterns to match
        buffer_size: Buffer size for reading (default: 64KB)

    Returns:
        First N characters of SHA256 hex digest (where N = HASH_DIGEST_LENGTH)
    """
    hasher = hashlib.sha256()
    files = []
    for pattern in patterns:
        files.extend(sorted(directory.rglob(pattern)))

    for file in sorted(set(files)):
        if file.is_file():
            with open(file, "rb") as f:
                while chunk := f.read(buffer_size):
                    hasher.update(chunk)

    return hasher.hexdigest()[:HASH_DIGEST_LENGTH]


def create_backup(
    file_path: Path, backup_dir: Path = None, auto_cleanup: bool = True
) -> Optional[Path]:
    """Create timestamped backup of a file.

    Args:
        file_path: Path to file to backup
        backup_dir: Optional backup directory (defaults to flows/.backup/)
        auto_cleanup: Automatically clean up old backups based on config

    Returns:
        Path to backup file, or None if file doesn't exist
    """
    if not file_path.exists():
        return None

    # Default backup directory is flows/.backup/
    if backup_dir is None:
        backup_dir = file_path.parent / ".backup"

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.stem}.{timestamp}{file_path.suffix}"
    backup_path = backup_dir / backup_name

    shutil.copy2(file_path, backup_path)
    log_info(f"Backup created: {backup_path}")

    # Auto cleanup old backups
    if auto_cleanup:
        try:
            # Import here to avoid circular dependency
            from .config import load_config

            # Load config to get retention settings
            repo_root = file_path.parent.parent
            config = load_config(repo_root)
            backup_config = config.get("backup", {})
            max_backups = backup_config.get("max_backups", 10)  # Default: keep 10
            max_age_days = backup_config.get("max_age_days", 30)  # Default: 30 days

            cleanup_old_backups(
                backup_dir,
                max_backups=max_backups,
                max_age_days=max_age_days,
                file_pattern=f"{file_path.stem}.*{file_path.suffix}",
            )
        except Exception as e:
            # Don't fail backup creation if cleanup fails
            log_warning(f"Backup cleanup failed: {e}")

    return backup_path


def cleanup_old_backups(
    backup_dir: Path,
    max_backups: int = None,
    max_age_days: int = None,
    file_pattern: str = "*.json",
) -> int:
    """Clean up old backup files based on retention policy.

    Args:
        backup_dir: Backup directory to clean
        max_backups: Maximum number of backups to keep (keeps newest)
        max_age_days: Maximum age in days (deletes older)
        file_pattern: Pattern for backup files (default: *.json)

    Returns:
        Number of backups deleted
    """
    if not backup_dir.exists():
        return 0

    # Get all backup files sorted by modification time (newest first)
    backups = sorted(
        backup_dir.glob(file_pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not backups:
        return 0

    deleted_count = 0
    now = datetime.now().timestamp()

    for idx, backup_file in enumerate(backups):
        should_delete = False

        # Check count limit (keep newest max_backups)
        if max_backups is not None and idx >= max_backups:
            should_delete = True

        # Check age limit
        if max_age_days is not None:
            age_seconds = now - backup_file.stat().st_mtime
            age_days = age_seconds / (24 * 3600)
            if age_days > max_age_days:
                should_delete = True

        if should_delete:
            backup_file.unlink()
            deleted_count += 1

    if deleted_count > 0:
        log_info(f"Cleaned up {deleted_count} old backup(s)")

    return deleted_count


def clear_watch_state_after_failure(config, reason: str = "upload failed") -> None:
    """Clear watch state after upload/deploy failure (helper to reduce code duplication)

    Args:
        config: Watch configuration object
        reason: Reason for clearing state (for logging)
    """
    log_warning(f"Failed to {reason}")
    log_warning("Clearing state - will retry on next poll")
    config.last_etag = None
    config.last_rev = None
