# Sandbox Module

Core PyPy sandbox implementation for secure script execution.

## Overview

The sandbox module provides the foundation for Shannot's security model through PyPy's syscall interception.

**Key Components:**

- **`VirtualizedProc`** - Core PyPy sandbox process controller
- **Mixin Classes** - Modular functionality for VFS, subprocess, sockets, etc.

## Architecture

Shannot v0.4.0+ uses PyPy sandbox mode instead of Linux namespaces:

| Component | Purpose |
|-----------|---------|
| `virtualizedproc.py` | PyPy sandbox process controller |
| `mix_vfs.py` | Virtual filesystem |
| `mix_subprocess.py` | Subprocess virtualization with approval |
| `mix_socket.py` | Socket virtualization (disabled) |
| `mix_pypy.py` | PyPy initialization |

## Usage

The sandbox is accessed through the CLI or MCP interface:

```bash
# Run script in sandbox
shannot run script.py

# Review pending operations
shannot approve
```

For MCP usage, see [MCP Integration](../mcp.md).

## Internal API

The internal Python API exports these symbols for contributors:

```python
from shannot import VirtualizedProc, signature, sigerror
```

These are implementation details. Use the CLI for production workloads.

## See Also

- [Usage Guide](../usage.md) - CLI commands
- [Configuration](../configuration.md) - Profiles and settings
- [MCP Server](mcp_server.md) - MCP implementation
