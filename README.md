# Shannot Sandbox

[![Tests](https://github.com/corv89/shannot/actions/workflows/test.yml/badge.svg)](https://github.com/corv89/shannot/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/os-linux-green.svg)](https://www.kernel.org/)

**Shannot** lets LLM agents and automated tools safely explore your Linux systems without risk of modification. Built on [PyPy sandbox](https://doc.pypy.org/en/latest/sandbox.html) architecture, it provides hardened sandboxing for system diagnostics, monitoring, and exploration - perfect for giving Claude or other AI assistants safe access to your systems.

> Claude __shannot__ do *that!*

## Features

🔒 **Run Untrusted Code Safely**
* PyPy sandbox intercepts all system calls
* Virtual filesystem prevents unauthorized access
* Network-isolated execution (no socket access)
* Session-based approval workflow for subprocess execution

🤖 **Perfect for LLM Agents**
* Let Claude and other AI assistants explore systems safely
* Command approval profiles control what executes automatically
* Interactive TUI for reviewing queued operations
* MCP integration planned for future release (temporarily removed in v0.4.0)

🌐 **Control Remote Systems**
* Run sandboxed scripts on Linux servers from any platform via SSH
* Zero-dependency SSH implementation using stdlib only
* Fetch files from remote hosts automatically
* No Python installation required on remote targets

⚡ **Deploy in Minutes**
* Zero external dependencies - pure Python stdlib only
* Auto-setup downloads PyPy runtime on first use
* No containers, VMs, or complex configuration required
* Works out of the box on any Linux system

## Requirements

**Host system:**
- Python 3.11+ (CPython or PyPy)
- Zero external dependencies!

**Sandboxed code:**
- Must use Python 3.6 compatible syntax
- Requires a PyPy sandbox executable (auto-downloaded on first run)

## Installation

- **Host** (any platform): Python 3.11+, zero runtime dependencies!
- **Sandbox binary**: PyPy sandbox (auto-downloaded on first run via `shannot setup`)

### Install Shannot

```bash
# Recommended: Install with UV (works on all platforms)
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
# Or for Windows: irm https://astral.sh/uv/install.ps1 | iex

uv tool install shannot

# Alternative: pipx (recommended for Ubuntu/Debian with PEP 668)
pipx install shannot

# Alternative: Traditional pip
pip install --user shannot

# Development install (contributors only)
git clone https://github.com/corv89/shannot.git
cd shannot
pip install -e .
```

**Note:** Shannot has **zero runtime dependencies** - pure Python stdlib only! The PyPy sandbox binary will be auto-downloaded when you first run `shannot setup`.

## Quick Start

### 1. Install the runtime

```bash
shannot setup
```

This downloads and installs the PyPy 3.6 stdlib to `~/.local/share/shannot/runtime/`.

### 2. Run a script in the sandbox

```bash
shannot run script.py --tmp=/path/to/tmp
```

The sandbox binary (`pypy-sandbox`) is auto-detected from PATH or standard locations. The `--tmp` option maps a real directory to the virtual `/tmp` inside the sandbox.

### 3. Review pending sessions

```bash
shannot approve
```

Opens an interactive TUI for reviewing and approving queued operations from dry-run sessions.

## How It Works

Unlike traditional container-based sandboxes, Shannot operates at the system call level, providing fine-grained control over exactly what sandboxed code can do.

Shannot uses PyPy's sandbox mode to create a secure execution environment:

1. **System call interception** - All syscalls from sandboxed code are intercepted and virtualized
2. **Virtual filesystem** - File operations map to controlled paths, preventing unauthorized access
3. **Subprocess approval workflow** - Commands queue in sessions for human review before execution
4. **Session-based execution** - Review, approve, or deny operations through an interactive TUI
5. **Zero persistence** - All changes exist only within the session, nothing touches the real system

This architecture enables LLM agents to explore systems safely while giving humans final control over any potentially risky operations.

## CLI Reference

### `shannot setup`

Install PyPy stdlib for sandboxing.

```
Options:
  -f, --force    Force reinstall even if already installed
  -q, --quiet    Suppress progress output
  -s, --status   Check if runtime is installed
  --remove       Remove installed runtime
```

### `shannot run`

Run a script in the sandbox.

```
Usage: shannot run [options] <script.py> [script_args...]

Options:
  --pypy-sandbox PATH  Path to pypy-sandbox executable (auto-detected if not specified)
  --lib-path PATH      Path to lib-python and lib_pypy (auto-detected if not specified)
  --tmp DIR            Real directory mapped to virtual /tmp
  --nocolor            Disable ANSI coloring
  --raw-stdout         Disable output sanitization
  --debug              Enable debug mode
  --dry-run            Log commands without executing
  --script-name NAME   Human-readable session name
  --analysis DESC      Description of script purpose
  --target USER@HOST   SSH target for remote execution
```

### `shannot approve`

Launch interactive TUI for reviewing and approving pending sessions.

### `shannot execute`

Execute a previously created session directly (used by remote protocol).

```
Options:
  --session-id ID  Session ID to execute (required)
  --json-output    Output results in JSON format
```

### `shannot remote`

Manage SSH remote targets for executing sandboxed code on remote hosts.

```
Subcommands:
  remote add <name>     Add a new remote target
  remote list           List configured remote targets
  remote test <name>    Test connection to a remote target
  remote remove <name>  Remove a remote target
```

### `shannot status`

Show system health and configuration status.

```
Options:
  --runtime  Show only runtime installation status
  --targets  Show only remote targets status
```

## Use Cases

**System diagnostics for LLM agents** - Let Claude or other AI assistants safely inspect system state without modification risk

**Safe exploration** - Test unfamiliar code or diagnose issues without worrying about side effects

**Automated monitoring** - Build scripts with guaranteed controlled execution

### Example Workflow

```bash
# 1. Write a diagnostic script (Python 3.6 compatible)
cat > check_system.py <<'EOF'
import subprocess
import os

# Check disk space
print("=== Disk Usage ===")
subprocess.call(['df', '-h'])

# Check memory
print("\n=== Memory Info ===")
with open('/proc/meminfo', 'r') as f:
    for line in f.readlines()[:5]:
        print(line.strip())

# List running processes
print("\n=== Processes ===")
subprocess.call(['ps', 'aux'])
EOF

# 2. Run in sandbox (operations queue for approval)
shannot run check_system.py

# 3. Review and approve subprocess calls
shannot approve

# With remote execution on production server
shannot run check_system.py --target prod-server

# Check status
shannot status
```

## Configuration

Shannot uses command approval profiles to control subprocess execution behavior:

- **Auto-approve list** - Commands like `ls`, `cat`, `grep` execute immediately
- **Always deny list** - Dangerous commands like `rm -rf /` are blocked
- **Profile locations**:
  - Project-local: `.shannot/profile.json`
  - Global: `~/.config/shannot/profile.json`

Example profile:

```json
{
  "auto_approve": [
    "cat", "ls", "find", "grep", "head", "tail"
  ],
  "always_deny": [
    "rm -rf /",
    "dd if=/dev/zero"
  ]
}
```

## Security Considerations

⚠️ **Important**: Shannot provides strong isolation but **is not a complete security boundary**.

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

**For production use**, combine Shannot with:
- Resource limits (systemd, cgroups)
- Principle of least privilege (dedicated service accounts)
- Regular security updates

See [SECURITY.md](SECURITY.md) for detailed security considerations.

## License

See LICENSE file for details.
