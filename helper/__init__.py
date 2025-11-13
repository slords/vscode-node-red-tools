"""
helper - Modular components for vscode-node-red-tools

This package contains the refactored modules from vscode-node-red-tools.py,
organized by functionality for better maintainability.
"""

# Re-export all constants (centralized configuration)
from .constants import (
    # Network and HTTP
    HTTP_TIMEOUT,
    HTTP_NOT_MODIFIED,
    HTTP_UNAUTHORIZED,
    HTTP_FORBIDDEN,
    HTTP_CONFLICT,
    RATE_LIMIT_REQUESTS_PER_MINUTE,
    RATE_LIMIT_REQUESTS_PER_10MIN,
    MAX_NETWORK_RETRIES,
    RETRY_BASE_DELAY,
    # File size and resource limits
    MAX_FLOWS_FILE_SIZE,
    MAX_NODE_FILE_SIZE,
    MAX_NODES,
    FILE_BUFFER_SIZE,
    HASH_DIGEST_LENGTH,
    # Subprocess configuration
    SUBPROCESS_TIMEOUT,
    MAX_PATH_LENGTH,
    WINDOWS_RESERVED_NAMES,
    # Parallel processing
    DEFAULT_MAX_WORKERS,
    PARALLEL_THRESHOLD,
    # Watch mode
    DEFAULT_POLL_INTERVAL,
    DEFAULT_DEBOUNCE,
    MAX_REBUILD_FAILURES,
    DEFAULT_CONVERGENCE_LIMIT,
    DEFAULT_CONVERGENCE_WINDOW,
    # Plugin system
    DEFAULT_PLUGIN_PRIORITY,
)

# Re-export logging functions for convenience
from .logging import (
    LogLevel,
    log_debug,
    log_info,
    log_success,
    log_warning,
    log_error,
    set_log_level,
    get_log_level,
    set_log_level_from_env,
    create_progress_context,
    show_progress_bar,
    set_active_dashboard,
    get_active_dashboard,
)

# Re-export exit codes
from .exit_codes import (
    SUCCESS,
    GENERAL_ERROR,
    KEYBOARD_INTERRUPT,
    CONFIG_ERROR,
    CONFIG_INVALID,
    CONFIG_NOT_FOUND,
    FILE_NOT_FOUND,
    FILE_PERMISSION_ERROR,
    FILE_INVALID,
    DIRECTORY_ERROR,
    SERVER_CONNECTION_ERROR,
    SERVER_AUTH_ERROR,
    SERVER_CONFLICT,
    SERVER_NOT_FOUND,
    SERVER_ERROR,
    VALIDATION_ERROR,
    VERIFICATION_FAILED,
    ROUND_TRIP_FAILED,
    PLUGIN_ERROR,
    PLUGIN_NOT_FOUND,
    PLUGIN_LOAD_ERROR,
    EXPLODE_ERROR,
    REBUILD_ERROR,
    DIFF_ERROR,
    WATCH_ERROR,
    get_exit_code_name,
    get_exit_code_description,
    list_exit_codes,
)

# Re-export utility functions
from .utils import (
    validate_server_url,
    validate_path_for_subprocess,
    sanitize_filename,
    write_compact_json,
    read_json,
    read_json_with_size_limit,
    format_compact_json,
    compute_file_hash,
    compute_dir_hash,
    create_backup,
    cleanup_old_backups,
    clear_watch_state_after_failure,
    RateLimiter,
)

# Re-export config functions
from .config import (
    validate_config,
)

# Re-export auth functions
from .server_client import ServerClient
from .auth import AuthConfig, resolve_auth_config

# Re-export dashboard classes
from .dashboard import (
    WatchConfig,
    WatchDashboard,
)

# Re-export diff functions
from .diff import (
    download_server_flows,
    prepare_source_for_diff,
    unified_diff_files,
    compare_directories_unified,
    launch_beyond_compare,
    diff_flows,
    _print_flows_diff,
)

