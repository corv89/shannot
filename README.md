# Shannot Sandbox

[![Tests](https://github.com/corv89/shannot/actions/workflows/test.yml/badge.svg)](https://github.com/corv89/shannot/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/os-linux-green.svg)](https://www.kernel.org/)

**Shannot** lets LLM agents and automated tools safely explore your Linux systems without risk of modification. Built on [bubblewrap](https://github.com/containers/bubblewrap), it provides hardened sandboxing for system diagnostics, monitoring, and exploration - perfect for giving Claude or other AI assistants safe access to your servers.

> Claude __shannot__ do *that!*

## Features

🔒 **Run Untrusted Commands Safely**
* Let LLM agents explore your system without risk of modification
* Network-isolated execution
* Control exactly which commands are allowed

🤖 **Works with your favorite LLMs**
* Plug-and-play standards-compliant [MCP integration](https://corv89.github.io/shannot/mcp/)
* Convenient auto-install for **Claude Code**, **Codex**, **LM Studio** and **Claude Desktop**
* Compatible with any local model that supports tool-calling

🌐 **Control Remote Systems**
* Run sandboxed commands on Linux servers from macOS, Windows or Linux via SSH

⚡ **Deploy in Minutes**
* Lightweight Python client + bubblewrap on target
* No containers, VMs, or complex setup required


## Quick Start

```bash
# Install (requires Python 3.10+)
pip install shannot

# On Linux: install bubblewrap
sudo apt install bubblewrap  # Debian/Ubuntu
sudo dnf install bubblewrap  # Fedora/RHEL

# Run commands in sandbox
shannot ls /
shannot df -h
shannot cat /etc/os-release
```

See [Installation Guide](https://corv89.github.io/shannot/installation/) for other platforms and methods.

## Profiles

Control what commands are allowed with JSON profiles:

```bash
shannot ls /                          # Uses minimal.json (default)
shannot --profile diagnostics df -h   # System monitoring commands
shannot --profile systemd journalctl  # Journal access
```

See [Profile Configuration](https://corv89.github.io/shannot/profiles/) for customization.

## Python API

```python
from shannot import SandboxManager, load_profile_from_path

profile = load_profile_from_path("diagnostics.json")
manager = SandboxManager(profile)

result = manager.run(["df", "-h"])
print(result.stdout)
```

See [API Reference](https://corv89.github.io/shannot/api/) for details.


## Documentation

📚 [**Full Documentation**](https://corv89.github.io/shannot/) • [Installation](https://corv89.github.io/shannot/installation/) • [MCP Integration](https://corv89.github.io/shannot/mcp/) • [API Reference](https://corv89.github.io/shannot/api/)

## Security Note

Shannot provides strong isolation but **is not a security boundary**. Don't run as root unless necessary. See [Security Considerations](https://corv89.github.io/shannot/security/) for details.

## License

Apache 2.0 - See [LICENSE](LICENSE)

Built on [Bubblewrap](https://github.com/containers/bubblewrap) and [libseccomp](https://github.com/seccomp/libseccomp)
