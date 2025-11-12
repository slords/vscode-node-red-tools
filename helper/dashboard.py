"""
Dashboard UI for watch mode

Provides Textual TUI dashboard for watch mode with real-time updates,
activity logging, and command interface.
"""

import os
import threading
from datetime import datetime
from typing import Optional

# Optional textual import
try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal
    from textual.widgets import Static, Input, RichLog

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

from .logging import log_warning, log_info
from .constants import (
    DEFAULT_POLL_INTERVAL,
    DEFAULT_DEBOUNCE,
)


class WatchConfig:
    """Configuration for watch mode

    Holds file paths, plugin cache, dashboard, and links to a `ServerClient`.
    Legacy fields (etag, rev, stats, session) have been removed; code should
    query `server_client` directly for network state and statistics.
    """

    def __init__(
        self,
        server_client,
        flows_path,
        src_path,
        use_dashboard: bool = False,
    ):
        """Initialize WatchConfig with server client and file paths.

        Args:
            server_client: ServerClient instance for server communication
            flows_path: Path to flows.json
            src_path: Path to src directory
            use_dashboard: Whether to enable the interactive dashboard
        """
        self.server_client = server_client
        self.use_dashboard = use_dashboard

        # File paths (passed from watch_mode)
        self.src_dir = src_path
        self.flows_file = flows_path

        # Watch mode settings
        self.poll_interval = DEFAULT_POLL_INTERVAL
        self.debounce_seconds = DEFAULT_DEBOUNCE

        # Dashboard
        self.dashboard = WatchDashboard(self) if self.use_dashboard else None

        # Plugin cache (set by watch_mode)
        self.plugins_dict = None

        # Command handler callback (set externally by watch_mode)
        self.command_handler = None

        # Thread-safe state flags
        self._thread_lock = threading.Lock()
        self._rebuild_pending = False
        self._pause_watching = False
        self._shutdown_requested = False
        self._last_file_change_time = 0.0

        # Watchdog observer (set by watch_src_and_rebuild)
        self.observer = None
        self.observer_event_handler = None  # Handler to recreate observer

    # Convenience properties for backwards compatibility
    @property
    def server_url(self):
        return self.server_client.url

    @property
    def username(self):
        return self.server_client.username

    @property
    def password(self):
        return self.server_client.password

    @property
    def verify_ssl(self):
        return self.server_client.verify_ssl

    @property
    def rebuild_pending(self):
        """Thread-safe getter for rebuild_pending flag"""
        with self._thread_lock:
            return self._rebuild_pending

    @rebuild_pending.setter
    def rebuild_pending(self, value):
        """Thread-safe setter for rebuild_pending flag"""
        with self._thread_lock:
            self._rebuild_pending = value

    @property
    def pause_watching(self):
        """Thread-safe getter for pause_watching flag"""
        with self._thread_lock:
            return self._pause_watching

    @pause_watching.setter
    def pause_watching(self, value):
        """Thread-safe setter for pause_watching flag

        When pausing: Stops and joins the observer thread completely
        When unpausing: Recreates the observer fresh and starts it

        This completely stops file watching during tool operations, avoiding
        any event processing. When resuming, we start with a fresh observer.
        """
        with self._thread_lock:
            # Transitioning TO paused: Stop and join observer
            if not self._pause_watching and value:
                if self.observer:
                    self.observer.stop()
                    self.observer.join()  # Wait for thread to fully terminate
                    self.observer = None

            # Transitioning FROM paused to active: Recreate observer
            elif self._pause_watching and not value:
                # Step 1: Flush filesystem buffers to ensure all writes complete
                os.sync()

                # Step 2: Unconditionally clear file watcher state
                # We paused because we're doing operations that overwrite files
                # Any pending rebuilds are now stale
                self._rebuild_pending = False
                self._last_file_change_time = 0.0

                # Step 3: Recreate observer if we have the handler
                if self.observer_event_handler:
                    self._recreate_observer()

            # Set the flag
            self._pause_watching = value

    def _recreate_observer(self):
        """Recreate the observer with the stored event handler (must be called with lock held)"""
        # Import here to avoid issues if watchdog not available
        try:
            from watchdog.observers import Observer

            self.observer = Observer()
            self.observer.schedule(
                self.observer_event_handler,
                str(self.src_dir),
                recursive=True
            )
            self.observer.start()
        except ImportError:
            pass

    @property
    def shutdown_requested(self) -> bool:
        """Thread-safe getter for shutdown_requested flag"""
        with self._thread_lock:
            return self._shutdown_requested

    @shutdown_requested.setter
    def shutdown_requested(self, value: bool) -> None:
        """Thread-safe setter for shutdown_requested flag"""
        with self._thread_lock:
            self._shutdown_requested = value

    @property
    def last_file_change_time(self) -> float:
        """Thread-safe getter for last_file_change_time"""
        with self._thread_lock:
            return self._last_file_change_time

    @last_file_change_time.setter
    def last_file_change_time(self, value: float) -> None:
        """Thread-safe setter for last_file_change_time"""
        with self._thread_lock:
            self._last_file_change_time = value

    def request_shutdown(self) -> None:
        """Request graceful shutdown of watch mode

        Sets shutdown flag to signal all threads to exit cleanly after
        completing their current operations.
        """
        if not self.shutdown_requested:
            self.shutdown_requested = True
            log_info("Graceful shutdown requested - finishing current operations...")

    def handle_dashboard_command(self, command: str) -> None:
        """Handle command from Textual dashboard

        Args:
            command: Command string from user input
        """
        if self.command_handler:
            self.command_handler(self, command)
        else:
            if self.dashboard:
                self.dashboard.log_activity(
                    "Command handler not initialized", is_error=True
                )


