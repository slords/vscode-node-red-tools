# Configuration Guide

This guide explains how to configure vscode-node-red-tools for your needs.

## Table of Contents

- [Configuration File](#configuration-file)
- [Configuration Options](#configuration-options)
- [Plugin Configuration](#plugin-configuration)
- [Watch Mode Configuration](#watch-mode-configuration)
- [Examples](#examples)

## Configuration File

### Location

The configuration file is named `.vscode-node-red-tools.json` and should be placed in the same directory as the main script.

### Creating Configuration

```bash
# Copy example configuration
cp .vscode-node-red-tools.example.json .vscode-node-red-tools.json

# Edit configuration
vim .vscode-node-red-tools.json
```

### Default Behavior

If no configuration file exists, the tool uses these defaults:

- `flows`: `flows/flows.json`
- `src`: `src`
- All plugins enabled
- Default watch intervals (poll: 1s, debounce: 2s)

## Configuration Options

### Complete Configuration

```json
{
  "flows": "flows/flows.json",
  "src": "src",
  "plugins": {
    "enabled": [],
    "disabled": [],
    "order": []
  },
  "watch": {
    "pollInterval": 5,
    "debounce": 0.5,
    "convergenceLimit": 5,
    "convergenceWindow": 60
  }
}
```

### flows

Path to flows.json file (relative to repo root).

**Type:** String
**Default:** `"flows/flows.json"`

**Example:**

```json
{
  "flows": "node-red/flows.json"
}
```

### src

Directory for exploded source files.

**Type:** String
**Default:** `"src"`

**Example:**

```json
{
  "src": "source"
}
```

### backup

Backup configuration (optional).

**Type:** Object
**Default:** Not configured

**Example:**

```json
{
  "backup": {
    "enabled": true,
    "directory": "backups",
    "maxBackups": 10
  }
}
```

## Plugin Configuration

The `plugins` section controls which plugins are loaded and their execution order.

### plugins.enabled

List of plugin names to enable. Empty array means all plugins are enabled.

**Type:** Array of strings
**Default:** `[]` (all enabled)

**Example:**

```json
{
  "plugins": {
    "enabled": ["normalize-ids", "action", "func", "prettier-explode"]
  }
}
```

When `enabled` is non-empty, **only** listed plugins are loaded. Others are disabled.

### plugins.disabled

List of plugin names to disable. Empty array means no plugins are disabled.

**Type:** Array of strings
**Default:** `[]` (none disabled)

**Example:**

```json
{
  "plugins": {
    "disabled": ["wrap_func", "prettier-explode"]
  }
}
```

This disables function wrapping and prettier formatting during explode.

**Note:** If both `enabled` and `disabled` are specified, `enabled` takes precedence.

### plugins.order

Custom plugin execution order. Empty array uses default priority order.

**Type:** Array of strings
**Default:** `[]` (use priority/filename)

**Example:**

```json
{
  "plugins": {
    "order": [
      "normalize-ids",
      "action",
      "global-function",
      "func",
      "template",
      "prettier-explode"
    ]
  }
}
```

This overrides the default priority-based ordering.

### Available Plugins

| Plugin Name             | Type         | Priority | Description                                |
| ----------------------- | ------------ | -------- | ------------------------------------------ |
| `normalize-ids`         | pre-explode  | 100      | Convert random IDs to functional names     |
| `action`                | explode      | 200      | Handle action nodes (.def.js, .execute.js) |
| `global-function`       | explode      | 210      | Handle global functions (.function.js)     |
| `wrap_func`             | explode      | 220      | Wrap functions for testing (.wrapped.js)   |
| `func`                  | explode      | 230      | Handle legacy functions (.js)              |
| `template`              | explode      | 240      | Handle template nodes (.vue, .html, etc.)  |
| `info`                  | explode      | 250      | Extract documentation (.md)                |
| `prettier-explode`      | post-explode | 300      | Format files after explode                 |
| `prettier-pre-rebuild`  | pre-rebuild  | 400      | Format files before rebuild                |
| `prettier-post-rebuild` | post-rebuild | 500      | Format flows.json after rebuild            |

## Watch Mode Configuration

The `watch` section controls watch mode behavior.

### watch.pollInterval

How often to poll the Node-RED server for changes (in seconds).

**Type:** Number
**Default:** `1`
**Range:** 1-60 recommended

**Example:**

```json
{
  "watch": {
    "pollInterval": 10
  }
}
```

**Considerations:**

- Lower values = faster detection, more server load
- Higher values = slower detection, less server load
- 1-5 seconds is a good balance

### watch.debounce

Wait time after file change before uploading (in seconds).

**Type:** Number
**Default:** `2.0`
**Range:** 0.1-5.0 recommended

**Example:**

```json
{
  "watch": {
    "debounce": 2.0
  }
}
```

**Considerations:**

- Lower values = faster uploads, may upload incomplete changes
- Higher values = slower uploads, groups multiple changes
- 1-3 seconds works well for most cases

### watch.convergenceLimit

Maximum number of upload/download cycles before oscillation warning (in cycles).

**Type:** Integer
**Default:** `5`
**Range:** 3-10 recommended

**Example:**

```json
{
  "watch": {
    "convergenceLimit": 5
  }
}
```

**Purpose:**
Prevents infinite loops when plugins cause changes that trigger endless cycles. When exceeded, convergence pauses until manual upload resumes it.

**Considerations:**

- Most flows converge in 1-2 cycles
- Higher values allow more complex convergence scenarios
- Lower values catch oscillation problems faster
- 5 cycles is a good balance for most cases

### watch.convergenceWindow

Time window for counting convergence cycles (in seconds).

**Type:** Number
**Default:** `60`
**Range:** 30-120 recommended

**Example:**

```json
{
  "watch": {
    "convergenceWindow": 60
  }
}
```

**Purpose:**
Only counts cycles within this time window. Older cycles are discarded from the count.

**Considerations:**

- Prevents false positives from normal editing over time
- 60 seconds gives good detection without false alarms
- Shorter windows catch oscillation faster
- Longer windows are more forgiving of complex flows

**How Convergence Protection Works:**

1. Each upload/download is counted as a cycle
2. If more than `convergenceLimit` cycles occur within `convergenceWindow` seconds
3. Warning displayed and convergence pauses
4. No more automatic uploads until you manually upload (which clears the pause)
5. Prevents plugin oscillation from consuming resources

## Examples

### Minimal Configuration

For basic use with defaults:

```json
{
  "flows": "flows/flows.json",
  "src": "src"
}
```

### Disable Function Wrapping

If you don't want functions wrapped for testing:

```json
{
  "plugins": {
    "disabled": ["wrap_func"]
  }
}
```

This uses the legacy func plugin that extracts to `.js` files without wrapping.

### Fast Watch Mode

For faster change detection:

```json
{
  "watch": {
    "pollInterval": 2,
    "debounce": 0.2,
    "convergenceLimit": 5,
    "convergenceWindow": 60
  }
}
```

**Warning:** Very low intervals may cause excessive server load.

### Conservative Watch Mode

For slower but more stable sync:

```json
{
  "watch": {
    "pollInterval": 15,
    "debounce": 3.0,
    "convergenceLimit": 5,
    "convergenceWindow": 60
  }
}
```

### Custom Plugin Order

If you need specific plugin execution order:

```json
{
  "plugins": {
    "order": [
      "normalize-ids",
      "action",
      "global-function",
      "wrap_func",
      "template",
      "info",
      "prettier-explode",
      "prettier-pre-rebuild",
      "prettier-post-rebuild"
    ]
  }
}
```

### Enable Only Specific Plugins

For minimal processing:

```json
{
  "plugins": {
    "enabled": ["normalize-ids", "func", "info"]
  }
}
```

This enables only ID normalization, basic function extraction, and documentation.

### Team Configuration

For team consistency:

```json
{
  "flows": "flows/flows.json",
  "src": "src",
  "plugins": {
    "enabled": [
      "normalize-ids",
      "action",
      "global-function",
      "wrap_func",
      "template",
      "info",
      "prettier-explode",
      "prettier-post-rebuild"
    ]
  },
  "watch": {
    "pollInterval": 5,
    "debounce": 1.0,
    "convergenceLimit": 5,
    "convergenceWindow": 60
  }
}
```

Commit this configuration to your repository so all team members use the same settings.

## Configuration Validation

Validate your configuration:

```bash
python3 vscode-node-red-tools.py validate-config
```

This checks:

- JSON syntax
- Valid configuration keys
- Correct value types
- Path existence
- Plugin names

## Command-Line Overrides

Command-line options override configuration file settings:

```bash
# Override flows path
python3 vscode-node-red-tools.py explode custom/flows.json

# Override src directory
python3 vscode-node-red-tools.py explode flows/flows.json custom_src/

# Override watch intervals
python3 vscode-node-red-tools.py watch \
  --server http://localhost:1880 \
  --username admin \
  --password pass \
  --poll-interval 10 \
  --debounce 2.0
```

## Environment Variables

Currently, the tool does not use environment variables. All configuration is via:

1. Configuration file (`.vscode-node-red-tools.json`)
2. Command-line arguments

## Best Practices

### Version Control

**Do commit:**

- `.vscode-node-red-tools.json` (shared team settings)

**Don't commit:**

- Sensitive credentials (use command-line arguments)
- Local overrides specific to your setup

### Plugin Selection

**Enable all plugins if:**

- You want full functionality
- You're okay with slower processing
- You want testable functions

**Disable prettier if:**

- You have custom formatting
- Processing is too slow
- You want minimal changes

**Disable wrap_func if:**

- You don't need testable functions
- You prefer simpler .js files
- You're migrating from an older tool

### Watch Mode Tuning

**Increase pollInterval if:**

- Server is under heavy load
- You don't need instant sync
- You're on a slow network

**Decrease debounce if:**

- You want faster uploads
- You rarely make batch edits
- You have a fast system

**Increase debounce if:**

- You make frequent batch edits
- You want to group changes
- You have a slower system

## Troubleshooting Configuration

### Configuration Not Loading

Check:

1. File is named `.vscode-node-red-tools.json` (with leading dot)
2. File is in the same directory as `vscode-node-red-tools.py`
3. JSON syntax is valid (use `python3 -m json.tool` to validate)

### Plugins Not Working

Check:

1. Plugin names match exactly (use `list-plugins` command)
2. No typos in `enabled` or `disabled` arrays
3. Plugins aren't conflicting (e.g., both enabled and disabled)

### Watch Mode Issues

Check:

1. `pollInterval` is positive number
2. `debounce` is non-negative number
3. `convergenceLimit` is positive integer
4. `convergenceWindow` is positive number
5. Values are reasonable (not too low or too high)

## Next Steps

- Review [USAGE.md](USAGE.md) for command examples
- Read [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md) to create custom plugins
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
