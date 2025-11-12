# Changelog

All notable changes to vscode-node-red-tools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2025-01-12

### Major Enhancements

This release focuses on production readiness with comprehensive error handling, logging infrastructure, and extensive documentation improvements.

### Added

- **Logging Levels System**
  - New `LogLevel` enum (DEBUG, INFO, WARNING, ERROR)
  - Global `--quiet` flag (warnings and errors only)
  - Global `--verbose` flag (debug messages)
  - Global `--log-level` flag (explicit level control)
  - Environment variable `NODERED_TOOLS_LOG_LEVEL` for global configuration
  - Precedence: CLI flags > environment variable > default (INFO)
  - Dashboard-aware logging (redirects to TUI when active)

- **Error Codes System**
  - All errors and warnings now include error codes ([E##], [W##])
  - Category-based code ranges:
    - 0: Success
    - 1-9: General errors
    - 10-19: Configuration errors
    - 20-29: File system errors
    - 30-39: Server/network errors
    - 40-49: Validation errors
    - 50-59: Plugin errors
    - 60-69: Operation errors
  - Named exit code constants in `helper/exit_codes.py`
  - All return statements now use named constants instead of magic numbers
  - Comprehensive error code documentation functions

- **Actionable Error Messages**
  - Deploy failures now include "Next steps" guidance
  - Connection errors provide troubleshooting steps
  - Timeout errors suggest diagnostics
  - HTTP errors reference server logs and credentials

- **ServerClient Refactoring**
  - New unified `ServerClient` class encapsulating all server interactions
  - Centralized authentication handling (token, basic auth, token file)
  - Integrated download/deploy/authentication logic
  - Built-in rate limiting (30-second minimum between deploys)
  - Convergence detection and automatic pause
  - Statistics tracking (upload/download counts, timestamps)
  - Proper error handling with recovery attempts

- **Documentation Enhancements**
  - Comprehensive "Common Pitfalls" section in TROUBLESHOOTING.md:
    - Security pitfalls (password exposure, config credentials, SSL verification)
    - Performance tuning (plugin impact, watch mode optimization, network considerations)
    - Large file handling (flows >1MB, many files, memory monitoring)
  - "Error Codes Reference" section in TROUBLESHOOTING.md
  - "Logging Levels" documentation in USAGE.md, CONFIGURATION.md, and TROUBLESHOOTING.md
  - Updated README.md with logging and error handling examples
  - All docs updated to reflect recent changes

### Changed

- **Improved Error Handling**
  - 87 log_error/log_warning calls updated across 12 files with error codes
  - Deploy operations wrapped in try/except with specific error handling
  - Misleading error messages corrected (e.g., "Run 'download'" → "Use watch mode")
  - Better context in error messages

- **Watch Mode Architecture**
  - Legacy credential resolution removed (now handled by ServerClient)
  - Cleaner separation of concerns between watcher and server client
  - Improved file watcher lifecycle management
  - Better handling of missing flows.json
  - Fixed orphan detection path comparison

- **Dashboard Improvements**
  - Fixed layout issues (blank lines, spacing)
  - Proper "single pane of glass" design
  - Improved connection and stats display
  - Better error message handling

- **Code Quality**
  - Removed `repo_root` parameter from entire codebase
  - Fixed security validation for external flows.json paths
  - All Python files now use named exit codes
  - Consistent error code display format

### Fixed

- **Security**
  - Fixed path validation to allow external flows.json paths
  - Proper security warnings in documentation

- **Reliability**
  - Fixed file watcher observer stop/join/recreate pattern
  - Fixed orphan detection path comparison issues
  - Improved error recovery in watch mode

- **Documentation**
  - Corrected misleading error messages
  - Added missing documentation for all recent features
  - Fixed inconsistencies in configuration examples

### Documentation

- TROUBLESHOOTING.md: Added 350+ lines of common pitfalls and best practices
- USAGE.md: Added logging and error code sections with examples
- CONFIGURATION.md: Added logging configuration and error code reference
- README.md: Added logging and error handling showcase
- All documentation updated for recent architectural changes

### Technical Debt

- Removed legacy credential resolution code
- Consolidated server interaction logic
- Eliminated magic number return codes
- Improved code organization and clarity

### Migration Notes

**Logging Levels:**
```bash
# New flags available
python3 vscode-node-red-tools.py --quiet explode    # Warnings/errors only
python3 vscode-node-red-tools.py --verbose rebuild  # Debug messages
export NODERED_TOOLS_LOG_LEVEL=DEBUG               # Set globally
```

**Error Codes:**
All errors now display codes. Example output:
```
✗ [E20] File not found: flows/flows.json
✗ [E30] Failed to connect to Node-RED server
⚠ [W10] Config file not found, using defaults
```

Use error codes when:
- Searching documentation
- Reporting issues
- Automating error handling
- Monitoring watch mode

## [2.0.0] - 2025-01-10

### Breaking Changes

- **Removed `--skip-plugins` flag** - Use `--disable all` instead for consistent plugin control
- **Removed `--skip-pre-explode` and `--skip-post-explode` flags** - Use configuration file to disable specific plugin types
- **Changed plugin control to use `--enable` and `--disable` globally** - These flags now apply to all commands

### Added

- **Global `--enable` and `--disable` parameters** supporting comma-separated plugin lists

  - Example: `--disable all --enable normalize-ids` to run only one plugin
  - Example: `--enable all --disable prettier` to run all except one
  - Support for "all" keyword to enable/disable all plugins at once
  - 4-stage processing order: disable all → enable all → disable list → enable list

- **Global `--flows` and `--src` parameters** with sensible defaults

  - `--flows` defaults to "flows/flows.json"
  - `--src` defaults to "src"
  - Can be overridden globally or by positional arguments in specific commands

- **Plugin preloading architecture**

  - Plugins are loaded once per command invocation instead of multiple times
  - Significantly improves performance for all operations
  - Consistent plugin state across all operations in a command

- **Enhanced `list-plugins` command**
  - Shows actual loaded state when using `--enable`/`--disable` flags
  - Displays "loaded"/"not loaded" status based on CLI overrides
  - Allows testing what plugins would be active before running commands

### Changed

- **Unified plugin control system**

  - All plugins now controlled uniformly through `--enable`/`--disable` or configuration
  - No special CLI flags for specific plugin types
  - Configuration file is now the primary method for plugin control

- **Improved code architecture**
  - Centralized plugin loading in `preload_plugins()` function
  - Reduced code duplication across command handlers
  - Cleaner function signatures using pre-loaded plugins

### Removed

- `--skip-plugins` flag (use `--disable all`)
- `--skip-pre-explode` flag (use config: `{"plugins": {"disabled": ["pre-explode-plugin-name"]}}`)
- `--skip-post-explode` flag (use config: `{"plugins": {"disabled": ["post-explode-plugin-name"]}}`)
- `skip_post_rebuild` internal parameter (dead code - never set to True)
- `skip_plugin_names` internal parameter (dead code - never used with values)

### Migration Guide

If you were using removed flags:

```bash
# Old:
python vscode-node-red-tools.py explode --skip-plugins
python vscode-node-red-tools.py explode --skip-pre-explode

# New:
python vscode-node-red-tools.py --disable all explode
# Or use config file: {"plugins": {"disabled": ["normalize-ids"]}}
```

For selective plugin control:

```bash
# Run only specific plugins:
python vscode-node-red-tools.py --disable all --enable normalize-ids explode

# Run all except specific plugins:
python vscode-node-red-tools.py --enable all --disable prettier rebuild
```

## [1.0.0] - 2025-01-10

### Initial Release

This is the initial release of vscode-node-red-tools, a comprehensive development toolchain for managing Node-RED flows as code.

#### Features

- **Core Commands**

  - `explode`: Break flows.json into individual source files
  - `rebuild`: Reconstruct flows.json from source files
  - `watch`: Bidirectional sync between local files and Node-RED server
  - `verify`: Round-trip consistency checking
  - `diff`: Directory comparison (console and Beyond Compare)
  - `list-plugins`: Show loaded plugins and priorities

- **Plugin System**

  - Extensible architecture with five plugin types (pre-explode, explode, post-explode, pre-rebuild, post-rebuild)
  - Priority-based execution order
  - Configuration support for enabling/disabling plugins

- **Built-in Plugins**

  - ID normalization (converts random IDs to functional names)
  - Action definitions (native JavaScript with export default)
  - Global function declarations
  - Function wrapping for testability
  - Template node support (Vue, HTML, Mustache, etc.)
  - Documentation extraction to Markdown
  - Prettier formatting integration

- **Watch Mode Features**

  - Server polling with ETag caching
  - File system watching with debouncing
  - Optimistic locking with conflict detection
  - Automatic stability checking
  - Optional TUI dashboard
  - Interactive commands

- **Developer Tools**
  - Round-trip verification
  - Statistics and benchmarking
  - Plugin scaffolding
  - Dry-run modes

#### Attribution

This project was inspired by [functions-templates-manager](https://github.com/daniel-payne/functions-templates-manager) by Daniel Payne, which demonstrated the value of editing Node-RED function nodes in VS Code with automatic synchronization.

### Notes

This project was split from a larger toolchain where it previously lived as "node-red-helper" in a tools directory. It has been refactored and enhanced with a plugin architecture and comprehensive watch mode capabilities.
