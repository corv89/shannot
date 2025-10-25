# Execution Module

Executor abstraction for running sandboxed commands locally or remotely.

## Overview

The execution module provides an abstract base class and concrete implementations for executing sandboxed commands. Executors allow Shannot to work across different platforms and execution environments while maintaining a consistent interface.

**Key Components:**

- **`SandboxExecutor`** - Abstract base class for all execution strategies
- **`LocalExecutor`** - Execute commands locally using Bubblewrap (Linux only)
- **`SSHExecutor`** - Execute commands on remote Linux systems via SSH

## Executor Architecture

Executors separate the "how" of command execution from the "what". This allows:

- **Cross-platform support**: Use SSH executor on macOS/Windows to execute on remote Linux
- **Remote diagnostics**: Check production systems from development machines
- **Unified interface**: Same code works locally and remotely
- **Pluggable backends**: Easy to add new execution strategies

## Common Usage Patterns

### Local Execution

```python
from shannot.executors import LocalExecutor
from shannot import load_profile_from_path

# Create local executor (Linux only)
executor = LocalExecutor()

# Load profile
profile = load_profile_from_path("~/.config/shannot/diagnostics.json")

# Execute command
result = await executor.run_command(profile, ["df", "-h"])
print(result.stdout)
```

### Remote Execution via SSH

```python
from shannot.executors import SSHExecutor

# Create SSH executor
executor = SSHExecutor(
    host="prod.example.com",
    username="readonly",
    key_filename="/path/to/ssh/key"
)

# Execute on remote system
result = await executor.run_command(profile, ["uptime"])
print(result.stdout)

# Clean up connection when done
await executor.cleanup()
```

### Reading Files

```python
# Read file using executor
content = await executor.read_file(profile, "/etc/os-release")
print(content)

# Works with both local and remote executors
```

### With Context Manager

```python
async with SSHExecutor(host="server.example.com") as executor:
    result = await executor.run_command(profile, ["ls", "/"])
    print(result.stdout)
# Connection automatically cleaned up
```

### Timeout Handling

```python
try:
    result = await executor.run_command(
        profile,
        ["sleep", "60"],
        timeout=5  # seconds
    )
except TimeoutError:
    print("Command timed out")
```

## Integration with Tools

Executors integrate seamlessly with the tools module:

```python
from shannot.tools import SandboxDeps
from shannot.executors import SSHExecutor

# Create executor
executor = SSHExecutor(host="prod.example.com")

# Use with tools
deps = SandboxDeps(
    profile_name="diagnostics",
    executor=executor
)

# Tools automatically use the executor
result = await run_sandbox_command(deps, command=["df", "-h"], args=[])
```

## Platform Compatibility

| Platform | LocalExecutor | SSHExecutor |
|----------|---------------|-------------|
| Linux    | ✅ Yes        | ✅ Yes      |
| macOS    | ❌ No         | ✅ Yes      |
| Windows  | ❌ No         | ✅ Yes      |

**Note:** LocalExecutor requires Bubblewrap, which is Linux-only. Use SSHExecutor on non-Linux platforms to execute commands on remote Linux systems.

## Related Documentation

- [SSH Executor Reference](executors/ssh.md) - SSH executor implementation details
- [Local Executor Reference](executors/local.md) - Local executor implementation details
- [Tools Module](tools.md) - High-level tools that use executors
- [Configuration Guide](../configuration.md) - Remote target configuration

## API Reference

::: shannot.execution
