# Configuration Module

Configuration system for managing executor settings and remote targets.

## Overview

The config module provides TOML-based configuration management for Shannot executors. It allows you to define reusable executor configurations (local or SSH) with their associated profiles and connection settings.

**Key Components:**

- **`ShannotConfig`** - Main configuration container with executor targets
- **`ExecutorConfig`** - Base configuration for executors
- **`LocalExecutorConfig`** - Local executor configuration
- **`SSHExecutorConfig`** - SSH executor configuration with connection details
- **`load_config()`** - Load configuration from TOML file

## Configuration File Format

Shannot uses TOML for configuration files, typically located at `~/.config/shannot/config.toml`:

```toml
[executors.production]
type = "ssh"
host = "prod.example.com"
username = "readonly"
key_file = "~/.ssh/prod_key"
profile = "diagnostics"
port = 22

[executors.staging]
type = "ssh"
host = "staging.example.com"
username = "readonly"
key_file = "~/.ssh/staging_key"
profile = "minimal"

[executors.local]
type = "local"
profile = "diagnostics"
bwrap_path = "/usr/bin/bwrap"
```

## Common Usage Patterns

### Loading Configuration

```python
from shannot.config import load_config

# Load from default location (~/.config/shannot/config.toml)
config = load_config()

# Load from custom path
config = load_config(Path("/etc/shannot/config.toml"))
```

### Getting Executors

```python
# Get specific executor
executor = config.get_executor("production")

# Use with commands
result = await executor.run_command(profile, ["df", "-h"])
```

### Listing Available Targets

```python
# List all configured executor names
targets = config.list_executors()
print(f"Available targets: {', '.join(targets)}")
```

### CLI Integration

```bash
# Use configured target from CLI
shannot --target production df -h

# MCP install on remote target
shannot mcp install claude-code --target staging
```

## Configuration Options

### SSH Executor Options

```toml
[executors.myserver]
type = "ssh"
host = "server.example.com"          # Required: hostname or IP
username = "readonly"                 # Optional: SSH username (default: current user)
key_file = "~/.ssh/id_rsa"           # Optional: SSH private key path
port = 22                             # Optional: SSH port (default: 22)
profile = "diagnostics"               # Optional: default profile for this target
connection_pool_size = 5              # Optional: max concurrent connections
known_hosts = "~/.ssh/known_hosts"   # Optional: known_hosts file
strict_host_key = true                # Optional: strict host key checking
```

### Local Executor Options

```toml
[executors.local]
type = "local"
profile = "minimal"                   # Optional: default profile
bwrap_path = "/usr/bin/bwrap"        # Optional: explicit bwrap path
```

## Environment Variables

Configuration paths can be overridden with environment variables:

```bash
# Custom config location
export SHANNOT_CONFIG=~/my-shannot-config.toml
shannot --target prod df -h

# Custom profile
export SANDBOX_PROFILE=~/.config/shannot/diagnostics.json
shannot --target prod df -h
```

## Programmatic Configuration

You can also create configurations programmatically:

```python
from shannot.config import ShannotConfig, SSHExecutorConfig

# Create config
config = ShannotConfig(executors={
    "prod": SSHExecutorConfig(
        type="ssh",
        host="prod.example.com",
        username="readonly",
        key_file=Path("~/.ssh/prod_key"),
        profile="diagnostics"
    )
})

# Use executor
executor = config.get_executor("prod")
```

## Related Documentation

- [Configuration Guide](../configuration.md) - Detailed configuration examples
- [Execution Module](execution.md) - Executor implementations
- [CLI Usage](../usage.md) - Using configured targets from command line
- [Deployment Guide](../deployment.md) - Production configuration patterns

## API Reference

::: shannot.config
