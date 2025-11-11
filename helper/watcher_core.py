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
from .config import load_config
from .plugin_loader import load_plugins
from .rebuild import rebuild_flows
from .dashboard import WatchConfig
from .watcher_server import authenticate, deploy_to_nodered
from .watcher_stages import download_from_nodered, rebuild_and_deploy

# Constants
MAX_NETWORK_RETRIES = 4
RETRY_BASE_DELAY = 2.0  # seconds, for exponential backoff
MAX_REBUILD_FAILURES = 5  # Max consecutive rebuild failures before stopping


def load_plugins_for_watch(config: WatchConfig) -> bool:
    """Load plugins and cache them in WatchConfig

    Also loads watch-specific config options (convergence limits, etc.)

    Returns:
        True if successful, False on error
    """
    try:
        from .dashboard import DEFAULT_CONVERGENCE_LIMIT, DEFAULT_CONVERGENCE_WINDOW

        config.plugin_config = load_config(config.repo_root)

        # Load watch-specific config options
        watch_config = config.plugin_config.get("watch", {})
        config.convergence_limit = watch_config.get(
            "convergenceLimit", DEFAULT_CONVERGENCE_LIMIT
        )
        config.convergence_window = watch_config.get(
            "convergenceWindow", DEFAULT_CONVERGENCE_WINDOW
        )

        config.plugins_dict = load_plugins(
            config.repo_root,
            config.plugin_config,
            enabled_override=config.enabled_override,
            disabled_override=config.disabled_override,
            quiet=False,  # Show plugins on initial load
        )
        return True
    except Exception as e:
        log_error(f"Failed to load plugins: {e}")
        return False


