# CLI Module

Command-line interface for interacting with Shannot sandboxes.

## Overview

The CLI module provides the command-line entry point for Shannot, enabling users to execute commands in read-only sandboxes directly from the terminal. It handles argument parsing, profile selection, and command execution.

**Key Features:**

- Direct command execution in sandboxes
- Profile auto-discovery and selection
- Sandbox verification and diagnostics
- Profile configuration export
- MCP server installation for LLM integration
- Remote execution configuration

## Command Structure

```bash
shannot [OPTIONS] COMMAND [ARGS...]
shannot verify                    # Verify sandbox setup
shannot export                    # Export active profile
shannot mcp install [CLIENT]      # Install MCP server
shannot remote add NAME HOST      # Add remote target
```

## Common Usage Patterns

### Basic Command Execution

```bash
# Run a simple command
shannot ls /

# Read a file
shannot cat /etc/os-release

# Check disk usage
shannot df -h

# Use custom profile
shannot --profile ~/.config/shannot/diagnostics.json df -h
```

### Verification and Diagnostics

```bash
# Verify sandbox is working
shannot verify

# Export current profile to see configuration
shannot export

# Save profile to file
shannot export > my-config.json

# Verbose output for debugging
shannot --verbose verify
```

### MCP Server Installation

```bash
# Install for Claude Desktop
shannot mcp install claude-desktop

# Install for Claude Code
shannot mcp install claude-code

# Specify custom profile
shannot mcp install claude-code --profile diagnostics

# Install on remote system
shannot mcp install claude-code --target production
```

### Remote Execution

```bash
# Add a remote server
shannot remote add prod server.example.com

# Execute on remote
shannot --target prod df -h

# Configure with SSH options
shannot remote add staging \
  --host staging.example.com \
  --user readonly \
  --key ~/.ssh/staging_key
```

## Profile Selection

Shannot searches for profiles in this order:

1. `--profile` command-line argument
2. `$SANDBOX_PROFILE` environment variable
3. `~/.config/shannot/minimal.json` (preferred user config)
4. `~/.config/shannot/profile.json` (legacy user config)
5. Bundled `profiles/minimal.json`
6. `/etc/shannot/minimal.json` (system-wide)
7. `/etc/shannot/profile.json` (legacy system)

## Related Documentation

- [Usage Guide](../usage.md) - Comprehensive CLI examples and workflows
- [Configuration](../configuration.md) - Remote target and profile configuration
- [MCP Integration](../mcp.md) - Model Context Protocol server setup
- [Deployment](../deployment.md) - Production deployment strategies

## API Reference

::: shannot.cli
