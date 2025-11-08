# Usage Guide

Complete guide to using Shannot for safe, read-only command execution.

## Quick Start

```bash
# Run a command in the sandbox
shannot ls /

# Check version
shannot --version

# Verify sandbox is working
shannot verify

# Export current profile configuration
shannot export

# Use custom profile
shannot --profile /path/to/profile.json cat /etc/os-release

# Get help
shannot --help
```

## Command-Line Interface

### Basic Syntax

```bash
shannot [OPTIONS] COMMAND [ARGS...]
```

### Global Options

```bash
Options:
  --version              Show version and exit
  --verbose, -v          Enable verbose logging
  --profile PATH, -p     Path to sandbox profile (default: auto-detect)
  --target NAME, -t      Target executor for remote execution
  --help, -h            Show help message
```

### Examples

```bash
# List root directory
shannot ls /

# Check system memory
shannot cat /proc/meminfo

# Search for files
shannot find /etc -name "*.conf"

# Use custom profile
shannot --profile ~/.config/shannot/diagnostics.json df -h

# Run on remote system
shannot --target production df -h
```

## Commands

### Direct Command Execution

Execute commands directly in the sandbox (recommended):

```bash
# Simple commands
shannot ls /
shannot cat /etc/os-release
shannot df -h

# Commands with arguments
shannot grep -r "error" /var/log
shannot find /etc -name "*.conf"

# Note: No shell interpolation - each invocation is isolated
```

### verify - Verify Sandbox

Test that the sandbox is configured correctly and working:

```bash
shannot verify

# Verbose output
shannot --verbose verify

# With custom profile
shannot --profile /etc/shannot/custom.json verify
```

This command checks:
- Bubblewrap is installed and accessible
- Profile is valid and can be loaded
- Basic commands execute successfully
- Write protection is enforced
- Sandbox isolation is working

### export - Export Profile

Display the active profile configuration as JSON:

```bash
# Show current profile
shannot export

# Save to file
shannot export > my-profile.json

# Export specific profile
shannot --profile /etc/shannot/custom.json export

# Pretty-print with jq
shannot export | jq .
```

## Profile Selection

Shannot searches for profiles in this order:

1. `--profile` command-line argument (must be full path with `.json`)
2. `$SANDBOX_PROFILE` environment variable (must be full path with `.json`)
3. `~/.config/shannot/minimal.json` (preferred default)
4. `~/.config/shannot/profile.json` (legacy user config)
5. `profiles/minimal.json` (bundled with shannot)
6. `/etc/shannot/minimal.json` (system-wide)
7. `/etc/shannot/profile.json` (legacy system config)

**Note:** Profile names must include the `.json` extension and can be absolute or relative paths.

```bash
# Explicit profile (full path)
shannot --profile /etc/shannot/diagnostics.json ls /

# Relative path (from current directory)
shannot --profile ./custom-profile.json ls /

# User config directory
shannot --profile ~/.config/shannot/minimal.json ls /

# Environment variable
export SANDBOX_PROFILE=~/.config/shannot/minimal.json
shannot ls /

# Use default (auto-discovered from search order above)
shannot ls /
```

## Remote Execution

Shannot can execute commands on remote Linux systems via SSH.

### Setup Remote Target

```bash
# Add a remote server
shannot remote add myserver server.example.com

# Add with authentication details
shannot remote add prod \
  --host prod.example.com \
  --user readonly \
  --key ~/.ssh/prod_key \
  --profile minimal

# List configured remotes
shannot remote list

# Test connection
shannot remote test myserver
```

### Run Commands on Remote

```bash
# Basic usage
shannot --target myserver df -h
shannot -t myserver cat /etc/os-release

# Use short form
shannot -t prod ls /var/log

# Combine with custom profile
shannot -t prod --profile diagnostics.json df -h

# Multiple commands on same remote
shannot -t myserver df -h
shannot -t myserver free -h
shannot -t myserver uptime
```

