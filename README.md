# vscode-node-red-tools

A comprehensive development toolchain for managing Node-RED flows as code. Break down monolithic `flows.json` files into individual, version-controllable source files that can be edited with full IDE support.

## Overview

**vscode-node-red-tools** enables you to:

- 🗂️ **Version Control**: See exactly what changed in diffs - no more massive JSON blobs
- 💻 **IDE Support**: Edit function code with full syntax highlighting, linting, and autocomplete
- 📝 **Documentation**: Keep info/documentation in separate markdown files
- 🔗 **Meaningful IDs**: Replace random IDs with functional names
- 🔄 **Bidirectional Sync**: Watch mode syncs changes between your editor and Node-RED server
- ✅ **Testability**: Export functions for unit testing outside Node-RED

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
npm install -g prettier

# Explode flows to source files
python3 vscode-node-red-tools.py explode flows/flows.json

# Edit files in src/ with your favorite editor

# Rebuild flows from source files
python3 vscode-node-red-tools.py rebuild flows/flows.json

# Or use watch mode for live bidirectional sync
# First, set up authentication (one time):
echo "your-token-here" > ~/.nodered-token
chmod 600 ~/.nodered-token

# Then start watch mode
python3 vscode-node-red-tools.py watch --server http://localhost:1880
```

## What It Does

### Explode

Breaks `flows.json` into individual files:

```
src/
├── .flow-skeleton.json              # Hidden skeleton with layout/wiring
├── tab_main_flow.json               # Tab definition
├── tab_main_flow.md                 # Tab documentation
├── tab_my_flows/                    # Nodes organized by tab
│   ├── func_process_data.json       # Node configuration
│   ├── func_process_data.wrapped.js # Function code (testable)
│   ├── func_process_data.md         # Node documentation
│   └── ...
└── subflow_utilities/               # Subflow nodes
    ├── func_helper.function.js      # Global function
    ├── func_action.def.js           # Action definition
    ├── func_action.execute.js       # Action code
    └── ...
```

### Rebuild

Reconstructs `flows.json` from source files with all changes applied.

### Watch

Bidirectional sync between local files and Node-RED server:

- **Edit locally** → auto-uploads to Node-RED
- **Edit in Node-RED** → auto-downloads to local files
- Conflict detection with optimistic locking
- Optional TUI dashboard for monitoring

## Key Features

### Export Default for Testing

All function code uses `export default` to enable importing for tests:

```javascript
// Regular function (.wrapped.js)
export default function myFunc(msg, node, context, flow, global, env, RED) {
  msg.payload = msg.payload * 2;
  return msg;
}

// Test it
import myFunc from "./src/tab_my_flows/func_process_data.wrapped.js";
const result = myFunc({ payload: 5 }, mockNode, ...);
assert.equal(result.payload, 10);
```

### Plugin System

Extensible architecture for customization:

- **Pre-explode**: Modify flows before exploding (e.g., normalize IDs)
- **Explode**: Extract node-specific data
- **Post-explode**: Format source files
- **Pre-rebuild**: Process files before rebuilding
- **Post-rebuild**: Format final flows.json

Built-in plugins handle ID normalization, function wrapping, action definitions, global functions, templates, and prettier formatting.

### Node Type Support

- **Regular Functions**: Extracted to `.wrapped.js` with all Node-RED parameters
- **Actions**: Native JavaScript `.def.js` files with optional `.execute.js`
- **Global Functions**: Function declarations in `.function.js` files
- **Templates**: Vue, HTML, Mustache, and other template formats
- **Documentation**: Info/documentation in `.md` files

## Documentation

- **[INSTALLATION.md](INSTALLATION.md)** - Dependencies and setup
- **[USAGE.md](USAGE.md)** - Commands, options, and examples
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Design, plugins, and stages
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration file details
- **[PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md)** - Creating custom plugins
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to contribute
- **[CHANGELOG.md](CHANGELOG.md)** - Version history

## Commands

```bash
# Explode flows to source files
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] explode [OPTIONS] FLOWS_FILE [SRC_DIR]

# Rebuild flows from source files
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] rebuild [OPTIONS] FLOWS_FILE [SRC_DIR]

# Watch mode (bidirectional sync)
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] watch [OPTIONS]

# Verify round-trip consistency
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] verify FLOWS_FILE

# Show loaded plugins
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] list-plugins

# Compare directories
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] diff [OPTIONS] SOURCE TARGET

# Display flow statistics
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] stats

# Benchmark performance
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] benchmark [OPTIONS] FLOWS_FILE

# Generate new plugin scaffold
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] new-plugin NAME TYPE [--priority PRIORITY]

# Validate configuration
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] validate-config

# Show version
python3 vscode-node-red-tools.py --version
```

See [USAGE.md](USAGE.md) for detailed command documentation.

## Logging and Error Handling

Built-in logging levels and error codes for better debugging and automation:

```bash
# Control output verbosity
python3 vscode-node-red-tools.py --quiet explode    # Warnings/errors only
python3 vscode-node-red-tools.py --verbose rebuild  # Debug messages
export NODERED_TOOLS_LOG_LEVEL=DEBUG               # Set globally

# All errors include codes for easy troubleshooting
✗ [E20] File not found: flows/flows.json
✗ [E30] Failed to connect to Node-RED server
✗ [E30] Next steps:
✗ [E30]   1. Verify Node-RED is running at http://localhost:1880
⚠ [W10] Config file not found, using defaults
```

See [CONFIGURATION.md](CONFIGURATION.md) for logging configuration and [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for error code reference.

## Requirements

- Python 3.8+
- Node.js + npm (for prettier)
- Python packages: `rich`, `watchdog`, `requests`, `textual`

See [INSTALLATION.md](INSTALLATION.md) for detailed installation instructions.

## Attribution

This project was inspired by [functions-templates-manager](https://github.com/daniel-payne/functions-templates-manager) by Daniel Payne, which demonstrated the value of editing Node-RED function nodes in VS Code with automatic synchronization. We've extended this concept to support all node types, added a plugin architecture for extensibility, and implemented comprehensive bidirectional watch mode with conflict detection.

## License

Historical license reference removed; see current LICENSE (BSL-1.1 → AGPL-3.0) - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Support

- 📖 Read the [documentation](USAGE.md)
- 🐛 Report issues on GitHub
- 💬 Ask questions in discussions
- ⭐ Star the project if you find it useful!
