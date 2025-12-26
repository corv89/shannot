# Usage Guide

Complete guide to using Shannot for safe, sandboxed script execution.

## Quick Start

```bash
# Install PyPy runtime (one-time)
shannot setup runtime

# Run a script in the sandbox
shannot run script.py

# Review and approve pending operations
shannot approve

# Check system status
shannot status
```

## CLI Commands

### shannot setup

Interactive setup menu or configuration subcommands.

```bash
shannot setup                      # Interactive setup menu
shannot setup runtime              # Install runtime
shannot setup runtime --force      # Force reinstall
shannot setup runtime --status     # Check if installed
shannot setup runtime --remove     # Remove installed runtime
shannot setup runtime --quiet      # Suppress progress output
shannot setup remote               # Interactive remote management
shannot setup mcp                  # Interactive MCP setup
```

### shannot run

Execute a Python script in the PyPy sandbox.

```bash
shannot run script.py                    # Basic execution
shannot run script.py --tmp=/tmp/work    # Map real directory to /tmp
shannot run script.py --dry-run          # Queue operations without executing
shannot run script.py --target prod      # Execute on remote target
```

**Options:**

| Option | Description |
|--------|-------------|
| `--pypy-sandbox PATH` | Path to pypy-sandbox executable |
| `--lib-path PATH` | Path to lib-python and lib_pypy |
| `--tmp DIR` | Real directory mapped to virtual /tmp |
| `--dry-run` | Log commands without executing |
| `--script-name NAME` | Human-readable session name |
| `--analysis DESC` | Description of script purpose |
| `--target NAME` | SSH target for remote execution |
| `--nocolor` | Disable ANSI coloring |
| `--raw-stdout` | Disable output sanitization |
| `--debug` | Enable debug mode |

### shannot approve

Interactive TUI for reviewing and approving pending sessions.

```bash
shannot approve                    # Launch TUI
shannot approve list               # List pending sessions
shannot approve show SESSION_ID    # Show session details
shannot approve history            # Show recent sessions
```

**TUI Controls:**

| Key | Action |
|-----|--------|
| `j/k` or `↑/↓` | Navigate up/down |
| `Enter` | View details / Execute |
| `Space` | Toggle selection |
| `x` | Execute selected sessions |
| `r` | Reject selected sessions |
| `a` | Select all |
| `n` | Deselect all |
| `q` / `Esc` | Quit / Go back |

### shannot setup remote

Manage SSH remote targets.

```bash
shannot setup remote add NAME [USER@]HOST    # Add remote target
shannot setup remote list                     # List configured targets
shannot setup remote test NAME                # Test connection
shannot setup remote remove NAME              # Remove target
```

**Add options:**

```bash
shannot setup remote add prod \
  --host prod.example.com \
  --user deploy \
  --port 22
```

### shannot status

Show system health and configuration status.

```bash
shannot status             # Full status
shannot status --runtime   # Runtime status only
shannot status --targets   # Remote targets only
```

## Session Workflow

Shannot uses a session-based approval workflow for subprocess execution:

### 1. Dry-Run Phase

When a script runs in the sandbox, subprocess calls are captured but not executed:

```python
# script.py
import subprocess
subprocess.call(['df', '-h'])      # Captured, not executed
subprocess.call(['rm', '-rf', '/']) # Captured, blocked by profile
```

```bash
shannot run script.py
# Output: Session created: 20250115-check-disk-a3f2
```

### 2. Review Phase

Use the interactive TUI to review captured operations:

```bash
shannot approve
```

The TUI shows:
- Pending subprocess commands
- Which commands match auto_approve (will execute immediately)
- Which commands match always_deny (will be blocked)
- Which commands require manual approval

### 3. Execute Phase

After approval, operations execute on the host system:

```bash
# From TUI: press 'x' to execute selected sessions
# Or directly:
shannot approve show SESSION_ID    # Review details
# Then press 'x' in TUI
```

## Approval Profiles

Profiles control which commands execute automatically vs. require approval.

### Profile Structure

```json
{
  "auto_approve": [
    "cat", "ls", "find", "grep", "head", "tail", "df", "free"
  ],
  "always_deny": [
    "rm -rf /",
    "dd if=/dev/zero",
    ":(){ :|:& };:"
  ]
}
```

