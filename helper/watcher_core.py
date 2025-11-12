"""
Watch mode core orchestration

Handles watch mode main loop and file handling:
- Plugin loading for watch mode
- File system watching
- Server polling
- Interactive commands
- Watch mode entry point
"""

import json
import time
from datetime import datetime
from pathlib import Path

# Watch-specific imports (conditional)
try:
    import requests
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    WATCH_AVAILABLE = True
except ImportError:
    WATCH_AVAILABLE = False

from .logging import log_info, log_success, log_warning, log_error
 
from .rebuild import rebuild_flows
from .dashboard import WatchConfig
from .watcher_server import authenticate, deploy_to_nodered
from .watcher_stages import download_from_nodered, rebuild_and_deploy
from .constants import (
    MAX_NETWORK_RETRIES,
    RETRY_BASE_DELAY,
    MAX_REBUILD_FAILURES,
)


def load_plugins_for_watch(watch_config: WatchConfig) -> bool:
    """Load plugins and cache them in WatchConfig

    Also loads watch-specific config options (convergence limits, etc.)

    Returns:
        True if successful, False on error
    """
    try:
        from .constants import DEFAULT_CONVERGENCE_LIMIT, DEFAULT_CONVERGENCE_WINDOW

        watch_config.convergence_limit = DEFAULT_CONVERGENCE_LIMIT
        watch_config.convergence_window = DEFAULT_CONVERGENCE_WINDOW

        # Plugins should be loaded by initialize_system and passed in; this is legacy support only.
        raise RuntimeError("load_plugins_for_watch should not be used; plugins_dict should be preloaded and passed in.")
        return True
    except Exception as e:
        log_error(f"Failed to load plugins: {e}")
        return False


