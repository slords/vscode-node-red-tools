# Changelog

All notable changes to vscode-node-red-tools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
