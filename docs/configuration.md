# Configuration Guide

This guide covers Shannot's configuration system for managing local and remote executors.

## Overview

Shannot uses a TOML configuration file to manage executors - the backends that run sandbox commands. You can define multiple executors (local, SSH remotes) and switch between them easily.

**Configuration file location**:
- Linux: `~/.config/shannot/config.toml`
- macOS: `~/Library/Application Support/shannot/config.toml`
- Windows: `%APPDATA%\Local\shannot\config.toml`

## Quick Start

### Add a Remote Server

```bash
# Add an SSH remote
shannot remote add prod \
  --host prod-server.example.com \
  --user admin \
  --key ~/.ssh/id_rsa

# List configured remotes
shannot remote list

# Test the connection
shannot remote test prod
```

### Use the Remote

```bash
# Run command on remote
shannot --target prod df -h

# Use with Claude Desktop
shannot mcp install --target prod
```

## Configuration File Format

### Basic Structure

```toml
# Default executor when not specified
default_executor = "local"

# Local execution (Linux only)
[executor.local]
type = "local"

# SSH remote
[executor.prod]
type = "ssh"
host = "prod-server.example.com"
username = "admin"
key_file = "~/.ssh/id_rsa"
port = 22
profile = "diagnostics"  # Optional: default profile
```

### Executor Types

#### Local Executor

Runs commands on the local Linux system using bubblewrap.

```toml
[executor.local]
type = "local"
bwrap_path = "/usr/bin/bwrap"  # Optional: explicit path
```

**Requirements**:
- Linux operating system
- bubblewrap installed (`apt install bubblewrap` or `dnf install bubblewrap`)

#### SSH Executor

Runs commands on a remote Linux system via SSH.

```toml
[executor.prod]
type = "ssh"
host = "prod-server.example.com"     # Required
username = "admin"                    # Optional (uses SSH config)
key_file = "~/.ssh/id_rsa"           # Optional (uses SSH agent)
port = 22                             # Optional (default: 22)
connection_pool_size = 5              # Optional (default: 5)
profile = "diagnostics"               # Optional (default profile)
```

**Requirements**:
- SSH access to remote system
- bubblewrap installed on remote
- SSH key-based authentication

## CLI Commands

### Managing Remotes

```bash
# Add a remote
shannot remote add NAME --host HOSTNAME [OPTIONS]

Options:
  --user, --username USERNAME    SSH username
  --key, --key-file PATH         SSH private key file
  --port PORT                    SSH port (default: 22)
  --profile PROFILE              Default profile for this remote

# List all configured executors
shannot remote list

# Test connection to a remote
shannot remote test NAME

# Remove a remote
shannot remote remove NAME
```

### Using Executors

```bash
# Run command with specific executor
shannot --target NAME COMMAND [ARGS...]

# Examples
shannot --target prod ls /
shannot --target staging df -h
shannot --target local cat /etc/os-release

# Without --target, uses default_executor from config
shannot df -h
```

### MCP Integration

```bash
# Install MCP with specific executor
shannot mcp install --target prod

# Claude Desktop will now execute on prod server
# Restart Claude Desktop after installation
```

## Configuration Examples

### Single Remote Server

```toml
default_executor = "prod"

[executor.prod]
type = "ssh"
host = "server.example.com"
username = "admin"
key_file = "~/.ssh/id_rsa"
```

### Multiple Environments

```toml
default_executor = "local"

[executor.local]
type = "local"

[executor.prod]
type = "ssh"
host = "prod.example.com"
username = "deploy"
key_file = "~/.ssh/prod_key"
profile = "minimal"

[executor.staging]
type = "ssh"
host = "staging.example.com"
username = "deploy"
key_file = "~/.ssh/staging_key"
profile = "diagnostics"

[executor.dev]
type = "ssh"
host = "dev.example.com"
username = "developer"
key_file = "~/.ssh/dev_key"
port = 2222
```

### Team Configuration

Share this file with your team:

```toml
default_executor = "local"

[executor.local]
type = "local"

# Production (read-only)
[executor.prod]
type = "ssh"
host = "prod.company.internal"
username = "readonly"
key_file = "~/.ssh/company_readonly"
profile = "minimal"

# Staging (diagnostics)
[executor.staging]
type = "ssh"
host = "staging.company.internal"
username = "deploy"
key_file = "~/.ssh/company_deploy"
profile = "diagnostics"
```

## SSH Setup

### Generate SSH Key

```bash
# Generate new SSH key
ssh-keygen -t ed25519 -f ~/.ssh/shannot_key -C "shannot@mycompany"

# Copy to remote server
ssh-copy-id -i ~/.ssh/shannot_key.pub user@remote-server
```

### Test SSH Connection

```bash
# Test SSH manually
ssh -i ~/.ssh/shannot_key user@remote-server

# Test with Shannot
shannot remote add myserver \
  --host remote-server \
  --user user \
  --key ~/.ssh/shannot_key

shannot remote test myserver
```

### SSH Config Integration

Shannot respects your `~/.ssh/config`:

```
# ~/.ssh/config
Host prod
    HostName prod.example.com
    User admin
    IdentityFile ~/.ssh/prod_key
    Port 22
```

Then in Shannot config:

```toml
[executor.prod]
type = "ssh"
host = "prod"  # Uses SSH config
```

## Troubleshooting

### "Executor 'NAME' not found"

Check your configuration:
```bash
shannot remote list
```

### "Connection failed" for SSH

1. Test SSH manually:
   ```bash
   ssh -i ~/.ssh/key user@host
   ```

2. Check SSH key permissions:
   ```bash
   chmod 600 ~/.ssh/key
   ```

3. Verify bubblewrap on remote:
   ```bash
   ssh user@host "which bwrap"
   ```

### "No module named 'asyncssh'"

Install remote dependencies:
```bash
pip install shannot[remote]
# or
pip install shannot[all]
```

### MCP not using remote executor

1. Check Claude Desktop config:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Roaming\Claude\claude_desktop_config.json`

2. Verify `args` includes `--target`:
   ```json
   {
     "mcpServers": {
       "shannot": {
         "command": "shannot-mcp",
         "args": ["--target", "prod"]
       }
     }
   }
   ```

3. Restart Claude Desktop completely.

## Advanced Topics

### Custom bwrap Path

If bubblewrap is in a non-standard location:

```toml
[executor.local]
type = "local"
bwrap_path = "/opt/custom/bin/bwrap"
```

### Connection Pooling

SSH executor maintains a pool of connections for performance:

```toml
[executor.prod]
type = "ssh"
host = "prod.example.com"
connection_pool_size = 10  # More connections = better concurrency
```

### Per-Executor Profiles

Set a default profile for each executor:

```toml
[executor.prod]
type = "ssh"
host = "prod.example.com"
profile = "minimal"  # Always use minimal profile

[executor.dev]
type = "ssh"
host = "dev.example.com"
profile = "diagnostics"  # Always use diagnostics
```

## Security Considerations

### SSH Keys

- **Use dedicated keys**: Don't reuse your personal SSH key
- **Set permissions**: `chmod 600 ~/.ssh/key`
- **Use passphrases**: Protect keys with strong passphrases
- **Rotate regularly**: Change keys periodically

### Least Privilege

- **Read-only access**: Use SSH users with minimal privileges
- **Minimal profiles**: Use `minimal.json` for production
- **Command restrictions**: Limit allowed commands in profiles

### Monitoring

- **Audit logs**: Monitor SSH access logs on remote systems
- **MCP logging**: Enable verbose logging for MCP server
- **Alert on failures**: Set up alerts for failed connections

## Next Steps

- See [MCP Guide](mcp.md) for Claude Desktop integration
- See [Profiles Guide](profiles.md) for profile configuration
- See [Deployment Guide](deployment.md) for production deployment scenarios

---

**Questions?** Open an issue on GitHub or check the troubleshooting section above.
