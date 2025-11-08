# Shannot

[![Tests](https://github.com/corv89/shannot/actions/workflows/test.yml/badge.svg)](https://github.com/corv89/shannot/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/corv89/shannot/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/os-linux-green.svg)](https://www.kernel.org/)

**Shannot** lets LLM agents and automated tools safely explore your Linux systems without risk of modification. Built on [bubblewrap](https://github.com/containers/bubblewrap), it provides bulletproof read-only sandboxing for system diagnostics, monitoring, and exploration - perfect for giving Claude or other AI assistants safe access to your servers.

> Claude __shannot__ do *that!*

## Features

:lock: **Run Untrusted Commands Safely**
Let LLM agents explore your system without risk of modification • Network-isolated execution • Control exactly which commands are allowed

:robot: **Works with Claude Desktop**
Plug-and-play [MCP integration](mcp.md) - give Claude safe read-only access to your servers

:globe_with_meridians: **Control Remote Systems**
Run sandboxed commands on Linux servers from your macOS or Windows laptop via SSH

:zap: **Deploy in Minutes**
Python client + bubblewrap on target • No containers, VMs, or complex setup required

## Quick Start

### Installation

**Client** (any platform): Python 3.10+
**Target** (Linux only): bubblewrap

=== "UV (Recommended)"

    ```bash
    # Install UV
    curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
    # Or for Windows: irm https://astral.sh/uv/install.ps1 | iex

    # Standard installation (includes MCP and remote execution)
    uv tool install shannot

    # Minimal installation (Linux-only local CLI)
    uv tool install "shannot[minimal]"
    ```

=== "pipx (Ubuntu/Debian)"

    ```bash
    # Install pipx
    sudo apt install pipx
    pipx ensurepath

    # Standard installation (includes MCP and remote execution)
    pipx install shannot

    # Minimal installation (Linux-only local CLI)
    pipx install "shannot[minimal]"
    ```

=== "pip"

    ```bash
    # Standard installation (includes MCP and remote execution)
    pip install --user shannot

    # Minimal installation (Linux-only local CLI)
    pip install --user "shannot[minimal]"
    ```

### Install bubblewrap (Linux only)

```bash
# Debian/Ubuntu
sudo apt install bubblewrap

# Fedora/RHEL
sudo dnf install bubblewrap

# Arch Linux
sudo pacman -S bubblewrap
```

See [Installation Guide](installation.md) for detailed instructions.

### Basic Usage

```bash
# Run a command in read-only sandbox
shannot ls /

# Verify bubblewrap is available
shannot verify

# Export MCP configuration for Claude Desktop
shannot export
```

See [Usage Guide](usage.md) for more examples.

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

profile = load_profile_from_path("~/.config/shannot/profile.json")
manager = SandboxManager(profile, Path("/usr/bin/bwrap"))

result = manager.run(["ls", "/"])
print(f"Output: {result.stdout}")
print(f"Duration: {result.duration:.2f}s")
```

See [API Reference](api.md) for complete documentation.

## Documentation

- **[Installation Guide](installation.md)** - Install Shannot on any platform
- **[Usage Guide](usage.md)** - Learn basic commands and workflows
- **[Profile Configuration](profiles.md)** - Configure sandbox behavior
- **[Configuration](configuration.md)** - Remote execution, Ansible, systemd
- **[Deployment](deployment.md)** - Production deployment guide
- **[MCP Integration](mcp.md)** - Claude Desktop setup
- **[API Reference](api.md)** - Python API documentation
- **[Testing](testing.md)** - Running and writing tests
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions

## Security Considerations

Shannot provides strong isolation but **is not a security boundary**:

- Sandbox escapes possible via kernel exploits
- Read-only access still exposes system information
- No built-in CPU/memory limits (use systemd/cgroups)
- Don't run as root unless necessary

For production, combine with SELinux/AppArmor, seccomp filters, and resource limits.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](https://github.com/corv89/shannot/blob/main/CONTRIBUTING.md) or [open an issue](https://github.com/corv89/shannot/issues).

## License

Apache 2.0 - See [LICENSE](https://github.com/corv89/shannot/blob/main/LICENSE)

Built on [Bubblewrap](https://github.com/containers/bubblewrap) and [libseccomp](https://github.com/seccomp/libseccomp)
