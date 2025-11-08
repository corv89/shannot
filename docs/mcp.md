# MCP Server Integration

This guide explains how to use Shannot's MCP (Model Context Protocol) server to give Claude Desktop,
Claude Code, or Codex CLI secure, read-only access to your Linux system.

## What is MCP?

MCP (Model Context Protocol) is Anthropic's standard protocol for connecting AI assistants to external tools. With Shannot's MCP server, Claude Desktop can:

- 📂 Read files and list directories
- 💾 Check disk usage
- 🧠 View memory info
- 🔍 Search for files and text
- 📊 Run diagnostic commands

**All operations are read-only and sandboxed** - Claude cannot modify your system.

## Quick Start

### For macOS/Windows Users (Remote Setup - 10 minutes)

Since Shannot requires Linux, you'll need a remote Linux server:

```bash
# 1. Install Shannot with remote support
pip install shannot[mcp,remote]

# 2. Configure a remote Linux target
shannot remote add myserver --host your-server.com --user yourname

# 3. Test the connection
shannot remote test myserver

# 4. Install MCP server for Claude Code
shannot mcp install --client claude-code --target myserver

# 5. Restart Claude Code
# Now you can ask: "Check disk space on myserver"
```

### For Linux Users (Local Setup - 5 minutes)

```bash
# 1. Install Shannot with MCP support
pip install shannot[mcp]

# 2. Install bubblewrap (if not already installed)
# Ubuntu/Debian:
sudo apt install bubblewrap
# Fedora/RHEL:
sudo dnf install bubblewrap
# Arch:
sudo pacman -S bubblewrap

# 3. Install MCP server for Claude Code
shannot mcp install --client claude-code

# 4. Restart Claude Code
# Now you can ask: "Show me /etc/os-release"
```

## Detailed Installation

### Option A: Using Shannot's installer (Recommended)

```bash
# Install for Claude Desktop (default)
shannot mcp install

# Install for Claude Code (user scope - available across all projects)
shannot mcp install --client claude-code

# Install for Codex CLI
shannot mcp install --client codex

# Use a configured remote target
shannot mcp install --target prod
shannot mcp install --client claude-code --target prod
```

The Claude Code installer uses **user scope** by default, making Shannot available across all your
projects. It updates both the IDE config and your CLI configuration (e.g., `~/.claude.json`) so
`/mcp` lists it immediately.

**Option B: Using Claude Code's CLI directly**

If you prefer Claude Code's native MCP management, you have full control over scoping:

```bash
# User scope (recommended - available across all your projects)
claude mcp add --transport stdio shannot --scope user -- shannot-mcp

# With a remote target
claude mcp add --transport stdio shannot-prod --scope user \
  --env SSH_AUTH_SOCK="${SSH_AUTH_SOCK}" -- shannot-mcp --target prod

# Local scope (only in current project, private to you)
claude mcp add --transport stdio shannot --scope local -- shannot-mcp

# Project scope (shared with team via .mcp.json in version control)
claude mcp add --transport stdio shannot --scope project -- shannot-mcp
```

**Understanding MCP scopes:**
- `local` (default): Only you can use it in this project
- `user`: Available to you across all projects
- `project`: Shared with your team via `.mcp.json` file (requires approval on first use)

**Note for macOS and Windows users:**

Shannot requires Linux to run locally (bubblewrap is Linux-only). You have two options:

**macOS:**
1. **Use a remote Linux target** (recommended):
   ```bash
   shannot remote add linux-server --host server.example.com --user yourname
   shannot mcp install --client claude-code --target linux-server
   ```
2. **Use a Linux VM** (Parallels, VMware, etc.) and run via SSH

**Windows:**
1. **Use a remote Linux target** (recommended):
   ```bash
   shannot remote add linux-server --host server.example.com --user yourname
   shannot mcp install --client claude-code --target linux-server
   ```
2. **Use WSL2** (Windows Subsystem for Linux) and install directly in WSL:
   ```bash
   # From WSL terminal
   pip install shannot[mcp]
   shannot mcp install --client claude-code
   ```

