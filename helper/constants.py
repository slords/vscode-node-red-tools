"""
Constants for vscode-node-red-tools

All configurable constants and limits in one place for easy maintenance.
"""

# =============================================================================
# Network and HTTP Configuration
# =============================================================================

HTTP_TIMEOUT = 30  # Timeout for HTTP requests to Node-RED (seconds)

# Rate limiting for API calls (prevents runaway loops)
RATE_LIMIT_REQUESTS_PER_MINUTE = 60  # Allow 1/second normal operation
RATE_LIMIT_REQUESTS_PER_10MIN = 600  # Allow bursts but prevent runaway

# Network retry configuration for watch mode
MAX_NETWORK_RETRIES = 4  # Max consecutive network failures before backoff
RETRY_BASE_DELAY = 2.0  # Base delay for exponential backoff (seconds)


# =============================================================================
# File Size and Resource Limits
# =============================================================================

MAX_FLOWS_FILE_SIZE = 100 * 1024 * 1024  # 100 MB for flows.json
MAX_NODE_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per individual node file
MAX_NODES = 10000  # Maximum number of nodes in a flow

FILE_BUFFER_SIZE = 65536  # 64KB for streaming hash computation
HASH_DIGEST_LENGTH = 16  # First N chars of SHA256 hex digest


# =============================================================================
# Subprocess and External Command Configuration
# =============================================================================

SUBPROCESS_TIMEOUT = 300  # 5 minutes max for external commands (prettier, etc.)
MAX_PATH_LENGTH = 4096  # Maximum path length for subprocess arguments

# Windows reserved filenames (for validation)
WINDOWS_RESERVED_NAMES = {
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

DEFAULT_MAX_WORKERS = None  # None = use os.cpu_count()
PARALLEL_THRESHOLD = 20  # Minimum nodes required to enable parallel processing


# =============================================================================
# Watch Mode Configuration
# =============================================================================

DEFAULT_POLL_INTERVAL = 1  # Poll interval for watch mode (seconds)
DEFAULT_DEBOUNCE = 2  # Seconds to wait after last change for local files
MAX_REBUILD_FAILURES = 5  # Max consecutive rebuild failures before stopping

# Convergence detection (prevents infinite upload/download cycles)
DEFAULT_CONVERGENCE_LIMIT = 5  # Max cycles in time window before warning
DEFAULT_CONVERGENCE_WINDOW = 60  # Time window for convergence detection (seconds)


# =============================================================================
# Plugin System Configuration
# =============================================================================

DEFAULT_PLUGIN_PRIORITY = 999  # Default priority for plugins without explicit priority
