"""
Dashboard UI for watch mode

Provides Textual TUI dashboard for watch mode with real-time updates,
activity logging, and command interface.
"""

import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

# Optional textual import
try:
    from textual.app import App, ComposeResult
    from textual.widgets import Static, Input, RichLog

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

from .logging import log_warning, log_info
from .utils import validate_server_url, RateLimiter

# Oscillation protection defaults
DEFAULT_CONVERGENCE_LIMIT = 5  # Max cycles in time window
DEFAULT_CONVERGENCE_WINDOW = 60  # Time window in seconds


class WatchConfig:
    """Configuration for watch mode

    Stores all watch mode configuration, runtime state, statistics,
    and dashboard integration.
    """

    def __init__(self, args, flows_path: Path, src_path: Path):
        """Initialize watch configuration from command line args

        Args:
            args: Argparse namespace with watch mode arguments
            flows_path: Path to flows.json
            src_path: Path to src directory
        """
        self.repo_root = flows_path.parent.parent
        self.src_dir = src_path
        self.flows_file = flows_path
        self.server_url = validate_server_url(args.server)
        self.username = args.username
        self.password = args.password
        self.poll_interval = args.poll_interval
        self.verify_ssl = not args.no_verify_ssl

        # Plugin control (from global args)
        self.enabled_override = None
        self.disabled_override = None
        if hasattr(args, "enable") and args.enable:
            self.enabled_override = [
                name.strip() for name in args.enable.split(",") if name.strip()
            ]
        if hasattr(args, "disable") and args.disable:
            self.disabled_override = [
                name.strip() for name in args.disable.split(",") if name.strip()
            ]

        self.debounce_seconds = args.debounce
        self.use_dashboard = args.dashboard

        # Runtime state
        self.last_etag: Optional[str] = None
        self.last_rev: Optional[str] = None
        self.session: Optional[object] = None  # requests.Session

        # Convergence tracking (oscillation protection)
        self.convergence_cycles: list = (
            []
        )  # Timestamps of recent upload/download cycles
        self.convergence_limit = DEFAULT_CONVERGENCE_LIMIT  # Max cycles in time window
        self.convergence_window = DEFAULT_CONVERGENCE_WINDOW  # Time window in seconds
        self.convergence_paused = False  # True if oscillation detected

        # Statistics (tracked regardless of dashboard)
        self.download_count = 0
        self.upload_count = 0
        self.error_count = 0
        self.last_download_time: Optional[datetime] = None
        self.last_upload_time: Optional[datetime] = None

        # Dashboard
        self.dashboard = WatchDashboard(self) if self.use_dashboard else None

        # Plugin cache (loaded once, reloaded on demand)
        self.plugin_config: Optional[dict] = None
        self.plugins_dict: Optional[dict] = None

        # Command handler callback for dashboard (will be set by watch_mode)
        self.command_handler = None

        # Rate limiter for API calls (prevents runaway requests)
        self.rate_limiter = RateLimiter()

        # Thread-safe state (single lock for all concurrency-sensitive flags)
        self._thread_lock = threading.Lock()
        self._rebuild_pending = False
        self._pause_watching = False
        self._shutdown_requested = False
        self._last_file_change_time = 0.0

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
        """Thread-safe setter for pause_watching flag"""
        with self._thread_lock:
            self._pause_watching = value

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

    def clear_file_watcher_state(self) -> None:
        """Clear file watcher state to prevent false rebuild triggers (thread-safe)

        Clears both rebuild_pending flag and last_file_change_time together.
        Use this when tool-initiated operations write files that shouldn't trigger
        a rebuild cycle (e.g., download/explode/deploy operations).

        Common use cases:
        - After download and explode complete (files came from server)
        - After rebuild and deploy complete (already synced with server)
        - After any tool operation that modifies files but shouldn't trigger rebuild
        """
        self.rebuild_pending = False
        self.last_file_change_time = 0.0

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

    def __init__(self, config: WatchConfig):
        """Initialize dashboard

        Args:
            config: Watch configuration object
        """
        self.config = config
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
            self.config.error_count += 1

        if self.app and self.app.is_running:
            # Check if we're in the app thread
            if threading.get_ident() == self.app._thread_id:
                # Already in app thread, call directly
                self.app.add_log_message(message, is_error)
            else:
                # Different thread, use call_from_thread
                self.app.call_from_thread(self.app.add_log_message, message, is_error)

    def log_download(self):
        """Record download event and update stats"""
        self.config.last_download_time = datetime.now()
        self.config.download_count += 1
        self.log_activity("Downloaded from server")

        if self.app and self.app.is_running:
            if threading.get_ident() == self.app._thread_id:
                self.app.update_stats()
            else:
                self.app.call_from_thread(self.app.update_stats)

    def log_upload(self):
        """Record upload event and update stats"""
        self.config.last_upload_time = datetime.now()
        self.config.upload_count += 1
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
        self.app = NodeRedDashboardApp(self.config)

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
            grid-size: 2 3;
            grid-rows: auto 1fr auto;
        }

        #status_panel {
            column-span: 2;
            height: auto;
            border: solid $primary;
        }

        #activity_log {
            column-span: 2;
            border: solid $success;
        }

        #command_input {
            column-span: 2;
            dock: bottom;
        }

        Static {
            padding: 1;
        }
        """

        BINDINGS = [
            ("q", "quit", "Quit"),
            ("ctrl+c", "quit", "Quit"),
        ]

        def __init__(self, config: WatchConfig):
            """Initialize dashboard app

            Args:
                config: Watch configuration object
            """
            super().__init__()
            self.config = config
            self.title = "Node-RED Watch Mode Dashboard"

        def compose(self) -> ComposeResult:
            """Create child widgets"""
            yield Static(self._build_status_text(), id="status_panel")
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

            # Focus input widget so it accepts commands
            input_widget = self.query_one("#command_input", Input)
            input_widget.focus()

        def _build_status_text(self) -> str:
            """Build status panel text

            Returns:
                Formatted status text with markup
            """
            status_icon = "✓" if self.config.session else "✗"
            status_color = "green" if self.config.session else "red"

            etag = self.config.last_etag or "(none)"
            rev = self.config.last_rev or "(none)"

            # Time since last sync
            download_ago = ""
            if self.config.last_download_time:
                ago = int(
                    (datetime.now() - self.config.last_download_time).total_seconds()
                )
                download_ago = f" ({ago}s ago)"

            upload_ago = ""
            if self.config.last_upload_time:
                ago = int(
                    (datetime.now() - self.config.last_upload_time).total_seconds()
                )
                upload_ago = f" ({ago}s ago)"

            return f"""[bold]Node-RED Watch Mode[/bold] - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[cyan]Server:[/cyan] {self.config.server_url}
[cyan]Status:[/cyan] [{status_color}]{status_icon} {"Connected" if self.config.session else "Disconnected"}[/{status_color}]
[cyan]User:[/cyan] {self.config.username}

[bold]Synchronization:[/bold]
  ETag: {etag}
  Rev: {rev}

[bold]Statistics:[/bold]
  Downloads: {self.config.download_count}{download_ago}
  Uploads: {self.config.upload_count}{upload_ago}
  Errors: [red]{self.config.error_count}[/red]"""

        def update_stats(self) -> None:
            """Update status panel with current stats"""
            status_widget = self.query_one("#status_panel", Static)
            status_widget.update(self._build_status_text())

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
            if hasattr(self.config, "handle_dashboard_command"):

                def run_command():
                    self.config.handle_dashboard_command(command)

                thread = threading.Thread(target=run_command, daemon=True)
                thread.start()
            else:
                self.add_log_message(
                    "Command handling not yet configured", is_error=True
                )
