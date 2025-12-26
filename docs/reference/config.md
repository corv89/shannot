# Config Module

Configuration management for Shannot.

## Overview

The config module provides path management, version information, and profile/remote configuration.

## Key Components

| Component | Purpose |
|-----------|---------|
| `VERSION` | Current Shannot version |
| `get_config_dir()` | XDG config directory |
| `get_data_dir()` | XDG data directory |
| `get_runtime_dir()` | PyPy runtime location |
| `load_profile()` | Load approval profile |
| `load_remotes()` | Load remote targets |

## Directory Structure

```
~/.config/shannot/
└── config.toml           # Global config (profile, audit, remotes)

~/.local/share/shannot/
├── runtime/              # PyPy sandbox runtime
│   ├── lib-python/       # Python stdlib
│   └── lib_pypy/         # PyPy modules
├── sessions/             # Session data
└── audit/                # Audit logs
```

## Configuration File

All settings are in `config.toml`:

```toml
[profile]
auto_approve = ["cat", "ls", "df", "free"]
always_deny = ["rm -rf /", "dd if=/dev/zero"]

[audit]
enabled = true

[remotes.prod]
host = "prod.example.com"
user = "deploy"
port = 22

[remotes.staging]
host = "staging.example.com"
user = "admin"
port = 22
```

**Locations (in order of precedence):**
1. `.shannot/config.toml` (project-local)
2. `~/.config/shannot/config.toml` (global)
3. Built-in default

## Environment Variables

| Variable | Description |
|----------|-------------|
| `XDG_CONFIG_HOME` | Config directory (default: `~/.config`) |
| `XDG_DATA_HOME` | Data directory (default: `~/.local/share`) |

## See Also

- [Configuration Guide](../configuration.md) - Detailed configuration
- [Profile Configuration](../profiles.md) - Approval profiles
- [Deployment](../deployment.md) - Remote targets