class WatchDashboard:
    """Textual TUI dashboard for watch mode

    Provides real-time UI with status panel, activity log, and command input.
    """

    def __init__(self, watch_config: WatchConfig):
        """Initialize dashboard

        Args:
            config: Watch configuration object
        """
        self.watch_config = watch_config
        self.app = None  # Will be set when starting

        # Import here to avoid circular dependency
        from .logging import set_active_dashboard

        # Set global reference so log functions can find us
        set_active_dashboard(self)

    def log_activity(self, message: str, is_error: bool = False):
        """Add activity to log

        Args:
            message: Log message to display
            is_error: Whether this is an error message
        """
        if is_error:
            sc = getattr(self.watch_config, "server_client", None)
            if sc:
                sc.error_count += 1

        if self.app and self.app.is_running:
            # Check if we're in the app thread
            if threading.get_ident() == self.app._thread_id:
                # Already in app thread, call directly
                self.app.add_log_message(message, is_error)
            else:
                # Different thread, use call_from_thread
                self.app.call_from_thread(self.app.add_log_message, message, is_error)

    def log_download(self):
        """Log download activity (ServerClient handles all counting).

        ServerClient.get_and_store_flows() increments download_count and sets timestamp.
        Dashboard just logs the activity and updates display.
        """
        self.log_activity("Downloaded from server")

        if self.app and self.app.is_running:
            if threading.get_ident() == self.app._thread_id:
                self.app.update_stats()
            else:
                self.app.call_from_thread(self.app.update_stats)

    def log_upload(self):
        """Log upload activity (ServerClient handles all counting).

        ServerClient.deploy_flows() increments upload_count and sets timestamp.
        Dashboard just logs the activity and updates display.
        """
        self.log_activity("Uploaded to server")

        if self.app and self.app.is_running:
            if threading.get_ident() == self.app._thread_id:
                self.app.update_stats()
            else:
                self.app.call_from_thread(self.app.update_stats)

    def start(self):
        """Create the Textual app (will be run in main thread)"""
        if not TEXTUAL_AVAILABLE:
            log_warning("Textual not available, dashboard disabled")
            return

        # Create app instance (will be run by watch_mode in main thread)
        self.app = NodeRedDashboardApp(self.watch_config)

    def run(self):
        """Run the dashboard (blocks until app exits)"""
        if self.app:
            self.app.run()

    def stop(self):
        """Stop the dashboard"""
        if self.app:
            self.app.exit()

            from .logging import set_active_dashboard

            set_active_dashboard(None)


