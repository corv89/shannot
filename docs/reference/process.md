# Process Module

Internal process management for PyPy sandbox execution.

## Overview

The process module handles low-level PyPy sandbox process lifecycle.

## Key Components

| Component | Purpose |
|-----------|---------|
| `VirtualizedProc` | PyPy sandbox process controller |
| `sandboxio.py` | Sandbox I/O protocol handling |
| `structs.py` | Data structures (Capture, Pending) |

## Internal Use Only

Process management is handled internally. Use the CLI for execution:

```bash
shannot run script.py
shannot approve
shannot status
```

## See Also

- [Sandbox Module](sandbox.md) - Sandbox architecture
- [Usage Guide](../usage.md) - CLI commands
