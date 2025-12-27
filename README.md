# Shannot

[![Tests](https://github.com/corv89/shannot/actions/workflows/test.yml/badge.svg)](https://github.com/corv89/shannot/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/os-linux-green.svg)](https://www.kernel.org/)

**Human-in-the-loop execution for LLM agents.**

Shannot lets you see what AI agents want to do before they do it. Scripts run in a supervised environment that captures all commands and file writes. You review in a TUI, approve what's safe, and only then do changes apply.

No more `--dangerously-skip-permissions`.

## How It Works

```mermaid
flowchart LR
    A[🤖 Agent writes script] --> B[shannot run]
    B --> C[📋 Intent captured]
    C --> D[shannot approve]
    D --> E[👤 Human reviews]
    E -->|✓| F[✅ Executes]
    E -->|✗| G[🚫 Blocked]
```

## Quick Start

```bash
# Install
pip install shannot

# Run a script (captures what it wants to do)
shannot run fix-nginx.py

# Review and approve
shannot approve
```

That's it. Two commands.

## Features

**Supervised Execution**
- All system calls intercepted via PyPy sandbox
- Commands captured during dry-run, executed only after approval
- File writes captured with full content, committed only after approval
- Diff preview for every file modification

**Remote Execution**
- Run scripts on remote Linux servers via SSH
- Zero dependencies on target — binary deployment
- Same approval workflow, regardless of where code runs

```bash
shannot run fix-nginx.py --target admin@prod.example.com
shannot approve
```

**Zero Dependencies**
- Pure Python stdlib — nothing to install beyond Python 3.11+
- PyPy sandbox runtime auto-downloads on first use
- Works out of the box on any Linux system

**Danger Classification**
- Commands color-coded by risk in TUI
- Auto-approve safe operations (ls, cat, df)
- Always-deny destructive patterns (rm -rf /)
- Everything else requires human review

## Installation

```bash
# Recommended
pip install shannot

# Or with uv
uv tool install shannot

# Or with pipx
pipx install shannot
```

**Requirements:**
- Python 3.11+ (host system)
- Linux (sandbox execution) or macOS (remote execution only)

**Note:** Scripts run in Python 3.6 (the PyPy sandbox version).

## CLI Reference

```bash
# Core workflow
shannot run <script.py>       # Capture intent
shannot run -c "print(1+1)"   # Inline code
shannot approve               # Review and execute

# Execute specific session
shannot run --session <id>    # Execute approved session
shannot run --session <id> --json-output  # Machine-friendly

# Remote execution
shannot run <script.py> --target user@host

# Setup
shannot setup                 # Interactive menu
shannot setup runtime         # Install PyPy sandbox
shannot setup remote add prod admin@prod.example.com
shannot setup remote test prod
shannot setup mcp install     # Claude Desktop integration

# Status
shannot status                # Runtime, config, pending sessions
```

## Configuration

Single TOML file: `~/.config/shannot/config.toml` (or `.shannot/config.toml` per-project)

```toml
[profile]
auto_approve = [
  "ls", "cat", "head", "tail", "df", "ps", "grep", "find",
  "systemctl status", "journalctl",
]
always_deny = [
  "rm -rf /", "rm -rf ~", "dd if=", "mkfs",
  "curl | sh", "wget | bash",
]

[audit]
enabled = true
rotation = "daily"
max_files = 30

[remotes.prod]
host = "prod.example.com"
user = "admin"

[remotes.staging]
host = "staging.local"
user = "deploy"
```

## Why Not Just Use a Container?

| Approach | Trade-off |
|----------|-----------|
| VM/Container | Agent can't do real work — isolated from your actual system |
| WASM | Capability-restricted — limited to what you expose |
| Policy sandbox | Static rules — can't adapt to context |
| **Shannot** | Agent does real work, with human approval |

Shannot is collaborative, not adversarial. The agent helps you. You stay in control.

## Use Cases

**LLM-assisted sysadmin** — Let Claude diagnose and fix server issues, with you approving each change

**Safe exploration** — Run unfamiliar scripts knowing you'll see exactly what they want to do

**Audited automation** — Every command and file write logged, nothing happens without approval

**Teaching** — Show students what scripts do before execution

## Security Model

Shannot provides **supervised execution**, not absolute isolation.

**What it provides:**
- System call interception via PyPy sandbox
- Virtual filesystem — scripts see only what you expose
- Command and file write approval workflow
- Conflict detection for file modifications
- Audit logging

**What it doesn't provide:**
- Memory/CPU limits (use cgroups separately)
- Network filtering (sockets are disabled entirely)
- Protection against PyPy sandbox escapes

For production, combine with:
- Dedicated service accounts (least privilege)
- Resource limits (systemd, cgroups)
- Network segmentation

See [SECURITY.md](SECURITY.md) for details.

## MCP Integration

Shannot includes an MCP server for Claude Desktop:

```bash
shannot setup mcp install
```

This lets Claude propose scripts directly, which you review and approve through the standard workflow.

## License

Apache 2.0 — See [LICENSE](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)
