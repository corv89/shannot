# Shannot Sandbox

[![Tests](https://github.com/corv89/shannot/actions/workflows/test.yml/badge.svg)](https://github.com/corv89/shannot/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/os-linux-green.svg)](https://www.kernel.org/)

**Shannot** lets LLM agents and automated tools safely explore your Linux systems without risk of modification. Built on [bubblewrap](https://github.com/containers/bubblewrap), it provides bulletproof read-only sandboxing for system diagnostics, monitoring, and exploration - perfect for giving Claude or other AI assistants safe access to your servers.

> Claude __shannot__ do *that!*

## Features

🔒 **Run Untrusted Commands Safely**
* Let LLM agents explore your system without risk of modification
* Network-isolated execution
* Control exactly which commands are allowed

🤖 **Works with Claude Desktop**
* Plug-and-play [MCP integration](https://corv89.github.io/shannot/mcp/)
* Give Claude safe read-only access to your servers

🌐 **Control Remote Systems**
* Run sandboxed commands on Linux servers from your macOS or Windows laptop via SSH

⚡ **Deploy in Minutes**
* Python client + bubblewrap on target
* No containers, VMs, or complex setup required


## Quick Start

### Installation

- **Client** (any platform): Python 3.10+
- **Target** (Linux only): bubblewrap

#### Install on Client (any platform)

```bash
# Install UV (recommended - works on all platforms)
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
# Or for Windows: irm https://astral.sh/uv/install.ps1 | iex

# Install shannot
uv tool install shannot

# Or with MCP support for Claude Desktop
uv tool install "shannot[mcp]"
```

#### Install on Target (Linux only)

If your target is a remote Linux system, bubblewrap is all you need (Python not required):

```bash
# Debian/Ubuntu
sudo apt install bubblewrap

# Fedora/RHEL
sudo dnf install bubblewrap

# openSUSE
sudo zypper install bubblewrap

# Arch Linux
sudo pacman -S bubblewrap
```

If client and target are the same Linux machine, install both shannot and bubblewrap.

See [Deployment Guide](https://corv89.github.io/shannot/deployment/) for remote execution setup via SSH.

<details>
<summary><b>Alternative installation methods</b></summary>

**pipx (recommended for Ubuntu/Debian):**

Ubuntu and Debian mark system Python as "externally managed" (PEP 668), which prevents `pip install --user`. Use `pipx` instead:

```bash
# Install pipx
sudo apt install pipx
pipx ensurepath

# Install shannot
pipx install shannot

# Or with optional dependencies
pipx install "shannot[mcp]"  # MCP/Claude Desktop support
pipx install "shannot[all]"  # All optional features
```

**Traditional pip:**

```bash
# Basic installation
pip install --user shannot

# With optional dependencies
pip install --user "shannot[mcp]"  # MCP/Claude Desktop support
pip install --user "shannot[all]"  # All optional features

# Note: On Ubuntu/Debian, you may need --break-system-packages
# (not recommended, use pipx or uv instead)
```
</details>

**Optional dependencies:**
- `[mcp]` - MCP server for Claude Desktop integration
- `[all]` - All optional features

### Usage

```bash
# Run a command in the sandbox
shannot ls /

# Check version
shannot --version

# Verify the sandbox is working
shannot verify

# Export your profile configuration
shannot export

# Use a custom profile
shannot --profile /path/to/profile.json cat /etc/os-release

# Get help
shannot --help
```

## Use Cases

**System diagnostics** - Let LLM agents inspect system state without modification risk
**Safe exploration** - Test unfamiliar commands without worrying about side effects
**Automated monitoring** - Build scripts with guaranteed read-only access

```bash
# Diagnostics
shannot df -h
shannot cat /proc/meminfo
shannot systemctl status

# Exploration
shannot find / -name "*.conf"
shannot grep -r "pattern" /var/log
```

```python
# Monitoring scripts
from shannot import SandboxManager, load_profile_from_path

profile = load_profile_from_path("~/.config/shannot/profile.json")
manager = SandboxManager(profile, Path("/usr/bin/bwrap"))

result = manager.run(["df", "-h"])
if result.succeeded():
    print(result.stdout)
```

## Configuration

Shannot uses JSON profiles to control sandbox behavior. Three profiles included:

- **`minimal.json`** (default) - Basic commands (ls, cat, grep, find), works out-of-the-box
- **`readonly.json`** - Extended command set, suitable for most use cases
- **`diagnostics.json`** - System monitoring (df, free, ps, uptime), perfect for LLM agents

```json
{
  "name": "minimal",
  "allowed_commands": ["ls", "cat", "grep", "find"],
  "binds": [{"source": "/usr", "target": "/usr", "read_only": true}],
  "tmpfs_paths": ["/tmp"],
  "environment": {"PATH": "/usr/bin:/bin"},
  "network_isolation": true
}
```

See [profiles](https://corv89.github.io/shannot/profiles) for complete documentation.

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

See [api](https://corv89.github.io/shannot/api) for complete documentation.

## Development

```bash
# Clone and install
git clone https://github.com/corv89/shannot.git
cd shannot
pip install -e ".[dev]"

# Run tests (integration tests require Linux + bubblewrap)
pytest tests/ -v
pytest tests/ -v -m "not integration"  # unit tests only

# Lint and type check
ruff check . && ruff format .
basedpyright
```


## Documentation

**[Full documentation](https://corv89.github.io/shannot/)**

Quick links:
- **[Installation Guide](https://corv89.github.io/shannot/installation/)** - Install Shannot on any platform
- **[Usage Guide](https://corv89.github.io/shannot/usage/)** - Learn basic commands and workflows
- **[Profile Configuration](https://corv89.github.io/shannot/profiles/)** - Configure sandbox behavior
- **[API Reference](https://corv89.github.io/shannot/api/)** - Python API documentation
- **[Deployment Guide](https://corv89.github.io/shannot/deployment/)** - Remote execution, Ansible, systemd
- **[MCP Integration](https://corv89.github.io/shannot/mcp/)** - Claude Desktop integration
- **[Troubleshooting](https://corv89.github.io/shannot/troubleshooting/)** - Common issues and solutions

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) or [open an issue](https://github.com/corv89/shannot/issues).

## Security Considerations

Shannot provides strong isolation but **is not a security boundary**:

- Sandbox escapes possible via kernel exploits
- Read-only access still exposes system information
- No built-in CPU/memory limits (use systemd/cgroups)
- Don't run as root unless necessary

For production, combine with SELinux/AppArmor, seccomp filters ([seccomp](https://corv89.github.io/shannot/seccomp)), and resource limits.

## License

Apache 2.0 - See [LICENSE](LICENSE)

Built on [Bubblewrap](https://github.com/containers/bubblewrap) and [libseccomp](https://github.com/seccomp/libseccomp)
