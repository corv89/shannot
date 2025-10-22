# Installation Guide

Complete installation guide for Shannot on all supported platforms.

## Prerequisites

### System Requirements

**Client** (any platform):
- Python 3.10 or newer

**Target** (Linux only):
- Linux with kernel 3.8 or newer
- bubblewrap package

### Check Your System

```bash
# Check Python version
python3 --version

# Check Linux kernel version (Linux only)
uname -r

# Check if bubblewrap is installed (Linux only)
which bwrap
bwrap --version
```

## Installation

### Client Installation (Any Platform)

#### Recommended: UV (Cross-platform)

```bash
# Install UV (works on macOS, Linux, Windows)
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
# Or for Windows: irm https://astral.sh/uv/install.ps1 | iex

# Install shannot
uv tool install shannot

# Or with MCP support for Claude Desktop
uv tool install "shannot[mcp]"
```

#### Alternative: pipx (Ubuntu/Debian)

Ubuntu and Debian mark system Python as "externally managed" (PEP 668). Use `pipx`:

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

#### Traditional: pip

```bash
# Basic installation
pip install --user shannot

# With optional dependencies
pip install --user "shannot[mcp]"  # MCP/Claude Desktop support
pip install --user "shannot[all]"  # All optional features

# Note: On Ubuntu/Debian, you may need --break-system-packages
# (not recommended, use pipx or uv instead)
```

#### From Source

```bash
# Clone the repository
git clone https://github.com/corv89/shannot.git
cd shannot

# Install with UV
uv tool install .

# Or with pip
pip install --user .
```

### Target Installation (Linux Only)

If your target is a remote Linux system, only bubblewrap is required (Python not needed):

#### Debian / Ubuntu

```bash
sudo apt install bubblewrap
```

#### Fedora / RHEL / CentOS

```bash
sudo dnf install bubblewrap
```

#### openSUSE

```bash
sudo zypper install bubblewrap
```

#### Arch Linux

```bash
sudo pacman -S bubblewrap
```

### Optional Dependencies

```bash
# MCP server for Claude Desktop
pip install --user "shannot[mcp]"

# Remote execution via SSH
pip install --user "shannot[remote]"

# Development tools (testing, linting)
pip install --user "shannot[dev]"

# Everything
pip install --user "shannot[all]"
```

## Post-Installation

### Verify Installation

```bash
# Check that shannot command is available
which shannot

# Check version
shannot --version

# Run verification test
shannot verify
```

### Configure Profile

Create a custom profile:

```bash
# Create config directory
mkdir -p ~/.config/shannot

# Copy profile
cp profiles/readonly.json ~/.config/shannot/profile.json

# Edit as needed
${EDITOR:-nano} ~/.config/shannot/profile.json
```

## Troubleshooting

### Command Not Found

If `shannot` is not found after installation:

```bash
# Check if it's installed
python3 -m shannot --version

# Add user bin to PATH
export PATH="$HOME/.local/bin:$PATH"
```

### Permission Denied

If bubblewrap fails with permission errors:

```bash
# Check bubblewrap permissions
ls -l $(which bwrap)

# bwrap should be setuid root
sudo chmod u+s $(which bwrap)
```

### Python Version Issues

If your system Python is too old:

```bash
# Install newer Python (example for RHEL/CentOS)
sudo dnf install python3.9

# Use specific Python version
python3.9 -m pip install --user shannot
python3.9 -m shannot verify
```

### Profile Not Found

If shannot can't find a profile:

```bash
# Specify profile explicitly
shannot --profile /path/to/profile.json run ls /

# Or set environment variable
export SANDBOX_PROFILE=/path/to/profile.json
shannot run ls /
```

## Uninstallation

```bash
# Uninstall shannot
pip uninstall shannot

# Remove configuration
rm -rf ~/.config/shannot

# Remove system-wide installation (if applicable)
sudo pip uninstall shannot
sudo rm -rf /etc/shannot
```

## Next Steps

- Read [usage.md](usage.md) for command-line usage
- Learn about [profiles.md](profiles.md) for configuration
- See [deployment.md](deployment.md) for advanced scenarios
