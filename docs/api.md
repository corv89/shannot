# Python API

The Python API from v0.3.x has been removed.

## Current Status

Shannot v0.4.0+ is designed as a **CLI-first tool**. The internal Python modules are not intended for direct consumption.

**For users:** Use the CLI or MCP interface:

```bash
# CLI usage
shannot run script.py
shannot approve
shannot status
```

```json
// MCP usage (Claude Desktop/Code)
{"tool": "sandbox_run", "script": "...", "profile": "diagnostics"}
```

**For contributors:** See [CONTRIBUTING.md](https://github.com/corv89/shannot/blob/main/CONTRIBUTING.md) for architecture and contribution guidelines.

## Exported Symbols

The package exports these internal primitives (not for general use):

| Symbol | Purpose |
|--------|---------|
| `VirtualizedProc` | PyPy sandbox process controller |
| `signature` | Sandbox I/O signature |
| `sigerror` | Sandbox I/O error signature |

These are implementation details subject to change without notice.

## Migration

If you were using the v0.3.x Python API, see [Migrating from v0.3.x](migrating-from-v3.md).

## See Also

- [Usage Guide](usage.md) - CLI commands
- [MCP Integration](mcp.md) - MCP tools for LLM agents
- [Configuration](configuration.md) - Profiles and remotes
