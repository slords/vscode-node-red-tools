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

This project is licensed under the Business Source License 1.1 (BSL-1.1) — see [LICENSE](LICENSE) for details.

**Use Limitations:**
- You may not embed, bundle, or distribute the Software as part of a product, service, or platform offered to third parties, except for non-production evaluation.
- Production use is not permitted by entities (including affiliates) with annual revenue over $1,000,000 unless a commercial license is obtained.

**License Conversion:**
- Each released version of the Licensed Work converts to the GNU Affero General Public License v3.0 (AGPL-3.0) five years from the date that version is published.

**SPDX:** Current `BSL-1.1`; future converted versions `AGPL-3.0-only`.

## Licensing FAQ

**Q: What does “non-production” mean?**  
"Production" refers to any environment (internal or external) where the Software (or a derivative) directly supports real users, customers, revenue-generating processes, SLA‑bound services, or operational workloads whose failure would impact business outcomes. Development, staging, QA, local experimentation, evaluation, prototyping, and internal feature design phases are considered non-production.

**Q: What counts as "embed, bundle, or include"?**  
Embedding, bundling, or including means distributing the Software (original or modified) inside another product, SaaS offering, platform, managed service, toolkit, or artifact delivered to third parties (paid or unpaid), OR shipping it as a dependency whose presence is part of a commercial deliverable. Internal use (e.g. as a developer tool) that is not redistributed to third parties is permitted under the License.

**Q: Can I modify the source for internal tooling?**  
Yes. You may copy, fork, patch, and create derivative works for non-production/internal use so long as you respect the Use Limitations (no production deployment above the revenue threshold and no embedding in a commercial product).

**Q: How is the $1,000,000 annual revenue threshold calculated?**  
Aggregate gross annual revenue (not profit) of the legal entity and all its controlled affiliates for the most recently completed fiscal year. If consolidated financials are produced for regulatory or reporting purposes, use that figure. If you are below the threshold when adoption begins and later exceed it, you must either (a) cease production use and embedding, or (b) seek a separate commercial license.

**Q: What is an affiliate?**  
Any entity that directly or indirectly controls, is controlled by, or is under common control with the licensee ("control" typically meaning ownership of >50% voting interests or equivalent influence over governance).

**Q: Does the Business Source License make this Open Source?**  
Not immediately. BSL is source-available with delayed conversion. Upon the Change Date, the code for that version becomes licensed under AGPL-3.0, which is an OSI-approved copyleft license with a network/service provision.

**Q: What happens at the Change Date?**  
Each specific released version covered by BSL converts to the AGPL-3.0 license exactly five years after its publication date. Newer versions may have a later Change Date. After conversion, AGPL terms apply to that version permanently.

**Q: Can I deploy to production if I’m under $1,000,000 in revenue?**  
Yes, provided you also respect the non-embedding clause. If you exceed the threshold later, production deployment becomes disallowed unless you obtain a commercial license.

**Q: May I publish forks?**  
Public forks for evaluation, experimentation, or collaboration are allowed so long as the fork clearly retains the BSL notice, Use Limitations, and does not violate embedding/production restrictions.

**Q: Why AGPL-3.0 as the Change License?**  
AGPL-3.0 ensures that improvements deployed as network services must be made available under the same terms, aligning long-term openness with user freedom.

**Q: How do I request a commercial license?**  
Open an issue or contact the maintainer with a short description of intended production or embedded use and scale.

**Q: Do I need to track the Change Date per version?**  
Yes. Each released version has its own five-year clock. Tooling that records release timestamps (e.g., tags) can help you manage conversion timelines.

**Q: Is telemetry or usage reporting affected?**  
If added, it must comply with the License terms; internal evaluation telemetry is fine. Providing external hosted dashboards as part of a product with the Software embedded would require a commercial license.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Support

- 📖 Read the [documentation](USAGE.md)
- 🐛 Report issues on GitHub
- 💬 Ask questions in discussions
- ⭐ Star the project if you find it useful!
