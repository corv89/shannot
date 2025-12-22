# Python API Reference

> **⚠️ NOTICE: This documents the v0.3.0 bubblewrap-based Python API**
>
> The API described in this document (`SandboxManager`, `SandboxProfile`, `ProcessResult`, `load_profile_from_path`) was available in Shannot v0.3.0 and has been removed in v0.4.0.
>
> **v0.4.0 Python API is limited**: Only low-level PyPy sandbox primitives are exported:
> - `VirtualizedProc` - Core PyPy sandbox process controller
> - `signature` - Sandbox I/O signature
> - `sigerror` - Sandbox I/O error signature
>
> These are intended for internal use. The high-level API will be redesigned for PyPy sandbox in a future version.
>
> For current v0.4.0 usage, use the CLI: `shannot run`, `shannot approve`, etc. See [README.md](../README.md).

---

# Python API Reference (v0.3.0 - Historical)

This guide covers using Shannot programmatically from Python code.

## Quick Start

```python
from shannot import SandboxManager, load_profile_from_path
from pathlib import Path

# Load profile
profile = load_profile_from_path("~/.config/shannot/profile.json")

# Create manager
manager = SandboxManager(profile, Path("/usr/bin/bwrap"))

# Run command
result = manager.run(["ls", "/"])
print(result.stdout)
```

## Core Components

### SandboxManager

The main interface for executing commands in the sandbox.

```python
from shannot import SandboxManager
from pathlib import Path

manager = SandboxManager(profile, Path("/usr/bin/bwrap"))
```

**Methods:**

- `run(command, *, check=True, env=None)` - Execute a command
  - `command`: List of command and arguments
  - `check`: Raise `SandboxError` on non-zero exit (default: True)
  - `env`: Optional environment variable overrides
  - Returns: `ProcessResult`

- `build_command(command)` - Build the full bwrap command
  - Returns: List of strings representing the complete command

**Properties:**

- `profile` - The active `SandboxProfile`
- `bubblewrap_path` - Path to the bwrap executable

### ProcessResult

Result object returned by `manager.run()`.

**Attributes:**

- `command` - Tuple of the executed command
- `returncode` - Exit code of the process
- `stdout` - Standard output as string
- `stderr` - Standard error as string
- `duration` - Execution time in seconds (float)

**Methods:**

- `succeeded()` - Returns True if returncode == 0

### SandboxProfile

Declarative sandbox configuration.

```python
from shannot import SandboxProfile, SandboxBind
from pathlib import Path

profile = SandboxProfile(
    name="my-sandbox",
    allowed_commands=["ls", "cat"],
    binds=[
        SandboxBind(
            source=Path("/usr"),
            target=Path("/usr"),
            read_only=True,
        )
    ],
    tmpfs_paths=[Path("/tmp")],
    environment={"PATH": "/usr/bin"},
    network_isolation=True,
    additional_args=["--hostname", "sandbox"],
)
```

**Parameters:**

- `name` - Profile identifier (required)
- `allowed_commands` - Commands that can be executed (default: all)
- `binds` - List of `SandboxBind` objects
- `tmpfs_paths` - Directories to mount as tmpfs
- `environment` - Environment variables
- `seccomp_profile` - Optional path to seccomp BPF file
- `network_isolation` - Enable network isolation (default: True)
- `additional_args` - Extra bwrap arguments

**Methods:**

- `validate()` - Raise `SandboxError` if configuration is invalid
- `from_mapping(data, *, base_path=None)` - Create from dict

### SandboxBind

Describes a bind mount.

```python
from shannot import SandboxBind
from pathlib import Path

bind = SandboxBind(
    source=Path("/usr"),
    target=Path("/usr"),
    read_only=True,
    create_target=False,
)
```

**Parameters:**

- `source` - Path on the host
- `target` - Path inside the sandbox
- `read_only` - Mount as read-only (default: True)
- `create_target` - Create target directory (default: True)

**Methods:**

