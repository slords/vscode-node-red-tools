"""
Server communication functions for watch mode

Handles low-level HTTP communication with Node-RED server:
- Authentication
- Downloading flows
- Deploying flows
"""

import json
from datetime import datetime

# Watch-specific imports (conditional)
try:
    import requests
    from requests.auth import HTTPBasicAuth

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .logging import log_info, log_success, log_warning, log_error
from .dashboard import WatchConfig
from .constants import HTTP_TIMEOUT
from .auth import ServerCredentials


def authenticate(watch_config: WatchConfig, credentials: ServerCredentials) -> bool:
    """Authenticate with Node-RED using resolved credentials

    Args:
        watch_config: Watch mode runtime configuration
        credentials: Resolved server credentials from auth.resolve_credentials()

    Returns:
        True if authentication successful, False otherwise
    """
    try:
        # Allow watch_config to be None for simple connection/auth test
        if watch_config is None:
            from .dashboard import WatchConfig
            from pathlib import Path
            dummy_args = type("Args", (), {})()
            # Use minimal dummy paths; not used for actual file ops
            dummy_config = WatchConfig(dummy_args, Path("/tmp/flows.json"), Path("/tmp/src"))
            # Ensure rate_limiter exists
            if not hasattr(dummy_config, "rate_limiter"):
                from .utils import RateLimiter
                dummy_config.rate_limiter = RateLimiter()
            watch_config = dummy_config
        watch_config.session = requests.Session()
        watch_config.session.verify = credentials.verify_ssl

        # Configure authentication based on type
        if credentials.auth_type == "bearer":
            # Bearer token authentication
            watch_config.session.headers.update(
                {"Authorization": f"Bearer {credentials.token}"}
            )
            log_info("Using bearer token authentication")

        elif credentials.auth_type == "basic":
            # HTTP Basic authentication
            watch_config.session.auth = HTTPBasicAuth(
                credentials.username, credentials.password
            )
            log_info(f"Using basic authentication for user: {credentials.username}")

        elif credentials.auth_type == "none":
            # No authentication (local development)
            log_info("Using anonymous access (no authentication)")
        else:
            log_error(f"Unknown authentication type: {credentials.auth_type}")
            return False

        if not credentials.verify_ssl:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            log_warning("SSL verification disabled")

        # Check rate limiter before making authentication request
        if not watch_config.rate_limiter.try_acquire():
            stats = watch_config.rate_limiter.get_stats()
            log_error(
                f"Rate limit exceeded during authentication: "
                f"{stats['requests_last_minute']}/{stats['limit_per_minute']} requests/min"
            )
            return False

        # Test connection with a simple GET request
        response = watch_config.session.get(f"{credentials.url}/flows", timeout=HTTP_TIMEOUT)
        response.raise_for_status()

        # Store server URL in watch_config for other functions
        watch_config.server_url = credentials.url
        watch_config.verify_ssl = credentials.verify_ssl

        log_success(f"Connected to Node-RED at {credentials.url}")
        return True

    except requests.exceptions.RequestException as e:
        log_error(f"Connection failed: {e}")
        return False


def _download_flows_from_server(
    watch_config: WatchConfig, force: bool
) -> tuple[bool, list, str, str]:
    """Download flows from Node-RED server

    Args:
        watch_config: Watch mode runtime configuration
        force: If True, skip ETag check and always download

    Returns:
        tuple of (no_change, flows, new_etag, new_rev)
        - no_change: True if 304 response (no changes), False if content downloaded
        - flows: Flow data (None if no_change)
        - new_etag: New ETag value (None if no_change)
        - new_rev: New revision number (None if no_change or not in response)

    Raises:
        requests.exceptions.RequestException: On network error
        RuntimeError: If rate limit exceeded
    """
    # Check rate limiter before making request
    if not watch_config.rate_limiter.try_acquire():
        stats = watch_config.rate_limiter.get_stats()
        raise RuntimeError(
            f"Rate limit exceeded: {stats['requests_last_minute']}/{stats['limit_per_minute']} requests/min, "
            f"{stats['requests_last_10min']}/{stats['limit_per_10min']} requests/10min. "
            f"Possible runaway loop or misconfiguration."
        )

    headers = {"Node-RED-API-Version": "v2"}

    # Only use conditional GET (ETag) if not forced and we have an ETag
    if not force and watch_config.last_etag:
        headers["If-None-Match"] = watch_config.last_etag

    response = watch_config.session.get(
        f"{watch_config.server_url}/flows", headers=headers, timeout=HTTP_TIMEOUT
    )

    if response.status_code == 304:
        # No changes on server - this is expected in watch mode
        return (True, None, None, None)

    response.raise_for_status()

    # Extract ETag and rev
    new_etag = response.headers.get("ETag")
    flows = response.json()

    new_rev = None
    if isinstance(flows, dict) and "rev" in flows:
        new_rev = flows["rev"]
        flows = flows.get("flows", [])

    return (False, flows, new_etag, new_rev)