### Common Remote Scenarios

```bash
# Check disk space on all servers
for server in prod staging dev; do
  echo "=== $server ==="
  shannot -t $server df -h
done

# Compare configurations across environments
shannot -t prod cat /etc/app/config.yaml > prod.yaml
shannot -t staging cat /etc/app/config.yaml > staging.yaml
diff prod.yaml staging.yaml

# Monitor logs on remote server
shannot -t prod tail -n 100 /var/log/app/error.log

# Check system health
shannot -t prod df -h
shannot -t prod free -h
shannot -t prod uptime
```

### Remove Remote Target

```bash
# Remove a remote
shannot remote remove myserver

# Or use alias
shannot remote rm myserver
```

## Common Use Cases

### System Diagnostics

```bash
# Check disk usage
shannot df -h

# View memory info
shannot cat /proc/meminfo

# Check CPU info
shannot cat /proc/cpuinfo

# List running processes (limited view due to PID namespace)
shannot ps aux

# Check system load
shannot uptime

# View network interfaces (read-only)
shannot ip addr show
```

### File Inspection

```bash
# Read configuration files
shannot cat /etc/os-release
shannot cat /etc/fstab

# Search for patterns
shannot grep -r "error" /var/log

# Find files
shannot find /etc -name "*.conf"

# Check file permissions
shannot ls -la /etc/passwd
```

### Log Analysis

```bash
# View recent logs
shannot tail -n 100 /var/log/messages

# Search logs
shannot grep "ERROR" /var/log/syslog

# Count log entries
shannot wc -l /var/log/*.log
```

### Kernel Log Analysis

The systemd profile includes journalctl for accessing kernel logs:

```bash
# View kernel logs (equivalent to dmesg)
shannot --profile systemd journalctl -k

# Alternative syntax (--dmesg is equivalent to -k)
shannot --profile systemd journalctl --dmesg

# Last hour of kernel messages
shannot --profile systemd journalctl -k --since "1 hour ago"

# Kernel errors only
shannot --profile systemd journalctl -k -p err

# Current boot kernel logs
shannot --profile systemd journalctl -k -b 0

# Previous boot kernel logs
shannot --profile systemd journalctl -k -b -1

# Search for hardware errors
shannot --profile systemd journalctl -k | grep -i "error\|fail"

# Check for disk issues
shannot --profile systemd journalctl -k | grep -i "ata\|scsi\|disk"

# Memory-related kernel messages
shannot --profile systemd journalctl -k | grep -i "oom\|memory"

# Network hardware issues
shannot --profile systemd journalctl -k | grep -i "eth\|wlan"

# Combined filters: recent boot errors
shannot --profile systemd journalctl -k -b 0 -p err
```

**Why journalctl instead of dmesg?**

- `dmesg` requires `CAP_SYSLOG` capability (restricted in sandbox)
- `journalctl -k` reads from journal files (accessible with proper permissions)
- `journalctl --dmesg` is equivalent to `journalctl -k`
- Both access the same kernel ring buffer data
- journalctl provides better filtering and time-based queries

**Setup for Full Access:**

For complete access to kernel logs, add your user to the `systemd-journal` group:

```bash
sudo usermod -aG systemd-journal $USER
# Log out and back in for changes to take effect
```

### Service Discovery Without D-Bus

The systemd profile uses **filesystem-based service discovery** for enhanced security. Traditional `systemctl` commands require D-Bus access, which has been removed from the profile because D-Bus provides two-way IPC that could be used to modify system state.

Instead, you can discover and monitor services using read-only filesystem methods:

#### List Running Services

```bash
# List all running services via cgroup filesystem
shannot --profile systemd ls -1 /sys/fs/cgroup/system.slice/ | grep '\.service$'

# Use systemd-cgls for hierarchical view
shannot --profile systemd systemd-cgls /sys/fs/cgroup/system.slice

# Cross-reference with services that have logged
shannot --profile systemd journalctl -F _SYSTEMD_UNIT | grep '\.service$'
```

