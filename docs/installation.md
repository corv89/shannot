# Installation Guide

Complete installation guide for Shannot on all supported platforms.

## Requirements

### Host System

- **Python 3.11+** (CPython or PyPy)
- **Zero runtime dependencies** - pure Python stdlib only

### Sandbox Runtime

- **PyPy sandbox binary** - auto-downloaded on first run via `shannot setup runtime`
- Storage: ~50MB in `~/.local/share/shannot/runtime/`

## Installation

### UV (Recommended)

[UV](https://docs.astral.sh/uv/) is the fastest way to install Python tools:

```bash
# Install UV (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or Windows
irm https://astral.sh/uv/install.ps1 | iex

# Install shannot
uv tool install shannot
```

### pipx (Ubuntu/Debian)

Ubuntu and Debian mark system Python as "externally managed" (PEP 668). Use `pipx`:

```bash
# Install pipx
sudo apt install pipx
pipx ensurepath

# Install shannot
pipx install shannot
```

### pip

```bash
# Basic installation
pip install --user shannot

# Note: On Ubuntu/Debian, you may need --break-system-packages
# (not recommended, use pipx or uv instead)
```

### From Source

```bash
# Clone the repository
git clone https://github.com/corv89/shannot.git
cd shannot

# Install with UV
uv tool install .

# Or with pip
pip install --user -e .
```

## Post-Installation Setup

### 1. Install PyPy Runtime

After installing shannot, run the setup command to download the PyPy sandbox runtime:

```bash
shannot setup runtime
```

This downloads:
- PyPy 3.6 stdlib (~50MB)
- Stored in `~/.local/share/shannot/runtime/`

**Note:** The PyPy sandbox binary itself must be separately compiled or downloaded. See the project repository for details.

### 2. Verify Installation

```bash
# Check shannot version
shannot --version

# Check runtime and configuration status
shannot status
```

Expected output:
```
Shannot v0.5.1
Runtime: installed at ~/.local/share/shannot/runtime/
PyPy sandbox: found at /path/to/pypy-sandbox
Profiles: using default profile
```

## Remote Target Setup

Shannot can execute sandboxed scripts on remote Linux hosts via SSH. Remote targets are auto-deployed - no manual installation required on the remote.

### Add a Remote Target

```bash
# Add a remote server
shannot setup remote add prod user@prod.example.com

# With explicit options
shannot setup remote add staging \
  --host staging.example.com \
  --user deploy \
  --port 22
```

### Test Connection

```bash
shannot setup remote test prod
```

### List Configured Remotes

```bash
shannot setup remote list
```

Remote targets are stored in the `[remotes.*]` sections of `~/.config/shannot/config.toml`.

## Configuration Paths

Shannot follows XDG Base Directory specification:

| Type | Path |
|------|------|
| Config | `~/.config/shannot/` |
| Data | `~/.local/share/shannot/` |
| Runtime | `~/.local/share/shannot/runtime/` |
| Sessions | `~/.local/share/shannot/sessions/` |

### Profile Locations

Approval profiles are loaded in order of precedence:

1. `.shannot/config.toml` (project-local)
2. `~/.config/shannot/config.toml` (global)
3. Built-in default profile

## Troubleshooting

### Command Not Found

If `shannot` is not found after installation:

```bash
# Check if it's installed
python3 -m shannot --version

# Add user bin to PATH
export PATH="$HOME/.local/bin:$PATH"

# Or for UV
export PATH="$HOME/.local/bin:$PATH"
```

### Runtime Not Found

If `shannot status` shows runtime not installed:

```bash
# Install the runtime
shannot setup runtime

# Force reinstall
shannot setup runtime --force
```

### Python Version Issues

Shannot requires Python 3.11+:

```bash
# Check Python version
python3 --version

# Install newer Python if needed (example for Fedora/RHEL)
sudo dnf install python3.11

# Use specific version
python3.11 -m pip install --user shannot
```

## Uninstallation

```bash
# Uninstall shannot
pip uninstall shannot

# Or with UV
uv tool uninstall shannot

# Remove configuration
rm -rf ~/.config/shannot

# Remove runtime and sessions
rm -rf ~/.local/share/shannot
```

## Next Steps

- [Usage Guide](usage.md) - Learn CLI commands and session workflow
- [Profile Configuration](profiles.md) - Configure command approval behavior
- [MCP Integration](mcp.md) - Set up Claude Desktop integration
