"""
Constants for vscode-node-red-tools

All configurable constants and limits in one place for easy maintenance.
"""

from __future__ import annotations

from typing import Set, Optional

# =============================================================================
# Network and HTTP Configuration
# =============================================================================

HTTP_TIMEOUT: int = 30  # Timeout for HTTP requests to Node-RED (seconds)

# HTTP Status Codes (for clarity and maintainability)
HTTP_NOT_MODIFIED: int = 304  # ETag matches, no new content
HTTP_UNAUTHORIZED: int = 401  # Authentication required
HTTP_FORBIDDEN: int = 403  # Authentication failed
HTTP_CONFLICT: int = 409  # Revision conflict on deploy

# Rate limiting for API calls (prevents runaway loops)
# Raised per user request to accommodate higher interactive usage without premature throttling.
# 180/min (~3/sec sustained) and 1200/10min balance responsiveness vs. protection.
RATE_LIMIT_REQUESTS_PER_MINUTE: int = 180  # ~3/sec sustained
RATE_LIMIT_REQUESTS_PER_10MIN: int = 1200  # Allows larger bursts over 10 minutes

# Network retry configuration for watch mode
MAX_NETWORK_RETRIES: int = 4  # Max consecutive network failures before backoff
RETRY_BASE_DELAY: float = 2.0  # Base delay for exponential backoff (seconds)


# =============================================================================
# File Size and Resource Limits
# =============================================================================

MAX_FLOWS_FILE_SIZE: int = 100 * 1024 * 1024  # 100 MB for flows.json
MAX_NODE_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB per individual node file
MAX_NODES: int = 10000  # Maximum number of nodes in a flow

FILE_BUFFER_SIZE: int = 65536  # 64KB for streaming hash computation
HASH_DIGEST_LENGTH: int = 16  # First N chars of SHA256 hex digest


# =============================================================================
# Subprocess and External Command Configuration
# =============================================================================

SUBPROCESS_TIMEOUT: int = 300  # 5 minutes max for external commands (prettier, etc.)
MAX_PATH_LENGTH: int = 4096  # Maximum path length for subprocess arguments

# Windows reserved filenames (for validation)
WINDOWS_RESERVED_NAMES: Set[str] = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


# =============================================================================
# Parallel Processing Configuration
# =============================================================================

DEFAULT_MAX_WORKERS: Optional[int] = None  # None = use os.cpu_count()
PARALLEL_THRESHOLD: int = 20  # Minimum nodes required to enable parallel processing


# =============================================================================
# Watch Mode Configuration
# =============================================================================

DEFAULT_POLL_INTERVAL: int = 1  # Poll interval for watch mode (seconds)
DEFAULT_DEBOUNCE: int = 2  # Seconds to wait after last change for local files
MAX_REBUILD_FAILURES: int = 5  # Max consecutive rebuild failures before stopping

# Convergence detection (prevents infinite upload/download cycles)
DEFAULT_CONVERGENCE_LIMIT: int = 5  # Max cycles in time window before warning
DEFAULT_CONVERGENCE_WINDOW: int = 60  # Time window for convergence detection (seconds)


# =============================================================================
# Plugin System Configuration
# =============================================================================

DEFAULT_PLUGIN_PRIORITY: int = (
    999  # Default priority for plugins without explicit priority
)
