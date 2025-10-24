# Profile Configuration Reference

Shannot uses JSON profiles to define sandbox behavior. This document describes all available configuration options.

## Profile Structure

```json
{
  "name": "profile-name",
  "allowed_commands": [...],
  "binds": [...],
  "tmpfs_paths": [...],
  "environment": {...},
  "seccomp_profile": "path/to/profile.bpf",
  "network_isolation": true,
  "additional_args": [...]
}
```

## Configuration Fields

### name (required)

**Type**: `string`

Human-readable identifier for the profile. Used in logging and error messages.

```json
{
  "name": "readonly-diagnostics"
}
```

### allowed_commands (optional)

**Type**: `array` of `string`
**Default**: `[]` (all commands allowed)

List of commands that can be executed in the sandbox. Supports:
- Exact command names: `"ls"`
- Full paths: `"/usr/bin/ls"`
- Shell globs: `"/usr/bin/*"`, `"*.sh"`

If empty, all commands are allowed. For security, always specify an allowlist.

```json
{
  "allowed_commands": [
    "ls",
    "/usr/bin/ls",
    "cat",
    "/usr/bin/cat",
    "/usr/bin/grep",
    "/usr/bin/find",
    "/usr/bin/*stat"
  ]
}
```

**Best Practice**: Include both bare names and full paths for common commands.

### binds (optional)

**Type**: `array` of objects
**Default**: `[]`

Filesystem bind mounts to expose inside the sandbox.

Each bind has these fields:

- `source` (required): Host path to mount
- `target` (required): Path inside sandbox
- `read_only` (optional): Whether mount is read-only (default: `true`)
- `create_target` (optional): Whether to create target dir/file (default: `true`)

```json
{
  "binds": [
    {
      "source": "/usr",
      "target": "/usr",
      "read_only": true,
      "create_target": false
    },
    {
      "source": "/etc",
      "target": "/etc",
      "read_only": true,
      "create_target": false
    },
    {
      "source": "/var/log",
      "target": "/var/log",
      "read_only": true,
      "create_target": true
    }
  ]
}
```

**Notes**:
- Paths must be absolute
- Source must exist on host
- Read-only is strongly recommended for security
- System paths like `/usr`, `/lib`, `/bin` typically need `create_target: false`

### tmpfs_paths (optional)

**Type**: `array` of `string`
**Default**: `[]`

Directories that should be backed by tmpfs (ephemeral RAM-based filesystem). All changes are lost when the sandbox exits.

```json
{
  "tmpfs_paths": [
    "/tmp",
    "/var/tmp",
    "/run",
    "/home/agent"
  ]
}
```

**Common paths**:
- `/tmp` - Temporary files
- `/run` - Runtime data
- `/var/tmp` - Temporary files that survive reboot (on host)
- `/home/*` - User directories

### environment (optional)

**Type**: `object` (string keys and values)
**Default**: `{}`

Environment variables to set inside the sandbox.

```json
{
  "environment": {
    "HOME": "/home/agent",
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "TERM": "xterm"
  }
}
```

**Important**: Only these variables will be available. Host environment is not inherited.

### seccomp_profile (optional)

**Type**: `string` (path)
**Default**: `null` (no seccomp filtering)

Path to a compiled seccomp BPF profile. Provides syscall-level filtering for additional security.

**Note:** Seccomp is **completely optional**. Shannot works perfectly without it. Most users don't need seccomp filtering.

```json
{
  "seccomp_profile": "/etc/shannot/readonly.bpf"
}
```

**Relative paths** are resolved relative to the profile file's directory.

**Creating seccomp profiles**: See [seccomp.md](seccomp.md) for a complete guide on compiling BPF filters from OCI JSON.

### network_isolation (optional)

**Type**: `boolean`
**Default**: `true`

Whether to isolate the sandbox from network access.

```json
{
  "network_isolation": true
}
```

When `true`, commands cannot access the network. Set to `false` only if network access is required for your use case.

### additional_args (optional)

**Type**: `array` of `string`
**Default**: `[]`

Extra arguments to pass directly to bubblewrap. Use for advanced configuration not covered by other fields.

```json
{
  "additional_args": [
    "--hostname", "sandbox",
    "--chdir", "/home/agent",
    "--dir", "/var/cache",
    "--die-with-parent"
  ]
}
```

**Common arguments**:
- `--hostname NAME` - Set sandbox hostname
- `--chdir PATH` - Set working directory
- `--dir PATH` - Create directory inside sandbox
- `--ro-bind-try SOURCE TARGET` - Bind mount that doesn't fail if source missing
- `--dev-bind PATH PATH` - Bind with device access

See `bwrap --help` for all options.

## Complete Example Profiles

### Read-Only System Diagnostics