# Watchdog-dependent code (only if watchdog is available)
if WATCH_AVAILABLE:

    class SrcFileHandler(FileSystemEventHandler):
        """Handles file system events in src/ directory"""

        def __init__(self, config: WatchConfig) -> None:
            self.config = config

        def on_modified(self, event) -> None:
            if event.is_directory:
                return

            if self.config.pause_watching:
                return

            path = Path(event.src_path)

            # Exclude skeleton and hidden files
            if path.name.startswith("."):
                return

            # Record change
            self.config.last_file_change_time = time.time()
            self.config.rebuild_pending = True

            # Log activity
            if self.config.dashboard:
                self.config.dashboard.log_activity(f"File changed: {path.name}")

    def poll_nodered(config: WatchConfig) -> None:
        """Periodic polling of Node-RED with exponential backoff retry"""
        consecutive_failures = 0
        max_retries = MAX_NETWORK_RETRIES
        base_delay = RETRY_BASE_DELAY

        while not config.shutdown_requested:
            time.sleep(config.poll_interval)

            # Check again after sleep (shutdown may have been requested)
            if config.shutdown_requested:
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

    def handle_command(config: WatchConfig, command: str) -> None:
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
            if config.dashboard:
                # Dashboard mode: exit the Textual app
                config.dashboard.stop()
            # Note: Threads will exit gracefully via shutdown flag check

        elif command in ["s", "status"]:
            # Show detailed status information
            log_info("=== Watch Mode Status ===")

            # Server info
            log_info(f"Server: {config.server_url}")
            status_text = "Connected" if config.session else "Disconnected"
            log_info(f"Status: {status_text}")
            log_info(f"Username: {config.username}")
            log_info("")

            # Sync state
            log_info("Synchronization:")
            etag = config.last_etag or "(none)"
            rev = config.last_rev or "(none)"
            log_info(f"  ETag: {etag}")
            log_info(f"  Rev: {rev}")
            log_info("")

            # Statistics (always show)
            log_info("Statistics:")
            log_info(f"  Downloads: {config.download_count}")
            log_info(f"  Uploads: {config.upload_count}")
            log_info(f"  Errors: {config.error_count}")

            # Last sync times
            if config.last_download_time or config.last_upload_time:
                log_info("")
                if config.last_download_time:
                    from datetime import datetime

                    ago = int(
                        (datetime.now() - config.last_download_time).total_seconds()
                    )
                    log_info(f"  Last download: {ago}s ago")
                if config.last_upload_time:
                    from datetime import datetime

                    ago = int(
                        (datetime.now() - config.last_upload_time).total_seconds()
                    )
                    log_info(f"  Last upload: {ago}s ago")

        elif command in ["d", "download"]:
            log_info("Manual download triggered...")
            download_from_nodered(config, force=True)

        elif command in ["u", "upload"]:
            log_info("Manual upload triggered (force rebuild)...")
            result = rebuild_flows(
                config.flows_file,
                config.src_dir,
                quiet_plugins=True,
                plugins_dict=config.plugins_dict,
                repo_root=config.repo_root,
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
            with open(config.flows_file, "r") as f:
                original = json.load(f)

            # Rebuild
            result = rebuild_flows(
                config.flows_file,
                config.src_dir,
                quiet_plugins=True,
                plugins_dict=config.plugins_dict,
                repo_root=config.repo_root,
            )
            if result != 0:
                log_error("Rebuild failed")
                return

            # Compare
            with open(config.flows_file, "r") as f:
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
            if config.plugins_dict:
                for plugin_type, plugins in config.plugins_dict.items():
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
                from .plugin_loader import load_plugins

                config.plugins_dict = load_plugins(
                    config.repo_root,
                    config.plugin_config,
                    enabled_override=plugin_names_to_reload,
                    disabled_override=None,
                    quiet=False,
                )

                # Count plugins
                total = sum(
                    len(config.plugins_dict[key]) for key in config.plugins_dict
                )
                log_success(f"Reloaded {total} plugins")
            else:
                log_info("No plugins loaded to reload")

        else:
            log_error(f"Unknown command: {command}")

    def watch_src_and_rebuild(config: WatchConfig) -> None:
        """Watch src/ for changes and rebuild"""
        event_handler = SrcFileHandler(config)
        observer = Observer()
        observer.schedule(event_handler, str(config.src_dir), recursive=True)
        observer.start()

        log_success(f"Watching {config.src_dir} for changes")

        # Only show help message if not using dashboard
        if not config.dashboard:
            log_info("Type '?' or 'help' for available commands")

        consecutive_failures = 0
        max_consecutive_failures = MAX_REBUILD_FAILURES

        try:
            import select
            import sys

            while not config.shutdown_requested:
                # Check for rebuild pending
                if config.rebuild_pending:
                    time_since_last_change = time.time() - config.last_file_change_time
                    if time_since_last_change >= config.debounce_seconds:
                        config.rebuild_pending = False

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
                            config.pause_watching = True
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
                                config.pause_watching = False

                # Check for user input (non-blocking)
                if select.select([sys.stdin], [], [], 0)[0]:
                    command = sys.stdin.readline().strip()
                    if command:
                        handle_command(config, command)

                time.sleep(0.1)

            # Graceful shutdown - log completion
            log_info("File watcher exiting gracefully...")

        except KeyboardInterrupt:
            log_info("Keyboard interrupt received - initiating graceful shutdown...")
            config.request_shutdown()
            # Wait for any ongoing rebuild to complete
            if config.pause_watching:
                log_info("Waiting for ongoing rebuild/deploy to complete...")
                # Give it up to 30 seconds to finish
                for _ in range(300):
                    if not config.pause_watching:
                        break
                    time.sleep(0.1)
            observer.stop()

        observer.join()
        log_success("Watch mode shutdown complete")


def perform_initial_setup(config: WatchConfig) -> bool:
    """Perform initial authentication and plugin loading

    Note: Initial sync happens automatically on first poll (etag=None triggers download)
    """
    # Create src/ if doesn't exist
    if not config.src_dir.exists():
        log_info(f"Creating source directory: {config.src_dir}")
        config.src_dir.mkdir(parents=True, exist_ok=True)

    # Authenticate
    log_info("Connecting to Node-RED...")
    if not authenticate(config):
        return False

    log_info("Watch mode ready - initial sync will happen on first poll")
    return True


def watch_mode(
    args,
    flows_path: Path,
    src_path: Path,
    plugins_dict: dict = None,
    plugin_config: dict = None,
    repo_root: Path = None,
) -> int:
    """Watch mode - bidirectional sync with Node-RED

    Args:
        args: Command line arguments
        flows_path: Path to flows.json
        src_path: Path to source directory
        plugins_dict: Pre-loaded plugins dictionary (avoids re-loading)
        plugin_config: Pre-loaded plugin configuration
        repo_root: Repository root path
    """
    if not WATCH_AVAILABLE:
        log_error("Watch mode requires: pip install requests watchdog")
        return 1

    try:
        config = WatchConfig(args, flows_path, src_path)

        # Use preloaded plugins if provided
        if plugins_dict is not None:
            config.plugins_dict = plugins_dict
            config.plugin_config = plugin_config
            config.repo_root = repo_root

            # Load watch-specific config options
            from .dashboard import DEFAULT_CONVERGENCE_LIMIT, DEFAULT_CONVERGENCE_WINDOW

            watch_config = plugin_config.get("watch", {})
            config.convergence_limit = watch_config.get(
                "convergenceLimit", DEFAULT_CONVERGENCE_LIMIT
            )
            config.convergence_window = watch_config.get(
                "convergenceWindow", DEFAULT_CONVERGENCE_WINDOW
            )

        # Set command handler for dashboard
        config.command_handler = handle_command

        if config.dashboard:
            # Dashboard mode: Start dashboard in main thread, run setup in background
            import threading

            # Flag to track setup completion
            setup_complete = threading.Event()
            setup_success = [False]  # Use list for mutability in closure

            def startup_worker():
                """Background thread for initial setup"""
                success = perform_initial_setup(config)
                setup_success[0] = success
                if success:
                    # Start background threads after setup completes
                    poll_thread = threading.Thread(
                        target=poll_nodered, args=(config,), daemon=True
                    )
                    poll_thread.start()

                    watch_thread = threading.Thread(
                        target=watch_src_and_rebuild, args=(config,), daemon=True
                    )
                    watch_thread.start()
                setup_complete.set()

            # Start setup in background
            setup_thread = threading.Thread(target=startup_worker, daemon=True)
            setup_thread.start()

            # Start dashboard in main thread (blocks until user exits)
            config.dashboard.start()
            config.dashboard.run()

            # Check if setup completed successfully
            if not setup_complete.is_set():
                log_error("Dashboard exited before initial setup completed")
                return 1

            if not setup_success[0]:
                return 1

            return 0
        else:
            # Non-dashboard mode: Traditional synchronous startup
            if not perform_initial_setup(config):
                return 1

            try:
                import threading

                # Start polling thread
                poll_thread = threading.Thread(
                    target=poll_nodered, args=(config,), daemon=True
                )
                poll_thread.start()

                # Run file watcher in main thread
                watch_src_and_rebuild(config)
                return 0

            except KeyboardInterrupt:
                log_info("Keyboard interrupt received - initiating graceful shutdown...")
                config.request_shutdown()
                # Give threads a moment to see shutdown flag
                time.sleep(0.5)
                return 0

    finally:
        # Stop dashboard on exit
        if config.dashboard:
            config.dashboard.stop()
        log_info("Watch mode cleanup complete")
