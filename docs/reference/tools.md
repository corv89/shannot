# Tools Module

Pydantic-AI compatible tools for sandboxed command execution in MCP servers and AI agents.

## Overview

The tools module provides type-safe, reusable tools that integrate Shannot's sandbox capabilities with Model Context Protocol (MCP) servers and Pydantic-AI agents. These tools handle command execution, file reading, and output streaming with proper error handling.

**Key Components:**

- **`SandboxDeps`** - Dependency container for sandbox configuration and executors
- **`run_sandbox_command`** - Execute arbitrary commands in the sandbox
- **`read_sandbox_file`** - Read file contents from sandboxed paths
- **`stream_sandbox_output`** - Stream command output (for long-running processes)

## Common Usage Patterns

### With MCP Servers

```python
from shannot.tools import SandboxDeps, run_sandbox_command
from shannot.executors import LocalExecutor

# Create dependencies
executor = LocalExecutor()
deps = SandboxDeps(profile_name="diagnostics", executor=executor)

# Use in MCP tool
result = await run_sandbox_command(
    deps,
    command=["df", "-h"],
    args=[]
)
print(result.stdout)
```

### With Pydantic-AI

```python
from pydantic_ai import Agent
from shannot.tools import SandboxDeps, run_sandbox_command

# Create agent with sandbox tools
agent = Agent(
    "openai:gpt-4",
    deps_type=SandboxDeps,
    system_prompt="You can execute read-only system commands."
)

# Register tool
@agent.tool
async def check_disk_usage(ctx) -> str:
    result = await run_sandbox_command(
        ctx.deps,
        command=["df", "-h"],
        args=[]
    )
    return result.stdout

# Run agent
deps = SandboxDeps(profile_name="diagnostics")
result = await agent.run("What's the disk usage?", deps=deps)
```

### Remote Execution

```python
from shannot.tools import SandboxDeps
from shannot.executors import SSHExecutor

# Configure SSH executor
executor = SSHExecutor(
    host="prod.example.com",
    username="readonly",
    key_filename="/path/to/key"
)

# Create deps with remote executor
deps = SandboxDeps(
    profile_name="diagnostics",
    executor=executor
)

# Commands now execute on remote host
result = await run_sandbox_command(deps, command=["uptime"], args=[])
```

### File Reading

```python
from shannot.tools import read_sandbox_file

# Read a configuration file
result = await read_sandbox_file(
    deps,
    filepath="/etc/os-release"
)
print(result.content)

# With line limits for large files
result = await read_sandbox_file(
    deps,
    filepath="/var/log/syslog",
    max_lines=100
)
```

### Custom Profiles

```python
from pathlib import Path

# Use custom profile path
deps = SandboxDeps(
    profile_path=Path("/etc/shannot/custom.json"),
    executor=executor
)

# Or specify profile name from standard locations
deps = SandboxDeps(
    profile_name="minimal",  # Loads ~/.config/shannot/minimal.json
    executor=executor
)
```

## Error Handling

The tools convert `SandboxError` exceptions to failed `ProcessResult` objects for compatibility with MCP and AI frameworks:

```python
result = await run_sandbox_command(deps, command=["forbidden"], args=[])

if result.returncode != 0:
    print(f"Command failed: {result.stderr}")
else:
    print(f"Success: {result.stdout}")
```

## Related Documentation

- [MCP Server Module](mcp_server.md) - MCP server implementation using these tools
- [Execution Module](execution.md) - Underlying execution interface
- [MCP Integration Guide](../mcp.md) - Setting up MCP servers with LLM clients
- [Python API Guide](../api.md) - General API usage patterns

## API Reference

::: shannot.tools
