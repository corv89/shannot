# Process Module

Process execution and result handling utilities for subprocess management.

## Overview

The process module provides low-level utilities for executing subprocesses and handling their results. It wraps Python's `subprocess` module with a more convenient API and structured result objects.

**Key Components:**

- **`ProcessResult`** - Structured result object containing exit code, stdout, stderr, and execution duration
- **`run_process()`** - Execute a subprocess and return a ProcessResult
- **`ensure_tool_available()`** - Verify an external tool is installed and accessible

## Common Usage Patterns

### Basic Process Execution

```python
from shannot.process import run_process

# Simple execution
result = run_process(["ls", "-la", "/tmp"])
print(result.stdout)

# Check exit status
if result.succeeded():
    print("Command succeeded")
else:
    print(f"Failed with exit code {result.returncode}")
```

### Error Handling

```python
# Automatic error checking
try:
    result = run_process(["false"], check=True)
except subprocess.CalledProcessError as e:
    print(f"Command failed: {e}")

# Manual error checking
result = run_process(["cat", "/missing"], check=False)
if not result.succeeded():
    print(f"Error: {result.stderr}")
    print(f"Exit code: {result.returncode}")
```

### Execution with Options

```python
from pathlib import Path

# Custom working directory
result = run_process(
    ["pwd"],
    cwd="/tmp"
)

# Custom environment
result = run_process(
    ["env"],
    env={"CUSTOM_VAR": "value", "PATH": "/usr/bin"}
)

# Timeout
result = run_process(
    ["sleep", "10"],
    timeout=5.0  # Raises TimeoutExpired after 5 seconds
)

# Print command before execution
result = run_process(
    ["ls", "/"],
    print_command=True  # Prints: + ls /
)
```

### Tool Availability Checking

```python
from shannot.process import ensure_tool_available
from pathlib import Path

# Check if a tool exists
try:
    bwrap_path = ensure_tool_available("bwrap", search_path=True)
    print(f"Found bwrap at: {bwrap_path}")
except FileNotFoundError as e:
    print(f"Tool not found: {e}")

# Check specific path
ensure_tool_available(Path("/usr/bin/bwrap"), search_path=False)
```

### Result Inspection

```python
result = run_process(["du", "-sh", "/var/log"])

# Access result properties
print(f"Command: {' '.join(result.command)}")
print(f"Exit code: {result.returncode}")
print(f"Duration: {result.duration:.3f} seconds")
print(f"Output length: {len(result.stdout)} bytes")

# Check success
if result.succeeded():
    for line in result.stdout.splitlines():
        print(line)
```

## Related Documentation

- [Sandbox Module](sandbox.md) - Uses process utilities for command execution
- [Execution Module](execution.md) - High-level execution interface
- [Python API Guide](../api.md) - Integration examples

## API Reference

::: shannot.process
