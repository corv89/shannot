# Usage Guide

Comprehensive guide to using Shannot for sandboxed command execution.

## Command-Line Interface

### Basic Usage

```bash
# Run a command in the sandbox
shannot run COMMAND [ARGS...]

# Example: List root directory
shannot run ls /

# Example: Check system memory
shannot run cat /proc/meminfo
```

### Global Options

```bash
shannot [OPTIONS] COMMAND [ARGS...]

Options:
  --verbose, -v          Enable verbose logging
  --profile PATH, -p     Path to sandbox profile (default: auto-detect)
  --help, -h            Show help message
```

## Subcommands

### run - Execute Command in Sandbox

Run a command within the sandboxed environment.

```bash
shannot run [OPTIONS] -- COMMAND [ARGS...]

Options:
  --bubblewrap PATH      Path to bubblewrap executable
  --no-check            Don't fail on non-zero exit codes
  --no-stdout           Suppress stdout output
  --no-stderr           Suppress stderr output

Examples:
  # Basic command
  shannot run ls -la /etc

  # Using -- separator for commands with options
  shannot run -- df -h

  # Multiple commands (not in shell, run separately)
  shannot run ls / && shannot run cat /etc/os-release
```

### verify - Verify Sandbox Configuration

Test that the sandbox is working correctly.

```bash
shannot verify [OPTIONS]

Options:
  --bubblewrap PATH          Path to bubblewrap executable
  --allowed-command CMD...   Command that should succeed (default: ls /)
  --disallowed-command CMD   Command that should fail (default: touch /tmp/probe)

Examples:
  # Basic verification
  shannot verify

  # Test specific commands
  shannot verify --allowed-command cat /etc/os-release

  # Verbose verification
  shannot --verbose verify
```

### export - Export Profile Configuration

Display the current profile as JSON.

```bash
shannot export

# Redirect to file
shannot export > my-profile.json

# Use with custom profile
shannot --profile /etc/shannot/custom.json export
```

## Profile Selection

Shannot searches for profiles in this order:

1. `--profile` command-line argument
2. `$SANDBOX_PROFILE` environment variable
3. `~/.config/shannot/profile.json`
4. `/etc/shannot/profile.json`
5. `/etc/sandbox/readonly.json`
6. `/usr/etc/sandbox/readonly.json`

```bash
# Explicit profile
shannot --profile /path/to/profile.json run ls /

# Environment variable
export SANDBOX_PROFILE=/path/to/profile.json
shannot run ls /

# Use default profile
shannot run ls /
```

## Common Use Cases

### System Diagnostics

```bash
# Check disk usage
shannot run df -h

# View memory info
shannot run cat /proc/meminfo

# Check CPU info
shannot run cat /proc/cpuinfo

# List running processes (limited view due to PID namespace)
shannot run ps aux

# Check system load
shannot run uptime

# View network interfaces (read-only)
shannot run ip addr show
```

### File Inspection

```bash
# Read configuration files
shannot run cat /etc/os-release
shannot run cat /etc/fstab

# Search for patterns
shannot run grep -r "error" /var/log

# Find files
shannot run find /etc -name "*.conf"

# Check file permissions
shannot run ls -la /etc/passwd
```

### Log Analysis

```bash
# View recent logs
shannot run tail -n 100 /var/log/messages

# Search logs
shannot run grep "ERROR" /var/log/syslog

# Count log entries
shannot run wc -l /var/log/*.log
```


## Python API

For programmatic usage, see [API documentation](api.md).

### Custom Bubblewrap Path

```bash
# Use custom bwrap binary
shannot run --bubblewrap /opt/custom/bin/bwrap ls /

# Or set environment variable
export BWRAP=/opt/custom/bin/bwrap
shannot run ls /
```

### Debugging

```bash
# Enable verbose logging
shannot --verbose run ls /

# Export profile to verify configuration
shannot export | jq .

# Check which commands are allowed
shannot export | jq '.allowed_commands'
```

## Limitations

### What the Sandbox CAN Do

- Execute allowed commands
- Read files from mounted paths
- Write to tmpfs locations (/tmp, /run)
- View limited process information

### What the Sandbox CANNOT Do

- Modify the host filesystem
- Access the network (by default)
- See all host processes
- Execute disallowed commands
- Persist data between runs

### Common Gotchas

1. **Command paths**: Use full paths or ensure command is in allowed list
   ```bash
   # May fail if 'ls' isn't in allowed_commands
   shannot run ls /

   # Better: use full path
   shannot run /usr/bin/ls /
   ```

2. **Shell features**: The sandbox doesn't provide a shell
   ```bash
   # Won't work - no shell to interpret *
   shannot run ls /*.conf

   # Use find instead
   shannot run find / -maxdepth 1 -name "*.conf"
   ```

3. **Environment variables**: Only those in profile are available
   ```bash
   # May not have expected PATH
   shannot run env
   ```

## Next Steps

- Configure [profiles.md](profiles.md) for your use case
- See [deployment.md](deployment.md) for production deployment
- Review security considerations in the main README
