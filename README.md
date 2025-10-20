# Shannot Sandbox

[![Tests](https://github.com/corv89/shannot/actions/workflows/test.yml/badge.svg)](https://github.com/corv89/shannot/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/os-linux-green.svg)](https://www.kernel.org/)

**Shannot** is an easy-to-deploy sandbox tool for running commands in a secure, read-only environment using Linux's [bubblewrap](https://github.com/containers/bubblewrap). It's designed for system diagnostics and monitoring, particularly with LLM-based agents where strict read-only enforcement is critical.

> Claude __shannot__ do *that!*

## 🚀 Try it now
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/corv89/shannot?quickstart=1)

Want to try Shannot without installing anything? Click the badge above to open a dev environment to start testing sandboxed commands in seconds!

## Features

- **Minimal dependencies** - Only requires Python 3.9+ and bubblewrap
- **Read-only by default** - Prevents any modifications to the host system
- **Network isolation** - Commands run without network access by default
- **JSON-based profiles** - Easy to configure and share
- **Command allowlisting** - Restrict which commands can be executed
- **Drop-in deployment** - Transfer to remote systems and run in minutes
- **Type-safe API** - Fully typed Python interface

## Quick Start

### Installation

```bash
# Install bubblewrap (if not already installed)
# Fedora/RHEL
sudo dnf install bubblewrap

# Debian/Ubuntu
sudo apt install bubblewrap

# Install shannot (once published)
pip install shannot

# Or use the installation script
./install.sh
```

### Usage

```bash
# Run a command in the sandbox
shannot run ls /

# Verify the sandbox is working
shannot verify

# Export your profile configuration
shannot export

# Use a custom profile
shannot --profile /path/to/profile.json run cat /etc/os-release

# Get help
shannot --help
```

## Use Cases

### Remote System Diagnostics

Allow LLM agents or remote operators to inspect system state without modification risk:

```bash
shannot run df -h
shannot run cat /proc/meminfo
shannot run systemctl status
```

### Safe Command Exploration

Test unfamiliar commands without worrying about side effects:

```bash
shannot run find / -name "*.conf"
shannot run grep -r "pattern" /var/log
```

### Automated Monitoring

Build monitoring scripts with guaranteed read-only access:

```python
from shannot import SandboxManager, load_profile_from_path
from pathlib import Path

profile = load_profile_from_path("~/.config/shannot/profile.json")
manager = SandboxManager(profile, Path("/usr/bin/bwrap"))

result = manager.run(["df", "-h"])
if result.succeeded():
    print(result.stdout)
```

## Configuration

Shannot uses JSON profiles to define sandbox behavior. Three profiles are included:

### Included Profiles

**`minimal.json`** (default) - Basic read-only access:
- Commands: ls, cat, grep, find
- Binds: /usr, /etc, /lib, /lib64
- Works out-of-the-box, no setup required

**`readonly.json`** - Comprehensive read-only profile:
- Extended command set
- Additional binds (includes /sbin, /var/lib/ca-certificates)
- Suitable for most use cases

**`diagnostics.json`** - System monitoring and diagnostics:
- Full diagnostic commands: df, free, ps, uptime
- Access to /proc, /sys, /var/log
- Perfect for LLM-based monitoring

### Quick Profile Example

```json
{
  "name": "minimal",
  "allowed_commands": ["ls", "cat", "grep", "find"],
  "binds": [
    {"source": "/usr", "target": "/usr", "read_only": true}
  ],
  "tmpfs_paths": ["/tmp"],
  "environment": {"PATH": "/usr/bin:/bin"},
  "network_isolation": true
}
```

See [docs/profiles.md](docs/profiles.md) for complete profile documentation.

## How It Works

Shannot wraps Linux's bubblewrap tool to create lightweight, secure sandboxes:

1. **Namespace isolation** - Each command runs in isolated namespaces (PID, mount, network, etc.)
2. **Read-only mounts** - System directories are mounted read-only
3. **Temporary filesystems** - Writable locations use ephemeral tmpfs
4. **Command allowlisting** - Only explicitly permitted commands can execute
5. **No persistence** - All changes are lost when the command exits

## Python API

```python
from shannot import SandboxManager, load_profile_from_path
from pathlib import Path

# Load profile and create manager
profile = load_profile_from_path("~/.config/shannot/profile.json")
manager = SandboxManager(profile, Path("/usr/bin/bwrap"))

# Run commands
result = manager.run(["ls", "/"])
print(f"Output: {result.stdout}")
print(f"Duration: {result.duration:.2f}s")
```

See [docs/api.md](docs/api.md) for complete API documentation including profile creation, error handling, and advanced usage.

## Requirements

- **Operating System**: Linux (kernel 3.8+)
- **Python**: 3.9 or newer
- **System Package**: bubblewrap (`bwrap`)

## Deployment

### Single-File Transfer

For quick deployment to remote systems:

### SSH Install

```bash
# Transfer and install in one command
ssh user@remote "bash -s" < install.sh
```

### Via pip

```bash
# From source
pip install git+https://github.com/corv89/shannot.git
```

See [docs/deployment.md](docs/deployment.md) for advanced deployment scenarios.

## Development

### Quick Start with Codespaces

The fastest way to start developing:

1. Click the "Open in GitHub Codespaces" badge above
2. Wait for the container to build (includes bubblewrap and all dependencies)
3. Start coding immediately - everything is pre-configured!

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/corv89/shannot.git
cd shannot

# Install bubblewrap (required for testing)
sudo apt install bubblewrap  # Debian/Ubuntu
sudo dnf install bubblewrap  # Fedora/RHEL

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linter and formatter
ruff check .
ruff format .

# Run type checker
basedpyright
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=shannot --cov-report=html

# Run only unit tests (skip integration tests)
pytest tests/ -v -m "not integration"

# Run only integration tests (requires Linux + bubblewrap)
pytest tests/ -v -m "integration"
```

**Note**: Integration tests require Linux and bubblewrap. They will be automatically skipped on other platforms.

### Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Documentation

- **[installation.md](docs/installation.md)** - Installation for various Linux distributions
- **[usage.md](docs/usage.md)** - CLI usage and common use cases
- **[profiles.md](docs/profiles.md)** - Complete profile configuration reference
- **[api.md](docs/api.md)** - Python API documentation
- **[deployment.md](docs/deployment.md)** - Deployment with Ansible, systemd, SSH
- **[seccomp.md](docs/seccomp.md)** - Optional: Adding seccomp BPF filters

## Contributing

Contributions are welcome!

- Report bugs via [GitHub Issues](https://github.com/corv89/shannot/issues)
- Submit pull requests
- Request features
- Share use cases

## Security Considerations

While Shannot provides strong isolation, it's not a security boundary:

- **Kernel vulnerabilities** - Sandbox escapes are possible via kernel exploits
- **Information leakage** - Read-only access still exposes system information
- **Resource limits** - No built-in CPU/memory limits (use systemd or cgroups)
- **Root usage** - Don't run shannot as root unless absolutely necessary

For production security, combine with:
- SELinux/AppArmor policies
- seccomp filters (supported via profiles)
- User namespaces
- Resource limits via cgroups

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

## Credits

Shannot builds upon:
- [Bubblewrap](https://github.com/containers/bubblewrap) - The low-level Linux sandboxing tool
- [libseccomp](https://github.com/seccomp/libseccomp) - The BPF-based syscall filtering library

## Support

- Documentation: [docs/](docs/)
- Issues: [GitHub Issues](https://github.com/corv89/shannot/issues)
- Discussions: [GitHub Discussions](https://github.com/corv89/shannot/discussions)
