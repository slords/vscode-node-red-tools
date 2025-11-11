"""
Plugin Helper Functions

Shared utility functions that can be used by any plugin.
"""

import re
import subprocess
from pathlib import Path
from typing import Optional

# Import security utilities
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from helper.utils import validate_path_for_subprocess
from helper.constants import SUBPROCESS_TIMEOUT


def to_camel_case(name: str) -> str:
    """Convert node name to camelCase for function/action name.

    Args:
        name: Node name (e.g., "func_build_action" or "Build Action")

    Returns:
        camelCase name (e.g., "buildAction")
    """
    words = re.sub(r"[^a-zA-Z0-9]+", " ", name).split()
    if not words:
        return "unnamed"
    return words[0].lower() + "".join(word.capitalize() for word in words[1:])


def to_snake_case(name: str) -> str:
    """Convert node name to snake_case for action registration.

    Args:
        name: Node name (e.g., "func_build_action" or "Build Action")

    Returns:
        snake_case name (e.g., "build_action")
    """
    words = re.sub(r"[^a-zA-Z0-9]+", " ", name).split()
    if not words:
        return "unnamed"
    return "_".join(word.lower() for word in words)


def extract_function_body(code: str, start_pattern: str) -> Optional[tuple[str, str]]:
    r"""Extract params and body from a function using brace balancing.

    Args:
        code: Source code containing function
        start_pattern: Regex pattern to match function start (must capture params and end with {)
                      Example: r"function\s+\w+\s*\((.*?)\)\s*{"
                      Example: r"\((.*?)\)\s*=>\s*{"

    Returns:
        (params, body) tuple where:
        - params: function parameters as string
        - body: function body content (between opening and closing braces)

        Returns None if pattern doesn't match or braces are unbalanced.

    Example:
        >>> code = "function foo(a, b) { return a + b; }"
        >>> extract_function_body(code, r"function\s+\w+\s*\((.*?)\)\s*{")
        ("a, b", " return a + b; ")
    """
    match = re.search(start_pattern, code, re.DOTALL)
    if not match:
        return None

    params = match.group(1)
    body_start = match.end() - 1  # Position of opening {

    # Balance braces to find function body
    brace_count = 0
    pos = body_start
    while pos < len(code):
        if code[pos] == "{":
            brace_count += 1
        elif code[pos] == "}":
            brace_count -= 1
            if brace_count == 0:
                break
        pos += 1

    if brace_count != 0:
        return None

    body = code[body_start + 1 : pos]
    return (params, body)


def run_prettier(filepath: Path, repo_root: Path) -> bool:
    """Run prettier on a file.

    Args:
        filepath: Path to file to format
        repo_root: Repository root directory (cwd for prettier)

    Returns:
        True if formatting succeeded, False otherwise
    """
    try:
        # Validate path exists and length before passing to subprocess
        validated_filepath = validate_path_for_subprocess(filepath, repo_root)

        result = subprocess.run(
            ["npx", "prettier", "--trailing-comma", "es5", "--write", str(validated_filepath)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        return True
    except FileNotFoundError:
        print(
            f"⚠ Warning: prettier not found (npx command failed) - skipping formatting for {filepath.name}"
        )
        return False
    except subprocess.CalledProcessError as e:
        print(f"⚠ Warning: prettier failed for {filepath.name}")
        if e.stderr:
            # Print first few lines of error
            error_lines = e.stderr.strip().split("\n")
            for line in error_lines[:3]:
                print(f"  {line}")
            if len(error_lines) > 3:
                print(f"  ... ({len(error_lines) - 3} more lines)")
        return False
    except Exception as e:
        print(f"⚠ Warning: unexpected error running prettier for {filepath.name}: {e}")
        return False


def run_prettier_parallel(
    directory: Path, repo_root: Path, additional_files: list = None
) -> bool:
    """Run prettier on a directory in parallel.

    For root files in directory: formats them as a list in one thread.
    For subdirectories: passes each directory to prettier (recursive) in parallel threads.

    Args:
        directory: Directory to format
        repo_root: Repository root directory (cwd for prettier)
        additional_files: Optional list of additional files to include with root files (e.g., flows.json)

    Returns:
        True if any formatting succeeded, False otherwise
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Collect root files (files directly in directory, not in subdirs)
    # Include ALL files (including hidden) - let prettier handle what it can format
    root_files = []
    for item in directory.iterdir():
        if item.is_file():
            root_files.append(item)

    # Add additional files (e.g., flows.json) to root files list
    if additional_files:
        root_files.extend(additional_files)

    # Collect subdirectories (skip .orphaned)
    subdirs = []
    for item in directory.iterdir():
        if item.is_dir() and item.name != ".orphaned":
            subdirs.append(item)

    if not root_files and not subdirs:
        return False

    # Worker function to format root files
    def format_root_files(files: list) -> bool:
        """Format root files as a list"""
        if not files:
            return False

        try:
            # Validate all file paths before passing to subprocess
            validated_files = []
            for f in files:
                try:
                    validated = validate_path_for_subprocess(f, repo_root)
                    validated_files.append(str(validated))
                except ValueError as e:
                    print(f"⚠ Warning: skipping file {f.name}: {e}")
                    continue

            if not validated_files:
                return False

            # Pass all root files to prettier at once
            subprocess.run(
                ["npx", "prettier", "--trailing-comma", "es5", "--write"] + validated_files,
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            return True
        except Exception as e:
            print(f"⚠ Warning: prettier failed for root files: {e}")
            return False

    # Worker function to format a subdirectory
    def format_directory(subdir: Path) -> bool:
        """Format a subdirectory recursively"""
        try:
            # Validate directory path before passing to subprocess
            validated_subdir = validate_path_for_subprocess(subdir, repo_root)

            # Pass directory to prettier (it handles recursion)
            subprocess.run(
                ["npx", "prettier", "--trailing-comma", "es5", "--write", str(validated_subdir)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            return True
        except Exception as e:
            print(f"⚠ Warning: prettier failed for {subdir.name}: {e}")
            return False

    # Build work items
    work_items = []
    if root_files:
        work_items.append(("root", root_files))
    for subdir in subdirs:
        work_items.append(("dir", subdir))

    # Process in parallel if multiple work items
    if len(work_items) > 1:
        any_success = False
        with ThreadPoolExecutor() as executor:
            futures = []
            for work_type, work_data in work_items:
                if work_type == "root":
                    futures.append(executor.submit(format_root_files, work_data))
                else:
                    futures.append(executor.submit(format_directory, work_data))

            for future in as_completed(futures):
                if future.result():
                    any_success = True

        return any_success
    else:
        # Single work item - process sequentially
        work_type, work_data = work_items[0]
        if work_type == "root":
            return format_root_files(work_data)
        else:
            return format_directory(work_data)
