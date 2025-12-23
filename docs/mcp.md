# MCP Server Integration

Shannot v0.5.0 provides MCP (Model Context Protocol) integration for secure, sandboxed Python script execution. This guide explains how to use Shannot's MCP server to give Claude Desktop or Claude Code controlled access to system operations through PyPy's sandbox architecture.

## What is MCP?

MCP (Model Context Protocol) is Anthropic's standard protocol for connecting AI assistants to external tools. With Shannot's MCP server, Claude can:

- 📝 Execute Python 3.6 scripts in a secure PyPy sandbox
- 🔒 Require interactive approval for sensitive operations
- ⚡ Auto-execute allowed operations (fast path)
- 📊 Run diagnostic commands (ls, df, ps, cat, grep)
- 🛡️ Block denied operations immediately

**Security Model**: Operations execute in PyPy sandbox with syscall-level virtualization. Session-based approval workflow ensures you review non-trivial operations before execution.

## Quick Start

### Linux Setup (5 minutes)

```bash
# 1. Install Shannot v0.5.0
pip install shannot>=0.5.0

# 2. Download PyPy sandbox runtime
shannot setup

# 3. Install MCP server for Claude Code
shannot mcp install --client claude-code

# 4. Restart Claude Code
# Now you can ask: "Run a Python script to check disk space"
```

### macOS/Windows Setup (Remote)

Since PyPy sandbox requires Linux, use a remote target:

```bash
# 1. Install Shannot locally
pip install shannot>=0.5.0

# 2. Configure remote Linux server
shannot remote add myserver --host your-server.com --user yourname

# 3. Test connection
shannot remote test myserver

# 4. Install MCP server with remote target
shannot mcp install --client claude-code --target myserver

# 5. Restart Claude Code
```

## How It Works

### Architecture

```
Claude → MCP Protocol → Shannot Server → PyPy Sandbox → Linux System
                              ↓
                     Session-Based Approval
```

1. **Claude sends Python script** via `sandbox_run` tool
2. **AST analysis** detects operations (UX optimization, not security)
3. **Three execution paths**:
   - **Fast path**: Auto-approved ops execute immediately
   - **Review path**: Unapproved ops create session for user review
   - **Blocked path**: Denied ops rejected immediately
4. **Session approval** (review path only):
   - User runs `shannot approve show <session_id>`
   - Reviews operations to be performed
   - Approves with `shannot approve --execute <session_id>`
5. **Results returned** to Claude

### Execution Workflow

#### Fast Path (Auto-Approved)

```python
# Claude sends:
{
  "script": "import subprocess\nsubprocess.call(['ls', '/tmp'])",
  "profile": "minimal"
}

# Shannot detects: "ls /tmp" is in auto_approve list
# → Executes immediately in PyPy sandbox
# → Returns: {"status": "success", "stdout": "...", "exit_code": 0}
```

#### Review Path (Needs Approval)

```python
# Claude sends:
{
  "script": "import subprocess\nsubprocess.call(['curl', 'https://example.com'])",
  "profile": "minimal"
}

# Shannot detects: "curl" not in auto_approve list
# → Creates session 20251222-mcp-request-a3f2
# → Returns: {
#     "status": "pending_approval",
#     "session_id": "20251222-mcp-request-a3f2",
#     "instructions": [
#       "Review with: shannot approve show 20251222-mcp-request-a3f2",
#       "Approve and execute: shannot approve --execute 20251222-mcp-request-a3f2"
#     ]
#   }

# User reviews and approves:
$ shannot approve show 20251222-mcp-request-a3f2
$ shannot approve --execute 20251222-mcp-request-a3f2

# Claude polls for results:
{
  "session_id": "20251222-mcp-request-a3f2"
}
# → Returns: {"status": "executed", "stdout": "...", "exit_code": 0}
```

#### Blocked Path (Denied)

```python
# Claude sends:
{
  "script": "import subprocess\nsubprocess.call(['rm', '-rf', '/'])",
  "profile": "minimal"
}

# Shannot detects: "rm -rf /" in always_deny list
# → Rejects immediately
# → Returns: {
#     "status": "denied",
#     "reason": "Script contains denied operation: 'rm -rf /'"
#   }
```

## Available Tools

### sandbox_run

Execute Python 3.6 script in PyPy sandbox with profile-based approval.