- `validate()` - Ensure paths are absolute

### BubblewrapCommandBuilder

Low-level command builder.

```python
from shannot import BubblewrapCommandBuilder

builder = BubblewrapCommandBuilder(profile, ["ls", "/"])
args = builder.build()  # Returns list of bwrap arguments
```

## Loading Profiles

### From File

```python
from shannot import load_profile_from_path

# Absolute path
profile = load_profile_from_path("/etc/shannot/profile.json")

# Relative path (expanded from current directory)
profile = load_profile_from_path("./custom.json")

# User home directory
profile = load_profile_from_path("~/.config/shannot/profile.json")
```

### From Dictionary

```python
from shannot import load_profile_from_mapping

data = {
    "name": "minimal",
    "allowed_commands": ["ls", "cat"],
    "binds": [
        {
            "source": "/usr",
            "target": "/usr",
            "read_only": True
        }
    ],
    "tmpfs_paths": ["/tmp"],
    "environment": {"PATH": "/usr/bin"},
    "network_isolation": True
}

profile = load_profile_from_mapping(data)
```

### With Base Path

Relative paths in the profile are resolved relative to `base_path`:

```python
from pathlib import Path

profile = load_profile_from_mapping(
    data,
    base_path=Path("/etc/shannot")
)
```

## Creating Profiles Programmatically

### Minimal Example

```python
from shannot import SandboxProfile, SandboxBind
from pathlib import Path

profile = SandboxProfile(
    name="minimal",
    binds=[
        SandboxBind(
            source=Path("/usr"),
            target=Path("/usr"),
            read_only=True,
        )
    ],
    tmpfs_paths=[Path("/tmp")],
    environment={"PATH": "/usr/bin"},
)
```

### Full Example

```python
profile = SandboxProfile(
    name="diagnostics",
    allowed_commands=[
        "ls", "/usr/bin/ls",
        "cat", "/usr/bin/cat",
        "df", "/usr/bin/df",
        "free", "/usr/bin/free",
    ],
    binds=[
        SandboxBind(
            source=Path("/usr"),
            target=Path("/usr"),
            read_only=True,
            create_target=False,
        ),
        SandboxBind(
            source=Path("/etc"),
            target=Path("/etc"),
            read_only=True,
            create_target=False,
        ),
        SandboxBind(
            source=Path("/var/log"),
            target=Path("/var/log"),
            read_only=True,
            create_target=True,
        ),
    ],
    tmpfs_paths=[
        Path("/tmp"),
        Path("/run"),
        Path("/home/diagnostics"),
    ],
    environment={
        "HOME": "/home/diagnostics",
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
    },
    network_isolation=True,
    additional_args=[
        "--hostname", "diagnostics",
        "--chdir", "/home/diagnostics",
    ],
)

# Validate before use
profile.validate()
```

## Running Commands

### Basic Execution

```python
manager = SandboxManager(profile, Path("/usr/bin/bwrap"))

result = manager.run(["ls", "/"])
print(result.stdout)
```

### With Error Checking

```python
# Raises SandboxError on non-zero exit
try:
    result = manager.run(["cat", "/nonexistent"], check=True)
except SandboxError as e:
    print(f"Command failed: {e}")

# Manual error checking
result = manager.run(["cat", "/nonexistent"], check=False)
if not result.succeeded():
    print(f"Exit code: {result.returncode}")
    print(f"Error: {result.stderr}")
```

### Custom Environment

```python
custom_env = {
    "CUSTOM_VAR": "value",
    "DEBUG": "1",
}

result = manager.run(["env"], env=custom_env)
print(result.stdout)
```

### Checking Results

```python
result = manager.run(["test", "-f", "/etc/passwd"], check=False)

if result.succeeded():
    print("File exists")
else:
    print("File does not exist")

print(f"Execution took {result.duration:.3f} seconds")
```

## Error Handling

### SandboxError

Raised for sandbox configuration or execution errors.