**Why remote is required for macOS/Windows:**
Shannot uses Linux kernel features (namespaces, seccomp) via bubblewrap for sandboxing.
These features are not available on macOS or native Windows.

### Verify installation (Claude Code users)

In Claude Code, check that Shannot is available:

```
> /mcp
```

You should see `shannot` listed among your MCP servers. You can also use `/mcp` to:
- View server status and available tools
- Manage server configurations
- Remove servers with `claude mcp remove shannot`

## Try it out

Open your client and ask:

> "Can you check how much disk space I have left?"

> "Show me the contents of /etc/os-release"

> "What are the largest directories in /var?"

Claude will use Shannot's sandboxed tools to answer!

## How It Works

```
You → Claude Desktop → MCP Protocol → Shannot Server → bubblewrap → Linux System
                                           ↓
                                    (read-only sandbox)
```

1. **You ask Claude a question** about your system
2. **Claude decides** which Shannot tool to use
3. **MCP server** receives the tool call
4. **Shannot runs** the command in a secure sandbox
5. **Claude responds** with the results

## Available Tools

Shannot exposes different tool sets based on **profiles**:

### Minimal Profile (Default)
- Local install: `sandbox_minimal` – run any command allowed by the profile (pass `{"command": ["ls", "/"]}`)
- Remote install (`--target prod`): tool name becomes `sandbox_prod_minimal` so Claude can distinguish hosts.

**Allowed commands**: ls, cat, grep, find

### Readonly Profile
Same base tool with a broader allowlist:
- head, tail, file, stat, wc, du

### Diagnostics Profile
Same tool with an extended allowlist:
- df, free, ps, uptime, hostname, uname, env, id

**Best for**: System monitoring and health checks

## Configuration

### Custom Profiles

You can create custom profiles in `~/.config/shannot/`:

```bash
# Create custom profile
cat > ~/.config/shannot/custom.json <<EOF
{
  "name": "custom",
  "allowed_commands": ["ls", "cat", "df"],
  "binds": [
    {"source": "/usr", "target": "/usr", "read_only": true},
    {"source": "/etc", "target": "/etc", "read_only": true}
  ],
  "tmpfs_paths": ["/tmp"],
  "environment": {
    "PATH": "/usr/bin:/bin",
    "HOME": "/home/sandbox"
  },
  "network_isolation": true
}
EOF

# Restart MCP server (or restart Claude Desktop)
```

The MCP server automatically discovers profiles in `~/.config/shannot/`.

### Remote Targets

To run Claude's commands on a remote Linux host:

1. **Add the remote target (once):**
   ```bash
   shannot remote add prod --host prod.example.com --user admin --profile diagnostics
   shannot remote test prod
   ```
2. **Install the MCP server for that target:**
   ```bash
   shannot mcp install --target prod
   ```
3. **Run the server manually (optional):**
   ```bash
   shannot-mcp --target prod --verbose
   ```

When you specify `--target`, the MCP server loads the matching executor from
`~/.config/shannot/config.toml` and reuses the associated profile (if set).
Claude's requests now execute on the remote host through the SSH executor.

> Tip: Run `ssh user@host` once outside of Claude to record the host key in your
> `known_hosts` file before installing the MCP server. This keeps connections secure.

### Manual Configuration

If `shannot mcp install` doesn't work on your platform, manually edit the client config. Defaults:

- **Claude Desktop (macOS)**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Claude Desktop (Windows)**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Claude Code (macOS)**: `~/Library/Application Support/Claude/claude_code_config.json`
  - Alternates: `~/Library/Application Support/Claude/claude_config.json`, `~/.claude/config.json`
- **Claude Code (Linux)**: `~/.config/Claude/claude_code_config.json`
  - Alternates: `~/.claude/config.json`, `~/.config/claude/config.json`
- **Claude Code (Windows)**: `%APPDATA%\Claude\claude_code_config.json`
  - Alternate: `%APPDATA%\Claude\claude_config.json`
- **Codex CLI (macOS)**: `~/Library/Application Support/OpenAI/Codex/codex_cli_config.json`
  - Alternate: `~/.config/openai/codex_cli_config.json`
