# MCP Server Module

Model Context Protocol (MCP) server implementation for LLM integration with PyPy sandbox.

## Overview

The MCP server module (v0.5.0) implements a Model Context Protocol server that exposes Shannot's PyPy sandbox capabilities to LLM clients like Claude Desktop and Claude Code. It provides script execution with hybrid approval workflow and profile-based security.

**Key Components:**

- **`ShannotMCPServer`** - Main MCP server implementing PyPy sandbox integration
- **`MCPServer`** - Base server class with JSON-RPC request routing
- **MCP Protocol** - Pure stdlib JSON-RPC 2.0 over stdin/stdout
- **MCP Types** - Dataclass definitions for tools, resources, content

## Architecture

```
shannot.mcp/
├── __init__.py          # Package exports
├── protocol.py          # JSON-RPC transport (stdlib only)
├── types.py             # MCP type definitions
├── server.py            # Base MCPServer class
└── server_impl.py       # ShannotMCPServer implementation
```

## MCP Tools

### sandbox_run

Execute Python 3.6 script in PyPy sandbox with profile-based approval.

**Input Schema:**
```python
{
  "script": str,        # Python 3.6 code to execute
  "profile": str,       # "minimal", "readonly", "diagnostics" (default: "minimal")
  "name": str           # Optional session name for tracking
}
```

**Returns:**
```python
{
  "status": "success" | "pending_approval" | "denied" | "error",
  "exit_code": int,            # (if success)
  "stdout": str,               # (if success)
  "stderr": str,               # (if success)
  "duration": float,           # (if success)
  "session_id": str,           # (if pending_approval)
  "instructions": list[str],   # (if pending_approval)
  "reason": str,               # (if denied)
  "error": str                 # (if error)
}
```

**Example:**
```python
# LLM calls tool
sandbox_run({
  "script": "import subprocess\nsubprocess.call(['df', '-h'])",
  "profile": "diagnostics"
})

# Fast path response (auto-approved):
{
  "status": "success",
  "exit_code": 0,
  "stdout": "Filesystem      Size  Used Avail Use% Mounted on\n...",
  "stderr": "",
  "duration": 0.123,
  "profile": "diagnostics"
}

# Review path response (needs approval):
{
  "status": "pending_approval",
  "session_id": "20251222-mcp-request-a3f2",
  "detected_operations": ["curl https://example.com"],
  "instructions": [
    "Review with: shannot approve show 20251222-mcp-request-a3f2",
    "Approve and execute: shannot approve --execute 20251222-mcp-request-a3f2"
  ]
}
```

### session_result

Poll status of pending session created by `sandbox_run`.

**Input Schema:**
```python
{
  "session_id": str  # Session ID from sandbox_run
}
```

**Returns:**
```python
{
  "session_id": str,
  "status": "pending" | "executed" | "expired" | "cancelled" | "rejected" | "failed",
  "created_at": str,
  "exit_code": int,       # (if executed)
  "stdout": str,          # (if executed)
  "stderr": str,          # (if executed)
  "executed_at": str,     # (if executed)
  "error": str,           # (if failed)
  "expires_at": str,      # (if pending)
  "instructions": list,   # (if pending)
  "message": str          # (if expired/cancelled/rejected)
}
```

**Example:**
```python
# Poll session
session_result({"session_id": "20251222-mcp-request-a3f2"})

# Response (after user approval):
{
  "session_id": "20251222-mcp-request-a3f2",
  "status": "executed",
  "exit_code": 0,
  "stdout": "...",
  "stderr": "",
  "executed_at": "2025-12-22T14:30:45"
}
```

## MCP Resources

### sandbox://profiles

List available approval profiles.

**Returns:** JSON array of profile names
```json
["minimal", "readonly", "diagnostics"]
```

### sandbox://profiles/{name}

Get profile configuration.

**Returns:** Profile structure
```json
{
  "auto_approve": ["ls", "cat", "grep", "find"],
  "always_deny": ["rm -rf /", "dd if=/dev/zero", ":(){ :|:& };:"]
}
```

### sandbox://status

Runtime status and configuration.

**Returns:** Status object
```json
{
  "version": "0.5.1",
  "runtime_available": true,
  "profiles": ["minimal", "readonly", "diagnostics"],
  "runtime": {
    "pypy_sandbox": "/path/to/pypy-sandbox",
    "lib_python": "/path/to/lib-python/3",
    "lib_pypy": "/path/to/lib_pypy"
  }
}
```

## Server Configuration

### Creating a Server

```python
from pathlib import Path
from shannot.mcp.server_impl import ShannotMCPServer
from shannot.mcp.protocol import serve

# Create server with default profiles
server = ShannotMCPServer(
    profile_paths=None,  # Use defaults
    verbose=False
)

# Create server with custom profiles
server = ShannotMCPServer(
    profile_paths=[
        Path("~/.config/shannot/custom.json").expanduser()
    ],
    verbose=True
)

# Start serving (blocks)
serve(server.handle_request)
```