#### Check Service Resource Usage

```bash
# Check if a service is running
shannot --profile systemd test -d /sys/fs/cgroup/system.slice/nginx.service && echo "Running" || echo "Not Running"

# Get service PIDs
shannot --profile systemd cat /sys/fs/cgroup/system.slice/nginx.service/cgroup.procs

# Check memory usage (in bytes)
shannot --profile systemd cat /sys/fs/cgroup/system.slice/nginx.service/memory.current

# Check CPU statistics
shannot --profile systemd cat /sys/fs/cgroup/system.slice/nginx.service/cpu.stat

# Monitor all services with resource usage
shannot --profile systemd systemd-cgtop --depth=3 -n 1
```

#### Find Failed Services

```bash
# Search for services with errors today
shannot --profile systemd journalctl -p err --since today | grep '\.service'

# Find failed service starts
shannot --profile systemd journalctl --since "1 hour ago" | grep -i "failed to start"

# Check for service crashes
shannot --profile systemd journalctl --since today | grep -i "core dump"
```

#### Analyze Service Logs

```bash
# View recent logs for a service
shannot --profile systemd journalctl -u nginx -n 50

# Check for errors in last hour
shannot --profile systemd journalctl -u nginx -p err --since "1 hour ago"

# Count service restarts
shannot --profile systemd journalctl -u nginx --since today | grep -c "Started"

# View service logs from previous boot
shannot --profile systemd journalctl -u nginx -b -1
```

#### Capabilities Comparison

| Feature | systemctl (D-Bus) | Filesystem Method |
|---------|-------------------|-------------------|
| List running services | ✅ `systemctl list-units` | ⚠️ Parse `/sys/fs/cgroup/system.slice/` |
| Service state (active/failed) | ✅ `systemctl status` | ❌ Must infer from logs |
| Resource usage | ⚠️ Limited | ✅ Full cgroup stats |
| Service logs | ✅ `journalctl -u` | ✅ `journalctl -u` |
| Start/stop service | ❌ (read-only) | ❌ (read-only) |

**Why No D-Bus Access?**

- **Security**: D-Bus socket enables two-way communication (less secure than read-only)
- **Read-only guarantee**: Filesystem methods are truly read-only
- **Sufficient data**: cgroup v2 exposes all necessary monitoring information  
- **Better for automation**: File-based access is more scriptable

**What You Can Still Do:**

- ✅ List running services (via `/sys/fs/cgroup/`)
- ✅ Monitor resource usage (via cgroup files and `systemd-cgtop`)
- ✅ Analyze logs (via `journalctl`)
- ✅ Find failures (via journal queries)
- ❌ Query service state (active/inactive) - must infer from cgroups + logs
- ❌ View service dependencies - parse unit files if needed


## Python API

For programmatic usage, see [API documentation](api.md).

### Custom Bubblewrap Path

```bash
# Use custom bwrap binary
shannot run --bubblewrap /opt/custom/bin/bwrap ls /

# Or set environment variable
export BWRAP=/opt/custom/bin/bwrap
shannot ls /
```

### Debugging

```bash
# Enable verbose logging
shannot --verbose ls /

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
   shannot ls /

   # Better: use full path
   shannot /usr/bin/ls /
   ```

2. **Shell features**: The sandbox doesn't provide a shell
   ```bash
   # Won't work - no shell to interpret *
   shannot ls /*.conf

   # Use find instead
   shannot find / -maxdepth 1 -name "*.conf"
   ```

3. **Environment variables**: Only those in profile are available
   ```bash
   # May not have expected PATH
   shannot env
   ```

## Next Steps

- Configure [profiles.md](profiles.md) for your use case
- See [deployment.md](deployment.md) for production deployment
- Review security considerations in the main README
