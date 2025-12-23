# Migrating from v0.3.x

This guide covers upgrading from Shannot v0.3.x (bubblewrap-based) to v0.4.0+ (PyPy sandbox).

## Overview

v0.4.0 replaced the bubblewrap sandbox with PyPy-based syscall interception. This is a complete architecture change with significant benefits:

| Feature | v0.3.x (bubblewrap) | v0.4.0+ (PyPy sandbox) |
|---------|---------------------|------------------------|
| Dependencies | bubblewrap, asyncssh | Zero (pure stdlib) |
| Linux requirement | Required | Not required |
| Remote installation | Manual setup | Auto-deploys |
| Profile format | Bind mounts, tmpfs | Command approval lists |
| Python version | Host Python | Python 3.6 (PyPy) |

## Key Changes

### No Bubblewrap Dependency

v0.3.x required bubblewrap (bwrap) installed on the system:

```bash
# v0.3.x - Required bubblewrap
apt install bubblewrap
shannot verify  # Check bwrap
```

v0.4.0+ has **zero external dependencies**:

```bash
# v0.4.0+ - Just install and setup
pip install shannot
shannot setup   # Downloads PyPy stdlib
```

### Remote Execution Auto-Deploys

v0.3.x required manual installation on remote targets with asyncssh:

```bash
# v0.3.x - Manual remote setup
pip install shannot[remote]  # asyncssh dependency
ssh user@host "pip install shannot && apt install bubblewrap"
```

v0.4.0+ auto-deploys on first use:

```bash
# v0.4.0+ - Just add the remote
shannot remote add prod user@host
shannot run script.py --target prod  # Auto-deploys
```

### Profile Format Changed Completely

v0.3.x profiles controlled bind mounts and namespace isolation:

```json
{
  "name": "diagnostics",
  "allowed_commands": ["ls", "cat", "df"],
  "binds": [
    {"source": "/usr", "target": "/usr", "read_only": true},
    {"source": "/etc", "target": "/etc", "read_only": true}
  ],
  "tmpfs_paths": ["/tmp"],
  "environment": {"PATH": "/usr/bin"},
  "network_isolation": true,
  "seccomp_profile": "/etc/shannot/seccomp.bpf"
}
```

v0.4.0+ profiles control command approval:

```json
{
  "auto_approve": ["ls", "cat", "df", "free", "uptime"],
  "always_deny": ["rm -rf /", "dd if=/dev/zero"]
}
```

### Python API Removed

v0.3.x provided a Python API:

```python
# v0.3.x - No longer works
from shannot import SandboxManager, load_profile_from_path
manager = SandboxManager(profile, Path("/usr/bin/bwrap"))
result = manager.run(["ls", "/"])
```

v0.4.0+ is CLI/MCP only. The internal API exports are for contributors:

```python
# v0.4.0+ - Internal use only
from shannot import VirtualizedProc  # Low-level, not for users
```

Use the CLI instead:

```bash
shannot run script.py
shannot approve
```

### Commands Changed

| v0.3.x | v0.4.0+ | Notes |
|--------|---------|-------|
| `shannot verify` | `shannot status` | Different checks |
| `shannot run CMD` | `shannot run SCRIPT.py` | Runs Python scripts, not commands |
| - | `shannot setup` | Downloads PyPy runtime |
| - | `shannot approve` | Interactive session approval |
| - | `shannot execute` | Execute approved sessions |

### Python 3.6 Compatibility Required

v0.3.x ran commands in bubblewrap with host Python.

v0.4.0+ runs Python scripts in PyPy sandbox, which requires **Python 3.6 syntax**:

```python
# NOT SUPPORTED in v0.4.0+:

# Match statements (3.10+)
match value:
    case 1: print("one")

# Union types (3.10+)
def process(x: int | str): pass

# Walrus operator (3.8+)
if (n := len(items)) > 10: pass

# dataclasses (3.7+)
from dataclasses import dataclass
```

See [Troubleshooting](troubleshooting.md#python-36-compatibility) for workarounds.

## Migration Steps

### 1. Uninstall Old Dependencies

```bash
# Remove bubblewrap (if only used for shannot)
apt remove bubblewrap

# Remove asyncssh extra
pip uninstall asyncssh
```

### 2. Reinstall Shannot

```bash
# Fresh install (no extras needed)
pip install shannot --upgrade

# Or with uv/pipx
uv tool install shannot
```

### 3. Setup PyPy Runtime

```bash
shannot setup
```

### 4. Migrate Profiles

Create new profiles in the v0.4.0+ format.

**Old profile** (`~/.config/shannot/profile.json`):
```json
{
  "name": "diagnostics",
  "allowed_commands": ["ls", "cat", "df", "free"],
  "binds": [...],
  "network_isolation": true
}
```

**New profile** (`~/.config/shannot/profile.json`):
```json
{
  "auto_approve": ["ls", "cat", "df", "free", "uptime", "ps"],
  "always_deny": ["rm -rf /", "dd if=/dev/zero"]
}
```

### 5. Migrate Remote Targets

v0.3.x used executor configuration in `config.toml`.

v0.4.0+ uses `remotes.toml`:

```bash
# Add remotes via CLI
shannot remote add prod user@prod.example.com
shannot remote add staging admin@staging.example.com

# Or create ~/.config/shannot/remotes.toml:
```

```toml
[remotes.prod]
host = "prod.example.com"
user = "user"
port = 22

[remotes.staging]
host = "staging.example.com"
user = "admin"
port = 22
```

### 6. Update Scripts

Convert shell command invocations to Python scripts:

**v0.3.x approach:**
```bash
shannot run ls -la /etc
shannot run df -h
```

**v0.4.0+ approach:**
```python
# diagnostics.py
import subprocess

print("=== Directory listing ===")
subprocess.call(["ls", "-la", "/etc"])

print("\n=== Disk usage ===")
subprocess.call(["df", "-h"])
```

```bash
shannot run diagnostics.py
```

### 7. Verify Installation

```bash
# Check status
shannot status

# Test a simple script
echo 'print("Hello from sandbox")' > /tmp/test.py
shannot run /tmp/test.py
```

## Configuration File Locations

| Purpose | v0.3.x | v0.4.0+ |
|---------|--------|---------|
| Profile | `~/.config/shannot/profile.json` | Same |
| Project profile | `.shannot/profile.json` | Same |
| Remote targets | `~/.config/shannot/config.toml` | `~/.config/shannot/remotes.toml` |
| Runtime | N/A | `~/.local/share/shannot/runtime/` |
| Sessions | N/A | `~/.local/share/shannot/sessions/` |

## Troubleshooting Migration

### "SandboxManager not found"

The Python API was removed. Use CLI commands instead:

```bash
shannot run script.py
shannot approve
```

### "Module asyncssh not found"

asyncssh is no longer needed. SSH is implemented using stdlib subprocess:

```bash
pip uninstall asyncssh  # Clean up
```

### "Profile validation failed"

Old profile format is not compatible. Create a new profile:

```json
{
  "auto_approve": ["cat", "ls", "df"],
  "always_deny": ["rm -rf /"]
}
```

### "Syntax error in sandboxed script"

Sandboxed code must use Python 3.6 syntax. See [Python 3.6 Compatibility](troubleshooting.md#python-36-compatibility).

## Getting Help

If you encounter issues during migration:

1. Check `shannot status` output
2. Review [Troubleshooting](troubleshooting.md)
3. Open an issue: https://github.com/corv89/shannot/issues

Include:
- Previous shannot version
- Current shannot version (`shannot --version`)
- Error messages
- Old profile configuration (if relevant)
