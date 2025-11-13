"""ServerClient

Single cohesive class encapsulating all interaction with a Node-RED server.
Replaces the old auth.ServerCredentials + scattered watcher_server functions approach.

Responsibilities:
- Store connection/auth configuration (url, auth_type, username/password/token, verify_ssl)
- Manage a requests.Session with proper auth headers
- Provide authenticate() (internal) and connect() (explicit initial test)
- Provide get_flows(force=False) with ETag handling returning (no_change, flows, new_etag, new_rev)
- Provide deploy_flows(flows_array, count_stats=True) with rev/etag updates and convergence tracking
- Track statistics: downloads, uploads, errors
- Track rev, ETag, and convergence cycles (oscillation detection)
- Enforce rate limiting via internal RateLimiter
- Automatically refresh auth on 401/403 responses once

Public Methods (minimal surface):
- connect() -> bool  (initial explicit authentication test)
- get_flows(force: bool = False) -> tuple[bool, list|None]
- deploy_flows(flows_array: list, count_stats: bool = True) -> bool
- is_authenticated -> bool (property)
- server_url / auth_type / verify_ssl (properties)

The WatchConfig will hold a reference to a ServerClient instance instead of credentials & session fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, TYPE_CHECKING, Any

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:  # pragma: no cover
    requests = None  # type: ignore
    HTTPBasicAuth = object  # type: ignore

if TYPE_CHECKING:
    # Provide type-only imports to satisfy static analyzers
    import requests as _requests

from .logging import log_info, log_success, log_warning, log_error
from .exit_codes import (
    SERVER_CONNECTION_ERROR,
    SERVER_AUTH_ERROR,
    SERVER_CONFLICT,
    SERVER_ERROR,
    FILE_NOT_FOUND,
    GENERAL_ERROR,
)
from .auth import resolve_auth_config, AuthConfig
from .constants import (
    HTTP_TIMEOUT,
    HTTP_NOT_MODIFIED,
    HTTP_UNAUTHORIZED,
    HTTP_FORBIDDEN,
    HTTP_CONFLICT,
    DEFAULT_CONVERGENCE_LIMIT,
    DEFAULT_CONVERGENCE_WINDOW,
)
from .utils import RateLimiter


@dataclass(init=False)
class ServerClient:
    """Encapsulates Node-RED server interaction and state."""

    url: str
    auth_type: str  # 'none', 'basic', 'bearer'
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    verify_ssl: bool = True

    # Runtime / session state (internal)
    _session: Optional["_requests.Session"] = field(
        default=None, init=False, repr=False
    )
    _authenticated: bool = field(default=False, init=False, repr=False)

    # Flow tracking
    last_etag: Optional[str] = None
    last_rev: Optional[str] = None

    # Oscillation detection (prevents infinite upload/download loops)
    # Tracks timestamps of recent deployments; if too many happen in a short window,
    # pauses automatic downloads until user manually uploads (resumes normal operation)
    convergence_cycles: List[datetime] = field(default_factory=list)
    convergence_limit: int = field(
        default=DEFAULT_CONVERGENCE_LIMIT
    )  # Max cycles in window
    convergence_window: int = field(
        default=DEFAULT_CONVERGENCE_WINDOW
    )  # Time window (seconds)
    convergence_paused: bool = False  # True when oscillation detected

    # Statistics
    download_count: int = 0
    upload_count: int = 0
    error_count: int = 0
    last_download_time: Optional[datetime] = None
    last_upload_time: Optional[datetime] = None

    # Rate limiting
    rate_limiter: RateLimiter = field(default_factory=RateLimiter)

    # flows_file path (needed for get_and_store_flows to write downloaded flows)
    flows_file: Optional[Path] = field(default=None)

    # ------------------------------------------------------------------
    # Credential resolution helper (integrated variant of old resolve_credentials)
    # ------------------------------------------------------------------
    def __init__(self, args: Any, config: dict):
        """Direct initializer building a fully configured ServerClient from CLI args + config.

        Args:
            args: Parsed CLI arguments object (expects .flows at minimum)
            config: Loaded configuration dictionary
        """
        flows_arg = getattr(args, "flows", None)
        if not flows_arg:
            raise ValueError("'flows' argument is required to construct ServerClient")

        flows_path = Path(flows_arg).resolve()
        auth: AuthConfig = resolve_auth_config(args, config)

        # Assign config/auth fields
        self.url = auth.url
        self.auth_type = auth.auth_type
        self.username = auth.username
        self.password = auth.password
        self.token = auth.token
        self.verify_ssl = auth.verify_ssl
        self._auth = auth  # retain full struct if future logic needs

        # Runtime state
        self._session = None
        self._authenticated = False
        self.last_etag = None
        self.last_rev = None
        self.convergence_cycles = []
        self.convergence_limit = DEFAULT_CONVERGENCE_LIMIT
        self.convergence_window = DEFAULT_CONVERGENCE_WINDOW
        self.convergence_paused = False
        self.download_count = 0
        self.upload_count = 0
        self.error_count = 0
        self.last_download_time = None
        self.last_upload_time = None
        self.rate_limiter = RateLimiter()

        # flows_file path (only thing ServerClient needs to know about filesystem)
        self.flows_file = flows_path

    @classmethod
    def from_args_and_config(
        cls, args: Any, config: dict
    ) -> "ServerClient":  # pragma: no cover - legacy wrapper
        """Deprecated factory retained for backward compatibility."""
        return cls(args, config)

    def _build_session(self) -> None:
        """Build requests session with authentication (logging already done by resolve_auth_config)"""
        if requests is None:
            raise RuntimeError(
                "'requests' library not available. Install it to use ServerClient."
            )
        self._session = requests.Session()
        self._session.verify = self.verify_ssl
        if self.auth_type == "bearer" and self.token:
            self._session.headers.update({"Authorization": f"Bearer {self.token}"})
        elif self.auth_type == "basic" and self.username and self.password:
            self._session.auth = HTTPBasicAuth(self.username, self.password)
        elif self.auth_type == "none":
            pass  # Anonymous access
        else:
            log_error(
                f"Unknown authentication type: {self.auth_type}", code=SERVER_AUTH_ERROR
            )
            raise ValueError(f"Unknown authentication type: {self.auth_type}")

        if not self.verify_ssl:
            try:
                import urllib3

                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                log_warning("SSL verification disabled", code=SERVER_CONNECTION_ERROR)
            except Exception:
                pass

    @property
    def session(self):  # -> requests.Session (runtime optional)
        if not self._session:
            self._build_session()
        return self._session  # type: ignore

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    def connect(self) -> bool:
        """Explicit initial authentication/connect test."""
        try:
            # Rate limit check
            if not self.rate_limiter.try_acquire():
                stats = self.rate_limiter.get_stats()
                log_error(
                    f"Rate limit exceeded during authentication: {stats['requests_last_minute']}/{stats['limit_per_minute']} requests/min",
                    code=SERVER_CONNECTION_ERROR,
                )
                return False
            resp = self.session.get(f"{self.url}/flows", timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            log_success(f"Connected to Node-RED at {self.url}")
            self._authenticated = True
            return True
        except Exception as e:
            self.error_count += 1
            log_error(f"Connection failed: {e}", code=SERVER_CONNECTION_ERROR)
            return False

    def _ensure_auth(self) -> bool:
        if self.is_authenticated:
            return True
        return self.connect()

    def _check_rate(self) -> bool:
        if not self.rate_limiter.try_acquire():
            stats = self.rate_limiter.get_stats()
            log_error(
                f"Rate limit exceeded: {stats['requests_last_minute']}/{stats['limit_per_minute']} requests/min, "
                f"{stats['requests_last_10min']}/{stats['limit_per_10min']} requests/10min",
                code=SERVER_CONNECTION_ERROR,
            )
            return False
        return True

    def get_and_store_flows(self, force: bool = False) -> Tuple[bool, Optional[list]]:
        """Retrieve flows and store them if changed.

        Returns (changed, flows_list_or_none)
        - changed True means flows downloaded and written
        - changed False means 304 (no new flows) or failure
        flows_list_or_none is provided only when changed=True
        """
        if not self._ensure_auth():
            return False, None
        if not self._check_rate():
            return False, None
        headers = {"Node-RED-API-Version": "v2"}
        if not force and self.last_etag:
            headers["If-None-Match"] = self.last_etag
        resp = self.session.get(
            f"{self.url}/flows", headers=headers, timeout=HTTP_TIMEOUT
        )
        if resp.status_code == HTTP_NOT_MODIFIED:
            return False, None
        resp.raise_for_status()
        new_etag = resp.headers.get("ETag")
        flows = resp.json()
        new_rev = None
        if isinstance(flows, dict) and "rev" in flows:
            new_rev = flows.get("rev")
            flows = flows.get("flows", [])
        if new_etag:
            self.last_etag = new_etag
        if new_rev:
            if new_rev != self.last_rev:
                log_info(
                    f"Flows changed (rev: {self.last_rev or 'initial'} → {new_rev})"
                )
            self.last_rev = new_rev
        self.download_count += 1
        self.last_download_time = datetime.now()
        # Persist flows immediately
        if not self.flows_file:
            log_error("flows_file path not set on ServerClient", code=FILE_NOT_FOUND)
            return False, None
        try:
            self.flows_file.parent.mkdir(parents=True, exist_ok=True)
            import json5 as _json

            self.flows_file.write_text(
                _json.dumps(
                    flows, separators=(",", ":"), ensure_ascii=False, quote_keys=True
                )
                + "\n"
            )
        except Exception as e:
            self.error_count += 1
            log_error(f"Failed to write flows file: {e}", code=GENERAL_ERROR)
            return False, None
        return True, flows

    def deploy_flows(self, flows_array: list, count_stats: bool = True) -> bool:
        """Deploy flows to server."""
        if not self._ensure_auth():
            return False
        if not self._check_rate():
            return False

        try:
            headers = {
                "Content-Type": "application/json",
                "Node-RED-Deployment-Type": "full",
                "Node-RED-API-Version": "v2",
            }
            body = {"flows": flows_array}
            import json5 as _json

            formatted_body = _json.dumps(
                body, separators=(",", ":"), ensure_ascii=False, quote_keys=True
            )
            params = {}
            if self.last_rev:
                params["rev"] = self.last_rev
            resp = self.session.post(
                f"{self.url}/flows",
                data=formatted_body,
                headers=headers,
                params=params,
                timeout=HTTP_TIMEOUT,
            )
            # Re-auth flow
            if resp.status_code in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
                log_warning(
                    "Authentication expired, re-authenticating...",
                    code=SERVER_AUTH_ERROR,
                )
                self._authenticated = False
                if not self._ensure_auth():
                    log_error("Re-authentication failed", code=SERVER_AUTH_ERROR)
                    return False
                if not self._check_rate():
                    return False
                resp = self.session.post(
                    f"{self.url}/flows",
                    data=formatted_body,
                    headers=headers,
                    params=params,
                    timeout=HTTP_TIMEOUT,
                )
            if resp.status_code == HTTP_CONFLICT:
                log_error(
                    f"Conflict detected ({HTTP_CONFLICT}) - server flows changed while you were editing",
                    code=SERVER_CONFLICT,
                )
                # Fetch latest to update rev/etag
                try:
                    if not self._check_rate():
                        return False
                    verify_resp = self.session.get(
                        f"{self.url}/flows",
                        headers={"Node-RED-API-Version": "v2"},
                        timeout=HTTP_TIMEOUT,
                    )
                    verify_resp.raise_for_status()
                    verify_etag = verify_resp.headers.get("ETag")
                    verify_data = verify_resp.json()
                    if isinstance(verify_data, dict) and "rev" in verify_data:
                        self.last_rev = verify_data["rev"]
                        log_info(f"Updated to server rev: {self.last_rev}")
                    if verify_etag:
                        self.last_etag = verify_etag
                    log_warning(
                        "Your local changes were not deployed - server was updated by someone else",
                        code=SERVER_CONFLICT,
                    )
                except Exception as e:
                    log_error(
                        f"Failed to fetch latest server state: {e}", code=SERVER_ERROR
                    )
                return False
            resp.raise_for_status()
            result = resp.json()
            deploy_rev = result.get("rev")
            if deploy_rev:
                self.last_rev = deploy_rev
            log_success("Deployed to Node-RED")
        except requests.exceptions.ConnectionError as e:
            log_error(
                f"Deploy failed: Connection error - {e}", code=SERVER_CONNECTION_ERROR
            )
            log_error("Next steps:", code=SERVER_CONNECTION_ERROR)
            log_error(
                f"  1. Verify Node-RED is running at {self.url}",
                code=SERVER_CONNECTION_ERROR,
            )
            log_error("  2. Check network connectivity", code=SERVER_CONNECTION_ERROR)
            log_error(
                "  3. Verify firewall settings allow the connection",
                code=SERVER_CONNECTION_ERROR,
            )
            self.error_count += 1
            return False
        except requests.exceptions.Timeout as e:
            log_error(
                f"Deploy failed: Request timeout - {e}", code=SERVER_CONNECTION_ERROR
            )
            log_error("Next steps:", code=SERVER_CONNECTION_ERROR)
            log_error(
                f"  1. Check if Node-RED server at {self.url} is responding slowly",
                code=SERVER_CONNECTION_ERROR,
            )
            log_error("  2. Verify network latency", code=SERVER_CONNECTION_ERROR)
            log_error(
                "  3. Consider increasing timeout if server is slow",
                code=SERVER_CONNECTION_ERROR,
            )
            self.error_count += 1
            return False
        except requests.exceptions.HTTPError as e:
            log_error(
                f"Deploy failed: HTTP {e.response.status_code} - {e}", code=SERVER_ERROR
            )
            log_error("Next steps:", code=SERVER_ERROR)
            log_error(f"  1. Check Node-RED server logs for details", code=SERVER_ERROR)
            log_error("  2. Verify credentials are correct", code=SERVER_ERROR)
            log_error("  3. Ensure flows.json format is valid", code=SERVER_ERROR)
            self.error_count += 1
            return False
        except Exception as e:
            log_error(f"Deploy failed: Unexpected error - {e}", code=SERVER_ERROR)
            log_error("Next steps:", code=SERVER_ERROR)
            log_error(
                f"  1. Check Node-RED server status at {self.url}", code=SERVER_ERROR
            )
            log_error("  2. Verify credentials are correct", code=SERVER_ERROR)
            log_error("  3. Check network connection", code=SERVER_ERROR)
            log_error("  4. Review server logs for more details", code=SERVER_ERROR)
            self.error_count += 1
            return False
        # Convergence tracking
        now = datetime.now()
        self.convergence_cycles.append(now)
        cutoff = now.timestamp() - self.convergence_window
        self.convergence_cycles = [
            ts for ts in self.convergence_cycles if ts.timestamp() > cutoff
        ]
        if (
            len(self.convergence_cycles) > self.convergence_limit
            and not self.convergence_paused
        ):
            log_warning(
                f"⚠️  Oscillation detected: {len(self.convergence_cycles)} cycles in {self.convergence_window}s",
                code=SERVER_ERROR,
            )
            log_warning(
                "Pausing convergence - manual uploads only until resumed",
                code=SERVER_ERROR,
            )
            self.convergence_paused = True
        if count_stats:
            self.upload_count += 1
            self.last_upload_time = now
            if self.convergence_paused:
                log_success("✓ Convergence resumed by user upload")
                self.convergence_paused = False
                self.convergence_cycles = []
        # Clear etag if not paused
        if not self.convergence_paused:
            self.last_etag = None
            log_info(
                f"Updated state - ETag cleared (will re-download), rev: {deploy_rev}"
            )
        else:
            log_info(
                f"Updated state - Convergence paused (ETag not cleared), rev: {deploy_rev}"
            )
        return True

    # Convenience properties for external consumers (dashboard, etc.)
    @property
    def stats(self) -> dict:
        return {
            "downloads": self.download_count,
            "uploads": self.upload_count,
            "errors": self.error_count,
            "last_download_time": self.last_download_time,
            "last_upload_time": self.last_upload_time,
            "rev": self.last_rev,
            "etag": self.last_etag,
            "convergence_paused": self.convergence_paused,
        }