```python
from shannot import SandboxError, SandboxManager, load_profile_from_path
from pathlib import Path

try:
    # Profile loading error
    profile = load_profile_from_path("missing.json")

    # Configuration error
    manager = SandboxManager(profile, Path("/missing/bwrap"))

    # Execution error
    result = manager.run(["forbidden_command"], check=True)

except SandboxError as e:
    print(f"Sandbox error: {e}")
except FileNotFoundError as e:
    print(f"File not found: {e}")
```

### Common Errors

**Profile not found:**
```python
# FileNotFoundError or SandboxError
profile = load_profile_from_path("nonexistent.json")
```

**Invalid profile:**
```python
# SandboxError: validation failed
profile = SandboxProfile(name="")  # Empty name
profile.validate()
```

**Bubblewrap not found:**
```python
# SandboxError: Bubblewrap executable not found
manager = SandboxManager(profile, Path("/wrong/path"))
```

**Command not allowed:**
```python
# SandboxError: Command not permitted
result = manager.run(["rm", "-rf", "/"], check=True)
```

**Command execution failed:**
```python
# SandboxError (if check=True)
result = manager.run(["ls", "/nonexistent"], check=True)
```

## Advanced Usage

### Building Commands

Get the full bwrap command without executing:

```python
from shannot import BubblewrapCommandBuilder

builder = BubblewrapCommandBuilder(profile, ["ls", "/"])
args = builder.build()

# Print the full command
print("bwrap", " ".join(args))

# Or execute with custom logic
import subprocess
subprocess.run(["bwrap"] + args)
```

### Reusing Managers

```python
# Create once, reuse for multiple commands
manager = SandboxManager(profile, Path("/usr/bin/bwrap"))

commands = [
    ["ls", "/"],
    ["cat", "/etc/os-release"],
    ["df", "-h"],
]

for cmd in commands:
    result = manager.run(cmd, check=False)
    print(f"{' '.join(cmd)}: {result.returncode}")
```

### Profile Introspection

```python
# Access profile properties
print(f"Profile: {manager.profile.name}")
print(f"Network isolated: {manager.profile.network_isolation}")
print(f"Allowed commands: {manager.profile.allowed_commands}")

# Check if command is allowed
cmd = "ls"
allowed = any(
    fnmatch.fnmatch(cmd, pattern)
    for pattern in manager.profile.allowed_commands
)
```

### Dynamic Profile Modification

```python
from dataclasses import replace

# Create a modified copy
new_profile = replace(
    profile,
    name="modified",
    network_isolation=False,
)

manager = SandboxManager(new_profile, Path("/usr/bin/bwrap"))
```

## Integration Examples

### Monitoring Script

```python
#!/usr/bin/env python3
from shannot import SandboxManager, load_profile_from_path
from pathlib import Path
import json

profile = load_profile_from_path("/etc/shannot/diagnostics.json")
manager = SandboxManager(profile, Path("/usr/bin/bwrap"))

metrics = {}

# Disk usage
result = manager.run(["df", "-h"])
if result.succeeded():
    metrics["disk"] = result.stdout

# Memory
result = manager.run(["free", "-h"])
if result.succeeded():
    metrics["memory"] = result.stdout

print(json.dumps(metrics, indent=2))
```

### Validation Service

```python
from shannot import SandboxManager, SandboxError, load_profile_from_path
from pathlib import Path

def validate_config(config_path):
    """Safely validate a config file."""
    profile = load_profile_from_path("~/.config/shannot/readonly.json")
    manager = SandboxManager(profile, Path("/usr/bin/bwrap"))

    try:
        result = manager.run(["cat", config_path], check=True)
        # Perform validation on result.stdout
        return True, result.stdout
    except SandboxError as e:
        return False, str(e)
```

## See Also

- [usage.md](usage.md) - CLI usage
- [profiles.md](profiles.md) - Profile configuration reference
- [seccomp.md](seccomp.md) - Adding seccomp filters
