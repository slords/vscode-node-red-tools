# Usage Guide

Complete guide to using vscode-node-red-tools commands and features.

## Table of Contents

- [Basic Workflow](#basic-workflow)
- [Commands](#commands)
  - [explode](#explode)
  - [rebuild](#rebuild)
  - [watch](#watch)
  - [verify](#verify)
  - [diff](#diff)
  - [list-plugins](#list-plugins)
  - [stats](#stats)
  - [benchmark](#benchmark)
  - [new-plugin](#new-plugin)
  - [validate-config](#validate-config)
  - [--version](#--version)
- [File Structure](#file-structure)
- [Workflow Examples](#workflow-examples)

## Basic Workflow

The typical workflow involves three main operations:

1. **Explode** - Break flows.json into source files
2. **Edit** - Modify source files in your editor
3. **Rebuild** - Reconstruct flows.json from source files

```bash
# Explode flows to source files
python3 vscode-node-red-tools.py explode flows/flows.json

# Edit files in src/ with VS Code, vim, etc.

# Rebuild flows.json
python3 vscode-node-red-tools.py rebuild flows/flows.json
```

## Commands

### explode

Breaks `flows.json` into individual source files.

**Syntax:**

```bash
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] explode [OPTIONS] FLOWS_FILE [SRC_DIR]
```

**Arguments:**

- `FLOWS_FILE` - Path to flows.json (optional, defaults to `--flows` value or "flows/flows.json")
- `SRC_DIR` - Output directory (optional, defaults to `--src` value or "src/")

**Options:**

- `--backup` - Create timestamped backup before exploding
- `--delete-orphaned` - Delete orphaned files instead of moving to .orphaned/
- `--dry-run` - Show what would happen without making changes

**Global Options:**

- `--flows PATH` - Set flows.json path (default: "flows/flows.json")
- `--src PATH` - Set source directory (default: "src")
- `--enable PLUGINS` - Enable specific plugins (comma-separated or "all")
- `--disable PLUGINS` - Disable specific plugins (comma-separated or "all")

**What it does:**

1. **Stage 1** - Pre-explode plugins (normalize IDs, modify flows JSON)
2. **Stage 2** - Core explode (extract nodes to files) + Explode plugins
3. **Stage 3** - Post-explode plugins (prettier formatting)

**Creates:**

- `.flow-skeleton.json` - Hidden skeleton with layout/wiring
- Individual files for each node (see [File Structure](#file-structure))

**Examples:**

```bash
# Basic explode (uses defaults)
python3 vscode-node-red-tools.py explode

# Explode specific file
python3 vscode-node-red-tools.py explode flows/flows.json

# Explode to custom directory
python3 vscode-node-red-tools.py explode flows/flows.json custom_src/

# Explode with backup
python3 vscode-node-red-tools.py explode --backup

# Skip all plugins (fast, minimal processing)
python3 vscode-node-red-tools.py --disable all explode

# Run only ID normalization plugin
python3 vscode-node-red-tools.py --disable all --enable normalize-ids explode

# Run all plugins except prettier
python3 vscode-node-red-tools.py --enable all --disable prettier explode
```

### rebuild

Reconstructs `flows.json` from source files.

**Syntax:**

```bash
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] rebuild [OPTIONS] FLOWS_FILE [SRC_DIR]
```

**Arguments:**

- `FLOWS_FILE` - Path to flows.json to create (optional, defaults to `--flows` value or "flows/flows.json")
- `SRC_DIR` - Source directory (optional, defaults to `--src` value or "src/")

**Options:**

- `--backup` - Create timestamped backup before rebuilding
- `--orphan-new` - Move new files (not in skeleton) to .orphaned/
- `--delete-new` - Delete new files (not in skeleton)
- `--dry-run` - Show what would change without writing files

**What it does:**

1. **Stage 1** - Pre-rebuild plugins (process files)
2. **Stage 2** - Core rebuild (assemble flows) + Explode plugins for rebuilding
3. **Stage 3** - Post-rebuild plugins (prettier formatting)

**Examples:**

```bash
# Basic rebuild (uses defaults)
python3 vscode-node-red-tools.py rebuild

# Rebuild specific file
python3 vscode-node-red-tools.py rebuild flows/flows.json

# Rebuild from custom directory
python3 vscode-node-red-tools.py rebuild flows/flows.json custom_src/

# Rebuild with backup
python3 vscode-node-red-tools.py rebuild --backup

# Skip plugins (faster)
python3 vscode-node-red-tools.py --disable all rebuild

# Run only specific plugins
python3 vscode-node-red-tools.py --disable all --enable prettier-pre-rebuild,prettier-post-rebuild rebuild
```

### watch

Bidirectional sync between source files and Node-RED server.

**Syntax:**

```bash
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] watch [OPTIONS]
```

**Server Options:**

- `--server URL` - Node-RED server URL (default: `http://127.0.0.1:1880`)

**Authentication Options (choose one method):**

Bearer Token (Recommended):
- `--token TOKEN` - Bearer token (not recommended - use env var or file instead)
- `--token-file PATH` - Path to file containing bearer token

HTTP Basic:
- `--username USER` - Username for HTTP Basic authentication
- `--password PASS` - Password (not recommended - use env var instead)

**Other Options:**

- `--flows FLOWS_FILE` - Path to flows.json (default: `flows/flows.json`)
- `--src SRC_DIR` - Source directory (default: `src/`)
- `--no-verify-ssl` - Disable SSL certificate verification
- `--dashboard` - Enable TUI dashboard (requires textual)

**Plugin Control (Global Options):**

- `--enable PLUGINS` - Enable specific plugins (comma-separated or "all")
- `--disable PLUGINS` - Disable specific plugins (comma-separated or "all")

**What it does:**

1. Downloads latest flows from server
2. Explodes to src/
3. Watches for changes in **both directions**:
   - **Local changes** (src/ files modified) → rebuild and upload to server
   - **Server changes** (flows modified in Node-RED UI) → download and explode to src/
4. Uses ETag and rev for optimistic locking (prevents conflicts)
5. Automatic stability checking after uploads (converges plugin changes)

**Interactive Commands** (while watching):

- `download` - Manual download from server
- `upload` - Force rebuild and upload
- `check` - Rebuild and upload only if different
- `status` - Show current state (ETag, rev, statistics)
- `reload-plugins` - Reload plugin modules
- `quit` or `exit` - Exit watch mode
- `?` or `help` - Show help

**Examples:**

```bash
# Watch with token file (recommended)
python3 vscode-node-red-tools.py watch \
  --server http://localhost:1880 \
  --token-file ~/.nodered-token

# Watch with token from environment variable (recommended)
export NODERED_TOKEN="your-token-here"
python3 vscode-node-red-tools.py watch --server http://localhost:1880

# Watch with basic auth (password from environment)
export NODERED_PASSWORD="your-password"
python3 vscode-node-red-tools.py watch \
  --server http://localhost:1880 \
  --username admin

# Watch with TUI dashboard
python3 vscode-node-red-tools.py watch \
  --server http://localhost:1880 \
  --token-file ~/.nodered-token \
  --dashboard

# Local development (no authentication)
python3 vscode-node-red-tools.py watch

# HTTPS with self-signed certificate
python3 vscode-node-red-tools.py watch \
  --server https://myserver:1880 \
  --token-file ~/.nodered-token \
  --no-verify-ssl
```

**Authentication Methods:**

The tool supports multiple authentication methods with automatic credential resolution:

1. **Token File** (Most Secure):
   ```bash
   # Create token file
   echo "your-token-here" > ~/.nodered-token
   chmod 600 ~/.nodered-token

   # Use with watch
   python3 vscode-node-red-tools.py watch --token-file ~/.nodered-token
   ```

2. **Environment Variables** (Recommended):
   ```bash
   # Bearer token
   export NODERED_TOKEN="your-token-here"
   python3 vscode-node-red-tools.py watch

   # Basic auth password
   export NODERED_PASSWORD="your-password"
   python3 vscode-node-red-tools.py watch --username admin
   ```

3. **Auto-discovery** (Token Files):
   The tool automatically searches for `.nodered-token` in:
   - Current directory (`./.nodered-token`)
   - Home directory (`~/.nodered-token`)

   ```bash
   # Just run watch - token file auto-discovered
   python3 vscode-node-red-tools.py watch
   ```

4. **Secure Prompt** (Basic Auth):
   If username is provided without password, you'll be prompted securely:
   ```bash
   python3 vscode-node-red-tools.py watch --username admin
   # Enter password for 'admin': [secure input]
   ```

**Security Warning:** Never use `--password` or `--token` CLI parameters in production - they're visible in process lists. Always use environment variables or token files.

**Dashboard Mode:**

When `--dashboard` is enabled, displays a Textual TUI with:

- Status panel (server, connection, sync state)
- Real-time activity log (scrollable)
- Statistics (downloads, uploads, errors, timing)
- Command input (type commands directly)
- Auto-updating timestamps

**Conflict Detection:**

- **ETag** - HTTP header for download change detection (304 Not Modified = no changes)
- **rev** - Node-RED revision parameter for upload conflict detection (409 Conflict = concurrent modification)

If a conflict is detected, watch mode will alert you and pause synchronization.

### verify

Verify round-trip consistency (explode → rebuild produces identical flows).

**Syntax:**

```bash
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] verify FLOWS_FILE
```

**Arguments:**

- `FLOWS_FILE` - Path to flows.json (default: `flows/flows.json`)
- `SRC_DIR` - Temporary directory for testing (default: `src/`)

**Options:**

**What it does:**

1. Loads original flows.json
2. Explodes to temporary directory
3. Rebuilds from temporary directory
4. Compares original vs rebuilt flows
5. Reports differences if any

**Exit Codes:**

- `0` - Verification successful (identical)
- `1` - Verification failed (differences found)

**Examples:**

```bash
# Verify round-trip
python3 vscode-node-red-tools.py verify flows/flows.json

# Verify and use result in script
if python3 vscode-node-red-tools.py verify flows/flows.json; then
  echo "Flows are consistent"
else
  echo "Flows have differences"
fi
```

### diff

Compare two directories or launch Beyond Compare.

**Syntax:**

```bash
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] diff [OPTIONS] SOURCE TARGET
```

**Arguments:**

- `DIR_A` - First directory
- `DIR_B` - Second directory

**Options:**

- `--bcomp` - Use Beyond Compare GUI instead of console diff

**Examples:**

```bash
# Console diff
python3 vscode-node-red-tools.py diff src/ src_backup/

# Beyond Compare GUI
python3 vscode-node-red-tools.py diff --bcomp src/ src_backup/
```

### list-plugins

Show all available plugins organized by execution stage, with their status and priorities.

**Syntax:**

```bash
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] list-plugins
```

**What it shows:**

- Plugins grouped by execution stage (PRE-EXPLODE, EXPLODE, POST-EXPLODE, PRE-REBUILD, POST-REBUILD)
- Plugin name, priority, status (loaded/not loaded), config order, filename
- Total plugin count with enabled/disabled summary

**Plugin Status:**

- `✓ loaded` - Plugin is active (via `--enable` flag or config)
- `✗ not loaded` - Plugin is disabled (via `--disable` flag or config)
- `✓ enabled` - Plugin would be active with current config (no CLI overrides)
- `✗ disabled` - Plugin would be disabled with current config (no CLI overrides)

**Examples:**

```bash
# Show all plugins with default config
python3 vscode-node-red-tools.py list-plugins

# Test which plugins would load with --disable all --enable normalize-ids
python3 vscode-node-red-tools.py --disable all --enable normalize-ids list-plugins

# Test which plugins would load with --enable all --disable prettier
python3 vscode-node-red-tools.py --enable all --disable prettier list-plugins
```

**Sample Output:**

```
PRE-EXPLODE (1 plugins)
-----------------------------------------------------------------------------------------------------
Plugin Name                    Priority   Status         Order     Filename
-----------------------------------------------------------------------------------------------------
normalize-ids                  100        ✓ loaded       -         100_normalize_ids_plugin.py

EXPLODE (6 plugins)
-----------------------------------------------------------------------------------------------------
Plugin Name                    Priority   Status         Order     Filename
-----------------------------------------------------------------------------------------------------
action                         200        ✓ loaded       -         200_action_plugin.py
global-function                210        ✓ loaded       -         210_global_function_plugin.py
...

→ Total: 10 plugins (10 enabled, 0 disabled)
```

### stats

Display comprehensive statistics about your flows and source files.

**Syntax:**

```bash
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] stats
```

**Arguments:**

- `FLOWS_FILE` - Path to flows.json (optional, defaults to `--flows` value or "flows/flows.json")
- `SRC_DIR` - Source directory (optional, defaults to `--src` value or "src/")

**What it shows:**

- Node counts by type
- File counts by extension
- Flow organization (tabs, subflows, groups)
- Plugin information (when loaded)
- Size statistics

**Example:**

```bash
# Basic stats (uses defaults)
python3 vscode-node-red-tools.py stats

# Stats for specific file
python3 vscode-node-red-tools.py stats flows/flows.json

# Skip plugins for faster execution
python3 vscode-node-red-tools.py --disable all stats
```

**Sample output:**

```
Flow Statistics:
  Total nodes: 127
  Function nodes: 45
  Inject nodes: 12
  Debug nodes: 18
  ...

Source Statistics:
  Total files: 89
  JavaScript files: 45
  JSON files: 44
  ...
```

### benchmark

Benchmark explode and rebuild performance to measure tool speed.

**Syntax:**

```bash
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] benchmark [OPTIONS] FLOWS_FILE
```

**Arguments:**

- `FLOWS_FILE` - Path to flows.json (required)
- `SRC_DIR` - Source directory (optional, default: `src/`)

**Options:**

- `--iterations N` - Number of iterations (default: 3)

**What it measures:**

- Explode time (flows → source files)
- Rebuild time (source files → flows)
- Plugin overhead (compare with/without plugins)
- Average, min, max times

**Example:**

```bash
# Run benchmark with default 3 iterations
python3 vscode-node-red-tools.py benchmark flows/flows.json

# More iterations for accuracy
python3 vscode-node-red-tools.py benchmark --iterations 10 flows/flows.json

# Benchmark without plugins
python3 vscode-node-red-tools.py --disable all benchmark flows/flows.json
```

**Sample output:**

```
Benchmarking: 5 iterations
Explode: 0.245s (avg), 0.231s (min), 0.267s (max)
Rebuild: 0.189s (avg), 0.175s (min), 0.201s (max)
Total: 0.434s (avg)
```

### new-plugin

Generate a new plugin scaffold with all required methods.

**Syntax:**

```bash
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] new-plugin NAME TYPE [--priority PRIORITY]
```

**Arguments:**

- `NAME` - Plugin name (lowercase with underscores, e.g., `my_custom`)
- `TYPE` - Plugin type: `pre-explode`, `explode`, `post-explode`, `pre-rebuild`, `post-rebuild`

**Options:**

- `--priority N` - Priority number (auto-assigned by type if not specified)

**What it creates:**

- Plugin file with correct naming (`300_my_custom_plugin.py`)
- Complete class structure with all required methods
- TODO comments showing where to add logic
- Documentation and examples
- Ready to test immediately

**Example:**

```bash
# Create explode plugin (auto-priority 200)
python3 vscode-node-red-tools.py new-plugin my_custom explode

# Create post-explode plugin with custom priority
python3 vscode-node-red-tools.py new-plugin my_formatter post-explode --priority 350
```

**Output:**

```
✓ Created plugin: plugins/200_my_custom_plugin.py
  Class name: MyCustomPlugin
  Type: explode
  Priority: 200

Next steps:
  1. Edit plugins/200_my_custom_plugin.py
  2. Implement the plugin logic
  3. Test with: python vscode-node-red-tools.py list-plugins
```

See [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md) for plugin development guide.

### validate-config

Validate your `.vscode-node-red-tools.json` configuration file.

**Syntax:**

```bash
python3 vscode-node-red-tools.py [GLOBAL_OPTIONS] validate-config
```

**What it checks:**

- JSON syntax validity
- Configuration structure
- Required fields
- Value types and ranges
- Plugin names (enabled/disabled/order)
- Path existence
- Watch mode settings

**Example:**

```bash
python3 vscode-node-red-tools.py validate-config
```

**Sample output:**

```
Validating configuration...
✓ Config file found: .vscode-node-red-tools.json
✓ Valid JSON format
✓ Valid config structure
✓ Flows path exists: flows/flows.json
✓ Source path exists: src/
✓ plugins.enabled is valid (5 plugins)
✓ watch.pollInterval is valid (1s)
✓ watch.debounce is valid (2s)

✓ Configuration is valid
```

**Error example:**

```
✗ Invalid JSON format: Expecting ',' delimiter: line 10 column 5
✗ Configuration is invalid (1 error(s))
```

### --version

Show version information.

**Syntax:**

```bash
python3 vscode-node-red-tools.py --version
```

## File Structure

When you explode flows, files are organized by tab and node type:

```
src/
├── .flow-skeleton.json              # Hidden skeleton with layout/wiring
├── tab_main_flow.json               # Tab definition
├── tab_main_flow.md                 # Tab documentation (optional)
├── tab_my_flows/                    # Nodes in "My Flows" tab
│   ├── func_process_data.json       # Regular function node config
│   ├── func_process_data.wrapped.js # Main function code
│   ├── func_process_data.initialize.js  # Initialize code (optional)
│   ├── func_process_data.finalize.js    # Finalize code (optional)
│   ├── func_process_data.md         # Documentation (optional)
│   ├── template_ui_card.json        # Template node config
│   ├── template_ui_card.vue         # Vue template
│   └── ...
├── subflow_utilities/               # Subflow nodes
│   ├── func_helper.function.js      # Global function (with export default)
│   ├── func_helper.json             # Auto-generated properties
│   ├── func_helper.md               # Optional documentation
│   ├── func_action.def.js           # Action definition (with export default)
│   ├── func_action.execute.js       # Action execute (with export default)
│   ├── func_action.json             # Auto-generated properties
│   └── ...
└── config_http_request.json         # Config nodes at root
```

### File Types

**Regular Function Nodes:**

- `<node_id>.wrapped.js` - Main function code (wrapped with Node-RED parameters)
- `<node_id>.initialize.js` - Initialize code (optional)
- `<node_id>.finalize.js` - Finalize code (optional)
- `<node_id>.json` - Node properties
- `<node_id>.md` - Documentation (optional)

**Global Functions** (`gfunc.functionName`):

- `<node_id>.function.js` - Function declaration (with export default)
- `<node_id>.json` - Auto-generated properties (do not edit)
- `<node_id>.md` - Documentation (optional)

**Actions** (`qcmd.actionName`):

- `<node_id>.def.js` - Action definition (native JavaScript with export default)
- `<node_id>.execute.js` - Execute function (optional, with export default)
- `<node_id>.json` - Auto-generated properties (do not edit)
- `<node_id>.md` - Documentation (optional)

**Template Nodes:**

- `<node_id>.vue` - Dashboard 2 template (ui_template)
- `<node_id>.ui-template.html` - Dashboard 1 template (ui-template)
- `<node_id>.template.<ext>` - Core template node (based on format)
- `<node_id>.json` - Node properties

**Other Nodes:**

- `<node_id>.json` - Node properties
- `<node_id>.md` - Documentation (optional)

## Workflow Examples

### Development Workflow

```bash
# Initial explode
python3 vscode-node-red-tools.py explode flows/flows.json

# Edit files in VS Code
code src/

# Rebuild and test
python3 vscode-node-red-tools.py rebuild flows/flows.json
```

**Note:** The `verify` command is available for testing tool stability (ensuring round-trip consistency), but is not typically needed during normal development.

### Watch Mode Workflow

```bash
# Set up token file (one time)
echo "your-token-here" > ~/.nodered-token
chmod 600 ~/.nodered-token

# Start watch mode
python3 vscode-node-red-tools.py watch --server http://localhost:1880

# Now edit in either place:
# - Edit src/ files → auto-uploads to Node-RED
# - Edit in Node-RED UI → auto-downloads to src/

# Monitor status
status

# Force upload if needed
upload

# Exit when done
quit
```

### Team Collaboration Workflow

```bash
# Developer A: Make changes locally
python3 vscode-node-red-tools.py explode flows/flows.json
# Edit files in src/
python3 vscode-node-red-tools.py rebuild flows/flows.json
git add src/
git commit -m "Add new feature"
git push

# Developer B: Pull changes
git pull
python3 vscode-node-red-tools.py rebuild flows/flows.json
# Import flows.json into Node-RED
```

### Migrating Existing Flows

```bash
# Export flows.json from Node-RED

# Explode with backup
python3 vscode-node-red-tools.py explode --backup flows/flows.json

# Rebuild to stabilize flows (plugins may normalize formatting/structure)
python3 vscode-node-red-tools.py rebuild flows/flows.json

# Verify round-trip stability
python3 vscode-node-red-tools.py verify flows/flows.json

# Commit source files
git add src/
git commit -m "Initial explode of flows"
```

**Note:** Many flows require a full explode/rebuild cycle to stabilize. This ensures plugins converge to a consistent state before committing source files.

## Next Steps

- Review [ARCHITECTURE.md](ARCHITECTURE.md) to understand how the tool works
- See [CONFIGURATION.md](CONFIGURATION.md) for configuration options
- Read [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md) to create custom plugins
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if you encounter issues