# Watchdog-dependent code (only if watchdog is available)
if WATCH_AVAILABLE:

    class SrcFileHandler(FileSystemEventHandler):
        """Handles file system events in src/ directory"""

        def __init__(self, watch_config: WatchConfig) -> None:
            self.watch_config = watch_config

        def on_modified(self, event) -> None:
            if event.is_directory:
                return

            if self.watch_config.pause_watching:
                return

            path = Path(event.src_path)

            # Exclude skeleton and hidden files
            if path.name.startswith("."):
                return

            # Record change
            self.watch_config.last_file_change_time = time.time()
            self.watch_config.rebuild_pending = True

            # Log activity
            if self.watch_config.dashboard:
                self.watch_config.dashboard.log_activity(f"File changed: {path.name}")

    def poll_nodered(watch_config: WatchConfig) -> None:
        """Periodic polling of Node-RED with exponential backoff retry"""
        consecutive_failures = 0
        max_retries = MAX_NETWORK_RETRIES
        base_delay = RETRY_BASE_DELAY

        while not watch_config.shutdown_requested:
            time.sleep(watch_config.poll_interval)

            # Check again after sleep (shutdown may have been requested)
            if watch_config.shutdown_requested:
                log_info("Polling thread exiting gracefully...")
                break

            success = download_from_nodered(config)

            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures <= max_retries:
                    delay = base_delay * (2 ** (consecutive_failures - 1))
                    log_warning(
                        f"Download failed (attempt {consecutive_failures}/{max_retries}), retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    log_error(
                        f"Download failed after {max_retries} retries, will retry on next poll interval"
                    )
                    consecutive_failures = 0

    def handle_command(watch_config: WatchConfig, command: str) -> None:
        """Handle interactive commands

        Supports both full command names and single-character shortcuts:
        - d: download
        - u: upload
        - c: check
        - r: reload-plugins
        - s: status
        - q: quit
        - h or ?: help
        """
        import sys
        import importlib

        command = command.strip().lower()

        if command in ["?", "h", "help"]:
            help_lines = [
                "Available Commands:",
                "  d, download       Download latest flows from server",
                "  u, upload         Upload local changes to server",
                "  c, check          Check sync status",
                "  r, reload-plugins Reload plugins",
                "  s, status         Show status",
                "  q, quit           Quit watch mode",
                "  h, help, ?        Show this help",
            ]
            for line in help_lines:
                log_info(line)

        elif command in ["q", "quit", "exit"]:
            log_info("Initiating graceful shutdown...")
            config.request_shutdown()
            if watch_config.dashboard:
                # Dashboard mode: exit the Textual app
                watch_config.dashboard.stop()
            # Note: Threads will exit gracefully via shutdown flag check

        elif command in ["s", "status"]:
            # Show detailed status information
            log_info("=== Watch Mode Status ===")

            # Server info
            log_info(f"Server: {watch_config.server_url}")
            status_text = "Connected" if watch_config.session else "Disconnected"
            log_info(f"Status: {status_text}")
            log_info(f"Username: {config.username}")
            log_info("")

            # Sync state
            log_info("Synchronization:")
            etag = watch_config.last_etag or "(none)"
            rev = watch_config.last_rev or "(none)"
            log_info(f"  ETag: {etag}")
            log_info(f"  Rev: {rev}")
            log_info("")

            # Statistics (always show)
            log_info("Statistics:")
            log_info(f"  Downloads: {watch_config.download_count}")
            log_info(f"  Uploads: {watch_config.upload_count}")
            log_info(f"  Errors: {config.error_count}")

            # Last sync times
            if watch_config.last_download_time or watch_config.last_upload_time:
                log_info("")
                if watch_config.last_download_time:
                    from datetime import datetime

                    ago = int(
                        (datetime.now() - watch_config.last_download_time).total_seconds()
                    )
                    log_info(f"  Last download: {ago}s ago")
                if watch_config.last_upload_time:
                    from datetime import datetime

                    ago = int(
                        (datetime.now() - watch_config.last_upload_time).total_seconds()
                    )
                    log_info(f"  Last upload: {ago}s ago")

        elif command in ["d", "download"]:
            log_info("Manual download triggered...")
            download_from_nodered(config, force=True)

        elif command in ["u", "upload"]:
            log_info("Manual upload triggered (force rebuild)...")
            result = rebuild_flows(
                watch_config.flows_file,
                watch_config.src_dir,
                quiet_plugins=True,
                plugins_dict=watch_config.plugins_dict,
                repo_root=watch_config.repo_root,
            )
            if result == 0:
                deploy_to_nodered(config)
                # Download to verify upload and update tracking (don't count - part of upload)
                log_info("Verifying upload...")
                download_from_nodered(config, force=True, count_stats=False)
            else:
                log_error("Rebuild failed, cannot upload")

        elif command in ["c", "check"]:
            log_info("Manual check triggered...")
            # Save original
            with open(watch_config.flows_file, "r") as f:
                original = json.load(f)

            # Rebuild
            result = rebuild_flows(
                watch_config.flows_file,
                watch_config.src_dir,
                quiet_plugins=True,
                plugins_dict=watch_config.plugins_dict,
                repo_root=watch_config.repo_root,
            )
            if result != 0:
                log_error("Rebuild failed")
                return

            # Compare
            with open(watch_config.flows_file, "r") as f:
                rebuilt = json.load(f)

            if original != rebuilt:
                log_info("Changes detected, uploading...")
                deploy_to_nodered(config)
            else:
                log_info("No changes detected")

        elif command in ["r", "reload-plugins", "reload"]:
            log_info("Reloading plugins...")

            # Build list of module names and plugin names from currently loaded plugins
            modules_to_reload = set()
            plugin_names_to_reload = []
            if watch_config.plugins_dict:
                for plugin_type, plugins in watch_config.plugins_dict.items():
                    for plugin in plugins:
                        # Get the module name from the plugin's class
                        module = plugin.__class__.__module__
                        modules_to_reload.add(module)
                        plugin_names_to_reload.append(plugin.get_name())
                        log_info(f"  Marking for reload: {plugin.get_name()}")

                # Remove from sys.modules to force reload
                for module_name in modules_to_reload:
                    if module_name in sys.modules:
                        del sys.modules[module_name]

                # Reload only the plugins that were loaded (ignore global enable/disable)
                raise RuntimeError("Plugin reload should be handled by re-initializing system with new config; direct load_plugins is deprecated.")
            else:
                log_info("No plugins loaded to reload")

        else:
            log_error(f"Unknown command: {command}")

    def watch_src_and_rebuild(watch_config: WatchConfig) -> None:
        """Watch src/ for changes and rebuild"""
        event_handler = SrcFileHandler(config)
        observer = Observer()
        observer.schedule(event_handler, str(watch_config.src_dir), recursive=True)
        observer.start()

        log_success(f"Watching {watch_config.src_dir} for changes")

        # Only show help message if not using dashboard
        if not watch_config.dashboard:
            log_info("Type '?' or 'help' for available commands")

        consecutive_failures = 0
        max_consecutive_failures = MAX_REBUILD_FAILURES

        try:
            import select
            import sys

            while not watch_config.shutdown_requested:
                # Check for rebuild pending
                if watch_config.rebuild_pending:
                    time_since_last_change = time.time() - watch_config.last_file_change_time
                    if time_since_last_change >= watch_config.debounce_seconds:
                        watch_config.rebuild_pending = False

                        # Check failure counter
                        if consecutive_failures >= max_consecutive_failures:
                            log_error(
                                f"Skipping rebuild after {max_consecutive_failures} consecutive failures"
                            )
                            log_error(
                                "Fix the errors and save a file again to retry, or use 'upload' command"
                            )
                        else:
                            # Pause file watcher during rebuild to prevent infinite loop
                            watch_config.pause_watching = True
                            try:
                                success = rebuild_and_deploy(config)
                                if success:
                                    consecutive_failures = 0
                                else:
                                    consecutive_failures += 1
                                    log_warning(
                                        f"Rebuild/deploy failed (failure {consecutive_failures}/{max_consecutive_failures})"
                                    )
                            finally:
                                # Always resume file watcher
                                watch_config.pause_watching = False

                # Check for user input (non-blocking)
                if select.select([sys.stdin], [], [], 0)[0]:
                    command = sys.stdin.readline().strip()
                    if command:
                        handle_command(config, command)
                        # If shutdown was requested by the command, break immediately
                        if watch_config.shutdown_requested:
                            break

                # If shutdown was requested by another thread, break immediately
                if watch_config.shutdown_requested:
                    break

                time.sleep(0.1)

            # Graceful shutdown - log completion
            log_info("File watcher exiting gracefully...")

        except KeyboardInterrupt:
            log_info("Keyboard interrupt received - initiating graceful shutdown...")
            config.request_shutdown()
            # Wait for any ongoing rebuild to complete
            if watch_config.pause_watching:
                log_info("Waiting for ongoing rebuild/deploy to complete...")
                # Give it up to 30 seconds to finish
                for _ in range(300):
                    if not watch_config.pause_watching:
                        break
                    time.sleep(0.1)
        # Always stop observer after main loop or exception
        observer.stop()
        observer.join()
        log_success("Watch mode shutdown complete")


