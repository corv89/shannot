# Sandbox Module

Core sandbox implementation for read-only command execution using Linux namespaces and Bubblewrap.

## Overview

The sandbox module provides the foundational building blocks for creating secure, read-only execution environments. It offers declarative configuration through profiles and handles the low-level details of constructing Bubblewrap commands.

**Key Components:**

- **`SandboxProfile`** - Immutable sandbox configuration describing allowed commands, bind mounts, and environment
- **`SandboxManager`** - High-level interface for executing commands within a sandbox
- **`BubblewrapCommandBuilder`** - Translates profiles into Bubblewrap argument vectors
- **`SandboxBind`** - Declarative bind mount specification
- **`SandboxError`** - Exception raised for configuration or execution failures

## Quick Start

```python
from shannot import SandboxManager, load_profile_from_path
from pathlib import Path

# Load a profile
profile = load_profile_from_path("~/.config/shannot/minimal.json")

# Create a sandbox manager
manager = SandboxManager(profile, Path("/usr/bin/bwrap"))

# Execute a command
result = manager.run(["ls", "/"])
print(result.stdout)
```

## Common Usage Patterns

### Creating Profiles Programmatically

```python
from shannot import SandboxProfile, SandboxBind
from pathlib import Path

profile = SandboxProfile(
    name="custom",
    allowed_commands=["ls", "cat", "grep"],
    binds=[
        SandboxBind(
            source=Path("/usr"),
            target=Path("/usr"),
            read_only=True
        )
    ],
    tmpfs_paths=[Path("/tmp")],
    environment={"PATH": "/usr/bin"},
    network_isolation=True
)
```

### Loading from Files

```python
from shannot import load_profile_from_path, load_profile_from_mapping

# From JSON file
profile = load_profile_from_path("/etc/shannot/diagnostics.json")

# From dictionary
data = {
    "name": "minimal",
    "allowed_commands": ["ls"],
    "binds": [{"source": "/usr", "target": "/usr", "read_only": True}],
    "tmpfs_paths": ["/tmp"],
    "environment": {"PATH": "/usr/bin"}
}
profile = load_profile_from_mapping(data)
```

### Executing Commands

```python
# Basic execution
result = manager.run(["cat", "/etc/os-release"])

# With custom environment
result = manager.run(["env"], env={"CUSTOM_VAR": "value"})

# Without automatic error checking
result = manager.run(["test", "-f", "/missing"], check=False)
if result.succeeded():
    print("File exists")
```

## Related Documentation

- [Python API Guide](../api.md) - Comprehensive API usage examples
- [Profile Configuration](../profiles.md) - Profile format and options
- [CLI Usage](../usage.md) - Command-line interface
- [Process Module](process.md) - Process execution utilities

## API Reference

::: shannot.sandbox
