"""
Watch mode functionality for vscode-node-red-tools

This module has been split into focused sub-modules:
- watcher_server.py: Server communication (authenticate, download, deploy)
- watcher_stages.py: Stage processing (download/explode orchestration)
- watcher_core.py: Watch mode orchestration (file watching, polling, commands)

This file re-exports all functions for backwards compatibility.
"""

# Import WATCH_AVAILABLE flag
try:
    import requests
    from watchdog.observers import Observer

    WATCH_AVAILABLE = True
except ImportError:
    WATCH_AVAILABLE = False

# Re-export server communication functions
from .watcher_server import (
    authenticate,
    deploy_to_nodered,
)

# Re-export stage processing functions
from .watcher_stages import (
    download_from_nodered,
    rebuild_and_deploy,
)

# Re-export core watch mode functions
from .watcher_core import (
    watch_mode,
)

# Re-export constants from server module
from .watcher_server import HTTP_TIMEOUT

# Make all exports available
__all__ = [
    # Availability flag
    "WATCH_AVAILABLE",
    # Server communication
    "authenticate",
    "deploy_to_nodered",
    # Stage processing
    "download_from_nodered",
    "rebuild_and_deploy",
    # Core watch mode
    "watch_mode",
    # Constants
    "HTTP_TIMEOUT",
]