### Profile Locations

1. `.shannot/profile.json` (project-local, highest priority)
2. `~/.config/shannot/profile.json` (global)
3. Built-in default profile

### Command Matching

Commands are matched by their base name (path stripped):

```python
subprocess.call(['/usr/bin/cat', '/etc/passwd'])  # Matches "cat"
subprocess.call(['cat', '/etc/passwd'])           # Matches "cat"
```

See [Profile Configuration](profiles.md) for details.

## Remote Execution

Execute sandboxed scripts on remote Linux hosts via SSH.

### Setup Remote Target

```bash
# Add remote
shannot setup remote add prod user@prod.example.com

# Test connection
shannot setup remote test prod
```

### Run on Remote

```bash
# Execute script on remote
shannot run script.py --target prod

# The workflow is the same:
# 1. Script runs in sandbox on remote
# 2. Operations captured in session
# 3. Review with `shannot approve`
# 4. Execute approved operations
```

### Auto-Deployment

When executing on a remote for the first time, Shannot automatically:
1. Deploys itself to the remote (`/tmp/shannot-v{version}/`)
2. Sets up the PyPy runtime
3. Executes the sandboxed script

No manual installation on remotes is required.

## Python 3.6 Compatibility

**Important:** Sandboxed scripts run in PyPy's Python 3.6 environment.

### Supported Syntax

```python
# OK: f-strings (Python 3.6+)
print(f"Value: {x}")

# OK: Basic type annotations
def greet(name: str) -> str:
    return f"Hello, {name}"
```

### Not Supported

```python
# NOT OK: Match statements (Python 3.10+)
match value:
    case 1: print("one")

# NOT OK: Union type syntax (Python 3.10+)
def process(x: int | str): pass

# NOT OK: Walrus operator (Python 3.8+)
if (n := len(items)) > 10: pass

# NOT OK: dataclasses (Python 3.7+)
from dataclasses import dataclass
```

### Workarounds

```python
# Instead of dataclasses, use namedtuple
from collections import namedtuple
Point = namedtuple('Point', ['x', 'y'])

# Instead of union types, use comments
def process(x):  # type: (Union[int, str]) -> None
    pass
```

## Common Use Cases

### System Diagnostics

```python
# diagnostics.py
import subprocess

print("=== Disk Usage ===")
subprocess.call(['df', '-h'])

print("\n=== Memory ===")
with open('/proc/meminfo') as f:
    for line in f.readlines()[:5]:
        print(line.strip())

print("\n=== Processes ===")
subprocess.call(['ps', 'aux', '--sort=-pcpu'])
```

```bash
shannot run diagnostics.py
shannot approve  # Review and execute
```

### Log Analysis

```python
# analyze_logs.py
import subprocess

# These commands are typically auto-approved
subprocess.call(['grep', 'ERROR', '/var/log/app.log'])
subprocess.call(['tail', '-n', '100', '/var/log/syslog'])
```

### Configuration Inspection

```python
# check_config.py
import os

# Read system configuration
with open('/etc/os-release') as f:
    print(f.read())

# Check environment
for key, value in sorted(os.environ.items()):
    print(f"{key}={value}")
```

## Limitations

### What Sandboxed Code CAN Do

- Read files from virtual filesystem
- Execute subprocess calls (captured for approval)
- Write to virtual /tmp (mapped to real directory if configured)
- Access virtual /proc for system information

### What Sandboxed Code CANNOT Do

- Modify the host filesystem directly
- Access the network (sockets disabled)
- Execute code outside the sandbox
- Bypass the approval workflow for subprocess calls

### Known Constraints

- **Python 3.6 syntax only** - PyPy sandbox limitation
- **1-hour session TTL** - Pending sessions expire after 1 hour
- **No interactive input** - stdin is not passed through by default

## Next Steps

- [Profile Configuration](profiles.md) - Customize command approval
- [Configuration Guide](configuration.md) - Remote targets and MCP
- [Deployment Guide](deployment.md) - Production deployment
- [Troubleshooting](troubleshooting.md) - Common issues
