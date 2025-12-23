# Tools Module

MCP tools for sandboxed script execution.

## Overview

The tools module provides MCP (Model Context Protocol) tools that integrate with Claude Desktop and Claude Code.

## Available Tools

### sandbox_run

Execute Python 3.6 scripts in the PyPy sandbox.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `script` | string | Yes | Python script content |
| `profile` | string | No | Profile name (minimal, readonly, diagnostics) |
| `target` | string | No | Remote SSH target name |

**Example:**

```json
{
  "script": "import subprocess\nsubprocess.call(['df', '-h'])",
  "profile": "diagnostics"
}
```

**Response:**

- **Fast path**: Auto-approved operations return immediately with output
- **Review path**: Returns session ID for user approval
- **Blocked path**: Returns error for denied operations

### session_result

Poll status of a pending session.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session ID from sandbox_run |

**Example:**

```json
{
  "session_id": "20250115-check-disk-a3f2"
}
```

## Profiles

| Profile | Auto-approved Commands |
|---------|----------------------|
| minimal | ls, cat, grep, find |
| readonly | minimal + head, tail, file, stat, wc, du |
| diagnostics | readonly + df, free, ps, uptime, hostname, uname, env, id |

## Integration

### With Claude Desktop

```bash
shannot mcp install --client claude-desktop
```

### With Claude Code

```bash
shannot mcp install --client claude-code
```

## See Also

- [MCP Integration](../mcp.md) - Complete MCP guide
- [MCP Server](mcp_server.md) - Server implementation
- [Profile Configuration](../profiles.md) - Custom profiles
