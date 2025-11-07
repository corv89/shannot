# Tools Module

Type-safe tools for sandboxed command execution in MCP servers and AI agents.

## Overview

The tools module provides type-safe, reusable tools that integrate Shannot's sandbox capabilities with Model Context Protocol (MCP) servers and AI agents. These tools handle command execution, file reading, and directory listing with proper error handling and validation.

**Key Components:**

- **`SandboxDeps`** - Dependency container for sandbox configuration and executors
- **`run_command`** - Execute commands in the sandbox
- **`read_file`** - Read file contents from sandboxed paths
- **`list_directory`** - List directory contents
- **`check_disk_usage`** - Get disk usage information
- **`check_memory`** - Get memory usage information
- **`search_files`** - Find files by pattern
- **`grep_content`** - Search for text in files

**Input/Output Models:**

- **`CommandInput`** - Input for command execution (dataclass)
- **`CommandOutput`** - Output from command execution (dataclass)
- **`FileReadInput`** - Input for file reading (dataclass)
- **`DirectoryListInput`** - Input for directory listing (dataclass)

## Common Usage Patterns

### With MCP Servers

```python
from shannot.tools import SandboxDeps, CommandInput, run_command
from shannot.executors import LocalExecutor

# Create dependencies
executor = LocalExecutor()
deps = SandboxDeps(profile_name="diagnostics", executor=executor)

# Use in MCP tool
cmd_input = CommandInput(command=["df", "-h"])
result = await run_command(deps, cmd_input)
print(result.stdout)
```

### With AI Agents

```python
from shannot.tools import SandboxDeps, CommandInput, run_command

# Create dependencies
deps = SandboxDeps(profile_name="diagnostics")

# Execute commands
cmd_input = CommandInput(command=["df", "-h"])
result = await run_command(deps, cmd_input)
print(f"Disk usage: {result.stdout}")

# The tools can be integrated with any AI framework that supports
# async functions and dependency injection
```

### Remote Execution

```python
from shannot.tools import SandboxDeps, CommandInput, run_command
from shannot.executors import SSHExecutor

# Configure SSH executor
executor = SSHExecutor(
    host="prod.example.com",
    username="readonly",
    key_file="/path/to/key"
)

# Create deps with remote executor
deps = SandboxDeps(
    profile_name="diagnostics",
    executor=executor
)

# Commands now execute on remote host
cmd_input = CommandInput(command=["uptime"])
result = await run_command(deps, cmd_input)
```

### File Operations

```python
from shannot.tools import FileReadInput, DirectoryListInput, read_file, list_directory

# Read a configuration file
file_input = FileReadInput(path="/etc/os-release")
content = await read_file(deps, file_input)
print(content)

# List directory contents
dir_input = DirectoryListInput(path="/var/log", long_format=True, show_hidden=False)
listing = await list_directory(deps, dir_input)
print(listing)
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

## Input Validation

Input models provide validation via `from_dict()` class methods for use with MCP and other frameworks:

```python
from shannot.tools import CommandInput
from shannot.validation import ValidationError

# Valid input
try:
    cmd = CommandInput.from_dict({"command": ["ls", "/"]})
except ValidationError as e:
    print(f"Invalid input: {e}")

# Invalid input (not a list)
try:
    cmd = CommandInput.from_dict({"command": "not a list"})
except ValidationError as e:
    print(f"Validation failed: {e}")  # Will raise
```

## Error Handling

The tools convert `SandboxError` exceptions to failed `ProcessResult` objects for compatibility with MCP and AI frameworks:

```python
from shannot.tools import CommandInput, run_command

cmd_input = CommandInput(command=["forbidden"])
result = await run_command(deps, cmd_input)

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
