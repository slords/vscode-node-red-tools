"""
Directory comparison and diff utilities

Provides functions for comparing Node-RED flows in different locations:
- Local src directory
- flows.json file
- Node-RED server (via HTTP)
"""

import difflib
import json
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path
from typing import List, Optional

try:
    import requests
    from requests.auth import HTTPBasicAuth

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .logging import log_info, log_error, log_warning
from .utils import HTTP_TIMEOUT


def download_server_flows(
    server_url: str, username: str, password: str, verify_ssl: bool
) -> dict:
    """Download flows from Node-RED server

    Args:
        server_url: Node-RED server URL
        username: Server username
        password: Server password
        verify_ssl: Whether to verify SSL certificates

    Returns:
        Flow data as dictionary

    Raises:
        requests.exceptions.RequestException: If download fails
    """
    if not REQUESTS_AVAILABLE:
        raise ImportError("requests module required for server downloads")

    try:
        session = requests.Session()
        session.auth = HTTPBasicAuth(username, password)
        session.verify = verify_ssl

        if not verify_ssl:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        response = session.get(
            f"{server_url.rstrip('/')}/flows", timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        log_error(f"Failed to download from server: {e}")
        raise


def prepare_source_for_diff(
    source_type: str,
    flows_path: Path,
    src_path: Path,
    server_url: Optional[str],
    username: Optional[str],
    password: Optional[str],
    verify_ssl: bool,
    temp_dir: Path,
    plugins_dict: dict,
    repo_root: Path,
) -> Path:
    """Prepare a source for comparison by creating an exploded directory

    Args:
        source_type: Type of source (src, flow, server)
        flows_path: Path to flows.json
        src_path: Path to src directory
        server_url: Server URL (required for server type)
        username: Server username (required for server type)
        password: Server password (required for server type)
        verify_ssl: Whether to verify SSL
        temp_dir: Temporary directory for exploded files
        plugins_dict: Pre-loaded plugins dictionary
        repo_root: Repository root path

    Returns:
        Path to exploded directory

    Raises:
        ValueError: If source type is invalid or required credentials missing
    """
    source_dir = temp_dir / f"{source_type}_exploded"
    source_dir.mkdir(parents=True, exist_ok=True)

    if source_type == "src":
        # Copy src/ contents to temp (already exploded)
        for item in src_path.iterdir():
            if item.name == ".flow-skeleton.json":
                continue
            dest = source_dir / item.name
            if item.is_file():
                shutil.copy2(item, dest)
            elif item.is_dir():
                shutil.copytree(item, dest)
        return source_dir

    elif source_type == "flow":
        # Explode flows.json to temp
        from .explode import explode_flows
        explode_flows(
            flows_path,
            source_dir,
            quiet_plugins=True,
            plugins_dict=plugins_dict,
            repo_root=repo_root,
        )
        return source_dir

    elif source_type == "server":
        # Download from server, write to temp file, explode
        if not server_url or not username or not password:
            raise ValueError(
                "Server comparison requires --server, --username, and --password"
            )

        log_info(f"Downloading flows from {server_url}")
        flow_data = download_server_flows(server_url, username, password, verify_ssl)

        # Write to temp flows file - compact format
        temp_flows = temp_dir / "server_flows.json"
        temp_flows.write_text(
            json.dumps(flow_data, separators=(",", ":"), ensure_ascii=False) + "\n"
        )

        # Explode to temp directory
        from .explode import explode_flows
        explode_flows(
            temp_flows,
            source_dir,
            quiet_plugins=True,
            plugins_dict=plugins_dict,
            repo_root=repo_root,
        )
        return source_dir

    else:
        raise ValueError(f"Invalid source type: {source_type}")


def unified_diff_files(
    file_a: Path, file_b: Path, label_a: str, label_b: str, context_lines: int = 3
) -> List[str]:
    """Generate unified diff between two files

    Args:
        file_a: First file to compare
        file_b: Second file to compare
        label_a: Label for first file
        label_b: Label for second file
        context_lines: Number of context lines to show (default: 3)

    Returns:
        List of diff lines (empty if files don't exist or are identical)
    """
    if not file_a.exists() or not file_b.exists():
        return []

    with open(file_a, "r") as f:
        a_lines = f.readlines()

    with open(file_b, "r") as f:
        b_lines = f.readlines()

    diff = difflib.unified_diff(
        a_lines,
        b_lines,
        fromfile=f"{label_a}/{file_a.name}",
        tofile=f"{label_b}/{file_b.name}",
        lineterm="",
        n=context_lines,
    )

    return list(diff)


def compare_directories_unified(
    dir_a: Path, dir_b: Path, label_a: str, label_b: str, context_lines: int = 3
) -> None:
    """Compare two directories and show unified diff

    Args:
        dir_a: First directory to compare
        dir_b: Second directory to compare
        label_a: Label for first directory
        label_b: Label for second directory
        context_lines: Number of context lines to show in diffs (default: 3)

    Notes:
        - Prints diff output to stdout
        - Skips .flow-skeleton.json and flows.skeleton.json files
    """
    # Get all files in both directories
    files_a = set(
        p.relative_to(dir_a)
        for p in dir_a.rglob("*")
        if p.is_file() and p.name not in [".flow-skeleton.json", "flows.skeleton.json"]
    )
    files_b = set(
        p.relative_to(dir_b)
        for p in dir_b.rglob("*")
        if p.is_file() and p.name not in [".flow-skeleton.json", "flows.skeleton.json"]
    )

    all_files = files_a | files_b
    has_differences = False

    for rel_path in sorted(all_files):
        file_a = dir_a / rel_path
        file_b = dir_b / rel_path

        # Check if file exists in both
        if not file_a.exists():
            print(f"\n=== Only in {label_b}: {rel_path} ===")
            has_differences = True
            continue

        if not file_b.exists():
            print(f"\n=== Only in {label_a}: {rel_path} ===")
            has_differences = True
            continue

        # Compare files
        diff = unified_diff_files(file_a, file_b, label_a, label_b, context_lines)
        if diff:
            has_differences = True
            print(f"\n=== {rel_path} ===")
            for line in diff:
                print(line)

    if not has_differences:
        print(f"No differences found between {label_a} and {label_b}")


def launch_beyond_compare(
    dir_a: Path, dir_b: Path, label_a: str, label_b: str, context_lines: int = 3
) -> None:
    """Launch Beyond Compare to compare directories

    Args:
        dir_a: First directory
        dir_b: Second directory
        label_a: Label for first directory (for display only)
        label_b: Label for second directory (for display only)
        context_lines: Context lines for fallback unified diff (default: 3)

    Notes:
        - Falls back to unified diff if Beyond Compare not found
        - Tries both 'bcomp' and 'bcompare' commands
    """
    try:
        print(f"Left ({label_a}): {dir_a}")
        print(f"Right ({label_b}): {dir_b}")
        result = subprocess.run(["bcomp", str(dir_a), str(dir_b)])

        if result.returncode == 0:
            print(f"\nNo differences found between {label_a} and {label_b}")
        elif result.returncode == 1:
            print(f"\nDifferences found between {label_a} and {label_b}")
        elif result.returncode >= 11:
            print(f"\nError in Beyond Compare (exit code: {result.returncode})")

    except FileNotFoundError:
        try:
            print("bcomp not found, trying bcompare...")
            subprocess.run(["bcompare", "-wait", str(dir_a), str(dir_b)], check=True)
        except FileNotFoundError:
            print("Error: Beyond Compare (bcomp or bcompare) not found")
            print("Falling back to unified diff...")
            compare_directories_unified(dir_a, dir_b, label_a, label_b, context_lines)


def _print_flows_diff(original_path: Path, rebuilt_path: Path) -> None:
    """Print diff between two flows files (for dry-run mode)

    Args:
        original_path: Path to original flows.json
        rebuilt_path: Path to rebuilt flows.json
    """
    try:
        with open(original_path) as f:
            original = json.load(f)
        with open(rebuilt_path) as f:
            rebuilt = json.load(f)

        # Format both as pretty JSON for readable diff
        original_json = json.dumps(original, indent=2, ensure_ascii=False)
        rebuilt_json = json.dumps(rebuilt, indent=2, ensure_ascii=False)

        # Generate unified diff
        diff = list(difflib.unified_diff(
            original_json.splitlines(keepends=True),
            rebuilt_json.splitlines(keepends=True),
            fromfile=str(original_path),
            tofile="(rebuilt - would be written)",
            lineterm=""
        ))

        if diff:
            log_info("\nChanges that would be made:")
            # Print first 100 lines of diff
            for line in diff[:100]:
                print(line.rstrip())
            if len(diff) > 100:
                print(f"\n... ({len(diff) - 100} more lines of diff)")
        else:
            log_info("No changes would be made - files are identical")

    except Exception as e:
        log_warning(f"Could not generate diff: {e}")
        log_info(f"Dry run complete - would write to {original_path}")


def diff_flows(
    source: str,
    target: str,
    flows_path: Path,
    src_path: Path,
    server_url: Optional[str],
    username: Optional[str],
    password: Optional[str],
    verify_ssl: bool,
    use_bcompare: bool,
    plugins_dict: dict = None,
    repo_root: Path = None,
    context: int = 3,
) -> int:
    """Compare two sources (src, flow, or server)

    Args:
        source: Source to compare from (src, flow, server)
        target: Source to compare to (src, flow, server)
        flows_path: Path to flows.json
        src_path: Path to src directory
        server_url: Node-RED server URL (required for server comparisons)
        username: Server username (required for server comparisons)
        password: Server password (required for server comparisons)
        verify_ssl: Whether to verify SSL certificates
        use_bcompare: Use Beyond Compare for visual diff
        plugins_dict: Pre-loaded plugins dictionary
        repo_root: Repository root path
        context: Number of context lines for unified diff

    Returns:
        Exit code (0 = success, 1 = error)
    """
    try:
        valid_sources = ["src", "flow", "server"]
        if source not in valid_sources or target not in valid_sources:
            log_error(
                f"Invalid source/target. Must be one of: {', '.join(valid_sources)}"
            )
            return 1

        if source == target:
            log_error("Source and target must be different")
            return 1

        log_info(f"Comparing {source} → {target}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Prepare both sources for comparison
            log_info(f"Preparing {source} for comparison...")
            source_dir = prepare_source_for_diff(
                source,
                flows_path,
                src_path,
                server_url,
                username,
                password,
                verify_ssl,
                temp_path,
                plugins_dict,
                repo_root,
            )

            log_info(f"Preparing {target} for comparison...")
            target_dir = prepare_source_for_diff(
                target,
                flows_path,
                src_path,
                server_url,
                username,
                password,
                verify_ssl,
                temp_path,
                plugins_dict,
                repo_root,
            )

            # Compare
            if use_bcompare:
                log_info("Launching Beyond Compare...")
                launch_beyond_compare(
                    source_dir, target_dir, source, target, context
                )
            else:
                log_info("Comparing files...\n")
                compare_directories_unified(
                    source_dir, target_dir, source, target, context
                )

        return 0

    except Exception as e:
        log_error(f"Diff failed: {e}")
        traceback.print_exc()
        return 1
