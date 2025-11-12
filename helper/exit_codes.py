"""
Exit code constants for vscode-node-red-tools

Provides named constants for all exit codes used throughout the application.
This makes exit codes self-documenting and consistent.
"""

# Success
SUCCESS = 0

# General errors (1-9)
GENERAL_ERROR = 1
KEYBOARD_INTERRUPT = 2

# Configuration errors (10-19)
CONFIG_ERROR = 10
CONFIG_INVALID = 11
CONFIG_NOT_FOUND = 12

# File system errors (20-29)
FILE_NOT_FOUND = 20
FILE_PERMISSION_ERROR = 21
FILE_INVALID = 22
DIRECTORY_ERROR = 23

# Server/network errors (30-39)
SERVER_CONNECTION_ERROR = 30
SERVER_AUTH_ERROR = 31
SERVER_CONFLICT = 32
SERVER_NOT_FOUND = 33
SERVER_ERROR = 34

# Validation errors (40-49)
VALIDATION_ERROR = 40
VERIFICATION_FAILED = 41
ROUND_TRIP_FAILED = 42

# Plugin errors (50-59)
PLUGIN_ERROR = 50
PLUGIN_NOT_FOUND = 51
PLUGIN_LOAD_ERROR = 52

# Operation errors (60-69)
EXPLODE_ERROR = 60
REBUILD_ERROR = 61
DIFF_ERROR = 62
WATCH_ERROR = 63


def get_exit_code_name(code: int) -> str:
    """Get human-readable name for exit code

    Args:
        code: Exit code number

    Returns:
        Name of the exit code constant (e.g., "SUCCESS", "CONFIG_ERROR")
    """
    code_map = {
        0: "SUCCESS",
        1: "GENERAL_ERROR",
        2: "KEYBOARD_INTERRUPT",
        10: "CONFIG_ERROR",
        11: "CONFIG_INVALID",
        12: "CONFIG_NOT_FOUND",
        20: "FILE_NOT_FOUND",
        21: "FILE_PERMISSION_ERROR",
        22: "FILE_INVALID",
        23: "DIRECTORY_ERROR",
        30: "SERVER_CONNECTION_ERROR",
        31: "SERVER_AUTH_ERROR",
        32: "SERVER_CONFLICT",
        33: "SERVER_NOT_FOUND",
        34: "SERVER_ERROR",
        40: "VALIDATION_ERROR",
        41: "VERIFICATION_FAILED",
        42: "ROUND_TRIP_FAILED",
        50: "PLUGIN_ERROR",
        51: "PLUGIN_NOT_FOUND",
        52: "PLUGIN_LOAD_ERROR",
        60: "EXPLODE_ERROR",
        61: "REBUILD_ERROR",
        62: "DIFF_ERROR",
        63: "WATCH_ERROR",
    }
    return code_map.get(code, f"UNKNOWN_ERROR_{code}")


def get_exit_code_description(code: int) -> str:
    """Get description of what exit code means

    Args:
        code: Exit code number

    Returns:
        Human-readable description of the error
    """
    descriptions = {
        0: "Operation completed successfully",
        1: "General error occurred",
        2: "Operation cancelled by user (Ctrl+C)",
        10: "Configuration error",
        11: "Configuration file is invalid",
        12: "Configuration file not found",
        20: "Required file not found",
        21: "Permission denied accessing file",
        22: "File format is invalid",
        23: "Directory error",
        30: "Failed to connect to Node-RED server",
        31: "Authentication failed",
        32: "Conflict detected (server was modified)",
        33: "Resource not found on server",
        34: "Server returned an error",
        40: "Validation error",
        41: "Verification failed",
        42: "Round-trip verification failed (flows don't match)",
        50: "Plugin error",
        51: "Plugin not found",
        52: "Failed to load plugin",
        60: "Explode operation failed",
        61: "Rebuild operation failed",
        62: "Diff operation failed",
        63: "Watch mode error",
    }
    return descriptions.get(code, "Unknown error")


def list_exit_codes() -> str:
    """Generate formatted list of all exit codes

    Returns:
        Formatted string showing all exit codes and their meanings
    """
    lines = ["Exit Codes:", ""]

    categories = [
        ("Success", [0]),
        ("General Errors", [1, 2]),
        ("Configuration Errors", list(range(10, 20))),
        ("File System Errors", list(range(20, 30))),
        ("Server/Network Errors", list(range(30, 40))),
        ("Validation Errors", list(range(40, 50))),
        ("Plugin Errors", list(range(50, 60))),
        ("Operation Errors", list(range(60, 70))),
    ]

    for category_name, codes in categories:
        lines.append(f"{category_name}:")
        for code in codes:
            name = get_exit_code_name(code)
            desc = get_exit_code_description(code)
            if name != f"UNKNOWN_ERROR_{code}":
                lines.append(f"  {code:2d} - {name:30s} {desc}")
        lines.append("")

    return "\n".join(lines)
