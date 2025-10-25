# MCP Main Module

Entry point and CLI for the MCP server application.

## Overview

The MCP main module provides the command-line interface and entry point for running the Shannot MCP server. It handles argument parsing, executor initialization, and server lifecycle management.

**Key Components:**

- **`entrypoint()`** - Main entry point for `shannot-mcp` command
- **`parse_args()`** - Command-line argument parser
- **Server initialization** - Sets up executor and server based on arguments
- **Logging configuration** - Configures logging for debugging

## Command-Line Interface

### Basic Usage

```bash
# Start MCP server with default settings
shannot-mcp

# Use specific profile
shannot-mcp --profile diagnostics

# Use multiple profiles
shannot-mcp --profile minimal --profile diagnostics

# Enable verbose logging
shannot-mcp --verbose

# Use remote executor target
shannot-mcp --target production
```

### Command-Line Options

```
Options:
  --profile PATH, -p     Profile to use (can be specified multiple times)
  --target NAME, -t      Remote executor target from config
  --verbose, -v          Enable verbose logging
  --help, -h            Show help message
```

## Usage Patterns

### Local Execution

```bash
# Run on local Linux system with diagnostics profile
shannot-mcp --profile diagnostics
```

The server will:
1. Create a LocalExecutor
2. Load the diagnostics profile
3. Start listening on stdio for MCP requests

### Remote Execution

```bash
# Execute on remote system configured as "production"
shannot-mcp --target production --profile diagnostics
```

The server will:
1. Load configuration from `~/.config/shannot/config.toml`
2. Create SSHExecutor for "production" target
3. Connect to remote system
4. Execute commands remotely in sandbox

### Multiple Profiles

```bash
# Serve multiple profiles
shannot-mcp --profile minimal --profile diagnostics --profile readonly
```

Each profile is available as a separate MCP resource and can be used by the LLM client.

### Debugging

```bash
# Enable verbose logging for troubleshooting
shannot-mcp --verbose --profile diagnostics 2> /tmp/shannot-mcp.log
```

Logs will show:
- Profile loading
- Executor initialization
- Tool invocations
- Command executions
- Errors and warnings

## Integration with LLM Clients

### Claude Desktop Integration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "args": ["--profile", "diagnostics"]
    }
  }
}
```

Or use the installer:
```bash
shannot mcp install claude-desktop --profile diagnostics
```

### Claude Code Integration

Add to Claude Code config:

```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "args": ["--profile", "diagnostics", "--verbose"]
    }
  }
}
```

Or use the installer:
```bash
shannot mcp install claude-code --profile diagnostics
```

### Remote System Monitoring

Monitor production systems from Claude:

```json
{
  "mcpServers": {
    "shannot-prod": {
      "command": "shannot-mcp",
      "args": ["--target", "production", "--profile", "diagnostics"]
    },
    "shannot-staging": {
      "command": "shannot-mcp",
      "args": ["--target", "staging", "--profile", "diagnostics"]
    }
  }
}
```

Now Claude can run diagnostics on both production and staging.

## Server Lifecycle

The MCP server runs until:
- The LLM client disconnects
- SIGINT (Ctrl+C) is received
- An unrecoverable error occurs

On shutdown:
- Executor connections are closed
- Resources are cleaned up
- Exit code 0 indicates clean shutdown

## Error Handling

Common errors and solutions:

**Profile not found:**
```
Error: Profile 'custom' not found
```
→ Ensure profile exists at `~/.config/shannot/custom.json` or specify full path

**Target not found:**
```
Error: Target 'production' not configured
```
→ Add target to `~/.config/shannot/config.toml`

**Bubblewrap not found:**
```
Error: Bubblewrap not found at /usr/bin/bwrap
```
→ Install bubblewrap: `apt install bubblewrap` (Linux only)

**SSH connection failed:**
```
Error: Failed to connect to host.example.com
```
→ Check SSH configuration, keys, and network connectivity

## Related Documentation

- [MCP Server Module](mcp_server.md) - Server implementation details
- [MCP Integration Guide](../mcp.md) - Complete MCP setup guide
- [Configuration](../configuration.md) - Configuring remote targets
- [Troubleshooting](../troubleshooting.md) - Common issues and solutions

## API Reference

::: shannot.mcp_main
