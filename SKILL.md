---
name: shannot
description: Run diagnostic scripts in sandbox with human approval (MCP tool)
---

# Shannot - Sandboxed System Diagnostics

Run diagnostic scripts in a sandbox with human approval.

## Usage

```bash
# Run a script locally
shannot run script.py

# Run against a remote host
shannot run script.py --target user@host

# Dry-run mode (queue all operations for review)
shannot run script.py --dry-run
```

After running with `--dry-run`, instruct the user to open `shannot approve` to review and execute queued operations.

## MCP Integration (v0.5.0+)

Shannot provides MCP (Model Context Protocol) integration for LLM agents like Claude.

### Available Tools

**sandbox_run** - Execute Python 3.6 scripts with profile-based approval:
- **Fast path**: Auto-approved operations execute immediately
- **Review path**: Unapproved operations create sessions for user approval
- **Blocked path**: Denied operations rejected immediately

**session_result** - Poll status of pending sessions

### Profiles

- **minimal**: ls, cat, grep, find
- **readonly**: minimal + head, tail, file, stat, wc, du
- **diagnostics**: readonly + df, free, ps, uptime, hostname, uname, env, id

### Example MCP Usage

```python
# Check disk space (diagnostics profile auto-approves df)
sandbox_run({
  "script": "import subprocess\nsubprocess.call(['df', '-h'])",
  "profile": "diagnostics"
})
# Returns immediately with disk usage

# Search files (may require approval depending on profile)
sandbox_run({
  "script": "import subprocess\nsubprocess.call(['find', '/home', '-name', '*.log'])",
  "profile": "minimal"
})
# Returns session ID for user approval
# User reviews: shannot approve show <session_id>
# User approves: shannot approve --execute <session_id>
# Poll results: session_result({"session_id": "<session_id>"})
```

### Remote Execution

```python
# Run diagnostics on a remote server
sandbox_run({
  "script": "import subprocess\nsubprocess.call(['df', '-h'])",
  "profile": "diagnostics",
  "target": "prod"  # Uses configured remote target
})
```

### Installation

```bash
# Install for Claude Desktop/Code
shannot mcp install --client claude-code
```

See [MCP Documentation](docs/mcp.md) for complete guide.

## Diagnostic Script Examples

### System Health Check

```python
# health_check.py - Comprehensive system status
import subprocess

print("=== System Information ===")
subprocess.call(["uname", "-a"])

print("\n=== Uptime ===")
subprocess.call(["uptime"])

print("\n=== Disk Usage ===")
subprocess.call(["df", "-h"])

print("\n=== Memory Usage ===")
subprocess.call(["free", "-h"])

print("\n=== Top Processes ===")
subprocess.call(["ps", "aux", "--sort=-pcpu"])
```

### Log Analysis

```python
# analyze_logs.py - Search for errors in logs
import subprocess

print("=== Recent Errors ===")
subprocess.call(["grep", "-i", "error", "/var/log/syslog"])

print("\n=== Last 50 Lines ===")
subprocess.call(["tail", "-n", "50", "/var/log/syslog"])
```

### Network Diagnostics

```python
# network_check.py - Network status
import subprocess

print("=== Network Interfaces ===")
subprocess.call(["ip", "addr"])

print("\n=== Listening Ports ===")
subprocess.call(["ss", "-tlnp"])

print("\n=== Routing Table ===")
subprocess.call(["ip", "route"])
```

### Service Status

```python
# service_check.py - Check systemd services
import subprocess

services = ["nginx", "postgresql", "redis"]

for service in services:
    print(f"\n=== {service} ===")
    subprocess.call(["systemctl", "status", service, "--no-pager"])
```

### File System Inspection

```python
# fs_check.py - Filesystem analysis
import subprocess
import os

print("=== Large Files ===")
subprocess.call(["find", "/var", "-size", "+100M", "-type", "f"])

print("\n=== Disk I/O Stats ===")
subprocess.call(["iostat", "-x", "1", "3"])

print("\n=== Mount Points ===")
subprocess.call(["mount"])
```

### Configuration Audit

```python
# config_audit.py - Check configuration files
import os

configs = [
    "/etc/nginx/nginx.conf",
    "/etc/postgresql/14/main/postgresql.conf",
    "/etc/redis/redis.conf"
]

for config in configs:
    print(f"\n=== {config} ===")
    if os.path.exists(config):
        with open(config) as f:
            # Print first 20 lines
            for i, line in enumerate(f):
                if i >= 20:
                    print("... (truncated)")
                    break
                print(line.rstrip())
    else:
        print("File not found")
```

## Writing Scripts

Scripts run in a virtualized environment with Python 3.6 syntax.

### Running Commands

```python
import subprocess

# Commands are intercepted and queued for approval
result = subprocess.run(["ls", "-la", "/etc"], capture_output=True, text=True)
print(result.stdout)
```

### Reading Files

```python
# File reads are allowed within the virtual filesystem
with open("/etc/hostname") as f:
    print(f.read())
```

### Writing Files

```python
# Writes are queued for approval, not executed immediately
with open("/tmp/output.txt", "w") as f:
    f.write("diagnostic results")
```

### Python 3.6 Compatibility

Sandboxed scripts must use Python 3.6 syntax:

```python
# Use namedtuple instead of dataclasses
from collections import namedtuple
Point = namedtuple('Point', ['x', 'y'])

# Use Union from typing instead of pipe syntax
from typing import Union
def process(x):
    # type: (Union[int, str]) -> None
    pass

# Use if/elif instead of match statements
if value == 1:
    print("one")
elif value == 2:
    print("two")
```

## Security Model

- **Reads**: Allowed within virtual filesystem boundaries
- **Commands**: Queued for human approval (or auto-approved via profile)
- **Writes**: Queued for human approval
- **Network**: Disabled (socket calls return errors)

## Tips

- Keep scripts focused on diagnostics and information gathering
- Use `--dry-run` to preview what operations a script will request
- Tell the user to run `shannot approve` to review queued operations
- Use the appropriate profile for your use case (diagnostics for system info, minimal for restricted access)
- For remote targets, ensure SSH keys are configured
