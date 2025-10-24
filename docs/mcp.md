# MCP Server Integration

This guide explains how to use Shannot's MCP (Model Context Protocol) server to give Claude Desktop secure, read-only access to your Linux system.

## What is MCP?

MCP (Model Context Protocol) is Anthropic's standard protocol for connecting AI assistants to external tools. With Shannot's MCP server, Claude Desktop can:

- 📂 Read files and list directories
- 💾 Check disk usage
- 🧠 View memory info
- 🔍 Search for files and text
- 📊 Run diagnostic commands

**All operations are read-only and sandboxed** - Claude cannot modify your system.

## Quick Start (5 minutes)

### 1. Install Shannot with MCP support

```bash
# Install with MCP dependencies (includes remote SSH support)
pip install shannot[mcp]

# Or install from source
cd shannot
pip install -e ".[mcp]"
```

### 2. Install MCP server config for Claude Desktop

```bash
shannot mcp install

# Use a configured remote target
shannot mcp install --target prod
```

This automatically adds Shannot to your Claude Desktop configuration.

### 3. Restart Claude Desktop

Quit and reopen Claude Desktop. You should now see Shannot tools available!

### 4. Try it out

Open Claude Desktop and ask:

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

If `shannot mcp install` doesn't work on your platform, manually edit your Claude Desktop config:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

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

## Next Steps

- **[See profiles.md](profiles.md)** to learn about creating custom profiles
- **[See api.md](api.md)** to use Shannot programmatically

## Getting Help

- 🐛 **Bug reports**: [GitHub Issues](https://github.com/corv89/shannot/issues)
- 💬 **Questions**: [GitHub Discussions](https://github.com/corv89/shannot/discussions)
- 📖 **Docs**: [Documentation](https://github.com/corv89/shannot/tree/main/docs)
