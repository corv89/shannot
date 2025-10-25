# MCP Server Module

Model Context Protocol (MCP) server implementation for LLM integration.

## Overview

The MCP server module implements a Model Context Protocol server that exposes Shannot's sandboxed command execution capabilities to LLM clients like Claude Desktop and Claude Code. It provides tools and resources for secure, read-only system diagnostics and monitoring.

**Key Components:**

- **`ShannotMCPServer`** - Main MCP server class implementing the protocol
- **MCP Tools** - Exposed as callable functions for LLM clients
  - `run_sandbox_command` - Execute commands in sandbox
  - `read_sandbox_file` - Read files from sandboxed paths
- **MCP Resources** - Profile configurations available as resources

## MCP Integration

The server integrates with LLM clients through the Model Context Protocol:

```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "args": ["--profile", "diagnostics"]
    }
  }
}
```

## Common Usage Patterns

### Starting the MCP Server

```bash
# Start with default profile
shannot-mcp

# Use specific profile
shannot-mcp --profile diagnostics

# Enable verbose logging
shannot-mcp --verbose

# Use remote executor
shannot-mcp --target production
```

### Programmatic Server Creation

```python
from shannot.mcp_server import ShannotMCPServer
from shannot.executors import LocalExecutor

# Create server
executor = LocalExecutor()
server = ShannotMCPServer(
    server_name="shannot",
    profile_specs=["diagnostics"],
    executor=executor
)

# Run server (stdio transport)
await server.run_stdio()
```

### Multi-Profile Server

```python
# Server with multiple profiles
server = ShannotMCPServer(
    server_name="shannot-multi",
    profile_specs=[
        "minimal",
        "diagnostics",
        Path("/etc/shannot/custom.json")
    ]
)
```

## MCP Tools

The server exposes these tools to LLM clients:

### run_sandbox_command

Execute arbitrary commands in the sandbox.

**Parameters:**
- `command` (list[str]): Command to execute (e.g., ["df", "-h"])
- `args` (list[str]): Additional arguments (usually empty)

**Returns:** ProcessResult with stdout, stderr, returncode

**Example from LLM:**
```
Can you check the disk usage?
→ Calls run_sandbox_command with command=["df", "-h"]
```

### read_sandbox_file

Read file contents from sandboxed paths.

**Parameters:**
- `filepath` (str): Absolute path to file
- `max_lines` (int, optional): Limit output lines

**Returns:** File content as string

**Example from LLM:**
```
What's in /etc/os-release?
→ Calls read_sandbox_file with filepath="/etc/os-release"
```

## MCP Resources

Profiles are exposed as MCP resources for inspection:

```python
# List available resources
resources = await server.list_resources()

# Read profile resource
profile_content = await server.read_resource(
    "shannot://profile/diagnostics"
)
```

## Installation for LLM Clients

### Claude Desktop

```bash
shannot mcp install claude-desktop --profile diagnostics
```

Configuration added to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "args": ["--profile", "diagnostics"]
    }
  }
}
```

### Claude Code

```bash
shannot mcp install claude-code --profile diagnostics
```

Configuration added to `~/.config/claude/config.json` or platform-specific location.

## Server Lifecycle

```python
# Server supports async context manager
async with ShannotMCPServer(
    server_name="shannot",
    profile_specs=["diagnostics"]
) as server:
    await server.run_stdio()
# Automatically cleaned up
```

## Security Considerations

- **Read-only enforcement**: All commands execute in read-only sandbox
- **Command filtering**: Only allowed commands in profile can execute
- **Path restrictions**: Only mounted paths are accessible
- **Network isolation**: Network access disabled by default
- **Process isolation**: Separate PID namespace prevents host process access

## Related Documentation

- [MCP Integration Guide](../mcp.md) - Setting up MCP with LLM clients
- [MCP Main Module](mcp_main.md) - Entry point and CLI for MCP server
- [Tools Module](tools.md) - Underlying tool implementations
- [Profiles Guide](../profiles.md) - Profile configuration options

## API Reference

::: shannot.mcp_server