```json
{
  "name": "readonly-diagnostics",
  "allowed_commands": [
    "ls", "/usr/bin/ls",
    "cat", "/usr/bin/cat",
    "head", "/usr/bin/head",
    "tail", "/usr/bin/tail",
    "grep", "/usr/bin/grep",
    "find", "/usr/bin/find",
    "df", "/usr/bin/df",
    "free", "/usr/bin/free",
    "uptime", "/usr/bin/uptime",
    "stat", "/usr/bin/stat"
  ],
  "binds": [
    {"source": "/usr", "target": "/usr", "read_only": true, "create_target": false},
    {"source": "/bin", "target": "/bin", "read_only": true, "create_target": false},
    {"source": "/lib", "target": "/lib", "read_only": true, "create_target": false},
    {"source": "/lib64", "target": "/lib64", "read_only": true, "create_target": false},
    {"source": "/etc", "target": "/etc", "read_only": true, "create_target": false},
    {"source": "/var/log", "target": "/var/log", "read_only": true, "create_target": true},
    {"source": "/proc", "target": "/proc", "read_only": false, "create_target": false}
  ],
  "tmpfs_paths": ["/tmp", "/run", "/home/agent"],
  "environment": {
    "HOME": "/home/agent",
    "PATH": "/usr/bin:/bin",
    "LANG": "C.UTF-8"
  },
  "network_isolation": true,
  "additional_args": ["--hostname", "diagnostics-sandbox"]
}
```

### Log Analysis

```json
{
  "name": "log-analysis",
  "allowed_commands": [
    "/usr/bin/grep",
    "/usr/bin/zgrep",
    "/usr/bin/cat",
    "/usr/bin/zcat",
    "/usr/bin/tail",
    "/usr/bin/wc",
    "/usr/bin/awk",
    "/usr/bin/sed"
  ],
  "binds": [
    {"source": "/usr", "target": "/usr", "read_only": true},
    {"source": "/lib64", "target": "/lib64", "read_only": true},
    {"source": "/var/log", "target": "/var/log", "read_only": true}
  ],
  "tmpfs_paths": ["/tmp"],
  "environment": {
    "PATH": "/usr/bin",
    "LANG": "C.UTF-8"
  },
  "network_isolation": true
}
```

### Configuration Inspection

```json
{
  "name": "config-inspection",
  "allowed_commands": [
    "/usr/bin/cat",
    "/usr/bin/grep",
    "/usr/bin/find",
    "/usr/bin/ls"
  ],
  "binds": [
    {"source": "/usr", "target": "/usr", "read_only": true},
    {"source": "/etc", "target": "/etc", "read_only": true}
  ],
  "tmpfs_paths": ["/tmp"],
  "environment": {
    "PATH": "/usr/bin:/bin"
  },
  "network_isolation": true
}
```

## Profile Best Practices

### Security

1. **Always use read-only binds** for system directories
   ```json
   {"source": "/usr", "target": "/usr", "read_only": true}
   ```

2. **Minimize allowed commands** to only what's needed
   ```json
   "allowed_commands": ["ls", "cat", "grep"]  // Not ["*"]
   ```

3. **Enable network isolation** unless specifically needed
   ```json
   "network_isolation": true
   ```

4. **Use tmpfs for writable paths** to prevent persistence
   ```json
   "tmpfs_paths": ["/tmp", "/var/tmp"]
   ```

### Compatibility

1. **Include both command names and paths**
   ```json
   "allowed_commands": ["ls", "/usr/bin/ls", "/bin/ls"]
   ```

2. **Bind essential system directories**
   ```json
   {"source": "/usr", "target": "/usr"},
   {"source": "/lib64", "target": "/lib64"}
   ```

3. **Set minimal PATH**
   ```json
   "environment": {"PATH": "/usr/bin:/bin"}
   ```

### Performance

1. **Reuse profiles** - Loading is fast but reuse is faster
2. **Bind only needed paths** - Fewer mounts = faster startup
3. **Avoid large tmpfs** - Uses RAM, start small

## Validation

Profiles are validated when loaded. Common errors:

**Invalid JSON**
```
SandboxError: Sandbox profile file profile.json is not valid JSON.
```

**Missing required fields**
```
SandboxError: Sandbox profile must have a non-empty name.
```

**Invalid paths**
```
SandboxError: Bind source must be absolute: relative/path
```

**Non-existent files**
```
SandboxError: Unable to read sandbox profile file: /path/to/profile.json
```

## Testing Profiles

```bash
# Validate profile syntax
shannot --profile myprofile.json export > /dev/null

# Test allowed command
shannot --profile myprofile.json run ls /

# Test disallowed command (should fail)
shannot --profile myprofile.json run rm /tmp/test

# Verify comprehensive check
shannot --profile myprofile.json verify
```

## Profile Locations

Shannot searches these locations in order:

1. `--profile` command-line argument
2. `$SANDBOX_PROFILE` environment variable
3. `~/.config/shannot/profile.json` (user config)
4. `/etc/shannot/profile.json` (system config)
5. `/etc/sandbox/readonly.json`
6. `/usr/etc/sandbox/readonly.json`

## Related Documentation

- [usage.md](usage.md) - Using profiles from command-line and Python
- [installation.md](installation.md) - Installing and configuring profiles
- [deployment.md](deployment.md) - Deploying profiles in production
