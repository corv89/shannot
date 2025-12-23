# Shannot

[![Tests](https://github.com/corv89/shannot/actions/workflows/test.yml/badge.svg)](https://github.com/corv89/shannot/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/corv89/shannot/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/os-linux-green.svg)](https://www.kernel.org/)

**Shannot** lets LLM agents and automated tools safely explore your Linux systems without risk of modification. Built on [PyPy sandbox](https://doc.pypy.org/en/latest/sandbox.html) architecture, it provides hardened sandboxing for system diagnostics, monitoring, and exploration - perfect for giving Claude or other AI assistants safe access to your systems.

> Claude __shannot__ do *that!*

## Features

:lock: **Run Untrusted Code Safely**

- PyPy sandbox intercepts all system calls
- Virtual filesystem prevents unauthorized access
- Network-isolated execution (no socket access)
- Session-based approval workflow for subprocess execution

:robot: **Perfect for LLM Agents**

- Let Claude and other AI assistants explore systems safely
- Command approval profiles control what executes automatically
- Interactive TUI for reviewing queued operations
- [MCP integration](mcp.md) for Claude Desktop and Claude Code

:globe_with_meridians: **Control Remote Systems**

- Run sandboxed scripts on Linux servers from any platform via SSH
- Zero-dependency SSH implementation using stdlib only
- Auto-deployment to remote hosts (no manual installation needed)
- Named remotes configuration for easy target management

:zap: **Deploy in Minutes**

- Zero external dependencies - pure Python stdlib only
- Auto-setup downloads PyPy runtime on first use
- No containers, VMs, or complex configuration required
- Works out of the box on any Linux system

## Quick Start

### Installation

**Requirements:**

- **Host**: Python 3.11+ (zero runtime dependencies!)
- **Sandbox**: PyPy sandbox binary (auto-downloaded on first run)

=== "UV (Recommended)"

    ```bash
    # Install UV
    curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux

    # Install shannot
    uv tool install shannot
    ```

=== "pipx (Ubuntu/Debian)"

    ```bash
    # Install pipx
    sudo apt install pipx
    pipx ensurepath

    # Install shannot
    pipx install shannot
    ```

=== "pip"

    ```bash
    pip install --user shannot
    ```

See [Installation Guide](installation.md) for detailed instructions.

### Basic Usage

```bash
# 1. Install PyPy runtime (one-time setup)
shannot setup

# 2. Run a script in the sandbox
shannot run script.py

# 3. Review and approve pending operations
shannot approve

# Check system status
shannot status
```

See [Usage Guide](usage.md) for more examples.

## How It Works

Unlike traditional container-based sandboxes, Shannot operates at the system call level, providing fine-grained control over exactly what sandboxed code can do.

1. **System call interception** - All syscalls from sandboxed code are intercepted and virtualized by PyPy sandbox
2. **Virtual filesystem** - File operations map to controlled paths, preventing unauthorized access
3. **Subprocess approval workflow** - Commands queue in sessions for human review before execution
4. **Profile-based control** - Approval profiles define which commands run immediately vs. require approval
5. **Zero persistence** - All changes exist only within the session, nothing touches the real system

This architecture enables LLM agents to explore systems safely while giving humans final control over any potentially risky operations.

## Documentation

- **[Installation Guide](installation.md)** - Install Shannot on any platform
- **[Usage Guide](usage.md)** - Learn CLI commands and session workflow
- **[Profile Configuration](profiles.md)** - Configure command approval behavior
- **[Configuration](configuration.md)** - Remote targets, MCP setup
- **[Deployment](deployment.md)** - Production deployment guide
- **[MCP Integration](mcp.md)** - Claude Desktop and Claude Code setup
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
- **[Migrating from v0.3.x](migrating-from-v3.md)** - Upgrade guide for older versions

## Security Considerations

Shannot provides strong isolation but **is not a complete security boundary**:

**What Shannot provides:**

- System call interception and virtualization
- Virtual filesystem isolation
- Subprocess execution control with approval workflow
- Zero network access (sockets disabled)

**Known limitations:**

- PyPy sandbox interpreter vulnerabilities could allow escape
- Virtual filesystem still exposes information about mapped paths
- No built-in CPU/memory resource limits
- Don't run as root unless necessary

For production, combine with SELinux/AppArmor, resource limits (systemd/cgroups), and principle of least privilege.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](https://github.com/corv89/shannot/blob/main/CONTRIBUTING.md) or [open an issue](https://github.com/corv89/shannot/issues).

## License

Apache 2.0 - See [LICENSE](https://github.com/corv89/shannot/blob/main/LICENSE)