def watch_mode(
    args,
    flows_path: Path,
    src_path: Path,
    plugins_dict: dict = None,
    config: dict = None,
    repo_root: Path = None,
    credentials=None,
) -> int:
    """Watch mode - bidirectional sync with Node-RED

    Args:
        args: Command line arguments
        flows_path: Path to flows.json
        src_path: Path to source directory
        plugins_dict: Pre-loaded plugins dictionary (avoids re-loading)
        config: Pre-loaded configuration
        repo_root: Repository root path
        credentials: Authentication credentials
    """
    if not WATCH_AVAILABLE:
        log_error("Watch mode requires: pip install requests watchdog")
        return 1

    watch_config = None
    try:
        # Use provided config; error if missing
        if config is None:
            log_error("No config provided to watch_mode")
            return 1
        if credentials is None:
            log_error("No credentials provided to watch_mode")
            return 1

        watch_config = WatchConfig(args, flows_path, src_path)

        # Use preloaded plugins if provided
        if plugins_dict is not None:
            watch_config.plugins_dict = plugins_dict
            watch_config.config = config
            watch_config.repo_root = repo_root
            watch_config.credentials = credentials

            # Always use the constants for convergence settings
            from .constants import DEFAULT_CONVERGENCE_LIMIT, DEFAULT_CONVERGENCE_WINDOW
            watch_config.convergence_limit = DEFAULT_CONVERGENCE_LIMIT
            watch_config.convergence_window = DEFAULT_CONVERGENCE_WINDOW

        # Set command handler for dashboard
        watch_config.command_handler = handle_command

        if watch_config.dashboard:
            setup_complete = threading.Event()
            setup_success = [False]  # Use list for mutability in closure

            def startup_worker():
                """Background thread for initial setup."""
                # Inline: Create src/ if doesn't exist
                if not watch_config.src_dir.exists():
                    log_info(f"Creating source directory: {watch_config.src_dir}")
                    watch_config.src_dir.mkdir(parents=True, exist_ok=True)
                setup_success[0] = True
                # Start background threads after setup completes
                poll_thread = threading.Thread(
                    target=poll_nodered, args=(watch_config,), daemon=True
                )
                poll_thread.start()

                watch_thread = threading.Thread(
                    target=watch_src_and_rebuild, args=(watch_config,), daemon=True
                )
                watch_thread.start()
                setup_complete.set()

            # Start setup in background
            setup_thread = threading.Thread(target=startup_worker, daemon=True)
            setup_thread.start()

            # Start dashboard in main thread (blocks until user exits)
            watch_config.dashboard.start()
            watch_config.dashboard.run()

            # Check if setup completed successfully
            if not setup_complete.is_set():
                log_error("Dashboard exited before initial setup completed")
                return 1

            if not setup_success[0]:
                return 1

            return 0
        else:
            # Non-dashboard mode: Traditional synchronous startup
            # Create src/ if doesn't exist
            if not watch_config.src_dir.exists():
                log_info(f"Creating source directory: {watch_config.src_dir}")
                watch_config.src_dir.mkdir(parents=True, exist_ok=True)

            try:
                import threading

                # Start polling thread
                poll_thread = threading.Thread(
                    target=poll_nodered, args=(watch_config,), daemon=True
                )
                poll_thread.start()

                # Run file watcher in main thread
                watch_src_and_rebuild(watch_config)
                return 0

            except KeyboardInterrupt:
                watch_config.request_shutdown()
                # Give threads a moment to see shutdown flag
                time.sleep(0.5)
                return 0
    finally:
        # Stop dashboard on exit
        if watch_config.dashboard:
            watch_config.dashboard.stop()
        log_info("Watch mode cleanup complete")
