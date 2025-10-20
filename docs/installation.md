# Installation Guide

This guide covers installing Shannot on various Linux distributions.

## Prerequisites

### System Requirements

- **Operating System**: Linux with kernel 3.8 or newer
- **Python**: 3.9 or newer
- **Required Package**: bubblewrap

### Check Your System

```bash
# Check Linux kernel version
uname -r

# Check Python version
python3 --version

# Check if bubblewrap is installed
which bwrap
bwrap --version
```

## Installing Bubblewrap

Bubblewrap must be installed before using Shannot.

### Fedora / RHEL / CentOS

```bash
sudo dnf install bubblewrap
```

### Debian / Ubuntu

```bash
sudo apt update
sudo apt install bubblewrap
```

### Arch Linux

```bash
sudo pacman -S bubblewrap
```

## Installing Shannot

### Direct from GitHub
```bash
pip install --user git+https://github.com/corv89/shannot.git
```

### From Source

```bash
# Clone the repository
git clone https://github.com/corv89/shannot.git
cd shannot

# Install
pip install --user .

# Or use the installation script
./install.sh
```

### From PyPi (once published)

```bash
# Install for current user
pip install --user shannot
```

## Post-Installation

### Verify Installation

```bash
# Check that shannot command is available
which shannot
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
