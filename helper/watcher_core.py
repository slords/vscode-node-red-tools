"""watcher_core

Core orchestration for watch mode:
 - File system event handling (debounced rebuild + deploy)
 - Periodic polling of Node-RED flows
 - Interactive command handling (download / upload / check / reload / status / quit)
 - Plugin reload (simplified – only reload originally loaded plugin set)
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from typing import Dict

try:  # Conditional imports for watch mode availability
    import requests  # noqa: F401
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    WATCH_MODULES_AVAILABLE = True
except ImportError:  # pragma: no cover - handled at runtime
    WATCH_MODULES_AVAILABLE = False
    # Provide stubs so name lookups don't fail if file imported without deps
    Observer = object  # type: ignore
    FileSystemEventHandler = object  # type: ignore

from .dashboard import WatchConfig
from .logging import (
    log_info,
    log_success,
    log_warning,
    log_error,
)
from .exit_codes import (
    SUCCESS,
    GENERAL_ERROR,
    REBUILD_ERROR,
    SERVER_CONNECTION_ERROR,
    WATCH_ERROR,
    FILE_INVALID,
    PLUGIN_LOAD_ERROR,
)
from .plugin_loader import load_plugins
from .rebuild import rebuild_flows
from .watcher_stages import sync_from_server, rebuild_and_deploy
from .constants import (
    MAX_NETWORK_RETRIES,
    RETRY_BASE_DELAY,
    MAX_REBUILD_FAILURES,
)
from .watcher import WATCH_AVAILABLE


class SrcFileHandler(FileSystemEventHandler):
    """Handles modified file events in src/ directory.

    We only care about modified (write) events; creation/deletion will also trigger
    modifications of directories which will eventually lead to a rebuild once a file
    changes. Hidden files are ignored. While a rebuild is running we suppress further
    modifications to avoid infinite loops.
    """

    def __init__(self, watch_config: WatchConfig) -> None:
        self.watch_config = watch_config

    def on_modified(self, event) -> None:  # type: ignore[override]
        # No need to check pause_watching - observer is stopped/joined when paused
        if getattr(event, "is_directory", False):
            return
        path = Path(getattr(event, "src_path", ""))
        if not path.exists():
            return
        if path.name.startswith("."):  # Ignore hidden/temporary files
            return
        # Record change & mark rebuild
        self.watch_config.last_file_change_time = time.time()
        self.watch_config.rebuild_pending = True
        if self.watch_config.dashboard:
            self.watch_config.dashboard.log_activity(f"File changed: {path.name}")


def poll_nodered(watch_config: WatchConfig) -> None:
    """Periodic polling of Node-RED with exponential backoff retry."""
    consecutive_failures = 0
    max_retries = MAX_NETWORK_RETRIES
    base_delay = RETRY_BASE_DELAY

    while not watch_config.shutdown_requested:
        time.sleep(watch_config.poll_interval)
        if watch_config.shutdown_requested:
            log_info("Polling thread exiting gracefully...")
            break

        success = sync_from_server(watch_config)
        if success:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures <= max_retries:
                delay = base_delay * (2 ** (consecutive_failures - 1))
                log_warning(
                    f"Download failed (attempt {consecutive_failures}/{max_retries}), retrying in {delay}s...",
                    code=SERVER_CONNECTION_ERROR,
                )
                time.sleep(delay)
            else:
                log_error(
                    f"Download failed after {max_retries} retries, will retry on next poll interval",
                    code=SERVER_CONNECTION_ERROR,
                )
                consecutive_failures = 0


def _reload_plugins_cached_set(watch_config: WatchConfig) -> None:
    """Hot-reload plugin modules for the already cached plugin instances only.

    We don't rescan the filesystem or consult config; we simply re-import the
    modules corresponding to currently loaded plugin objects and re-instantiate
    their classes, preserving original ordering and grouping.
    """
    if not watch_config.plugins_dict:
        log_warning("No cached plugins to reload")
        return
    import importlib.util, sys

    new_mapping: Dict[str, list] = {k: [] for k in watch_config.plugins_dict.keys()}

    for p_type, plist in watch_config.plugins_dict.items():
        for plugin in plist:
            # Prefer stored metadata added during initial load
            source_path = getattr(plugin, "_source_path", None)
            cls_name = getattr(plugin, "_class_name", plugin.__class__.__name__)
            mod_name = (
                plugin.__class__.__module__
            )  # fallback name (may be auto-generated)

            if source_path and Path(source_path).exists():
                try:
                    # Remove any existing module to force re-load
                    if mod_name in sys.modules:
                        del sys.modules[mod_name]
                    spec = importlib.util.spec_from_file_location(
                        Path(source_path).stem, source_path
                    )
                    if not spec or not spec.loader:
                        raise RuntimeError("spec_from_file_location returned None")
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    cls = getattr(module, cls_name, None)
                    if cls is None:
                        log_warning(
                            f"Reload skipped: class {cls_name} not found in reloaded module {source_path}",
                            code=PLUGIN_LOAD_ERROR,
                        )
                        continue
                    new_instance = cls()
                    # Re-attach metadata for future reloads
                    try:
                        new_instance._source_path = source_path  # type: ignore[attr-defined]
                        new_instance._class_name = cls_name  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    new_mapping[p_type].append(new_instance)
                    log_info(f"  Reloaded: {new_instance.get_name()} ({p_type})")
                    continue
                except Exception as e:
                    log_warning(
                        f"Path-based reload failed for {source_path}: {e}; attempting module fallback",
                        code=PLUGIN_LOAD_ERROR,
                    )

            # Fallback: attempt module import by name (may fail if not on sys.path)
            try:
                if mod_name in sys.modules:
                    del sys.modules[mod_name]
                module = importlib.util.find_spec(mod_name)
                if module is None:
                    raise ImportError(f"Module spec not found for {mod_name}")
                reloaded = importlib.util.module_from_spec(module)
                assert module.loader is not None
                module.loader.exec_module(reloaded)  # type: ignore[attr-defined]
                cls = getattr(reloaded, cls_name, None)
                if cls is None:
                    log_warning(
                        f"Reload skipped: class {cls_name} not found in module {mod_name}",
                        code=PLUGIN_LOAD_ERROR,
                    )
                    continue
                new_instance = cls()
                new_mapping[p_type].append(new_instance)
                log_info(
                    f"  Reloaded via fallback: {new_instance.get_name()} ({p_type})"
                )
            except Exception as e:
                log_warning(
                    f"Failed to reload plugin {cls_name} ({mod_name}): {e}",
                    code=PLUGIN_LOAD_ERROR,
                )

    watch_config.plugins_dict = new_mapping
    log_success("Plugins reloaded successfully (cached set)")


def handle_command(watch_config: WatchConfig, command: str) -> None:
    """Handle interactive watch mode commands.

    Shortcuts:
      d  download        – force download flows
      u  upload          – rebuild & upload
      c  check           – rebuild, compare, upload if changed
      r  reload-plugins  – reload cached plugin set
      s  status          – show current status
      q  quit            – exit watch mode
      h / ? / help       – show help
    """
    command = command.strip().lower()
    # Acquire server_client once (avoid UnboundLocalError in branches)
    sc = getattr(watch_config, "server_client", None)

    if command in {"?", "h", "help"}:
        for line in [
            "Available Commands:",
            "  d, download       Download latest flows from server",
            "  u, upload         Upload local changes to server",
            "  c, check          Check sync status",
            "  r, reload-plugins Reload plugins",
            "  s, status         Show status",
            "  q, quit           Quit watch mode",
            "  h, help, ?        Show this help",
        ]:
            log_info(line)
        return

    if command in {"q", "quit", "exit"}:
        log_info("Initiating graceful shutdown...")
        watch_config.request_shutdown()
        if watch_config.dashboard:
            watch_config.dashboard.stop()
        return

    if command in {"s", "status"}:
        log_info("=== Watch Mode Status ===")
        log_info(f"Server: {watch_config.server_url}")
        sc = getattr(watch_config, "server_client", None)
        status_text = "Connected" if (sc and sc.is_authenticated) else "Disconnected"
        log_info(f"Status: {status_text}")
        log_info(f"Username: {watch_config.username}")
        log_info("")
        log_info("Synchronization:")
        if sc:
            log_info(f"  ETag: {sc.last_etag or '(none)'}")
            log_info(f"  Rev: {sc.last_rev or '(none)'}")
        else:
            log_info("  ETag: (n/a)")
            log_info("  Rev: (n/a)")
        log_info("")
        log_info("Statistics:")
        if sc:
            log_info(f"  Downloads: {sc.download_count}")
            log_info(f"  Uploads: {sc.upload_count}")
            log_info(f"  Errors: {sc.error_count}")
            if sc.last_download_time or sc.last_upload_time:
                from datetime import datetime

                if sc.last_download_time:
                    ago = int((datetime.now() - sc.last_download_time).total_seconds())
                    log_info(f"  Last download: {ago}s ago")
                if sc.last_upload_time:
                    ago = int((datetime.now() - sc.last_upload_time).total_seconds())
                    log_info(f"  Last upload: {ago}s ago")
        else:
            log_info("  Downloads: 0")
            log_info("  Uploads: 0")
            log_info("  Errors: 0")
        return

    if command in {"d", "download"}:
        log_info("Manual download triggered...")
        sync_from_server(watch_config, force=True)
        return

    if command in {"u", "upload"}:
        log_info("Manual upload triggered (force rebuild)...")
        result = rebuild_flows(
            watch_config.flows_file,
            watch_config.src_dir,
            quiet_plugins=True,
            plugins_dict=watch_config.plugins_dict,
        )
        if result == SUCCESS:
            if sc:
                try:
                    sc.deploy_flows(json.loads(watch_config.flows_file.read_text()))
                except Exception as e:
                    log_error(f"Upload failed: {e}", code=SERVER_CONNECTION_ERROR)
                    return
            log_info("Verifying upload...")
            sync_from_server(watch_config, force=True, count_stats=False)
        else:
            log_error("Rebuild failed, cannot upload", code=REBUILD_ERROR)
        return

    if command in {"c", "check"}:
        log_info("Manual check triggered...")
        try:
            original = json.loads(watch_config.flows_file.read_text())
        except Exception:
            log_error("Failed to read flows file for comparison", code=FILE_INVALID)
            return
        result = rebuild_flows(
            watch_config.flows_file,
            watch_config.src_dir,
            quiet_plugins=True,
            plugins_dict=watch_config.plugins_dict,
        )
        if result != SUCCESS:
            log_error("Rebuild failed", code=REBUILD_ERROR)
            return
        try:
            rebuilt = json.loads(watch_config.flows_file.read_text())
        except Exception:
            log_error(
                "Failed to read rebuilt flows file for comparison", code=FILE_INVALID
            )
            return
        if original != rebuilt:
            log_info("Changes detected, uploading...")
            if sc:
                try:
                    sc.deploy_flows(json.loads(watch_config.flows_file.read_text()))
                except Exception as e:
                    log_error(f"Upload failed: {e}", code=SERVER_CONNECTION_ERROR)
                    return
        else:
            log_info("No changes detected")
        return

    if command in {"r", "reload-plugins", "reload"}:
        log_info("Reloading plugins...")
        try:
            _reload_plugins_cached_set(watch_config)
        except Exception as e:  # Defensive – unexpected errors during reload
            log_error(f"Plugin reload failed: {e}", code=PLUGIN_LOAD_ERROR)
        return

    log_error(f"Unknown command: {command}", code=GENERAL_ERROR)


def watch_src_and_rebuild(watch_config: WatchConfig) -> None:
    """File watching loop – triggers rebuild & deploy after debounce period."""
    event_handler = SrcFileHandler(watch_config)
    observer = Observer()
    observer.schedule(event_handler, str(watch_config.src_dir), recursive=True)
    observer.start()

    # Store observer and handler in config so pause_watching setter can recreate it
    watch_config.observer = observer
    watch_config.observer_event_handler = event_handler

    log_success(f"Watching {watch_config.src_dir} for changes")

    if not watch_config.dashboard:
        log_info("Type '?' or 'help' for available commands")

    consecutive_failures = 0
    max_consecutive_failures = MAX_REBUILD_FAILURES

    try:
        import select
        import sys

        while not watch_config.shutdown_requested:
            if watch_config.rebuild_pending:
                time_since = time.time() - watch_config.last_file_change_time
                if time_since >= watch_config.debounce_seconds:
                    watch_config.rebuild_pending = False
                    if consecutive_failures >= max_consecutive_failures:
                        log_error(
                            f"Skipping rebuild after {max_consecutive_failures} consecutive failures",
                            code=REBUILD_ERROR,
                        )
                        log_error(
                            "Fix the errors and save a file again to retry, or use 'upload' command"
                        )
                    else:
                        watch_config.pause_watching = True
                        try:
                            success = rebuild_and_deploy(watch_config)
                            if success:
                                consecutive_failures = 0
                            else:
                                consecutive_failures += 1
                                log_warning(
                                    f"Rebuild/deploy failed (failure {consecutive_failures}/{max_consecutive_failures})",
                                    code=REBUILD_ERROR,
                                )
                        finally:
                            watch_config.pause_watching = False

            if select.select([sys.stdin], [], [], 0)[0]:
                cmd = sys.stdin.readline().strip()
                if cmd:
                    handle_command(watch_config, cmd)
                    if watch_config.shutdown_requested:
                        break

            if watch_config.shutdown_requested:
                break
            time.sleep(0.1)

        log_info("File watcher exiting gracefully...")
    except KeyboardInterrupt:
        log_info("Keyboard interrupt received - initiating graceful shutdown...")
        watch_config.request_shutdown()
        if watch_config.pause_watching:
            log_info("Waiting for ongoing rebuild/deploy to complete...")
            for _ in range(300):  # up to ~30s
                if not watch_config.pause_watching:
                    break
                time.sleep(0.1)
    finally:
        try:
            observer.stop()
            observer.join()
        except Exception:
            pass
        log_success("Watch mode shutdown complete")


def watch_mode(
    args,
    flows_path: Path,
    src_path: Path,
    plugins_dict: dict = None,
    config: dict = None,
    server_client=None,
) -> int:
    """Entry point for watch mode (bidirectional sync with Node-RED)."""
    if not WATCH_AVAILABLE or not WATCH_MODULES_AVAILABLE:
        log_error("Watch mode requires: pip install requests watchdog")
        return WATCH_ERROR

    watch_config = None
    try:
        if config is None:
            config = {}
        if server_client is None:
            log_error(
                "No server_client provided to watch_mode", code=SERVER_CONNECTION_ERROR
            )
            return SERVER_CONNECTION_ERROR

        # Create WatchConfig with ServerClient and file paths
        watch_config = WatchConfig(
            server_client=server_client,
            flows_path=flows_path,
            src_path=src_path,
            use_dashboard=getattr(args, "dashboard", False),
        )

        # Verify connection (ServerClient may already be authenticated from initialize_system)
        if not server_client.is_authenticated:
            if not server_client.connect():
                log_error(
                    "Connection failed for watch mode", code=SERVER_CONNECTION_ERROR
                )
                return SERVER_CONNECTION_ERROR

        # Attach plugins and command handler
        if plugins_dict is not None:
            watch_config.plugins_dict = plugins_dict
        watch_config.command_handler = handle_command

        if watch_config.dashboard:
            setup_complete = threading.Event()
            setup_success = [False]

            def startup_worker():
                """Background thread for initial setup."""
                if not watch_config.src_dir.exists():
                    log_info(f"Creating source directory: {watch_config.src_dir}")
                    watch_config.src_dir.mkdir(parents=True, exist_ok=True)
                setup_success[0] = True
                poll_thread = threading.Thread(
                    target=poll_nodered, args=(watch_config,), daemon=True
                )
                poll_thread.start()
                watch_thread = threading.Thread(
                    target=watch_src_and_rebuild, args=(watch_config,), daemon=True
                )
                watch_thread.start()
                setup_complete.set()

            setup_thread = threading.Thread(target=startup_worker, daemon=True)
            setup_thread.start()
            watch_config.dashboard.start()
            watch_config.dashboard.run()
            if not setup_complete.is_set():
                log_error(
                    "Dashboard exited before initial setup completed", code=WATCH_ERROR
                )
            elif not setup_success[0]:
                log_error("Setup thread reported failure", code=WATCH_ERROR)
            else:
                # Normal successful dashboard run
                pass
            # Return SUCCESS for graceful exit regardless; errors already logged
            return SUCCESS

        # Non-dashboard mode
        if not watch_config.src_dir.exists():
            log_info(f"Creating source directory: {watch_config.src_dir}")
            watch_config.src_dir.mkdir(parents=True, exist_ok=True)
        try:
            poll_thread = threading.Thread(
                target=poll_nodered, args=(watch_config,), daemon=True
            )
            poll_thread.start()
            watch_src_and_rebuild(watch_config)
        except KeyboardInterrupt:
            watch_config.request_shutdown()
            time.sleep(0.5)  # allow threads to observe shutdown flag
        return SUCCESS
    finally:
        if watch_config and watch_config.dashboard:
            try:
                watch_config.dashboard.stop()
            except Exception:
                pass
        log_info("Watch mode cleanup complete")

    # Duplicate legacy watch_mode removed (see earlier definition). This stub has been eliminated.
