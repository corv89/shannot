# Configuration Guide

Shannot's configuration system for approval profiles, remote targets, and MCP integration.

## Overview

Shannot uses a **zero-dependency** philosophy - pure Python stdlib only. Configuration is straightforward:

- **Approval Profiles** - JSON files controlling command approval behavior
- **Remote Targets** - TOML file for SSH host configuration
- **MCP Setup** - Configuration for Claude Desktop and Claude Code

## Approval Profiles

Profiles control which subprocess commands execute automatically vs. require approval.

### Profile Structure

```json
{
  "auto_approve": [
    "cat", "head", "tail", "less",
    "ls", "find", "stat", "file",
    "df", "du", "free", "uptime",
    "ps", "pgrep", "uname", "hostname"
  ],
  "always_deny": [
    "rm -rf /",
    "dd if=/dev/zero",
    "mkfs",
    ":(){ :|:& };:",
    "> /dev/sda"
  ]
}
```

### Profile Locations

Profiles are loaded in order of precedence:

1. **Project-local**: `.shannot/profile.json`
2. **Global**: `~/.config/shannot/profile.json`
3. **Built-in**: Default profile (if no files found)

### Creating a Profile

```bash
# Create global config directory
mkdir -p ~/.config/shannot

# Create profile
cat > ~/.config/shannot/profile.json << 'EOF'
{
  "auto_approve": [
    "cat", "ls", "find", "grep", "head", "tail",
    "df", "du", "free", "uptime", "ps"
  ],
  "always_deny": [
    "rm -rf /",
    "dd if=/dev/zero"
  ]
}
EOF
```

### Project-Local Profiles

For project-specific settings, create a `.shannot/` directory:

```bash
mkdir -p .shannot

cat > .shannot/profile.json << 'EOF'
{
  "auto_approve": [
    "npm", "yarn", "pnpm",
    "cat", "ls", "grep"
  ],
  "always_deny": []
}
EOF
```

See [Profile Configuration](profiles.md) for detailed profile options.

## Remote Targets

Remote targets are SSH hosts where sandboxed scripts can execute.

### Configuration File

Remote targets are stored in `~/.config/shannot/remotes.toml`:

```toml
# SSH remote targets for shannot

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

### Managing Remotes via CLI

```bash
# Add a remote
shannot setup remote add prod --host prod.example.com --user deploy

# Shorthand format
shannot setup remote add staging admin@staging.example.com

# With custom port
shannot setup remote add dev --host 192.168.1.100 --user developer --port 2222

# List configured remotes
shannot setup remote list

# Test connection
shannot setup remote test prod

# Remove a remote
shannot setup remote remove staging
```

### Using Remote Targets

```bash
# Execute on remote
shannot run script.py --target prod

# With MCP (Claude Desktop/Code)
# The `target` parameter in sandbox_run tool
```

### Auto-Deployment

When targeting a remote for the first time:

1. Shannot deploys itself to `/tmp/shannot-v{version}/`
2. No manual installation required on the remote
3. Deployment is cached (fast `test -x` check on subsequent runs)

## MCP Configuration

### Claude Desktop

Install MCP configuration for Claude Desktop:

```bash
shannot setup mcp install
# or
shannot setup mcp install --client claude-desktop
```

This adds to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

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

### Claude Code

Install for Claude Code:

```bash
shannot setup mcp install --client claude-code
```

Generates `.mcp.json` or updates user config.

### Manual Configuration

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

### MCP with Remote Target

To execute on a specific remote by default:

```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "args": ["--profile", "diagnostics"],
      "env": {}
    }
  }
}
```

Then use the `target` parameter in `sandbox_run` tool calls.

See [MCP Integration](mcp.md) for complete MCP documentation.

## Directory Structure

Shannot follows XDG Base Directory specification:

```
~/.config/shannot/
├── profile.json          # Global approval profile
└── remotes.toml          # SSH remote targets

~/.local/share/shannot/
├── runtime/              # PyPy sandbox runtime
│   ├── lib-python/       # Python stdlib
│   └── lib_pypy/         # PyPy-specific modules
└── sessions/             # Session data
    └── 20250115-abc123/  # Individual session
        └── session.json

.shannot/                 # Project-local (optional)
└── profile.json          # Project-specific profile
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `XDG_CONFIG_HOME` | Config directory (default: `~/.config`) |
| `XDG_DATA_HOME` | Data directory (default: `~/.local/share`) |
| `SHANNOT_RELEASE_PATH` | Custom release tarball path for deployment |

## Best Practices

### Profiles

1. **Start minimal** - Add commands to `auto_approve` as needed
2. **Use project-local profiles** - Different projects have different needs
3. **Block dangerous commands** - Always populate `always_deny`

### Remote Targets

1. **Use SSH keys** - Password authentication is not supported
2. **Use SSH agent** - Avoid storing unencrypted keys
3. **Limit permissions** - Use dedicated service accounts on remotes

### Security

1. **Review sessions** - Don't blindly approve all operations
2. **Use read-only access** - Sandboxed code can only read by default
3. **Monitor execution** - Check session history regularly

## Next Steps

- [Profile Configuration](profiles.md) - Detailed profile options
- [MCP Integration](mcp.md) - Claude Desktop/Code setup
- [Deployment Guide](deployment.md) - Production deployment
- [Troubleshooting](troubleshooting.md) - Common issues
