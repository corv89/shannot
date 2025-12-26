# Troubleshooting Guide

Common issues when using Shannot and their solutions.

## PyPy Sandbox Issues

### "PyPy sandbox not found"

**Symptoms:**
```
Error: PyPy sandbox binary not found
```

**Solutions:**

1. Run the setup command:
   ```bash
   shannot setup runtime
   ```

2. Check if pypy-sandbox is in PATH:
   ```bash
   which pypy-sandbox
   ```

3. Specify path explicitly:
   ```bash
   shannot run --pypy-sandbox /path/to/pypy-sandbox script.py
   ```

### "Runtime not installed"

**Symptoms:**
```
Error: Runtime not installed. Run 'shannot setup runtime' first.
```

**Solution:**
```bash
# Install runtime
shannot setup runtime

# Force reinstall
shannot setup runtime --force

# Check status
shannot setup runtime --status
```

### "lib-python not found"

**Symptoms:**
```
Error: lib-python directory not found at expected location
```

**Solution:**
```bash
# Reinstall runtime
shannot setup runtime --force

# Or specify path explicitly
shannot run --lib-path /path/to/runtime script.py
```

## Python 3.6 Compatibility

### Syntax Errors

**Symptoms:**
```
SyntaxError: invalid syntax
```

**Cause:** Using Python 3.7+ syntax in sandboxed scripts.

**Common Issues:**

1. **Match statements (Python 3.10+)**
   ```python
   # NOT SUPPORTED
   match value:
       case 1: print("one")

   # Use instead
   if value == 1:
       print("one")
   ```

2. **Union type syntax (Python 3.10+)**
   ```python
   # NOT SUPPORTED
   def process(x: int | str): pass

   # Use instead
   from typing import Union
   def process(x: Union[int, str]): pass
   ```

3. **Walrus operator (Python 3.8+)**
   ```python
   # NOT SUPPORTED
   if (n := len(items)) > 10: pass

   # Use instead
   n = len(items)
   if n > 10: pass
   ```

4. **dataclasses (Python 3.7+)**
   ```python
   # NOT SUPPORTED
   from dataclasses import dataclass
   @dataclass
   class Point:
       x: int
       y: int

   # Use instead
   from collections import namedtuple
   Point = namedtuple('Point', ['x', 'y'])
   ```

### Module Not Found

**Symptoms:**
```
ModuleNotFoundError: No module named 'xxx'
```

**Cause:** Third-party modules are not available in the sandbox.

**Solution:** Only use Python 3.6 stdlib modules. The sandbox does not have pip access.

## Session Issues

### "Session not found"

**Symptoms:**
```
Error: Session 'xxx' not found
```

**Causes:**
1. Session ID is incorrect
2. Session has expired (1-hour TTL)
3. Session was already executed

**Solutions:**
```bash
# List all sessions
shannot approve list

# Check session history
shannot approve history

# Create new session
shannot run script.py
```

### "Session expired"

**Symptoms:**
```
Error: Session 'xxx' has expired
```

**Cause:** Sessions expire after 1 hour.

**Solution:** Create a new session:
```bash
shannot run script.py
```

### "Session already executed"

**Symptoms:**
```
Error: Session 'xxx' was already executed
```

**Solution:** Create a new session for re-execution:
```bash
shannot run script.py
```

## Remote Execution Issues

### SSH Connection Failed

**Symptoms:**
```
Error: SSH connection failed: Connection refused
Error: SSH connection failed: Permission denied
```

**Solutions:**

1. Test SSH manually:
   ```bash
   ssh user@host
   ```

2. Check SSH key permissions:
   ```bash
   chmod 600 ~/.ssh/id_rsa
   chmod 700 ~/.ssh
   ```

3. Verify host in known_hosts:
   ```bash
   ssh-keygen -R host
   ssh user@host  # Accept new key
   ```

4. Check SSH agent:
   ```bash
   eval $(ssh-agent)
   ssh-add ~/.ssh/key
   ```

### Remote Deployment Failed

**Symptoms:**
```
Error: Failed to deploy to remote
```

**Solutions:**

1. Check remote access:
   ```bash
   ssh user@host "ls -la /tmp/"
   ```

2. Check disk space on remote:
   ```bash
   ssh user@host "df -h /tmp"
   ```

3. Manual deployment check:
   ```bash
   ssh user@host "test -x /tmp/shannot-v0.5.1/shannot && echo OK"
   ```

### Remote Target Not Found

**Symptoms:**
```
Error: Remote 'xxx' not found in configuration
```

**Solutions:**

1. List configured remotes:
   ```bash
   shannot setup remote list
   ```

2. Add the remote:
   ```bash
   shannot setup remote add name user@host
   ```

## Profile Issues

### Profile Not Loading

**Symptoms:**
```
Using default profile (no custom profile found)
```

**Solutions:**

1. Check profile location:
   ```bash
   ls -la ~/.config/shannot/profile.json
   ls -la .shannot/profile.json
   ```

2. Verify JSON syntax:
   ```bash
   python3 -m json.tool ~/.config/shannot/profile.json
   ```

3. Check current profile:
   ```bash
   shannot status
   ```

### Command Not Auto-Approved

**Symptoms:** Commands that should be auto-approved require manual approval.

**Causes:**
1. Command not in `auto_approve` list
2. Using full path instead of base name

**Solution:** Use base command names in profiles:
```json
{
  "auto_approve": ["cat", "ls", "grep"]
}
```

Not:
```json
{
  "auto_approve": ["/usr/bin/cat", "/usr/bin/ls"]
}
```

### Command Unexpectedly Blocked

**Symptoms:** Command is blocked even though it's not in `always_deny`.

**Cause:** Prefix matching in `always_deny`.

**Example:**
```json
{
  "always_deny": ["rm"]  // Blocks ALL rm commands
}
```

**Solution:** Be specific:
```json
{
  "always_deny": ["rm -rf /", "rm -rf ~"]
}
```

## TUI Issues

### TUI Not Rendering Correctly

**Symptoms:**
- Garbled display
- Missing colors
- Cursor positioning issues

**Solutions:**

1. Check terminal type:
   ```bash
   echo $TERM
   ```

2. Try a different terminal emulator

3. Disable colors:
   ```bash
   shannot run script.py --nocolor
   ```

### Keyboard Input Not Working

**Symptoms:** Arrow keys or vim keys don't work.

**Solution:** Ensure terminal supports raw mode. Some terminals or SSH configurations may interfere.

## MCP Issues

### MCP Server Not Starting

**Symptoms:**
- Claude Desktop can't connect to shannot
- "Server not responding" errors

**Solutions:**

1. Test MCP server manually:
   ```bash
   shannot-mcp --verbose
   ```

2. Check Claude Desktop config:
   ```bash
   cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

3. Reinstall MCP configuration:
   ```bash
   shannot setup mcp install
   ```

4. Restart Claude Desktop completely

### MCP Permission Errors

**Symptoms:**
- Operations fail with permission denied
- Sandbox can't access files

**Solution:** Check that the runtime is installed and accessible:
```bash
shannot setup runtime
shannot status
```

## Getting Help

If you're still stuck:

1. Run diagnostics:
   ```bash
   shannot status
   shannot setup runtime --status
   ```

2. Enable debug mode:
   ```bash
   shannot run script.py --debug
   ```

3. Check version:
   ```bash
   shannot --version
   ```

4. Open an issue: https://github.com/corv89/shannot/issues

Include in your issue:
- Output of `shannot status`
- Output of `shannot --version`
- Error message and stack trace
- Steps to reproduce