### Profile Structure

Custom profiles are JSON files with:

```json
{
  "auto_approve": [
    "ls", "cat", "grep", "find"
  ],
  "always_deny": [
    "rm -rf /",
    "dd if=/dev/zero"
  ]
}
```

Place in `~/.config/shannot/{name}.json` and server auto-discovers.

## Installation for LLM Clients

### Claude Desktop (macOS)

```bash
shannot setup mcp install
# or
shannot setup mcp install --client claude-desktop
```

Adds to `~/Library/Application Support/Claude/claude_desktop_config.json`:
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

### Claude Code

```bash
shannot setup mcp install --client claude-code
```

Generates `.mcp.json` snippet or updates user config.

### Manual Configuration

```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "args": ["--verbose"],  # optional
      "env": {}
    }
  }
}
```

## Execution Workflow

### Three Execution Paths

**1. Fast Path (Auto-Approved)**
- AST detects only allowed operations
- Executes immediately in PyPy sandbox
- Returns results directly

**2. Review Path (Pending Approval)**
- AST detects unapproved operations
- Creates session for user review
- User approves with `shannot approve`
- LLM polls with `session_result`

**3. Blocked Path (Denied)**
- AST detects denied operations
- Rejects immediately
- Returns error with reason

### AST Analysis

Server performs best-effort AST analysis to detect subprocess calls:

```python
# Detected (literal arguments):
import subprocess
subprocess.call(['ls', '/tmp'])  # → "ls /tmp"

# Not detected (dynamic arguments):
import subprocess
cmd = ['ls', '/tmp']
subprocess.call(cmd)  # → []
```

**Important**: AST analysis is UX optimization, NOT security. Security enforced at runtime by PyPy sandbox subprocess virtualization.

## Security Model

### Protection Layers

1. **PyPy Sandbox**: Syscall-level virtualization
2. **Subprocess Virtualization**: Profile-based approval enforcement
3. **Session Workflow**: Interactive review for sensitive operations
4. **Profile Allowlists**: Restrict executable commands
5. **Session TTL**: 1-hour expiry for pending approvals

### What's Protected

✅ Unauthorized file modifications (sandbox prevents writes)
✅ Network access (socket operations virtualized)
✅ Privilege escalation (no actual syscalls reach kernel)
✅ Subprocess injection (profiles enforce allowlist)

### Limitations

⚠️ AST analysis can miss dynamic operations
⚠️ Python 3.6 syntax only (PyPy sandbox limitation)
⚠️ Session approval required for non-trivial operations

## Programmatic Usage

### Synchronous Server

```python
from shannot.mcp.server_impl import ShannotMCPServer
from shannot.mcp.protocol import serve

# Create and serve
server = ShannotMCPServer()
serve(server.handle_request)
```

### Custom Handler

```python
# Process single request
request = {
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
}
response = server.handle_request(request)
print(response)
```

### Testing

```python
# Test tool call
result = server._handle_sandbox_run({
    "script": "print('hello')",
    "profile": "minimal"
})
print(result.text)  # JSON response
```

## CLI Usage

```bash
# Start server (default profiles)
shannot-mcp

# With verbose logging
shannot-mcp --verbose

# Load custom profile
# (place profile at ~/.config/shannot/custom.json)
shannot-mcp --profile custom

# With multiple profiles
shannot-mcp --profile ~/.config/shannot/profile1.json \
            --profile ~/.config/shannot/profile2.json
```

## Error Handling

```python
# Runtime not found
{
  "status": "error",
  "error": "PyPy sandbox runtime not found. Run 'shannot setup runtime' to install."
}

# Invalid profile
{
  "status": "error",
  "error": "Unknown profile 'nonexistent'"
}

# Session not found
{
  "status": "error",
  "error": "Session not found: invalid-id"
}
```

## Related Documentation

- [MCP Integration Guide](../mcp.md) - Complete MCP setup and usage
- [MCP Testing](../mcp-testing.md) - Testing procedures
- [MCP Main Module](mcp_main.md) - Entry point and CLI
- [Session Management](../usage.md#session-workflow) - Session workflow

## API Reference

### shannot.mcp.server_impl

- `ShannotMCPServer` - Main MCP server class
- `find_runtime()` - Locate PyPy sandbox runtime

### shannot.mcp.server

- `MCPServer` - Base server with request routing
- `ServerCapabilities` - Capability negotiation
- `ServerInfo` - Server metadata

### shannot.mcp.protocol

- `read_message()` - Read JSON-RPC message from stdin
- `write_message()` - Write JSON-RPC message to stdout
- `serve()` - Main serving loop

### shannot.mcp.types

- `TextContent` - Text content type
- `Tool` - Tool definition
- `Resource` - Resource definition
- `ServerInfo` - Server information
