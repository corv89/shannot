# Deployment Guide

Production deployment guide for Shannot on local and remote systems.

## Quick Start

### Local Deployment

```bash
# Install shannot
uv tool install shannot

# Setup PyPy runtime
shannot setup runtime

# Verify installation
shannot status
```

### Remote Deployment

```bash
# Add a remote target
shannot setup remote add prod user@prod.example.com

# Test connection
shannot setup remote test prod

# Run script on remote (auto-deploys on first use)
shannot run script.py --target prod
```

## Auto-Deployment

When executing on a remote target for the first time, Shannot automatically:

1. **Deploys itself** - Uploads to `/tmp/shannot-v{version}/`
2. **Sets up runtime** - Configures PyPy sandbox environment
3. **Executes script** - Runs in sandboxed environment

No manual installation on remotes is required.

### Deployment Location

```
/tmp/shannot-v0.5.1/
├── shannot           # CLI executable
├── lib-python/       # Python stdlib
└── lib_pypy/         # PyPy modules
```

### Deployment Check

Deployment is fast - just runs `test -x /tmp/shannot-v{version}/shannot` over SSH. Only uploads if binary is missing.

## Multi-Server Setup

### Configure Multiple Remotes

```bash
# Production server
shannot setup remote add prod \
  --host prod.example.com \
  --user deploy

# Staging server
shannot setup remote add staging \
  --host staging.example.com \
  --user admin

# Development VM
shannot setup remote add dev \
  --host 192.168.1.100 \
  --user developer \
  --port 2222
```

### Remotes Configuration

Remote targets are stored in `~/.config/shannot/remotes.toml`:

```toml
[remotes.prod]
host = "prod.example.com"
user = "deploy"
port = 22

[remotes.staging]
host = "staging.example.com"
user = "admin"
port = 22

[remotes.dev]
host = "192.168.1.100"
user = "developer"
port = 2222
```

### Multi-Server Execution

```bash
# Run diagnostics on all servers
for server in prod staging dev; do
  echo "=== $server ==="
  shannot run diagnostics.py --target $server
done
```

## Claude Desktop Integration

### Install MCP Configuration

```bash
shannot setup mcp install
```

This configures Claude Desktop to use Shannot for sandboxed script execution.

### Configuration Location

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Roaming\Claude\claude_desktop_config.json`

### Manual Configuration

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

### With Verbose Logging

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

See [MCP Integration](mcp.md) for complete MCP documentation.

## CI/CD Integration

### GitHub Actions

```yaml
name: Run Diagnostics

on:
  workflow_dispatch:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  diagnostics:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install shannot
        run: |
          pip install shannot
          shannot setup

      - name: Run diagnostics
        run: |
          shannot run diagnostics.py --dry-run

      - name: Show pending operations
        run: |
          shannot approve list
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any

    stages {
        stage('Setup') {
            steps {
                sh 'pip install shannot'
                sh 'shannot setup runtime'
            }
        }

        stage('Run Diagnostics') {
            steps {
                sh 'shannot run diagnostics.py --dry-run'
                sh 'shannot approve list'
            }
        }
    }
}
```

## Security Best Practices

### SSH Key Management

```bash
# Generate dedicated key
ssh-keygen -t ed25519 -f ~/.ssh/shannot_key -C "shannot@$(hostname)"

# Copy to remote
ssh-copy-id -i ~/.ssh/shannot_key.pub user@remote

# Use with shannot (relies on SSH agent or config)
ssh-add ~/.ssh/shannot_key
```

### SSH Config

```
# ~/.ssh/config
Host prod
    HostName prod.example.com
    User deploy
    IdentityFile ~/.ssh/shannot_key
    Port 22

Host staging
    HostName staging.example.com
    User admin
    IdentityFile ~/.ssh/shannot_key
```

Then in remotes.toml, use the SSH config alias:

```toml
[remotes.prod]
host = "prod"
user = "deploy"
port = 22
```

### Least Privilege

Create dedicated service accounts on remotes:

```bash
# On remote server
sudo useradd -m -s /bin/bash shannot-agent
sudo passwd -l shannot-agent  # Disable password login

# Add SSH key
sudo -u shannot-agent mkdir -p /home/shannot-agent/.ssh
sudo -u shannot-agent chmod 700 /home/shannot-agent/.ssh
# Add public key to authorized_keys
```

### Approval Profiles

Use restrictive profiles for production:

```json
{
  "auto_approve": [
    "cat", "head", "tail",
    "ls", "find",
    "df", "free", "uptime"
  ],
  "always_deny": [
    "rm", "mv", "cp",
    "chmod", "chown",
    "systemctl start", "systemctl stop"
  ]
}
```

## Monitoring

### Session History

```bash
# View recent sessions
shannot approve history

# Output:
# + 20250115-disk-check-a3f2    executed    2h ago
# o 20250115-log-analysis-b4c5  pending     1h ago
# x 20250114-cleanup-c6d7       rejected    1d ago
```

### Status Icons

| Icon | Status |
|------|--------|
| `o` | Pending |
| `-` | Approved |
| `+` | Executed |
| `x` | Rejected |
| `!` | Failed |

### Audit Logging

Enable verbose logging for audit trails:

```bash
shannot run script.py --debug 2>&1 | tee audit.log
```

## Troubleshooting

### Remote Connection Failed

```bash
# Test SSH manually
ssh user@host

# Check SSH key
ssh -i ~/.ssh/key user@host

# Verify in known_hosts
ssh-keygen -R host && ssh user@host
```

### Deployment Failed

```bash
# Check remote access
ssh user@host "ls -la /tmp/"

# Manual deployment check
ssh user@host "test -x /tmp/shannot-v0.5.1/shannot && echo OK"
```

### Session Not Found

Sessions expire after 1 hour. Create a new session:

```bash
shannot run script.py
```

See [Troubleshooting](troubleshooting.md) for more solutions.

## Next Steps

- [MCP Integration](mcp.md) - Claude Desktop/Code setup
- [Profile Configuration](profiles.md) - Customize command approval
- [Troubleshooting](troubleshooting.md) - Common issues