# Re-export skeleton functions
from .skeleton import (
    get_node_directory,
    create_skeleton,
    load_skeleton,
    save_skeleton,
)

# Re-export file operations
from .file_ops import (
    find_orphaned_files,
    handle_orphaned_files,
    find_new_files,
    detect_node_type,
    create_node_from_files,
    handle_new_files,
)

# Re-export plugin loader
from .plugin_loader import (
    Plugin,
    extract_numeric_prefix,
    DEFAULT_PLUGIN_PRIORITY,
)

# Re-export rebuild operations
from .rebuild import (
    rebuild_single_node,
    rebuild_flows,
)

# Re-export explode operations
from .explode import (
    explode_flows,
)

from .watcher import WATCH_AVAILABLE, watch_mode

# Re-export command operations (general)
from .commands import (
    stats_command,
    benchmark_command,
    verify_flows,
)

# Re-export command operations (plugin)
from .commands_plugin import (
    new_plugin_command,
    list_plugins_command,
)

# Re-export initialization
from .initialize import (
    initialize_system,
)

__all__ = [
    # Constants
    "HTTP_TIMEOUT",
    "RATE_LIMIT_REQUESTS_PER_MINUTE",
    "RATE_LIMIT_REQUESTS_PER_10MIN",
    "MAX_NETWORK_RETRIES",
    "RETRY_BASE_DELAY",
    "MAX_FLOWS_FILE_SIZE",
    "MAX_NODE_FILE_SIZE",
    "MAX_NODES",
    "FILE_BUFFER_SIZE",
    "HASH_DIGEST_LENGTH",
    "SUBPROCESS_TIMEOUT",
    "MAX_PATH_LENGTH",
    "WINDOWS_RESERVED_NAMES",
    "DEFAULT_MAX_WORKERS",
    "PARALLEL_THRESHOLD",
    "DEFAULT_POLL_INTERVAL",
    "MAX_REBUILD_FAILURES",
    "DEFAULT_CONVERGENCE_LIMIT",
    "DEFAULT_CONVERGENCE_WINDOW",
    "DEFAULT_PLUGIN_PRIORITY",
    # Logging
    "log_info",
    "log_success",
    "log_warning",
    "log_error",
    "create_progress_context",
    "show_progress_bar",
    "set_active_dashboard",
    "get_active_dashboard",
    # Auth
    "ServerClient",
    "AuthConfig",
    "resolve_auth_config",
    # Utils
    "validate_server_url",
    "validate_path_for_subprocess",
    "sanitize_filename",
    "write_compact_json",
    "read_json",
    "read_json_with_size_limit",
    "format_compact_json",
    "compute_file_hash",
    "compute_dir_hash",
    "create_backup",
    "cleanup_old_backups",
    "clear_watch_state_after_failure",
    "RateLimiter",
    # Config
    "validate_config",
    # Dashboard
    "WatchConfig",
    "WatchDashboard",
    # Diff
    "download_server_flows",
    "prepare_source_for_diff",
    "unified_diff_files",
    "compare_directories_unified",
    "launch_beyond_compare",
    "diff_flows",
    "_print_flows_diff",
    # Skeleton
    "get_node_directory",
    "create_skeleton",
    "load_skeleton",
    "save_skeleton",
    # File Operations
    "find_orphaned_files",
    "handle_orphaned_files",
    "find_new_files",
    "detect_node_type",
    "create_node_from_files",
    "handle_new_files",
    # Plugin Loader
    "Plugin",
    "extract_numeric_prefix",
    "DEFAULT_PLUGIN_PRIORITY",
    # Rebuild
    "rebuild_single_node",
    "rebuild_flows",
    # Explode
    "explode_flows",
    # Watcher
    "WATCH_AVAILABLE",
    "watch_mode",
    # Commands (general)
    "stats_command",
    "benchmark_command",
    "verify_flows",
    # Commands (plugin)
    "new_plugin_command",
    "list_plugins_command",
    # Initialization
    "initialize_system",
]
