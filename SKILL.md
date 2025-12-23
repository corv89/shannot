# Shannot - Sandboxed System Diagnostics

Run diagnostic scripts in a sandbox with human approval.

## Usage

```bash
# Run a script locally
shannot run /path/to/pypy-sandbox -S /tmp/script.py

# Run against a remote host (files fetched via SSH)
shannot run /path/to/pypy-sandbox -S /tmp/script.py --target user@host

# Dry-run mode (queue all operations for review)
shannot run /path/to/pypy-sandbox -S /tmp/script.py --dry-run
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
# → Returns immediately with disk usage

# Search files (minimal profile doesn't include find in /home)
sandbox_run({
  "script": "import subprocess\nsubprocess.call(['find', '/home', '-name', '*.log'])",
  "profile": "minimal"
})
# → Returns session ID for user approval
# User reviews: shannot approve show <session_id>
# User approves: shannot approve --execute <session_id>
# Poll results: session_result({"session_id": "<session_id>"})
```

### Installation

```bash
# Install for Claude Desktop/Code
shannot mcp install --client claude-code
```

See [MCP Documentation](docs/mcp.md) for complete guide.

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

## Security Model

- **Reads**: Allowed within virtual filesystem boundaries
- **Commands**: Queued for human approval (or auto-approved via profile)
- **Writes**: Queued for human approval
- **Network**: Disabled (socket calls return errors)

## Tips

- Keep scripts focused on diagnostics and information gathering
- Use `--dry-run` to preview what operations a script will request
- Tell the user to run `shannot approve` to review queued operations
