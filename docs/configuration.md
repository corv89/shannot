# Configuration Guide

Shannot's configuration system lets you manage multiple execution targets - run sandboxed commands locally or on remote Linux servers via SSH.

## Overview

Shannot uses a TOML configuration file to manage **executors** - the backends that run sandbox commands. Define multiple executors (local Linux, SSH remotes) and switch between them seamlessly.

### Configuration File Location

Platform-specific locations (auto-detected):

- **Linux**: `~/.config/shannot/config.toml`
- **macOS**: `~/Library/Application Support/shannot/config.toml`
- **Windows**: `%APPDATA%\Local\shannot\config.toml`

No configuration file needed for basic local usage - Shannot works out-of-the-box on Linux.

## Quick Start

### Add a Remote Server

```bash
# Add an SSH remote with all options
shannot remote add prod \
  --host prod-server.example.com \
  --user admin \
  --key ~/.ssh/id_rsa \
  --port 22 \
  --profile diagnostics

# Simple remote (uses SSH config and defaults)
shannot remote add staging staging.internal

# List all configured remotes
shannot remote list

# Test the connection
shannot remote test prod
```

### Use the Remote

```bash
# Run commands on remote system
shannot --target prod df -h
shannot --target prod cat /etc/os-release
shannot -t staging ls /var/log

# Use different profile for specific command
shannot --target prod --profile minimal.json ls /

# Set as default target (via environment)
export SHANNOT_TARGET=prod
shannot df -h  # Runs on prod

# Use with Claude Desktop (MCP)
shannot mcp install --target prod
```

## Complete Examples

### Example 1: Simple Setup

```bash
# 1. Add remote server
shannot remote add webserver web1.company.com

# 2. Test connection
shannot remote test webserver

# 3. Run commands
shannot -t webserver df -h
shannot -t webserver free -h
shannot -t webserver uptime
```

### Example 2: Multiple Environments

```bash
# Add production server (restricted access)
shannot remote add prod \
  --host prod.example.com \
  --user readonly \
  --key ~/.ssh/prod_readonly_key \
  --profile minimal

# Add staging server (more access)
shannot remote add staging \
  --host staging.example.com \
  --user developer \
  --profile diagnostics

# Add dev VM (local)
shannot remote add dev \
  --host localhost \
  --user devuser \
  --port 2222

# List all remotes
shannot remote list

# Use them
shannot -t prod cat /etc/os-release      # Minimal commands only
shannot -t staging df -h                  # Full diagnostics
shannot -t dev ps aux                     # Dev environment
```

### Example 3: Team Configuration

Share this configuration with your team by committing `~/.config/shannot/config.toml`:

```toml
default_executor = "local"

[executor.local]
type = "local"

[executor.prod]
type = "ssh"
host = "prod.company.internal"
username = "monitoring"
key_file = "~/.ssh/company_monitoring_key"
profile = "minimal"

[executor.staging]
type = "ssh"
host = "staging.company.internal"
username = "monitoring"
key_file = "~/.ssh/company_monitoring_key"
profile = "diagnostics"

[executor.dev]
type = "ssh"
host = "dev.company.internal"
username = "developer"
key_file = "~/.ssh/company_dev_key"
profile = "diagnostics"
port = 2222
```

Team members can then:
```bash
# Everyone uses the same remote names
shannot -t prod df -h
shannot -t staging cat /var/log/app.log
shannot -t dev ps aux
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
known_hosts = "~/.ssh/known_hosts"    # Optional (defaults to SSH config)
strict_host_key = true                # Optional (default true; disable only for throwaway hosts)
```

**Requirements**:
- SSH access to remote system
- bubblewrap installed on remote
- SSH key-based authentication
 - Valid host key entry in `known_hosts` (unless `strict_host_key = false`)

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

## Host Key Verification

Shannot enforces strict SSH host-key validation by default (matching OpenSSH). Make sure each remote's host key is present in your `known_hosts` file before using it via Shannot or Claude. You can point at a specific file with `known_hosts = "~/.ssh/known_hosts"`.

If you set `strict_host_key = false`, host keys will not be checked—this is insecure and should only be used for disposable lab environments.

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

This error indicates you installed the minimal version of Shannot. Reinstall with full dependencies:
```bash
pip install --user shannot
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
