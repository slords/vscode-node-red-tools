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
- [Common Pitfalls](#common-pitfalls)
  - [Security Pitfalls](#security-pitfalls)
  - [Performance Tuning](#performance-tuning)
  - [Large File Handling](#large-file-handling)

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
   export NODERED_PASSWORD="pass"
   python3 vscode-node-red-tools.py watch --dashboard \
     --server http://localhost:1880 \
     --username admin
   ```

2. Skip plugins temporarily:

   ```bash
   export NODERED_PASSWORD="pass"
   python3 vscode-node-red-tools.py watch --disable all \
     --server http://localhost:1880 \
     --username admin
   ```

3. Adjust watch timing constants (if needed):
   Edit `helper/constants.py` to increase `DEFAULT_DEBOUNCE` from 2 to a higher value.

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
   export NODERED_TOKEN="your-token"
   python3 vscode-node-red-tools.py watch \
     --server http://localhost:1880
   ```

### Authentication Failed

**Problem:** `401 Unauthorized` or authentication errors.

**Solutions:**

1. Verify credentials are correctly configured:

   ```bash
   # Check which authentication method you're using

   # For token authentication:
   cat ~/.nodered-token  # Should contain valid token

   # For basic auth:
   echo $NODERED_PASSWORD  # Should be set
   ```

2. Test authentication method:

   ```bash
   # Token authentication (recommended)
   export NODERED_TOKEN="your-token"
   python3 vscode-node-red-tools.py watch --server http://localhost:1880

   # Basic authentication
   export NODERED_PASSWORD="your-password"
   python3 vscode-node-red-tools.py watch --server http://localhost:1880 --username admin
   ```

3. Check Node-RED security settings:

   ```bash
   # Check settings.js for adminAuth configuration
   cat ~/.node-red/settings.js | grep -A 10 adminAuth
   ```

4. Verify token hasn't expired (if using token authentication)

5. Try logging into Node-RED UI with same credentials to verify they work

### SSL Certificate Errors

**Problem:** SSL certificate verification errors.

**Solutions:**

1. Use `--no-verify-ssl` flag:

   ```bash
   export NODERED_TOKEN="your-token"
   python3 vscode-node-red-tools.py watch \
     --server https://myserver:1880 \
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

1. Adjust watch timing constants (if needed):
   Edit `helper/constants.py` to increase `DEFAULT_POLL_INTERVAL` or `DEFAULT_DEBOUNCE`.

2. Skip plugins to improve performance:

   ```bash
   export NODERED_TOKEN="your-token"
   python3 vscode-node-red-tools.py watch --disable all \
     --server http://localhost:1880
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

## Common Pitfalls

This section covers common mistakes and best practices to avoid issues.

### Security Pitfalls

#### Password Exposure in Command History

**Problem:** Passwords passed on command line are visible in shell history.

**Bad Practice:**

```bash
# DON'T DO THIS - password visible in history
python3 vscode-node-red-tools.py watch \
  --server http://localhost:1880 \
  --username admin \
  --password mysecretpassword
```

**Best Practices:**

1. **Use environment variables (recommended):**

   ```bash
   # Set password in environment
   export NODERED_PASSWORD="mysecretpassword"

   # Run without --password flag
   python3 vscode-node-red-tools.py watch \
     --server http://localhost:1880 \
     --username admin
   ```

2. **Use token authentication (most secure):**

   ```bash
   # Store token in file
   echo "your-access-token" > ~/.nodered-token
   chmod 600 ~/.nodered-token

   # Or use environment variable
   export NODERED_TOKEN="your-access-token"

   # Run with token auth (no username/password needed)
   python3 vscode-node-red-tools.py watch \
     --server http://localhost:1880
   ```

3. **Use token file in config:**

   ```json
   {
     "server": {
       "url": "http://localhost:1880",
       "tokenFile": "~/.nodered-token"
     }
   }
   ```

4. **Never commit credentials to git:**
   ```bash
   # Add to .gitignore
   echo ".vscode-node-red-tools.json" >> .gitignore
   echo ".nodered-token" >> .gitignore
   ```

#### Config Files with Embedded Credentials

**Problem:** Config files contain plaintext passwords in version control.

**Bad Practice:**

```json
{
  "server": {
    "url": "http://localhost:1880",
    "username": "admin",
    "password": "mysecretpassword"
  }
}
```

**Best Practice:**

```json
{
  "server": {
    "url": "http://localhost:1880",
    "tokenFile": "~/.nodered-token"
  }
}
```

Then set token outside of version control:

```bash
echo "your-token" > ~/.nodered-token
chmod 600 ~/.nodered-token
```

#### SSL Verification Disabled Without Understanding Risks

**Problem:** Using `--no-verify-ssl` without understanding security implications.

**When It's Acceptable:**

- Development environments with self-signed certificates
- Localhost connections
- Trusted internal networks

**When It's Dangerous:**

- Production environments
- Public networks
- Untrusted servers

**Best Practice:**

1. Use proper SSL certificates in production
2. Only disable verification for development:

   ```bash
   # Add to development-specific config
   {
     "server": {
       "verifySSL": false  // Only for dev!
     }
   }
   ```

3. Document why verification is disabled

### Performance Tuning

#### Understanding Plugin Performance Impact

**Issue:** Plugins can significantly impact performance, especially prettier.

**Performance Impact by Plugin Type:**

1. **Prettier plugins (slowest):**
   - `prettier-explode` - Formats all extracted files
   - `prettier-post-rebuild` - Formats rebuilt flows.json
   - Impact: 2-10x slower depending on flow size

2. **Pre-explode plugins (medium):**
   - `normalize-ids` - Scans and modifies all nodes
   - Impact: 1.5-3x slower

3. **Explode plugins (fast):**
   - `function-code` - Only processes function nodes
   - Impact: <10% overhead

**Optimization Strategies:**

1. **Disable prettier for large flows:**

   ```json
   {
     "plugins": {
       "disabled": ["prettier-explode", "prettier-post-rebuild"]
     }
   }
   ```

2. **Use prettier selectively:**

   ```bash
   # Explode without formatting
   python3 vscode-node-red-tools.py explode --disable prettier-explode flows/flows.json

   # Format manually when needed
   npx prettier --write "src/**/*.{js,json,md}"
   ```

3. **Profile plugin impact:**

   ```bash
   # Time with all plugins
   time python3 vscode-node-red-tools.py explode flows/flows.json

   # Time without plugins
   time python3 vscode-node-red-tools.py explode --disable all flows/flows.json
   ```

#### Watch Mode Performance

**Issue:** Watch mode can be CPU-intensive with large flows.

**Optimization Tips:**

1. **Disable expensive plugins in watch mode:**

   ```bash
   export NODERED_TOKEN="your-token"
   python3 vscode-node-red-tools.py watch \
     --server http://localhost:1880 \
     --disable prettier-explode,prettier-post-rebuild
   ```

2. **Use logging levels to reduce output:**

   ```bash
   # Reduce noise in watch mode
   python3 vscode-node-red-tools.py watch \
     --log-level WARNING \
     --server http://localhost:1880
   ```

3. **Monitor for oscillation:**
   - Dashboard shows convergence cycles
   - Tool automatically pauses after detecting oscillation
   - Resume with manual upload (Ctrl+U in dashboard)

4. **Adjust timing if needed:**
   - Default poll interval: 5 seconds
   - Default debounce: 2 seconds
   - Can be adjusted in `helper/constants.py` if needed

#### Network Optimization

**Issue:** Excessive polling can impact Node-RED server.

**Best Practices:**

1. **Use reasonable poll intervals:**
   - Default 5s is appropriate for most cases
   - Don't poll more frequently unless needed

2. **Rate limiting is built-in:**
   - 30-second minimum between deploys
   - Prevents overwhelming server

3. **Use dashboard to monitor activity:**
   ```bash
   python3 vscode-node-red-tools.py watch --dashboard
   ```

### Large File Handling

#### Large flows.json Files

**Issue:** Very large flows (>1MB) can cause performance issues.

**Symptoms:**

- Slow explode/rebuild times
- High memory usage
- Watch mode oscillation

**Solutions:**

1. **Split flows into multiple tabs:**
   - Keep individual tabs under 200 nodes
   - Use Link nodes to connect between tabs

2. **Disable prettier for large flows:**

   ```json
   {
     "plugins": {
       "disabled": ["prettier-explode", "prettier-post-rebuild"]
     }
   }
   ```

3. **Process in stages:**

   ```bash
   # Explode without plugins first
   python3 vscode-node-red-tools.py explode --disable all flows/flows.json

   # Format manually if needed
   npx prettier --write "src/**/*.js"
   ```

#### Many Small Files (>1000 nodes)

**Issue:** Thousands of files can slow down file system operations.

**Solutions:**

1. **Use .gitignore patterns:**

   ```gitignore
   src/*/node_*.json
   src/*/.flow-skeleton.json
   ```

2. **Consider breaking up flows:**
   - Use subflows for repeated patterns
   - Move config nodes to shared tabs

3. **Optimize IDE settings:**
   - Exclude src/ from file watchers in IDE
   - Disable auto-save on src/ directory

#### Function Nodes with Large Code

**Issue:** Function nodes with 1000+ lines of code.

**Best Practice:**

1. **Keep function code concise:**
   - Move complex logic to external modules
   - Use require() in function nodes

2. **Watch for wrapped vs unwrapped:**
   - `.wrapped.js` - Code wrapped in function
   - `.js` - Raw code (advanced use)

3. **Consider refactoring:**
   - Split large functions into multiple nodes
   - Use subflows for reusable logic

#### Memory Considerations

**Issue:** Long-running watch mode may accumulate memory over time.

**Monitoring:**

```bash
# Check memory usage (Linux/Mac)
ps aux | grep vscode-node-red-tools

# Watch over time
watch -n 30 'ps aux | grep vscode-node-red-tools'
```

**Best Practices:**

1. **Restart watch mode periodically:**
   - Daily restarts for long-running instances
   - Monitor for memory growth

2. **Use exit codes to detect issues:**
   - All errors now have specific codes
   - Monitor for error patterns

3. **Report suspected memory leaks:**
   - Note how long watch mode was running
   - Document memory growth rate
   - Include flow size and plugin configuration

## Error Codes Reference

All errors and warnings now include error codes for easier troubleshooting:

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

**Examples:**

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

## Logging Levels

Control output verbosity with logging levels:

**Available Levels:**
- `DEBUG` - Show all messages including debug info
- `INFO` - Normal operation messages (default)
- `WARNING` - Only warnings and errors
- `ERROR` - Only errors

**Usage:**

```bash
# Quiet mode (warnings and errors only)
python3 vscode-node-red-tools.py explode --quiet flows/flows.json

# Verbose mode (includes debug messages)
python3 vscode-node-red-tools.py explode --verbose flows/flows.json

# Explicit level
python3 vscode-node-red-tools.py explode --log-level DEBUG flows/flows.json

# Environment variable (applies to all commands)
export NODERED_TOOLS_LOG_LEVEL=WARNING
python3 vscode-node-red-tools.py explode flows/flows.json
```

**When to Use:**

- `--quiet` - CI/CD pipelines, cron jobs
- `--verbose` - Debugging issues, development
- `--log-level ERROR` - Monitoring scripts (only show failures)

## Still Having Issues?

Open an issue on GitHub with:

- Exact commands run
- Error messages with error codes (e.g., [E30])
- System information
- Sample flows.json (if possible)
- Steps to reproduce
- Log level output (try with --verbose)
