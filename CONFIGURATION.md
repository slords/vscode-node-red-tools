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
- Server URL: `http://127.0.0.1:1880` (no authentication)

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
  "server": {
    "url": "http://127.0.0.1:1880",
    "username": null,
    "password": null,
    "token": null,
    "tokenFile": null,
    "verifySSL": true
  },
  "backup": {
    "enabled": true,
    "directory": "backups",
    "maxBackups": 10
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

## Server Configuration

The `server` section configures connection to the Node-RED server for watch mode.

### server.url

Node-RED server URL.

**Type:** String
**Default:** `"http://127.0.0.1:1880"`

**Example:**

```json
{
  "server": {
    "url": "https://myserver.example.com:1880"
  }
}
```

### server.username

Username for HTTP Basic authentication (optional).

**Type:** String or null
**Default:** `null`

**Example:**

```json
{
  "server": {
    "username": "admin"
  }
}
```

**Note:** Password must be provided via environment variable (`NODERED_PASSWORD`) or CLI parameter for security. See [Authentication](#authentication) section below.

### server.password

Password for HTTP Basic authentication (optional, **NOT RECOMMENDED**).

**Type:** String or null
**Default:** `null`

**Security Warning:** Storing passwords in config files is insecure. Use the `NODERED_PASSWORD` environment variable instead.

### server.token

Bearer token for authentication (optional, **NOT RECOMMENDED**).

**Type:** String or null
**Default:** `null`

**Security Warning:** Storing tokens in config files is insecure. Use the `NODERED_TOKEN` environment variable or token file instead.

### server.tokenFile

Path to file containing bearer token (recommended for token authentication).

**Type:** String or null
**Default:** `null`

**Example:**

```json
{
  "server": {
    "tokenFile": "~/.nodered-token"
  }
}
```

The token file should contain only the token string with no extra whitespace.

### server.verifySSL

Enable/disable SSL certificate verification for HTTPS connections.

**Type:** Boolean
**Default:** `true`

**Example:**

```json
{
  "server": {
    "url": "https://localhost:1880",
    "verifySSL": false
  }
}
```

**Warning:** Only disable SSL verification for development/testing with self-signed certificates.

## Authentication

The tool supports multiple authentication methods with automatic credential resolution:

### Authentication Methods

1. **Bearer Token** (Recommended) - Most secure, supports token rotation
2. **HTTP Basic** (Username/Password) - Traditional authentication
3. **Anonymous** - No authentication (local development only)

### Credential Resolution Priority

Credentials are resolved from multiple sources in priority order:

**For Token Authentication:**

1. `--token-file` CLI parameter
2. `--token` CLI parameter (with security warning)
3. `config.server.tokenFile`
4. `config.server.token` (with security warning)
5. Token file search (`./.nodered-token`, `~/.nodered-token`)
6. `NODERED_TOKEN` environment variable

**For Basic Authentication:**

1. `--username` and `--password` CLI parameters
2. `config.server.username` and `config.server.password`
3. `NODERED_PASSWORD` environment variable (if username configured)
4. Secure password prompt (if username configured)

### Using Environment Variables (Recommended)

The most secure way to provide credentials:

```bash
# Bearer token (recommended)
export NODERED_TOKEN="your-token-here"
python3 vscode-node-red-tools.py watch

# Basic authentication
export NODERED_PASSWORD="your-password-here"
python3 vscode-node-red-tools.py watch --username admin
```

### Using Token Files (Recommended)

Store your token in a file for automatic loading:

```bash
# Create token file
echo "your-token-here" > ~/.nodered-token
chmod 600 ~/.nodered-token

# Tool will automatically find and use it
python3 vscode-node-red-tools.py watch
```

The tool searches for `.nodered-token` in:

1. Current directory (`./.nodered-token`)
2. Home directory (`~/.nodered-token`)

### Configuration Examples

**Token authentication with file:**

```json
{
  "server": {
    "url": "https://nodered.example.com:1880",
    "tokenFile": "~/.nodered-token",
    "verifySSL": true
  }
}
```

**Basic authentication (password via environment):**

```json
{
  "server": {
    "url": "http://localhost:1880",
    "username": "admin"
  }
}
```

Then set `NODERED_PASSWORD` environment variable.

**Local development (no authentication):**

```json
{
  "server": {
    "url": "http://127.0.0.1:1880"
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

## Watch Mode Constants

Watch mode timing parameters are runtime constants defined in `helper/constants.py`. These are NOT configurable via the config file or CLI to prevent misconfiguration.

**If you need to adjust these values**, edit `helper/constants.py`:

```python
DEFAULT_POLL_INTERVAL = 1      # Poll interval for watch mode (seconds)
DEFAULT_DEBOUNCE = 2           # Wait after last change for local files (seconds)
DEFAULT_CONVERGENCE_LIMIT = 5  # Max upload/download cycles before warning
DEFAULT_CONVERGENCE_WINDOW = 60 # Time window for convergence detection (seconds)
```

**Note:** Very low poll intervals or debounce values can cause excessive server load or upload/download oscillation. The defaults are tuned for typical use cases.

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

### Secure Production Configuration

For production with token authentication:

```json
{
  "flows": "flows/flows.json",
  "src": "src",
  "server": {
    "url": "https://nodered.production.example.com:1880",
    "tokenFile": "~/.nodered-token",
    "verifySSL": true
  },
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
  }
}
```

Store your token in `~/.nodered-token` with restricted permissions:

```bash
echo "your-token-here" > ~/.nodered-token
chmod 600 ~/.nodered-token
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
  "server": {
    "url": "http://localhost:1880"
  },
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
  }
}
```

Commit this configuration to your repository so all team members use the same settings.

**Note:** Each team member should configure their own credentials via environment variables or token files (not in the committed config).

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

# Override server and authentication
python3 vscode-node-red-tools.py watch \
  --server https://myserver:1880 \
  --token-file ~/.nodered-token \
  --no-verify-ssl
```