- **Codex CLI (Linux)**: `~/.config/openai/codex_cli_config.json`
  - Alternate: `~/.config/codex/config.json`
- **Codex CLI (Windows)**: `%APPDATA%\OpenAI\Codex\codex_cli_config.json`

Add:

```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "env": {}
    }
  }
}
```

## Testing

### Test MCP server functionality

```bash
# Test that tools work
shannot mcp test
```

### Manual testing

Run the MCP server directly to see logs:

```bash
# Start server in verbose mode
shannot-mcp --verbose
```

The server will wait for MCP protocol messages on stdin.

## Troubleshooting

### "shannot-mcp command not found"

Make sure you installed with MCP support:

```bash
pip install shannot[mcp]
```

And that the install location is in your PATH.

### "Profile not found"

Check that profiles exist:

```bash
ls ~/.config/shannot/
ls $(python -c "import shannot; print(shannot.__file__.rsplit('/',1)[0])")/../profiles/
```

### Claude Desktop doesn't show Shannot tools

1. Restart Claude Desktop completely (quit, don't just close window)
2. Check config was written correctly:
   ```bash
   cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```
3. Look for errors in Claude Desktop logs (Help → View Logs)

### Claude Code doesn't show Shannot tools

1. Reload or restart Claude Code
2. Use `/mcp` command to check server status
3. Check that the server is properly configured:
   ```bash
   claude mcp list
   claude mcp get shannot
   ```
4. If you used `--scope project`, make sure you approved the `.mcp.json` file when prompted
5. Try removing and re-adding:
   ```bash
   claude mcp remove shannot
   shannot mcp install --client claude-code
   ```

### Commands fail with "not allowed"

The command you tried isn't in the profile's allowlist. Either:

1. Use a different profile with more commands (e.g., `diagnostics`)
2. Create a custom profile with the commands you need

### Permission denied errors

This is normal! The sandbox is read-only. You'll see errors when trying to:
- Write files
- Modify system state
- Access restricted paths

This is by design - Shannot prevents Claude from making changes.

## Security Notes

### What Shannot Protects Against

✅ **Accidental modifications** - Claude can't accidentally `rm -rf /`
✅ **Data persistence** - All changes to /tmp are lost after each command
✅ **Network access** - Commands can't phone home (network isolated)
✅ **Privilege escalation** - Runs in unprivileged namespace

### What Shannot Does NOT Protect Against

⚠️ **Information disclosure** - Claude can read any file the sandbox can see
⚠️ **Kernel exploits** - Not a security boundary against kernel bugs
⚠️ **Resource exhaustion** - No built-in CPU/memory limits

### Best Practices

1. **Review allowed commands** in profiles before using
2. **Use minimal profiles** when possible (principle of least privilege)
3. **Don't run as root** - use a regular user account
4. **Monitor usage** - check `~/.shannot/audit.log` (if enabled)
5. **Keep profiles simple** - only allow commands you actually need

## Advanced Usage

### Multiple Profiles

Claude can use multiple profiles simultaneously:

```bash
# Install with all bundled profiles
shannot mcp install
```

Claude will see tools like:
- `sandbox_minimal_read_file`
- `sandbox_readonly_read_file`
- `sandbox_diagnostics_check_disk`

Ask Claude: "Use the diagnostics profile to check disk space"

### Remote Systems

You can connect Shannot MCP to remote systems via SSH:

```json
{
  "mcpServers": {
    "shannot-remote": {
      "command": "ssh",
      "args": ["myserver.com", "shannot-mcp"],
      "env": {}
    }
  }
}
```

Now Claude can inspect remote systems!

### Team Collaboration (Claude Code)

Share Shannot MCP server with your team using project scope:

1. **Add server at project scope:**
   ```bash
   claude mcp add --transport stdio shannot --scope project -- shannot-mcp
   ```

2. **This creates `.mcp.json` in your project root:**
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

3. **Commit to version control:**
   ```bash
   git add .mcp.json
   git commit -m "Add Shannot MCP server for team"
   ```

4. **Team members will be prompted to approve** the server on first use. They can:
   - Review with `/mcp` command
   - Approve to enable the server
   - Reset choices with `claude mcp reset-project-choices` if needed

**For remote targets shared across the team:**

```bash
# Each team member configures the remote once
shannot remote add staging --host staging.example.com --user deploy

# Then add to project scope
claude mcp add --transport stdio shannot-staging --scope project \
  --env SSH_AUTH_SOCK="${SSH_AUTH_SOCK}" -- shannot-mcp --target staging
```

### Custom Tool Names

Edit the MCP server code in `shannot/mcp_server.py` to customize tool names and descriptions.

## Examples

### Disk Space Investigation

> **You**: My disk is filling up, can you help me figure out what's taking up space?

> **Claude**: I'll check your disk usage.
>
> *[Uses sandbox_diagnostics_check_disk]*
>
> Your /home partition is 87% full. Let me find the largest directories...
>
> *[Uses sandbox_diagnostics tool to run `du`]*
>
> The largest directories are:
> - /home/user/Downloads: 45GB
> - /home/user/.cache: 12GB
> - /home/user/VirtualBox: 8GB

### Log Analysis

> **You**: Are there any errors in my system logs from today?

> **Claude**: I'll search the logs.
>
> *[Uses sandbox_readonly tool to grep logs]*
>
> Found 3 errors in /var/log/syslog:
> - 10:23: "disk write error on /dev/sda"
> - 14:45: "network timeout to 192.168.1.1"
> - 16:20: "temperature warning: CPU over 80°C"

### Configuration Review

> **You**: Show me my SSH server configuration

> **Claude**: *[Uses sandbox_readonly_read_file on /etc/ssh/sshd_config]*
>
> Here's your SSH config. I notice:
> - Port: 22 (default)
> - PasswordAuthentication: yes (consider disabling)
> - PermitRootLogin: no (good!)

### Kernel Log Investigation

> **You**: Check the kernel logs for any hardware errors

> **Claude**: I'll analyze the kernel logs using journalctl.
>
> *[Uses check-kernel-logs prompt with sandbox_systemd tool]*
>
> *[Runs `journalctl -k -p err --since "24 hours ago"`]*
>
> Found 2 kernel errors in the last 24 hours:
> - 14:23: "ata1.00: exception Emask 0x0 SAct 0x0 SErr 0x0 action 0x6"
> - 16:45: "ACPI Warning: \_SB.PCI0.LPCB.EC0._QA2: Return Package has no elements"
>
> The ATA error suggests a possible disk issue. I recommend:
> 1. Check SMART status with `smartctl -a /dev/sda`
> 2. Monitor for additional disk errors
> 3. Ensure backups are current

> **You**: Show me all kernel messages from the current boot

> **Claude**: *[Uses sandbox_systemd tool to run `journalctl -k -b 0`]*
>
> Here are the kernel messages from this boot session. The system booted successfully with:
> - No critical errors
> - All hardware detected properly
> - 3 warnings about firmware loading (non-critical)
> - Network interfaces initialized correctly

## Quick Reference - Claude Code CLI Commands

```bash
# Installation
claude mcp add --transport stdio shannot -- shannot-mcp
claude mcp add --transport stdio shannot --scope user -- shannot-mcp
claude mcp add --transport stdio shannot --scope project -- shannot-mcp

# With remote target
claude mcp add --transport stdio shannot-prod -- shannot-mcp --target prod

# Management
claude mcp list                    # List all servers
claude mcp get shannot             # Get server details
claude mcp remove shannot          # Remove server
claude mcp reset-project-choices   # Reset approval choices

# In Claude Code
/mcp                               # View server status
```

**Alternative: Use Shannot's installer**
```bash
shannot mcp install --client claude-code
shannot mcp install --client claude-code --target prod
```

## Next Steps

- **[See profiles.md](profiles.md)** to learn about creating custom profiles
- **[See api.md](api.md)** to use Shannot programmatically

## Getting Help

- 🐛 **Bug reports**: [GitHub Issues](https://github.com/corv89/shannot/issues)
- 💬 **Questions**: [GitHub Discussions](https://github.com/corv89/shannot/discussions)
- 📖 **Docs**: [Documentation](https://github.com/corv89/shannot/tree/main/docs)
