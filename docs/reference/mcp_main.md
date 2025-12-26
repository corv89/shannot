# MCP Main Module

Entry point and CLI for the Shannot MCP server (v0.5.0).

## Overview

The MCP main module provides the command-line interface for running the Shannot MCP server with PyPy sandbox integration. It handles argument parsing, profile loading, and server lifecycle management.

**Key Components:**

- **`main()`** - Main entry point for `shannot-mcp` command
- **Argument parsing** - Handle --profile and --verbose flags
- **Server initialization** - Create ShannotMCPServer with profiles
- **Protocol serving** - Start JSON-RPC 2.0 stdio transport

## Command-Line Interface

### Basic Usage

```bash
# Start MCP server with default profiles
shannot-mcp

# Enable verbose logging
shannot-mcp --verbose

# Load custom profile
shannot-mcp --profile ~/.config/shannot/custom.json

# Load multiple custom profiles
shannot-mcp --profile ~/profile1.json --profile ~/profile2.json
```

### Command-Line Options

```
Usage: shannot-mcp [OPTIONS]

Options:
  --profile PATH      Custom profile path (can be specified multiple times)
  --verbose           Enable verbose logging (DEBUG level)
  --help             Show help message and exit
```

## Entry Point

### Console Script

Defined in `pyproject.toml`:

```toml
[project.scripts]
shannot-mcp = "shannot.mcp_main:main"
```

### main() Function

```python
def main() -> int:
    """Main entry point for shannot-mcp command."""
    parser = argparse.ArgumentParser(
        prog="shannot-mcp",
        description="Shannot MCP server for LLM integration"
    )
    parser.add_argument(
        "--profile",
        action="append",
        type=Path,
        help="Custom profile path (can be specified multiple times)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Create server
    server = ShannotMCPServer(
        profile_paths=args.profile,
        verbose=args.verbose
    )

    # Serve via stdio
    serve(server.handle_request)

    return 0
```

## Usage Patterns

### Default Profiles

Without --profile, server uses built-in profiles:

```bash
shannot-mcp
```

Loads:
- `minimal` (ls, cat, grep, find)
- `readonly` (minimal + head, tail, file, stat, wc, du)
- `diagnostics` (readonly + df, free, ps, uptime, hostname, uname, env, id)

### Custom Profiles

Load custom profiles from filesystem:

```bash
# Single custom profile
shannot-mcp --profile ~/.config/shannot/custom.json

# Multiple profiles (stacked)
shannot-mcp --profile ~/minimal.json \
            --profile ~/diagnostics.json
```

**Profile Format** (`~/.config/shannot/custom.json`):
```json
{
  "auto_approve": [
    "echo",
    "printf",
    "date"
  ],
  "always_deny": [
    "eval",
    "exec"
  ]
}
```

### Verbose Logging

Enable DEBUG-level logging for troubleshooting:

```bash
shannot-mcp --verbose
```

Output includes:
- Profile loading details
- PyPy runtime detection
- Tool registration
- Request/response JSON-RPC messages

## Integration with LLM Clients

### Claude Desktop

```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

With verbose logging:
```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "args": ["--verbose"],
      "env": {}
    }
  }
}
```

With custom profile:
```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "args": ["--profile", "/path/to/custom.json"],
      "env": {}
    }
  }
}
```

### Claude Code

Via `shannot setup mcp install`:
```bash
shannot setup mcp install --client claude-code
```

Generates configuration for Claude Code's user or project scope.

## Server Lifecycle

### Startup Sequence

1. **Parse arguments** - Handle --profile and --verbose flags
2. **Load profiles** - From specified paths or use defaults
3. **Find runtime** - Locate PyPy sandbox binary
4. **Create server** - Initialize ShannotMCPServer
5. **Register tools** - sandbox_run, session_result
6. **Register resources** - profiles, status
7. **Start serving** - JSON-RPC 2.0 over stdio (blocks)

### Shutdown

- Server runs until EOF on stdin (client disconnect)
- Graceful shutdown on keyboard interrupt (Ctrl+C)
- Returns exit code 0 on success

## Logging

### Log Levels

**Default (INFO)**:
- Server initialization
- Profile loading summary
- Runtime detection status

**Verbose (DEBUG)**:
- Detailed profile loading
- Runtime path discovery
- Tool/resource registration
- JSON-RPC request/response

### Log Configuration

```python
if verbose:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)
```

Logs to stderr (stdout reserved for JSON-RPC protocol).

## Error Handling

### Runtime Not Found

```python
# Warning logged, server continues
logger.warning("PyPy runtime not found")
self.runtime = None

# Tools return error when called
{
  "status": "error",
  "error": "PyPy sandbox runtime not found. Run 'shannot setup runtime' to install."
}
```

### Profile Loading Failure

```python
# Warning logged, profile skipped
logger.warning(f"Failed to load profile {path}: {e}")

# Server continues with remaining profiles
```

### Invalid Arguments

```bash
$ shannot-mcp --invalid-flag
usage: shannot-mcp [-h] [--profile PROFILE] [--verbose]
shannot-mcp: error: unrecognized arguments: --invalid-flag
```

## Testing

### Manual Test

```bash
# Start server
shannot-mcp --verbose

# In another terminal, send JSON-RPC
echo '{"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1}' | shannot-mcp
```

### Integration Test

```python
from shannot.mcp_main import main
import sys

# Mock argv
sys.argv = ["shannot-mcp", "--verbose"]

# Run main
exit_code = main()
assert exit_code == 0
```

## Environment

### No Environment Variables

Server does not use environment variables (intentional simplicity).

### Working Directory

Server runs from current directory. Profile paths are resolved relative to CWD if not absolute.

## Security

### Stdio-Only Transport

- Server only accepts input from stdin
- Output only to stdout (protocol) and stderr (logs)
- No network sockets or file access

### Profile Isolation

- Profiles loaded at startup
- No dynamic profile loading during runtime
- Profiles are immutable once loaded

### Logging Safety

- Verbose mode logs to stderr (not protocol stdout)
- Sensitive data not logged (scripts may contain secrets)

## Related Documentation

- [MCP Server Module](mcp_server.md) - Server implementation details
- [MCP Integration Guide](../mcp.md) - Complete setup and usage
- [MCP Testing](../mcp-testing.md) - Testing procedures

## API Reference

### shannot.mcp_main

```python
def main() -> int:
    """Main entry point for shannot-mcp command.

    Returns
    -------
    int
        Exit code (0 for success).
    """
```

### Usage Example

```python
from shannot.mcp_main import main
import sys

if __name__ == "__main__":
    sys.exit(main())
```
