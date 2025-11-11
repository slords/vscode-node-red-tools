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


def authenticate(config: WatchConfig) -> bool:
    """Authenticate with Node-RED"""
    try:
        config.session = requests.Session()
        config.session.auth = HTTPBasicAuth(config.username, config.password)
        config.session.verify = config.verify_ssl

        if not config.verify_ssl:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            log_warning("SSL verification disabled")

        # Check rate limiter before making authentication request
        if not config.rate_limiter.try_acquire():
            stats = config.rate_limiter.get_stats()
            log_error(
                f"Rate limit exceeded during authentication: "
                f"{stats['requests_last_minute']}/{stats['limit_per_minute']} requests/min"
            )
            return False

        response = config.session.get(
            f"{config.server_url}/flows", timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()

        log_success(f"Authenticated with Node-RED at {config.server_url}")
        return True
    except requests.exceptions.RequestException as e:
        log_error(f"Authentication failed: {e}")
        return False


def _download_flows_from_server(
    config: WatchConfig, force: bool
) -> tuple[bool, list, str, str]:
    """Download flows from Node-RED server

    Args:
        config: Watch configuration
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
    if not config.rate_limiter.try_acquire():
        stats = config.rate_limiter.get_stats()
        raise RuntimeError(
            f"Rate limit exceeded: {stats['requests_last_minute']}/{stats['limit_per_minute']} requests/min, "
            f"{stats['requests_last_10min']}/{stats['limit_per_10min']} requests/10min. "
            f"Possible runaway loop or misconfiguration."
        )

    headers = {"Node-RED-API-Version": "v2"}

    # Only use conditional GET (ETag) if not forced and we have an ETag
    if not force and config.last_etag:
        headers["If-None-Match"] = config.last_etag

    response = config.session.get(
        f"{config.server_url}/flows", headers=headers, timeout=HTTP_TIMEOUT
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


def deploy_to_nodered(config: WatchConfig, count_stats: bool = True) -> bool:
    """Deploy flows to Node-RED

    Args:
        config: Watch configuration
        count_stats: If True, count this upload in statistics (False for plugin auto-uploads)
    """
    try:
        # Check rate limiter before making request
        if not config.rate_limiter.try_acquire():
            stats = config.rate_limiter.get_stats()
            log_error(
                f"Rate limit exceeded: {stats['requests_last_minute']}/{stats['limit_per_minute']} requests/min, "
                f"{stats['requests_last_10min']}/{stats['limit_per_10min']} requests/10min"
            )
            log_error("Possible runaway loop or misconfiguration - deployment aborted")
            return False

        if not config.flows_file.exists():
            log_error(f"Flows file not found: {config.flows_file}")
            return False

        with open(config.flows_file, "r") as f:
            flows_array = json.load(f)

        log_info(f"Deploying to Node-RED at {config.server_url}...")
        headers = {
            "Content-Type": "application/json",
            "Node-RED-Deployment-Type": "full",
            "Node-RED-API-Version": "v2",
        }

        body = {"flows": flows_array}
        formatted_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

        params = {}
        if config.last_rev:
            params["rev"] = config.last_rev

        response = config.session.post(
            f"{config.server_url}/flows",
            data=formatted_body,
            headers=headers,
            params=params,
            timeout=HTTP_TIMEOUT,
        )

        # Handle auth expiration
        if response.status_code in (401, 403):
            log_warning("Authentication expired, re-authenticating...")
            if not authenticate(config):
                log_error("Re-authentication failed")
                return False

            # Check rate limiter for retry request
            if not config.rate_limiter.try_acquire():
                log_error("Rate limit exceeded - cannot retry deployment after re-auth")
                return False

            response = config.session.post(
                f"{config.server_url}/flows",
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
                if not config.rate_limiter.try_acquire():
                    log_error("Rate limit exceeded - cannot fetch latest flows")
                    return False

                verify_response = config.session.get(
                    f"{config.server_url}/flows",
                    headers={"Node-RED-API-Version": "v2"},
                    timeout=HTTP_TIMEOUT,
                )
                verify_response.raise_for_status()

                # Update our state with latest server version
                verify_etag = verify_response.headers.get("ETag")
                verify_data = verify_response.json()

                if isinstance(verify_data, dict) and "rev" in verify_data:
                    new_rev = verify_data["rev"]
                    config.last_rev = new_rev
                    log_info(f"Updated to server rev: {new_rev}")

                if verify_etag:
                    config.last_etag = verify_etag

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
            config.last_rev = deploy_rev

        log_success("Deployed to Node-RED")

        # Track convergence cycle (oscillation protection)
        from datetime import datetime

        now = datetime.now()
        config.convergence_cycles.append(now)

        # Remove cycles outside the time window
        cutoff = now.timestamp() - config.convergence_window
        config.convergence_cycles = [
            ts for ts in config.convergence_cycles if ts.timestamp() > cutoff
        ]

        # Check for oscillation (too many cycles in time window)
        if len(config.convergence_cycles) > config.convergence_limit:
            if not config.convergence_paused:
                log_warning(
                    f"⚠️  Oscillation detected: {len(config.convergence_cycles)} upload/download cycles in {config.convergence_window}s"
                )
                log_warning(
                    "Pausing convergence - plugins may be oscillating. Manual upload will resume."
                )
                config.convergence_paused = True

        # Clear flag on user upload (count_stats=True means user-initiated)
        if count_stats and config.convergence_paused:
            log_success("✓ Convergence resumed by user upload")
            config.convergence_paused = False
            config.convergence_cycles = []  # Clear cycle history

        # Only clear ETag if convergence not paused
        if not config.convergence_paused:
            config.last_etag = None
            log_info(
                f"Updated state - ETag cleared (will re-download), rev: {deploy_rev}"
            )
        else:
            log_info(
                f"Updated state - Convergence paused (ETag not cleared), rev: {deploy_rev}"
            )

        # Update statistics (only if this is a counted upload, not plugin auto-upload)
        if count_stats:
            if config.dashboard:
                config.dashboard.log_upload()
            else:
                # Non-dashboard mode: still track stats
                config.upload_count += 1
                config.last_upload_time = datetime.now()

        return True

    except requests.exceptions.RequestException as e:
        log_error(f"Deploy failed: {e}")
        if config.dashboard:
            config.dashboard.log_activity(f"Deploy failed: {e}", is_error=True)
        return False
