# Architecture

This document explains the design principles, architecture, and plugin system of vscode-node-red-tools.

## Table of Contents

- [Design Principles](#design-principles)
- [Separation of Concerns](#separation-of-concerns)
- [Stage-Based Processing](#stage-based-processing)
- [Plugin System](#plugin-system)
- [Watch Mode Architecture](#watch-mode-architecture)
- [Data Flow](#data-flow)

## Design Principles

### 1. Separation of Concerns

The tool follows strict separation between core functionality and transformations:

**Core Tool** (vscode-node-red-tools.py) - Pure orchestrator:
- Loads flows.json
- Breaks nodes into individual JSON files
- Runs plugin stages in order
- No transformations or formatting

**Plugins** - All transformations:
- ID normalization
- Code extraction
- Function wrapping
- Formatting
- Documentation extraction

This separation makes the core stable and extensible through plugins.

### 2. Idempotency

Operations are designed to be idempotent:
- Exploding the same flows.json multiple times produces identical output
- Rebuilding from source files multiple times produces identical flows.json
- Plugins preserve exact function bodies (no reformatting of user code)

### 3. Round-Trip Consistency

The `verify` command tests that:
```
flows.json → explode → rebuild → flows.json'
```

Where `flows.json` and `flows.json'` are semantically identical (may differ in formatting only).

### 4. Extensibility

The plugin architecture allows customization without modifying core code:
- Add new node type handlers
- Customize formatting
- Add validation rules
- Integrate with external tools

## Separation of Concerns

### Core Responsibilities

**vscode-node-red-tools.py:**
- Command-line interface
- Argument parsing
- Plugin loading and orchestration
- Stage management
- Error handling and reporting

**helper/ modules:**
- `explode.py` - Core explode logic (file creation)
- `rebuild.py` - Core rebuild logic (JSON assembly)
- `skeleton.py` - Skeleton file management
- `file_ops.py` - File operations
- `config.py` - Configuration loading
- `watcher*.py` - Watch mode implementation
- `dashboard.py` - TUI dashboard

### Plugin Responsibilities

**Pre-explode plugins:**
- Modify flows JSON before exploding
- Example: normalize-ids converts random IDs to functional names

**Explode plugins:**
- Extract node-specific data to files
- Example: action plugin extracts .def.js and .execute.js

**Post-explode plugins:**
- Format source files after exploding
- Example: prettier-explode formats all source files

**Pre-rebuild plugins:**
- Process files before rebuilding
- Example: prettier-pre-rebuild ensures consistent formatting

**Post-rebuild plugins:**
- Format flows.json after rebuilding
- Example: prettier-post-rebuild formats final JSON

## Stage-Based Processing

Both explode and rebuild use a 3-stage architecture for predictable, modular processing.

### Explode Stages

```
┌─────────────────┐
│  flows.json     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Stage 1: Pre-Explode   │  ← normalize-ids plugin
│  (Modify flows JSON)    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Stage 2: Explode       │  ← action, func, template plugins
│  (Extract to files)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Stage 3: Post-Explode  │  ← prettier-explode plugin
│  (Format files)         │
└────────┬────────────────┘
         │
         ▼
┌─────────────────┐
│  src/           │
│  ├── .flow-skeleton.json
│  ├── tab_*/
│  └── ...
└─────────────────┘
```

### Rebuild Stages

```
┌─────────────────┐
│  src/           │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Stage 1: Pre-Rebuild   │  ← prettier-pre-rebuild plugin
│  (Process files)        │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Stage 2: Rebuild       │  ← action, func, template plugins
│  (Assemble flows)       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Stage 3: Post-Rebuild  │  ← prettier-post-rebuild plugin
│  (Format flows.json)    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────┐
│  flows.json     │
└─────────────────┘
```

## Plugin System

### Plugin Types

Plugins are categorized by when they run:

| Type | When | Purpose | Examples |
|------|------|---------|----------|
| **pre-explode** | Before exploding | Modify flows JSON | normalize-ids |
| **explode** | During explode | Extract node data | action, func, template |
| **post-explode** | After exploding | Format source files | prettier-explode |
| **pre-rebuild** | Before rebuilding | Process source files | prettier-pre-rebuild |
| **post-rebuild** | After rebuilding | Format flows.json | prettier-post-rebuild |

### Plugin Priority

Plugins execute in priority order (lowest first):

1. **Config file order** - `.vscode-node-red-tools.json` `plugins.order` array
2. **get_priority() method** - Return value from plugin
3. **Filename prefix** - Numeric prefix like `100_plugin.py`
4. **Default** - 999 if no priority specified

Example:
```
100_normalize_ids_plugin.py    (priority 100)
200_action_plugin.py           (priority 200)
210_global_function_plugin.py  (priority 210)
300_prettier_explode_plugin.py (priority 300)
```

### Plugin Interface

Each plugin implements:

```python
class MyPlugin:
    def get_name(self) -> str:
        """Return plugin name for identification"""
        return "my-plugin"

    def get_priority(self):
        """Return priority (or None to use filename)"""
        return None

    def get_plugin_type(self) -> str:
        """Return plugin type"""
        return "explode"  # or pre-explode, post-explode, etc.

    # Type-specific methods...
```

### Plugin Communication

Plugins can communicate through the flows JSON and claimed fields:

**Claimed Fields:**
- Plugins mark fields they've handled
- Prevents duplicate processing
- Example: wrap_func claims `func` field, so func plugin skips it

**Flow Modifications:**
- Pre-explode plugins can add metadata to nodes
- Explode plugins read this metadata
- Post-rebuild plugins clean up metadata

## Watch Mode Architecture

Watch mode implements bidirectional sync using two independent monitoring systems.

### Architecture Overview

```
┌──────────────────┐         ┌──────────────────┐
│  Node-RED Server │◄───────►│  Local Files     │
│  (flows.json)    │         │  (src/)          │
└────────┬─────────┘         └────────┬─────────┘
         │                            │
         │ Polling                    │ Watching
         │ (every 1s)                 │ (filesystem events)
         │                            │
         ▼                            ▼
┌────────────────────────────────────────────┐
│           Watch Mode Orchestrator          │
│  ┌──────────────┐      ┌──────────────┐    │
│  │ Server Stage │      │  File Stage  │    │
│  │ (download)   │      │  (rebuild)   │    │
│  └──────────────┘      └──────────────┘    │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │     Convergence Mechanism            │  │
│  │  (etag clearing triggers downloads)  │  │
│  └──────────────────────────────────────┘  │
└────────────────────────────────────────────┘
```

### Server Polling

**Uses HTTP ETag for efficiency:**

```python
# First request
GET /flows
→ 200 OK, ETag: "abc123"
# Store ETag

# Subsequent requests
GET /flows
Headers: If-None-Match: "abc123"
→ 304 Not Modified (no download needed)

# When flows change
GET /flows
Headers: If-None-Match: "abc123"
→ 200 OK, ETag: "def456" (download and explode)
```

**Polling interval:**
- Default: 1 second
- Configurable via `--poll-interval`
- Fast enough for responsiveness
- Slow enough to avoid server load

### File Watching

**Uses watchdog library for filesystem events:**

```python
# File change detected
src/tab_my_flows/func_process.wrapped.js modified
↓
Debounce (wait 2s for more changes)
↓
Pause file watcher (prevent detecting own changes)
↓
Rebuild flows.json
↓
Upload to server (with rev parameter)
  ├─ Clear ETag (triggers re-download on next poll)
  └─ Track cycle for oscillation detection
↓
Resume file watcher
```

**Debouncing:**
- Default: 2 seconds
- Configurable via `--debounce`
- Groups rapid changes into single operation
- Prevents multiple uploads for batch edits

### Optimistic Locking

**Downloads use ETag:**
- 304 Not Modified = skip download
- Efficient caching

**Uploads use rev parameter:**
```python
POST /flows?rev=current_revision
→ 200 OK (success)
→ 409 Conflict (concurrent modification detected)
```

If 409 Conflict occurs:
- Watch mode pauses
- User is alerted
- Manual resolution required

### Convergence Mechanism

After any upload, convergence happens automatically via the polling loop:

```
Upload completes → Clear ETag
↓
Next poll cycle (1 second later)
↓
Is ETag None? ─No──► Normal polling (304 checks)
  │
  Yes (download without If-None-Match)
  ↓
Download from server
↓
Run pre-explode plugins
  └─ Flows modified? → Upload immediately
↓
Run explode stage
  └─ Unstable nodes? (rebuild would differ) → Set upload flag
↓
Run post-explode plugins
  └─ Files modified? → Set upload flag
↓
Upload flag set? → Rebuild + Upload
↓
Is ETag None? → Yes, repeat poll (go to top)
```

**Why this works:**
- Any upload clears ETag to None
- ETag=None forces download on next poll (no If-None-Match header)
- Pre-explode uploads immediately if changes (normalize IDs)
- Explode checks: would rebuild differ? If yes → set upload flag (unstable nodes)
- Post-explode sets flag if formatting changes files
- Upload flag triggers rebuild + upload at end of cycle
- Multiple uploads per cycle possible (both use latest rev from responses)
- When stable (no changes) → ETag gets set → normal 304 polling resumes
- Poll interval (1s) prevents runaway loops

**Convergence example (extreme case):**
- Poll 1: User changed files → Upload → **ETag cleared**
- Poll 2 (1s later):
  - Download → pre-explode normalizes IDs → **Upload #1** (rev updated)
  - Explode writes node files → detects unstable nodes → **set upload flag**
  - Post-explode formats files → **set upload flag** (already set)
  - Check flag → Rebuild + **Upload #2** (uses rev from Upload #1)
  - **ETag cleared** (already None, but cycle tracked)
- Poll 3 (1s later): Download → no changes → ETag set → **Stable**
- Poll 4+: ETag set → 304 Not Modified → efficient polling

**Note:** Explode is normally stable (99% of cases) - explode and rebuild produce
identical results. The any_node_unstable flag detects rare cases where explode
identifies that rebuilding the written files would produce a different node than
the original node it started with (e.g., template code normalized to match node name).
When detected, one upload/download cycle stabilizes it permanently.

**Oscillation Protection:**
- Tracks timestamps of upload/download cycles
- >5 cycles in 60 seconds → oscillation detected
- Pauses convergence (stops clearing ETag)
- Warns user about oscillating plugins
- Normal polling and file watching continue

### Plugin Change Detection

Plugins report whether they modified data:

```python
# Pre-explode plugin
def pre_explode(self, flows):
    modified = self.normalize_ids(flows)
    return {"modified": modified}  # True if changes made

# Post-explode plugin
def post_explode(self, src_dir, flows_file):
    changed_files = self.format_files(src_dir)
    return {"files_changed": bool(changed_files)}
```

## Data Flow

### Explode Data Flow

```
flows.json (list of nodes)
↓
Pre-explode plugins (modify JSON)
↓
Group nodes by parent (tab/subflow)
↓
For each node:
  ├─ Create directory structure
  ├─ Run explode plugins
  │  ├─ Check claimed fields
  │  ├─ Extract data to files
  │  └─ Mark fields as claimed
  └─ Write .json file (remaining fields)
↓
Write .flow-skeleton.json (wiring/layout)
↓
Post-explode plugins (format files)
↓
src/ directory complete
```

### Rebuild Data Flow

```
src/ directory
↓
Read .flow-skeleton.json (wiring/layout)
↓
Pre-rebuild plugins (format source files)
↓
For each node directory:
  ├─ Read .json file (base properties)
  ├─ Run explode plugins in rebuild mode
  │  ├─ Read extracted files
  │  ├─ Inject data back into node
  │  └─ Generate templates if needed
  └─ Merge with skeleton (wiring/layout)
↓
Assemble complete flows (list of nodes)
↓
Post-rebuild plugins (format JSON)
↓
flows.json complete
```

### Watch Mode Data Flow

```
                Start Watch Mode
                       ↓
              Download from server
                       ↓
                Explode to src/
                       ↓
           ┌───────────┴───────────┐
           ▼                       ▼
    Server Polling          File Watching
    (every 1s)              (filesystem events)
           │                       │
           ├─ ETag check          ├─ Debounce
           ├─ Download if changed ├─ Pause watcher
           └─ Explode to src/     ├─ Rebuild
                                  ├─ Upload (clears ETag)
                                  └─ Resume watcher
                                     (next poll re-downloads)
```

## Module Organization

```
vscode-node-red-tools/
├── vscode-node-red-tools.py     # Main entry point, CLI
├── helper/                      # Core functionality
│   ├── __init__.py              # Module exports
│   ├── commands.py              # Stats, verify commands
│   ├── commands_plugin.py       # Plugin commands
│   ├── config.py                # Configuration
│   ├── dashboard.py             # TUI dashboard
│   ├── diff.py                  # Directory comparison
│   ├── explode.py               # Core explode logic
│   ├── file_ops.py              # File operations
│   ├── logging.py               # Logging utilities
│   ├── plugin_loader.py         # Plugin discovery
│   ├── rebuild.py               # Core rebuild logic
│   ├── skeleton.py              # Skeleton management
│   ├── utils.py                 # Utility functions
│   ├── watcher.py               # Watch mode exports
│   ├── watcher_core.py          # Watch orchestration
│   ├── watcher_server.py        # Server communication
│   └── watcher_stages.py        # Download/upload stages
└── plugins/                     # Plugin system
    ├── 100_normalize_ids_plugin.py
    ├── 200_action_plugin.py
    ├── 210_global_function_plugin.py
    ├── 220_wrap_func_plugin.py
    ├── 230_func_plugin.py
    ├── 240_template_plugin.py
    ├── 250_info_plugin.py
    ├── 300_prettier_explode_plugin.py
    ├── 400_prettier_pre_rebuild_plugin.py
    ├── 500_prettier_post_rebuild_plugin.py
    └── plugin_helpers.py        # Shared utilities
```

## Performance Considerations

### Parallel Processing

The tool uses parallel processing where applicable:
- Multiple nodes exploded in parallel
- Multiple files formatted in parallel
- Plugin operations parallelized when independent

### Caching

Watch mode implements caching:
- ETag-based HTTP caching (304 Not Modified)
- File change debouncing (group rapid edits)
- Plugin result caching (avoid redundant work)

### Memory Efficiency

- Streaming file operations for large flows
- Incremental JSON parsing
- Plugin-specific optimizations

## Error Handling

### Graceful Degradation

- Plugin failures don't crash the tool
- Skipped plugins are logged
- Partial results preserved

### Recovery

- Backup support (`--backup` flag)
- Verification before destructive operations
- Clear error messages with suggestions

## Next Steps

- Read [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md) to create plugins
- See [CONFIGURATION.md](CONFIGURATION.md) for customization options
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
