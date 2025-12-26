# Profile Configuration

Approval profiles control which subprocess commands execute automatically, which require manual approval, and which are always blocked.

## Profile Structure

Profile settings are defined in the `[profile]` section of `config.toml`:

```toml
[profile]
auto_approve = [
    "cat", "head", "tail", "less",
    "ls", "find", "stat", "file",
    "df", "du", "free", "uptime",
    "ps", "pgrep", "systemctl status",
    "uname", "hostname", "whoami", "id",
]
always_deny = [
    "rm -rf /",
    "dd if=/dev/zero",
    "mkfs",
    ":(){ :|:& };:",
    "> /dev/sda",
]
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `auto_approve` | `list[str]` | Commands that execute immediately without approval |
| `always_deny` | `list[str]` | Commands that are always blocked |

Commands not matching either list require manual approval through the TUI.

## Command Matching

### Base Name Extraction

Commands are matched by their **base name** (path stripped):

```python
subprocess.call(['/usr/bin/cat', '/etc/passwd'])  # Matches "cat"
subprocess.call(['cat', '/etc/passwd'])           # Matches "cat"
subprocess.call(['/bin/ls', '-la'])               # Matches "ls"
```

### Prefix Matching

The first word of the command string is matched:

```python
subprocess.call(['systemctl', 'status', 'nginx'])  # Matches "systemctl status"
subprocess.call(['git', 'status'])                 # Matches "git"
```

### Environment Variables

Leading environment variables are stripped:

```python
subprocess.call(['FOO=bar', 'cat', '/etc/passwd'])  # Matches "cat"
subprocess.call(['LC_ALL=C', 'ls', '-la'])          # Matches "ls"
```

## Profile Locations

Profiles are loaded in order of precedence:

1. **Project-local**: `.shannot/config.toml`
2. **Global**: `~/.config/shannot/config.toml`
3. **Built-in**: Default profile

### Project-Local Profile

Create a `.shannot/` directory in your project root:

```bash
mkdir -p .shannot

cat > .shannot/config.toml << 'EOF'
[profile]
auto_approve = ["npm", "yarn", "cat", "ls"]
always_deny = ["rm -rf"]
EOF
```

### Global Profile

Create in your config directory:

```bash
mkdir -p ~/.config/shannot

cat > ~/.config/shannot/config.toml << 'EOF'
[profile]
auto_approve = [
    "cat", "head", "tail", "grep",
    "ls", "find", "df", "free",
]
always_deny = [
    "rm -rf /",
    "dd if=/dev/zero",
]
EOF
```

## Default Profile

If no config file is found, Shannot uses a built-in default:

```toml
[profile]
auto_approve = [
    "cat", "head", "tail", "less",
    "ls", "find", "stat", "file",
    "df", "du", "free", "uptime",
    "ps", "top", "htop", "pgrep",
    "systemctl status", "journalctl",
    "uname", "hostname", "whoami", "id",
    "env", "printenv",
    "ip", "ss", "netstat",
    "date", "cal",
]
always_deny = [
    "rm -rf /",
    "dd if=/dev/zero",
    "mkfs",
    ":(){ :|:& };:",
    "> /dev/sda",
]
```

## Example Profiles

### Minimal (Read-Only)

For strict read-only access:

```toml
[profile]
auto_approve = [
    "cat", "head", "tail", "less",
    "ls", "find", "stat",
    "df", "free", "uptime",
]
always_deny = [
    "rm", "mv", "cp",
    "chmod", "chown",
    "dd", "mkfs",
    "systemctl start", "systemctl stop",
    "service start", "service stop",
]
```

### Diagnostics

For system diagnostics with broader access:

```toml
[profile]
auto_approve = [
    "cat", "head", "tail", "less", "grep", "awk", "sed",
    "ls", "find", "stat", "file", "wc",
    "df", "du", "free", "uptime", "vmstat", "iostat",
    "ps", "top", "htop", "pgrep", "pstree",
    "systemctl status", "journalctl",
    "ip", "ss", "netstat", "ping", "traceroute",
    "uname", "hostname", "hostnamectl",
    "lsblk", "fdisk -l", "mount",
]
always_deny = [
    "rm -rf /",
    "dd if=/dev/zero",
    "mkfs",
    ":(){ :|:& };:",
    "> /dev/sda",
    "shutdown", "reboot", "halt",
    "systemctl start", "systemctl stop", "systemctl restart",
]
```

### Development

For development environments:

```toml
[profile]
auto_approve = [
    "cat", "head", "tail", "grep",
    "ls", "find", "stat",
    "npm", "yarn", "pnpm",
    "pip", "pip3", "python", "python3",
    "git status", "git log", "git diff",
    "make", "cmake",
]
always_deny = [
    "rm -rf /",
    "rm -rf ~",
    "dd if=/dev/zero",
    "git push --force",
]
```

## Permission Check Order

When a subprocess command is executed:

1. **Check `always_deny`** - If matched, command is blocked (returns exit 127)
2. **Check session-approved** - If previously approved in session, execute
3. **Check `auto_approve`** - If matched, execute immediately
4. **Otherwise** - Queue for manual approval

```
Command: "df -h"
  ↓
Check always_deny → Not matched
  ↓
Check session-approved → Not matched
  ↓
Check auto_approve → Matched! ("df")
  ↓
Execute immediately
```

## Dry-Run Mode

In dry-run mode (`shannot run --dry-run`):

- Commands are captured but not executed
- All commands return exit code 0 (fake success)
- Operations are queued in a session for later approval

```bash
# Run in dry-run mode
shannot run script.py --dry-run

# Review captured operations
shannot approve

# Execute approved operations
# (press 'x' in TUI)
```

## Best Practices

### 1. Start Minimal

Begin with a small `auto_approve` list and expand as needed:

```toml
[profile]
auto_approve = ["cat", "ls", "df"]
always_deny = ["rm -rf /"]
```

### 2. Block Dangerous Commands

Always populate `always_deny` with known dangerous patterns:

```toml
[profile]
always_deny = [
    "rm -rf /",
    "rm -rf ~",
    "dd if=/dev/zero",
    "mkfs",
    ":(){ :|:& };:",
    "chmod -R 777 /",
    "chown -R",
    "shutdown",
    "reboot",
]
```

### 3. Use Project-Local Profiles

Different projects have different needs:

```
project-a/.shannot/config.toml  # Allows npm, yarn
project-b/.shannot/config.toml  # Allows pip, python
```

### 4. Review Before Approval

Always review session contents before executing:

```bash
shannot approve show SESSION_ID
```

### 5. Audit Regularly

Check session history to ensure profiles are appropriate:

```bash
shannot approve history
```

## Troubleshooting

### Command Not Auto-Approved

Check if the command matches exactly:

```bash
# Won't match "cat" if profile has "/usr/bin/cat"
# Use base names only: "cat", "ls", "grep"
```

### Command Blocked Unexpectedly

Check `always_deny` patterns. Prefix matching may catch unintended commands:

```toml
# This will block ALL rm commands, not just "rm -rf /"
[profile]
always_deny = ["rm"]

# Better: be specific
[profile]
always_deny = ["rm -rf /", "rm -rf ~"]
```

### Profile Not Loading

Verify file location and TOML syntax:

```bash
# Check which profile is being used
shannot status

# View config file
cat ~/.config/shannot/config.toml
```

## See Also

- [Usage Guide](usage.md) - Session workflow
- [Configuration Guide](configuration.md) - Full configuration options
- [Troubleshooting](troubleshooting.md) - Common issues