**Parameters:**
- `script` (required): Python 3.6 code to execute
- `profile` (optional): Approval profile (`minimal`, `readonly`, `diagnostics`, default: `minimal`)
- `name` (optional): Human-readable session name for tracking
- `target` (optional): Named SSH remote for remote execution (e.g., `prod`, `staging`)

**Python 3.6 Syntax Limitations:**
- ❌ No f-strings (use `.format()`)
- ❌ No async/await
- ❌ No walrus operator (`:=`)
- ❌ No dataclasses
- ✅ Use Python 3.6 compatible syntax

**Example:**
```python
# Claude's tool call:
sandbox_run({
  "script": """
import subprocess
result = subprocess.call(['df', '-h'])
""",
  "profile": "diagnostics",
  "name": "disk-check"
})
```

### session_result

Poll status of a pending session created by `sandbox_run`.

**Parameters:**
- `session_id` (required): Session ID returned by `sandbox_run`

**Returns:**
- `pending`: Awaiting user approval
- `executed`: Complete with results (stdout/stderr/exit_code)
- `expired`: Session expired (1 hour TTL)
- `cancelled`: User cancelled session
- `rejected`: User rejected session
- `failed`: Execution error

**Example:**
```python
# Poll session status:
session_result({"session_id": "20251222-mcp-request-a3f2"})

# Returns (when executed):
{
  "session_id": "20251222-mcp-request-a3f2",
  "status": "executed",
  "exit_code": 0,
  "stdout": "Filesystem      Size  Used Avail Use% Mounted on\n...",
  "stderr": "",
  "executed_at": "2025-12-22T14:30:45"
}
```

## Approval Profiles

Profiles control which operations execute immediately (fast path) vs requiring approval (review path).

### Minimal Profile (Default)

**Auto-approved commands:**
- `ls`, `cat`, `grep`, `find`

**Always denied:**
- `rm -rf /`
- `dd if=/dev/zero`
- `:(){ :|:& };:` (fork bomb)

**Best for**: Basic file inspection

### Readonly Profile

**Auto-approved commands:**
- All minimal commands plus:
- `head`, `tail`, `file`, `stat`, `wc`, `du`

**Best for**: Extended file analysis

### Diagnostics Profile

**Auto-approved commands:**
- All readonly commands plus:
- `df`, `free`, `ps`, `uptime`, `hostname`, `uname`, `env`, `id`

**Best for**: System monitoring and health checks

### Custom Profiles

Create custom profiles in `~/.config/shannot/`:

```bash
# Create custom.json
cat > ~/.config/shannot/custom.json <<'EOF'
{
  "auto_approve": [
    "echo",
    "printf",
    "date"
  ],
  "always_deny": [
    "eval",
    "exec"
  ]
}
EOF

# Use in MCP:
sandbox_run({
  "script": "import subprocess\nsubprocess.call(['echo', 'hello'])",
  "profile": "custom"
})
```

## Installation

### Option A: Using Shannot's Installer (Recommended)

```bash
# Install for Claude Desktop (default)
shannot mcp install

# Install for Claude Code
shannot mcp install --client claude-code

# Use a remote target
shannot mcp install --client claude-code --target prod
```

### Option B: Manual Configuration

#### Claude Desktop (macOS)
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

#### Claude Desktop (Windows)
Edit `%APPDATA%\Claude\claude_desktop_config.json` with the same JSON.

#### Claude Code
Use the `.mcp.json` snippet from `shannot mcp install --client claude-code`, or:

```bash
# User scope (recommended)
claude mcp add --transport stdio shannot --scope user -- shannot-mcp

# Project scope (shared with team)
claude mcp add --transport stdio shannot --scope project -- shannot-mcp
```

### Verify Installation

In Claude Code:
```
> /mcp
```

You should see `shannot` listed with 2 tools (`sandbox_run`, `session_result`) and 3 resources.

## Session Management

### List Pending Sessions

```bash
shannot approve list
```

### Review Session Details

```bash
shannot approve show <session_id>
```

Shows:
- Script content
- Detected operations
- Profile used
- Creation/expiry time

### Approve and Execute

```bash
shannot approve --execute <session_id>
```

### Cancel Session

```bash
shannot approve cancel <session_id>
```

### Session TTL