## Environment Variables

The tool supports environment variables for secure credential management:

### NODERED_TOKEN

Bearer token for authentication (recommended for token-based auth).

```bash
export NODERED_TOKEN="your-token-here"
python3 vscode-node-red-tools.py watch
```

### NODERED_PASSWORD

Password for HTTP Basic authentication (when username is configured).

```bash
export NODERED_PASSWORD="your-password-here"
python3 vscode-node-red-tools.py watch --username admin
```

**Security Best Practice:** Always use environment variables or token files instead of storing credentials in config files or CLI parameters.

## Best Practices

### Version Control

**Do commit:**

- `.vscode-node-red-tools.json` (shared team settings)

**Don't commit:**

- Sensitive credentials (use environment variables or token files)
- Token files (`.nodered-token`)
- Passwords or tokens in config files
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

### Authentication Best Practices

**Always use:**

- Token files (`~/.nodered-token`) or environment variables for credentials
- Token authentication over username/password when possible
- SSL/TLS (`https://`) for production servers
- `verifySSL: true` for production (only disable for dev/testing)

**Never:**

- Commit credentials to version control
- Store passwords or tokens in config files
- Use `--password` or `--token` CLI parameters (visible in process list)

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

### Authentication Issues

Check:

1. Credentials are set via environment variables or token files (not config)
2. Token file has correct permissions (`chmod 600 ~/.nodered-token`)
3. Server URL is correct and accessible
4. SSL verification is appropriate for your setup (`verifySSL` setting)
5. For basic auth, password is provided via `NODERED_PASSWORD` or prompt

## Logging Configuration

Control output verbosity using logging levels. Logging configuration is not stored in the config file; it's controlled via CLI flags or environment variables.

### Environment Variable

Set the logging level globally for all commands:

```bash
export NODERED_TOOLS_LOG_LEVEL=WARNING
```

**Valid Values:**

- `DEBUG` - Show all messages including debug info
- `INFO` - Normal operation (default)
- `WARNING` - Only warnings and errors
- `ERROR` - Only errors

### CLI Flags

Override logging level for specific command:

```bash
# Quiet mode (warnings and errors only)
python3 vscode-node-red-tools.py --quiet explode

# Verbose mode (debug messages)
python3 vscode-node-red-tools.py --verbose rebuild

# Explicit level
python3 vscode-node-red-tools.py --log-level DEBUG watch
```

### Precedence

CLI flags take precedence over environment variable:

1. `--log-level` flag (highest priority)
2. `--quiet` or `--verbose` flags
3. `NODERED_TOOLS_LOG_LEVEL` environment variable
4. Default (`INFO`)

### Use Cases

**Development:**

```bash
# See everything that's happening
python3 vscode-node-red-tools.py --verbose watch
```

**Production/CI:**

```bash
# Only show important issues
python3 vscode-node-red-tools.py --quiet explode flows/flows.json
```

**Debugging:**

```bash
# Maximum detail
export NODERED_TOOLS_LOG_LEVEL=DEBUG
python3 vscode-node-red-tools.py explode flows/flows.json
```

## Error Codes

All errors and warnings include error codes for easier troubleshooting:

**Format:**

- Errors: `[E##]`
- Warnings: `[W##]`

**Code Ranges:**

- 0: Success
- 1-9: General errors
- 10-19: Configuration errors
- 20-29: File system errors
- 30-39: Server/network errors
- 40-49: Validation errors
- 50-59: Plugin errors
- 60-69: Operation errors

**Example Output:**

```
✗ [E20] File not found: flows/flows.json
⚠ [W10] Config file not found, using defaults
✓ Deployed to Node-RED
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for complete error code reference.

## Next Steps

- Review [USAGE.md](USAGE.md) for command examples
- Read [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md) to create custom plugins
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