def deploy_to_nodered(watch_config: WatchConfig, count_stats: bool = True) -> bool:
    """Deploy flows to Node-RED

    Args:
        watch_config: Watch mode runtime configuration
        count_stats: If True, count this upload in statistics (False for plugin auto-uploads)
    """
    try:
        # Check rate limiter before making request
        if not watch_config.rate_limiter.try_acquire():
            stats = watch_config.rate_limiter.get_stats()
            log_error(
                f"Rate limit exceeded: {stats['requests_last_minute']}/{stats['limit_per_minute']} requests/min, "
                f"{stats['requests_last_10min']}/{stats['limit_per_10min']} requests/10min"
            )
            log_error("Possible runaway loop or misconfiguration - deployment aborted")
            return False

        if not watch_config.flows_file.exists():
            log_error(f"Flows file not found: {watch_config.flows_file}")
            return False

        with open(watch_config.flows_file, "r") as f:
            flows_array = json.load(f)

        log_info(f"Deploying to Node-RED at {watch_config.server_url}...")
        headers = {
            "Content-Type": "application/json",
            "Node-RED-Deployment-Type": "full",
            "Node-RED-API-Version": "v2",
        }

        body = {"flows": flows_array}
        formatted_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

        params = {}
        if watch_config.last_rev:
            params["rev"] = watch_config.last_rev

        response = watch_config.session.post(
            f"{watch_config.server_url}/flows",
            data=formatted_body,
            headers=headers,
            params=params,
            timeout=HTTP_TIMEOUT,
        )

        # Handle auth expiration
        if response.status_code in (401, 403):
            log_warning("Authentication expired, re-authenticating...")
            if not authenticate(watch_config, watch_config.credentials):
                log_error("Re-authentication failed")
                return False

            # Check rate limiter for retry request
            if not watch_config.rate_limiter.try_acquire():
                log_error("Rate limit exceeded - cannot retry deployment after re-auth")
                return False

            response = watch_config.session.post(
                f"{watch_config.server_url}/flows",
                data=formatted_body,
                headers=headers,
                params=params,
                timeout=HTTP_TIMEOUT,
            )

        if response.status_code == 409:
            log_error(
                "Conflict detected (409) - server flows changed while you were editing"
            )
            log_info("Fetching latest flows from server to resolve conflict...")

            # Fetch latest flows and update state
            try:
                # Check rate limiter for conflict resolution request
                if not watch_config.rate_limiter.try_acquire():
                    log_error("Rate limit exceeded - cannot fetch latest flows")
                    return False

                verify_response = watch_config.session.get(
                    f"{watch_config.server_url}/flows",
                    headers={"Node-RED-API-Version": "v2"},
                    timeout=HTTP_TIMEOUT,
                )
                verify_response.raise_for_status()

                # Update our state with latest server version
                verify_etag = verify_response.headers.get("ETag")
                verify_data = verify_response.json()

                if isinstance(verify_data, dict) and "rev" in verify_data:
                    new_rev = verify_data["rev"]
                    watch_config.last_rev = new_rev
                    log_info(f"Updated to server rev: {new_rev}")

                if verify_etag:
                    watch_config.last_etag = verify_etag

                log_warning(
                    "Your local changes were not deployed - server was updated by someone else"
                )
                log_warning(
                    "Will download server version on next poll and your local edits may be lost"
                )
                log_warning(
                    "Recommendation: Save your work elsewhere if needed before next sync"
                )

            except Exception as e:
                log_error(f"Failed to fetch latest server state: {e}")

            return False

        response.raise_for_status()

        # Extract rev from deploy response (accurate)
        result = response.json()
        deploy_rev = result.get("rev")
        if deploy_rev:
            watch_config.last_rev = deploy_rev

        log_success("Deployed to Node-RED")

        # Track convergence cycle (oscillation protection)
        from datetime import datetime

        now = datetime.now()
        watch_config.convergence_cycles.append(now)

        # Remove cycles outside the time window
        cutoff = now.timestamp() - watch_config.convergence_window
        watch_config.convergence_cycles = [
            ts for ts in watch_config.convergence_cycles if ts.timestamp() > cutoff
        ]

        # Check for oscillation (too many cycles in time window)
        if len(watch_config.convergence_cycles) > watch_config.convergence_limit:
            if not watch_config.convergence_paused:
                log_warning(
                    f"⚠️  Oscillation detected: {len(watch_config.convergence_cycles)} upload/download cycles in {watch_config.convergence_window}s"
                )
                log_warning(
                    "Pausing convergence - plugins may be oscillating. Manual upload will resume."
                )
                watch_config.convergence_paused = True

        # Clear flag on user upload (count_stats=True means user-initiated)
        if count_stats and watch_config.convergence_paused:
            log_success("✓ Convergence resumed by user upload")
            watch_config.convergence_paused = False
            watch_config.convergence_cycles = []  # Clear cycle history

        # Only clear ETag if convergence not paused
        if not watch_config.convergence_paused:
            watch_config.last_etag = None
            log_info(
                f"Updated state - ETag cleared (will re-download), rev: {deploy_rev}"
            )
        else:
            log_info(
                f"Updated state - Convergence paused (ETag not cleared), rev: {deploy_rev}"
            )

        # Update statistics (only if this is a counted upload, not plugin auto-upload)
        if count_stats:
            if watch_config.dashboard:
                watch_config.dashboard.log_upload()
            else:
                # Non-dashboard mode: still track stats
                watch_config.upload_count += 1
                watch_config.last_upload_time = datetime.now()

        return True

    except requests.exceptions.RequestException as e:
        log_error(f"Deploy failed: {e}")
        if watch_config.dashboard:
            watch_config.dashboard.log_activity(f"Deploy failed: {e}", is_error=True)
        return False