# Textual TUI Application
if TEXTUAL_AVAILABLE:

    class NodeRedDashboardApp(App):
        """Textual TUI for Node-RED watch mode

        Provides real-time dashboard with:
        - Status panel (connection, sync state)
        - Activity log (scrollable)
        - Command input
        - Statistics (downloads, uploads, errors)
        """

        CSS = """
        Screen {
            layout: grid;
            grid-size: 2;
            grid-rows: auto 1fr auto;
            grid-gutter: 0;
            border: solid $primary;
        }

        #status_container {
            column-span: 2;
            layout: horizontal;
            height: auto;
            padding: 0;
            margin: 0;
            border-bottom: solid $primary;
        }

        #connection_panel {
            width: 1fr;
            border-right: solid $primary;
            content-align: left top;
            height: 8;
            padding: 0 1;
            margin: 0;
            overflow-y: hidden;
        }

        #stats_panel {
            width: 35;
            content-align: left top;
            height: 8;
            padding: 0 1;
            margin: 0;
            overflow-y: hidden;
        }

        #activity_log {
            column-span: 2;
            margin: 0;
            padding: 0 1;
            border-bottom: solid $primary;
        }

        #command_input {
            column-span: 2;
            dock: bottom;
            background: transparent;
            color: #00ff00;
            height: 1;
            padding: 0 1;
            margin: 0;
            border: none;
            outline: none;
        }
        #command_input:focus {
            background: transparent;
            color: #00ff00;
            border: none;
            outline: none;
        }
        #command_input > .input--placeholder {
            color: #888888;
        }
        #command_input > * {
            background: transparent;
            color: #00ff00;
        }
        """

        BINDINGS = [
            ("q", "quit", "Quit"),
            ("ctrl+c", "quit", "Quit"),
        ]

        def __init__(self, watch_config: WatchConfig):
            """Initialize dashboard app

            Args:
                config: Watch configuration object
            """
            super().__init__()
            self.watch_config = watch_config
            self.title = "Node-RED Watch Mode Dashboard"

        def compose(self) -> ComposeResult:
            """Create child widgets with two-column status layout"""
            with Horizontal(id="status_container"):
                yield Static(self._build_connection_text(), id="connection_panel")
                yield Static(self._build_stats_text(), id="stats_panel")
            yield RichLog(id="activity_log", highlight=True, markup=True)
            yield Input(
                placeholder="Enter command ([d]ownload, [u]pload, [c]heck, [r]eload-plugins, [s]tatus, [q]uit, [h]elp)",
                id="command_input",
            )

        def on_mount(self) -> None:
            """App mounted, set up periodic refresh"""
            self.set_interval(1.0, self.update_stats)
            log_widget = self.query_one("#activity_log", RichLog)
            log_widget.write("[dim]Dashboard started and ready[/dim]")

            # Focus input widget and force styling (no borders, transparent background)
            input_widget = self.query_one("#command_input", Input)
            input_widget.styles.background = "transparent"
            input_widget.styles.color = "#00ff00"
            input_widget.styles.border = ("none", "transparent")
            input_widget.focus()

        def _build_connection_text(self) -> str:
            """Build connection panel (left column)"""
            sc = getattr(self.watch_config, "server_client", None)
            is_connected = bool(sc and sc.is_authenticated)
            status_icon = "✓" if is_connected else "✗"
            status_color = "green" if is_connected else "red"

            # With fixed-width stats panel, connection panel is flexible
            # Display full rev and etag, let them wrap if needed (overflow hidden prevents layout issues)
            rev = sc.last_rev if sc and sc.last_rev else "(none)"
            etag = sc.last_etag if sc and sc.last_etag else "(none)"

            # Keep full server URL - panel is now flexible width
            server_url = self.watch_config.server_url

            return (
                f"[bold]Node-RED Watch Mode[/bold] - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"[cyan]Server:[/cyan] {server_url}\n"
                f"[cyan]Status:[/cyan] [{status_color}]{status_icon} "
                f"{'Connected' if is_connected else 'Disconnected'}[/{status_color}]\n"
                f"[cyan]User:[/cyan] {self.watch_config.username}\n"
                f"\n"
                f"[bold]Synchronization:[/bold]\n"
                f"  Rev: {rev}\n"
                f"  ETag: {etag}"
            )

        def _build_stats_text(self) -> str:
            """Build statistics panel (right column)"""
            sc = getattr(self.watch_config, "server_client", None)

            # Statistics + timestamps from ServerClient
            downloads = sc.download_count if sc else 0
            uploads = sc.upload_count if sc else 0
            errors = sc.error_count if sc else 0

            download_ago = ""
            if sc and sc.last_download_time:
                ago = int((datetime.now() - sc.last_download_time).total_seconds())
                download_ago = f" ({ago}s ago)"

            upload_ago = ""
            if sc and sc.last_upload_time:
                ago = int((datetime.now() - sc.last_upload_time).total_seconds())
                upload_ago = f" ({ago}s ago)"

            # Get rate limiting stats
            rate_1m = rate_10m = limit_1m = limit_10m = 0
            if sc and sc.rate_limiter:
                rl_stats = sc.rate_limiter.get_stats()
                rate_1m = rl_stats["requests_last_minute"]
                limit_1m = rl_stats["limit_per_minute"]
                rate_10m = rl_stats["requests_last_10min"]
                limit_10m = rl_stats["limit_per_10min"]

            return (
                f"[bold]Statistics:[/bold]\n"
                f"  Downloads: {downloads}{download_ago}\n"
                f"  Uploads: {uploads}{upload_ago}\n"
                f"  Errors: [red]{errors}[/red]\n"
                f"\n"
                f"[bold]Rate Limiting:[/bold]\n"
                f"  1-min: {rate_1m}/{limit_1m}\n"
                f"  10-min: {rate_10m}/{limit_10m}"
            )

        def update_stats(self) -> None:
            """Update both status panels with current info"""
            conn_widget = self.query_one("#connection_panel", Static)
            conn_widget.update(self._build_connection_text())

            stats_widget = self.query_one("#stats_panel", Static)
            stats_widget.update(self._build_stats_text())

        def add_log_message(self, message: str, is_error: bool = False) -> None:
            """Add message to activity log

            Args:
                message: Message to add
                is_error: Whether this is an error message
            """
            log_widget = self.query_one("#activity_log", RichLog)
            timestamp = datetime.now().strftime("%H:%M:%S")

            if is_error:
                log_widget.write(f"[red][{timestamp}] {message}[/red]")
            else:
                log_widget.write(f"[{timestamp}] {message}")

        def on_input_submitted(self, event: Input.Submitted) -> None:
            """Handle command input

            Args:
                event: Input submission event
            """
            command = event.value.strip().lower()
            event.input.value = ""  # Clear input

            if not command:
                return

            # Log the command
            self.add_log_message(f"Command: {command}", is_error=False)

            # Handle command in background thread to avoid blocking UI
            if hasattr(self.watch_config, "handle_dashboard_command"):

                def run_command():
                    self.watch_config.handle_dashboard_command(command)

                thread = threading.Thread(target=run_command, daemon=True)
                thread.start()
            else:
                self.add_log_message(
                    "Command handling not yet configured", is_error=True
                )
