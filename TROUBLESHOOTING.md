# Troubleshooting Guide

Common issues and their solutions when using vscode-node-red-tools.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Explode Issues](#explode-issues)
- [Rebuild Issues](#rebuild-issues)
- [Watch Mode Issues](#watch-mode-issues)
- [Plugin Issues](#plugin-issues)
- [Verification Issues](#verification-issues)
- [Performance Issues](#performance-issues)

## Installation Issues

### Python Package Installation Fails

**Problem:** `pip install -r requirements.txt` fails with permission or version errors.

**Solutions:**

1. Use a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   pip install -r requirements.txt
   ```

2. Update pip:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Install with user flag:
   ```bash
   pip install --user -r requirements.txt
   ```

### Prettier Not Found

**Problem:** `prettier: command not found` or similar error.

**Solutions:**

1. Install prettier globally:
   ```bash
   npm install -g prettier
   ```

2. Use npx (doesn't require global install):
   ```bash
   npx prettier --version
   ```
   The tool will use `npx prettier` if global `prettier` isn't found.

3. Add npm global bin to PATH:
   ```bash
   npm config get prefix  # Shows npm directory
   # Add <prefix>/bin to your PATH
   ```

### Module Import Errors

**Problem:** `ModuleNotFoundError: No module named 'rich'` or similar.

**Solution:**

Ensure you're in the correct environment and dependencies are installed:
```bash
# Activate virtual environment if using one
source venv/bin/activate

# Verify installation
pip list | grep rich
pip list | grep watchdog

# Reinstall if needed
pip install -r requirements.txt
```

## Explode Issues

### No Files Created

**Problem:** Running explode doesn't create any files in src/.

**Possible Causes:**

1. **Wrong flows.json path:**
   ```bash
   # Check file exists
   ls -l flows/flows.json

   # Use absolute path
   python3 vscode-node-red-tools.py explode /full/path/to/flows.json
   ```

2. **Empty flows.json:**
   ```bash
   # Check file isn't empty
   cat flows/flows.json
   ```

3. **Permission issues:**
   ```bash
   # Check you can write to directory
   touch src/test.txt
   rm src/test.txt
   ```

### Plugin Errors During Explode

**Problem:** Errors mentioning specific plugins during explode.

**Solutions:**

1. Skip problematic plugins:
   ```bash
   python3 vscode-node-red-tools.py explode --disable all flows/flows.json
   ```

2. Disable specific plugin in config:
   ```json
   {
     "plugins": {
       "disabled": ["prettier-explode"]
     }
   }
   ```

3. Check plugin compatibility:
   ```bash
   python3 vscode-node-red-tools.py list-plugins
   ```

### Missing Node Files

**Problem:** Some nodes aren't exploded to files.

**Causes:**

1. **Config nodes:** Config nodes at root level are stored as single .json files
2. **Unknown node types:** Only handled node types get special treatment
3. **Plugin disabled:** Check if required plugin is disabled

**Solution:**

Check what plugins are active:
```bash
python3 vscode-node-red-tools.py list-plugins
```

### ID Normalization Issues

**Problem:** IDs aren't normalized or normalization fails.

**Solutions:**

1. Disable normalization plugin in config:
   ```json
   {
     "plugins": {
       "disabled": ["normalize-ids"]
     }
   }
   ```

2. Check for duplicate names:
   - Nodes with identical names may cause conflicts
   - Manually edit node names in Node-RED before exploding

3. Check for special characters:
   - IDs are sanitized for filesystem
   - Original IDs stored in .json files

## Rebuild Issues

### Rebuild Produces Different JSON

**Problem:** Rebuilt flows.json differs from original.

**Possible Causes:**

1. **Formatting differences:** Expected if prettier is enabled
2. **Plugin modifications:** Some plugins add/remove fields
3. **Missing files:** Source files deleted or moved

**Solutions:**

1. Verify round-trip:
   ```bash
   python3 vscode-node-red-tools.py verify flows/flows.json
   ```

2. Compare directories:
   ```bash
   python3 vscode-node-red-tools.py diff src/ src_backup/
   ```

3. Check for missing files:
   ```bash
   # Ensure skeleton exists
   ls -la src/.flow-skeleton.json
   ```

### Missing Skeleton File

**Problem:** `.flow-skeleton.json` not found during rebuild.

**Cause:** Skeleton file is hidden (starts with dot) and contains wiring/layout.

**Solution:**

1. Check it exists:
   ```bash
   ls -la src/.flow-skeleton.json
   ```

2. If missing, re-explode from original flows:
   ```bash
   python3 vscode-node-red-tools.py explode flows/flows.json.backup
   ```

### Function Code Not Injected

**Problem:** Function code from .js files not appearing in rebuilt flows.

**Solutions:**

1. Check file naming:
   - Should be `<node_id>.wrapped.js` or `<node_id>.js`
   - Must match node ID in .json file

2. Check plugin is enabled:
   ```bash
   python3 vscode-node-red-tools.py list-plugins | grep func
   ```

3. Verify file content:
   ```bash
   cat src/tab_*/func_*.wrapped.js
   ```

## Watch Mode Issues

### Watch Mode Looping

**Problem:** Watch mode continuously uploading/downloading in a loop.

**Causes:**

1. **Plugin oscillation:** Plugins making incompatible changes
2. **File watcher detecting own changes:** Pause mechanism failed
3. **Prettier configuration:** Inconsistent formatting between explode/rebuild

**Solutions:**

1. Enable dashboard to see what's happening:
   ```bash
   python3 vscode-node-red-tools.py watch --dashboard \
     --server http://localhost:1880 \
     --username admin \
     --password pass
   ```

2. Skip plugins temporarily:
   ```bash
   python3 vscode-node-red-tools.py watch --disable all \
     --server http://localhost:1880 \
     --username admin \
     --password pass
   ```

3. Increase debounce:
   ```json
   {
     "watch": {
       "debounce": 2.0
     }
   }
   ```

4. Check prettier config is consistent:
   ```bash
   npx prettier --version
   cat .prettierrc
   ```

### Connection Refused

**Problem:** `Connection refused` or `Failed to connect` errors.

**Solutions:**

1. Verify server URL:
   ```bash
   curl http://localhost:1880
   ```

2. Check Node-RED is running:
   ```bash
   # Check if port is open
   netstat -an | grep 1880
   ```

3. Try explicit protocol:
   ```bash
   # Use http:// or https:// explicitly
   python3 vscode-node-red-tools.py watch \
     --server http://localhost:1880 \
     --username admin \
     --password pass
   ```

### Authentication Failed

**Problem:** `401 Unauthorized` or authentication errors.

**Solutions:**

1. Verify credentials:
   ```bash
   # Try logging into Node-RED UI with same credentials
   ```

2. Check Node-RED security settings:
   ```bash
   # Check settings.js for adminAuth configuration
   cat ~/.node-red/settings.js | grep -A 10 adminAuth
   ```

3. Use different authentication:
   - Some Node-RED setups use different auth methods
   - Check Node-RED documentation for your setup

### SSL Certificate Errors

**Problem:** SSL certificate verification errors.

**Solutions:**

1. Use `--no-verify-ssl` flag:
   ```bash
   python3 vscode-node-red-tools.py watch \
     --server https://myserver:1880 \
     --username admin \
     --password pass \
     --no-verify-ssl
   ```

2. Install proper SSL certificate on server

3. Use HTTP instead of HTTPS (if appropriate for your environment)

### Conflict Detection (409 Error)

**Problem:** `409 Conflict` errors during upload.

**Cause:** Someone else modified flows on server while you were editing.

**Solutions:**

1. Stop watch mode
2. Download latest from server manually
3. Compare and merge changes
4. Restart watch mode

**Prevention:**
- Use watch mode on single-user instances
- Coordinate with team on multi-user setups
- Use version control for collaboration

## Plugin Issues

### Plugins Not Loading

**Problem:** Plugins don't appear in list or don't run.

**Solutions:**

1. List plugins to verify:
   ```bash
   python3 vscode-node-red-tools.py list-plugins
   ```

2. Check plugin file naming:
   - Must be in `plugins/` directory
   - Must end with `_plugin.py`
   - Must implement required interface

3. Check for Python errors:
   - Syntax errors prevent plugin loading
   - Check console output for errors

4. Verify plugin is enabled in config:
   ```json
   {
     "plugins": {
       "enabled": ["my-plugin"]
     }
   }
   ```

### Plugin Errors

**Problem:** Plugin crashes during execution.

**Solutions:**

1. Skip plugins to isolate issue:
   ```bash
   python3 vscode-node-red-tools.py explode --disable all flows/flows.json
   ```

2. Test one plugin at a time:
   ```json
   {
     "plugins": {
       "enabled": ["normalize-ids"]
     }
   }
   ```

3. Check plugin implementation:
   - Review plugin code for errors
   - Add error handling to plugin
   - Check plugin return values

4. Update plugin to latest version:
   ```bash
   git pull origin main
   ```

### Custom Plugin Not Working

**Problem:** Your custom plugin doesn't run or has no effect.

**Solutions:**

1. Verify plugin is loaded:
   ```bash
   python3 vscode-node-red-tools.py list-plugins | grep my-plugin
   ```

2. Check plugin interface:
   - Implements required methods
   - Returns correct values
   - get_name() returns unique name

3. Test in isolation:
   ```json
   {
     "plugins": {
       "enabled": ["my-plugin"]
     }
   }
   ```

4. Add debug logging:
   ```python
   def explode_node(self, node, node_dir, node_id, claimed_fields):
       print(f"Processing node: {node_id}")
       # ... rest of code
   ```

## Verification Issues

### Verification Fails

**Problem:** `verify` command reports differences.

**Causes:**

1. **Expected:** Minor formatting differences
2. **Plugin issue:** Plugin not properly round-tripping
3. **Bug:** Actual data loss or corruption

**Solutions:**

1. Check what differs:
   ```bash
   python3 vscode-node-red-tools.py verify flows/flows.json
   # Look at reported differences
   ```

2. Compare manually:
   ```bash
   # Explode, rebuild, and diff
   python3 vscode-node-red-tools.py explode flows/flows.json
   python3 vscode-node-red-tools.py rebuild flows/flows.json.rebuilt
   diff flows/flows.json flows/flows.json.rebuilt
   ```

3. Skip formatting:
   ```bash
   python3 vscode-node-red-tools.py explode --disable all flows/flows.json
   python3 vscode-node-red-tools.py verify --disable all flows/flows.json
   ```

4. Report issue with sample flows.json if data is lost

## Performance Issues

### Slow Explode/Rebuild

**Problem:** Explode or rebuild takes very long.

**Solutions:**

1. Skip plugins for speed:
   ```bash
   python3 vscode-node-red-tools.py explode --disable all flows/flows.json
   ```

2. Disable prettier (usually the slowest):
   ```json
   {
     "plugins": {
       "disabled": [
         "prettier-explode",
         "prettier-pre-rebuild",
         "prettier-post-rebuild"
       ]
     }
   }
   ```

3. Check file count:
   ```bash
   # Large flows create many files
   find src/ -type f | wc -l
   ```

4. Monitor CPU/disk usage:
   ```bash
   # Linux
   htop
   iotop
   ```

### Watch Mode High CPU

**Problem:** Watch mode uses excessive CPU.

**Solutions:**

1. Increase poll interval:
   ```json
   {
     "watch": {
       "pollInterval": 10
     }
   }
   ```

2. Increase debounce:
   ```json
   {
     "watch": {
       "debounce": 2.0
     }
   }
   ```

3. Skip plugins:
   ```bash
   python3 vscode-node-red-tools.py watch --disable all \
     --server http://localhost:1880 \
     --username admin \
     --password pass
   ```

4. Check for watch mode looping (see above)

## Getting Help

If your issue isn't covered here:

1. **Check documentation:**
   - [USAGE.md](USAGE.md) - Command usage
   - [CONFIGURATION.md](CONFIGURATION.md) - Configuration options
   - [ARCHITECTURE.md](ARCHITECTURE.md) - Design details

2. **Search existing issues:**
   - Check GitHub issues for similar problems

3. **Enable verbose output:**
   - Add debug prints to plugins
   - Use `--dashboard` mode for watch mode details

4. **Create minimal reproduction:**
   - Isolate the issue
   - Create minimal flows.json that shows problem
   - Note exact commands used

5. **Report issue:**
   - Include error messages
   - Include system info (OS, Python version)
   - Include steps to reproduce
   - Include sample flows.json if possible

## Common Error Messages

### `FileNotFoundError: [Errno 2] No such file or directory: 'flows/flows.json'`

**Cause:** flows.json doesn't exist at specified path.

**Solution:** Check path and create flows/ directory if needed.

### `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`

**Cause:** flows.json is empty or not valid JSON.

**Solution:** Verify flows.json contains valid JSON content.

### `PermissionError: [Errno 13] Permission denied`

**Cause:** No write permission for src/ or flows/ directory.

**Solution:** Check directory permissions or run with appropriate user.

### `subprocess.CalledProcessError: Command '['prettier', ...]' returned non-zero exit status 2`

**Cause:** Prettier failed to format files.

**Solutions:**
1. Check prettier is installed: `npx prettier --version`
2. Check files for syntax errors
3. Disable prettier plugins temporarily

### `ConnectionError: HTTPConnectionPool(...): Max retries exceeded`

**Cause:** Can't connect to Node-RED server.

**Solutions:**
1. Verify server is running
2. Check URL is correct
3. Check firewall/network settings

## Debug Mode

Add debug output to track execution:

```python
# Add to vscode-node-red-tools.py or plugins
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or add print statements in plugins:

```python
def explode_node(self, node, node_dir, node_id, claimed_fields):
    print(f"[DEBUG] Processing {node_id}, claimed: {claimed_fields}")
    # ... rest of code
```

## Still Having Issues?

Open an issue on GitHub with:
- Exact commands run
- Error messages (full stack trace)
- System information
- Sample flows.json (if possible)
- Steps to reproduce