Sessions expire after **1 hour** if not approved. Expired sessions return:

```json
{
  "status": "expired",
  "message": "Session expired (1 hour TTL)"
}
```

## Resources

Shannot exposes MCP resources for inspection:

### sandbox://profiles

List available approval profiles:

```json
["minimal", "readonly", "diagnostics", "custom"]
```

### sandbox://profiles/{name}

Get profile configuration:

```json
{
  "auto_approve": ["ls", "cat", "grep", "find"],
  "always_deny": ["rm -rf /", "dd if=/dev/zero", ":(){ :|:& };:"]
}
```

### sandbox://status

Runtime status and configuration:

```json
{
  "version": "0.5.1",
  "runtime_available": true,
  "profiles": ["minimal", "readonly", "diagnostics"],
  "runtime": {
    "pypy_sandbox": "/Users/user/.local/share/shannot/runtime/pypy-sandbox",
    "lib_python": "/Users/user/.local/share/shannot/runtime/lib-python/3",
    "lib_pypy": "/Users/user/.local/share/shannot/runtime/lib_pypy"
  }
}
```

### sandbox://remotes

List configured SSH remotes for remote execution:

```json
{
  "remotes": {
    "prod": {"host": "prod.example.com", "user": "admin", "port": 22},
    "staging": {"host": "staging.local", "user": "deploy", "port": 2222}
  }
}
```

If no remotes are configured, returns `{"remotes": {}}`.

## Examples

### Disk Space Check

**User**: "Check how much disk space I have"

**Claude**: *Calls sandbox_run with diagnostics profile*

```python
sandbox_run({
  "script": """
import subprocess
subprocess.call(['df', '-h'])
""",
  "profile": "diagnostics"
})
```

**Result**: Executes immediately (fast path) and returns disk usage.

### File Search (Requires Approval)

**User**: "Find all Python files in /home that are larger than 1MB"

**Claude**: *Calls sandbox_run*

```python
sandbox_run({
  "script": """
import subprocess
subprocess.call(['find', '/home', '-name', '*.py', '-size', '+1M'])
""",
  "profile": "minimal"
})
```

**Result**: Creates session (review path) because searching /home may be sensitive.

**User approves**:
```bash
shannot approve --execute 20251222-mcp-request-b4d9
```

**Claude polls**:
```python
session_result({"session_id": "20251222-mcp-request-b4d9"})
```

**Result**: Returns found files.

### Blocked Operation

**User**: "Delete all temporary files"

**Claude**: *Calls sandbox_run*

```python
sandbox_run({
  "script": """
import subprocess
subprocess.call(['rm', '-rf', '/tmp/*'])
""",
  "profile": "minimal"
})
```

**Result**: Rejected immediately (blocked path) due to `rm -rf` pattern.

## Security Model

### What Shannot Protects Against

✅ **Unauthorized modifications** - PyPy sandbox prevents actual file writes
✅ **Network access** - Socket operations are virtualized
✅ **Privilege escalation** - No actual system calls reach the kernel
✅ **Subprocess injection** - All subprocess calls intercepted and approved

### Security Boundaries

**AST Analysis (UX Optimization)**:
- Best-effort operation detection
- Helps provide fast feedback
- **NOT a security boundary**
- Can miss dynamic operations (eval, getattr, etc.)

**Runtime Enforcement (Security Boundary)**:
- PyPy sandbox intercepts ALL system calls
- Subprocess virtualization enforces approval profiles
- Security enforced at runtime, not static analysis

### Best Practices

1. **Review allowed commands** in profiles before using
2. **Use minimal profiles** when possible
3. **Don't run as root** - use a regular user account
4. **Review sessions** before approving in interactive mode
5. **Monitor pending sessions** with `shannot approve list`

## Troubleshooting

### "PyPy sandbox runtime not found"

```bash
# Download PyPy sandbox
shannot setup

# Verify installation
shannot status
```

### "shannot-mcp command not found"

Ensure you installed v0.5.0+:

```bash
pip install --upgrade "shannot>=0.5.0"
```

### Claude doesn't show Shannot tools

1. Restart Claude completely
2. Check configuration:
   ```bash
   cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```
3. For Claude Code, use `/mcp` to check server status

### Session expired

Sessions have a 1-hour TTL. Approve within this window:

```bash
# Check pending sessions
shannot approve list

# Approve before expiry
shannot approve --execute <session_id>
```

### "Operation not in profile allowlist"

Either:
1. Use a broader profile (`readonly` or `diagnostics`)
2. Create a custom profile with needed commands
3. Approve the session interactively

## Remote Execution

Execute sandboxed scripts on remote Linux hosts via SSH. This is essential for macOS/Windows users (PyPy sandbox requires Linux) and for managing production servers.

### Configuring Remotes

```bash
# Add a named remote target
shannot remote add prod --host prod.example.com --user admin

# Add with custom SSH port
shannot remote add staging --host staging.local --user deploy --port 2222

# Test connection
shannot remote test prod

# List configured remotes
shannot remote list
```

### Using Remote Targets with MCP

**Option 1: Direct target parameter** (recommended for per-request targeting)

Claude can specify the target in each `sandbox_run` request:

```python
# Execute on prod server
sandbox_run({
  "script": "import subprocess\nsubprocess.call(['df', '-h'])",
  "profile": "diagnostics",
  "target": "prod"
})

# Response includes target
{"status": "success", "stdout": "...", "target": "prod"}
```

**Option 2: Default remote** (for consistent targeting)

Install MCP server with a default target:

```bash
shannot mcp install --target prod
# All requests now execute on prod by default
```

### Security: Named Remotes Only

For security, the `target` parameter only accepts named remotes configured via `shannot remote add`. Arbitrary `user@host` or `user@host:port` formats are rejected:

```python
# ❌ Rejected - arbitrary SSH target
sandbox_run({"script": "...", "target": "attacker@evil.com"})
# Error: "Arbitrary SSH targets are not allowed"

# ✅ Allowed - named remote
sandbox_run({"script": "...", "target": "prod"})
```

This prevents Claude from being social-engineered into connecting to unauthorized hosts.

### Discovering Available Remotes

Claude can query available remotes via the `sandbox://remotes` resource:

```json
{
  "remotes": {
    "prod": {"host": "prod.example.com", "user": "admin", "port": 22},
    "staging": {"host": "staging.local", "user": "deploy", "port": 2222}
  }
}
```

### Remote Execution Flow

1. **First request**: Shannot automatically deploys itself to the remote (fast check, ~50ms after initial deploy)
2. **Script execution**: Runs in PyPy sandbox on remote host
3. **Results returned**: stdout, stderr, exit_code sent back via SSH

Same three execution paths apply:
- **Fast path**: Auto-approved ops execute immediately on remote
- **Review path**: Creates local session, user approves, then executes on remote
- **Blocked path**: Denied ops rejected immediately (never sent to remote)

## Advanced Usage

### Multiple Profiles

Install with multiple profiles for different use cases:

```bash
shannot mcp install --client claude-code
```

Claude can use any profile via the `profile` parameter:

```python
# Minimal for basic file ops
sandbox_run({"script": "...", "profile": "minimal"})

# Diagnostics for system health
sandbox_run({"script": "...", "profile": "diagnostics"})
```

### Session Naming

Use meaningful names for session tracking:

```python
sandbox_run({
  "script": "...",
  "profile": "minimal",
  "name": "analyze-logs-for-errors"
})
```

Names appear in `shannot approve list` for easier identification.

### Verbose Logging

Run MCP server with verbose output for debugging:

```bash
shannot-mcp --verbose
```

## Testing

See [MCP Testing Guide](mcp-testing.md) for comprehensive testing instructions.

Quick test:

```bash
# Run test suite
uv run pytest test/test_mcp*.py -v

# Manual server test
shannot-mcp --verbose
# (Send test JSON-RPC messages to stdin)
```

## Next Steps

- **[Session Management](../README.md#session-approval-workflow)** - Learn about session approval workflow
- **[Profiles](../README.md#profiles)** - Create custom approval profiles
- **[Remote Execution](../README.md#remote-execution)** - Execute on remote Linux hosts

## Getting Help

- 🐛 **Bug reports**: [GitHub Issues](https://github.com/corv89/shannot/issues)
- 💬 **Questions**: [GitHub Discussions](https://github.com/corv89/shannot/discussions)
- 📖 **Docs**: [Documentation](https://github.com/corv89/shannot/tree/main/docs)
