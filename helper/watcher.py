"""Thin watch module.

Provides:
 - WATCH_AVAILABLE flag (presence of optional dependencies)
 - watch_mode entry point
 - download_from_nodered, rebuild_and_deploy convenience re-exports
"""

try:  # Optional deps for watch mode
    import requests  # noqa: F401
    from watchdog.observers import Observer  # noqa: F401

    WATCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    WATCH_AVAILABLE = False

from .watcher_core import watch_mode
from .watcher_stages import sync_from_server, rebuild_and_deploy

__all__ = [
    "WATCH_AVAILABLE",
    "watch_mode",
    "sync_from_server",
    "rebuild_and_deploy",
]
