"""
Logging and progress display utilities for vscode-node-red-tools

Provides console logging functions with configurable levels and progress bar
support with optional rich/textual integration.
"""

import os
import sys
from typing import Optional
from enum import IntEnum

# Optional imports
try:
    from rich.progress import (
        Progress,
        SpinnerColumn,
        BarColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class LogLevel(IntEnum):
    """Logging levels for controlling output verbosity"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40


# Global logging level (can be set via environment or API)
_LOG_LEVEL = LogLevel.INFO

# Global dashboard reference for log redirection
_ACTIVE_DASHBOARD: Optional[object] = None


def set_log_level(level: LogLevel):
    """Set the global logging level

    Args:
        level: LogLevel to set (DEBUG, INFO, WARNING, ERROR)
    """
    global _LOG_LEVEL
    _LOG_LEVEL = level


def get_log_level() -> LogLevel:
    """Get the current logging level

    Returns:
        Current LogLevel
    """
    return _LOG_LEVEL


def set_log_level_from_env():
    """Set logging level from NODERED_TOOLS_LOG_LEVEL environment variable

    Valid values: DEBUG, INFO, WARNING, ERROR (case-insensitive)
    Default: INFO
    """
    global _LOG_LEVEL
    env_level = os.environ.get("NODERED_TOOLS_LOG_LEVEL", "INFO").upper()
    level_map = {
        "DEBUG": LogLevel.DEBUG,
        "INFO": LogLevel.INFO,
        "WARNING": LogLevel.WARNING,
        "ERROR": LogLevel.ERROR,
    }
    _LOG_LEVEL = level_map.get(env_level, LogLevel.INFO)


# Initialize from environment on module load
set_log_level_from_env()


def set_active_dashboard(dashboard):
    """Set the active dashboard for log redirection

    Args:
        dashboard: Dashboard instance with log_activity() method, or None to disable
    """
    global _ACTIVE_DASHBOARD
    _ACTIVE_DASHBOARD = dashboard


def get_active_dashboard():
    """Get the active dashboard instance"""
    return _ACTIVE_DASHBOARD


def log_debug(msg: str):
    """Print debug message (only if log level is DEBUG)

    Args:
        msg: Message to print (icon will be added automatically)
    """
    global _ACTIVE_DASHBOARD, _LOG_LEVEL
    if _LOG_LEVEL > LogLevel.DEBUG:
        return
    if _ACTIVE_DASHBOARD:
        _ACTIVE_DASHBOARD.log_activity(f"🐛 {msg}")
    else:
        print(f"🐛 {msg}")


def log_info(msg: str):
    """Print info message (only if log level is INFO or lower)

    Args:
        msg: Message to print (icon will be added automatically)
    """
    global _ACTIVE_DASHBOARD, _LOG_LEVEL
    if _LOG_LEVEL > LogLevel.INFO:
        return
    if _ACTIVE_DASHBOARD:
        _ACTIVE_DASHBOARD.log_activity(f"→ {msg}")
    else:
        print(f"→ {msg}")


def log_success(msg: str):
    """Print success message (only if log level is INFO or lower)

    Args:
        msg: Message to print (icon will be added automatically)
    """
    global _ACTIVE_DASHBOARD, _LOG_LEVEL
    if _LOG_LEVEL > LogLevel.INFO:
        return
    if _ACTIVE_DASHBOARD:
        _ACTIVE_DASHBOARD.log_activity(f"✓ {msg}")
    else:
        print(f"✓ {msg}")


def log_warning(msg: str):
    """Print warning message (only if log level is WARNING or lower)

    Args:
        msg: Message to print (icon will be added automatically)
    """
    global _ACTIVE_DASHBOARD, _LOG_LEVEL
    if _LOG_LEVEL > LogLevel.WARNING:
        return
    if _ACTIVE_DASHBOARD:
        _ACTIVE_DASHBOARD.log_activity(f"⚠ {msg}")
    else:
        print(f"⚠ {msg}")


def log_error(msg: str):
    """Print error message (always shown)

    Args:
        msg: Message to print (icon will be added automatically)
    """
    global _ACTIVE_DASHBOARD
    if _ACTIVE_DASHBOARD:
        _ACTIVE_DASHBOARD.log_activity(f"✗ {msg}", is_error=True)
    else:
        print(f"✗ {msg}", file=sys.stderr)


def create_progress_context(show_progress: bool = True):
    """Create a progress bar context (rich if available, fallback otherwise)

    Args:
        show_progress: Whether to show progress (False disables progress output)

    Returns:
        Context manager that provides add_task() and update() methods

    Notes:
        - Progress is suppressed when dashboard is active
        - Progress is suppressed when not outputting to a terminal
        - Falls back to dummy context if rich is unavailable
    """
    # Suppress progress bars when dashboard is active (use dashboard logging instead)
    global _ACTIVE_DASHBOARD
    if _ACTIVE_DASHBOARD:
        show_progress = False

    if show_progress and RICH_AVAILABLE and sys.stdout.isatty():
        # Use rich progress bar
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeElapsedColumn(),
        )
    else:
        # Fallback: dummy context manager with add_task/update methods
        class DummyProgress:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def add_task(self, description, total=100):
                return 0  # Return dummy task id

            def update(self, task_id, advance=1, **kwargs):
                pass  # No-op

        return DummyProgress()


def show_progress_bar(
    current: int, total: int, prefix: str = "Processing", width: int = 20
) -> None:
    """Show an in-place updating progress bar (fallback for legacy code)

    Args:
        current: Current progress count
        total: Total count
        prefix: Prefix text (e.g., "Processing nodes")
        width: Width of the progress bar in characters

    Example output:
        → Processing nodes: [###########···········] 50% (125/250)

    Notes:
        - Only shows progress if output is to a terminal
        - Updates in place using carriage return
        - Prints newline when complete
    """
    # Only show progress bar if output is to a terminal
    if not sys.stdout.isatty():
        return

    # Calculate progress
    percent = int(100 * current / total)
    filled = int(width * current / total)
    bar = "#" * filled + "·" * (width - filled)

    # Print with carriage return to update in place
    print(f"\r→ {prefix}: [{bar}] {percent}% ({current}/{total})", end="", flush=True)

    # Print newline when complete
    if current == total:
        print()
