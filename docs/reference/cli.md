# CLI Module

Command-line interface for Shannot.

## Overview

The CLI provides commands for sandbox execution, session approval, and system management.

## Commands

### shannot setup

Interactive setup menu or configuration subcommands.

```bash
shannot setup                      # Interactive setup menu
shannot setup runtime              # Install runtime
shannot setup runtime --force      # Force reinstall
shannot setup runtime --status     # Check if installed
shannot setup runtime --remove     # Remove runtime
shannot setup remote               # Interactive remote management
shannot setup mcp                  # Interactive MCP setup
```

### shannot run

Execute a Python script in the PyPy sandbox.

```bash
shannot run script.py                    # Basic execution
shannot run script.py --tmp=/tmp/work    # Map real directory to /tmp
shannot run script.py --dry-run          # Queue without executing
shannot run script.py --target prod      # Execute on remote
```

**Options:**

| Option | Description |
|--------|-------------|
| `--pypy-sandbox PATH` | Path to pypy-sandbox executable |
| `--lib-path PATH` | Path to lib-python and lib_pypy |
| `--tmp DIR` | Real directory mapped to virtual /tmp |
| `--dry-run` | Log commands without executing |
| `--target NAME` | SSH target for remote execution |
| `--debug` | Enable debug mode |

### shannot approve

Interactive TUI for reviewing and approving sessions.

```bash
shannot approve                    # Launch TUI
shannot approve list               # List pending sessions
shannot approve show SESSION_ID    # Show session details
shannot approve history            # Show recent sessions
```

**TUI Controls:**

| Key | Action |
|-----|--------|
| `j/k` or arrows | Navigate |
| `Enter` | View details / Execute |
| `Space` | Toggle selection |
| `x` | Execute selected |
| `r` | Reject selected |
| `q` / `Esc` | Quit |

### shannot setup remote

Manage SSH remote targets.

```bash
shannot setup remote add NAME [USER@]HOST    # Add target
shannot setup remote list                     # List targets
shannot setup remote test NAME                # Test connection
shannot setup remote remove NAME              # Remove target
```

### shannot status

Show system health and configuration.

```bash
shannot status             # Full status
shannot status --runtime   # Runtime only
shannot status --targets   # Remote targets only
```

### shannot setup mcp

MCP server management.

```bash
shannot setup mcp install                         # Install for Claude Desktop
shannot setup mcp install --client claude-code    # Install for Claude Code
```

### shannot rollback

Rollback session changes to pre-execution state.

```bash
shannot rollback <session_id>           # Rollback with conflict check
shannot rollback <session_id> --force   # Skip conflict detection
shannot rollback <session_id> --dry-run # Preview without making changes
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `session_id` | Session ID to rollback |

**Options:**

| Option | Description |
|--------|-------------|
| `--force`, `-f` | Skip conflict detection |
| `--dry-run`, `-n` | Preview without making changes |

**Exit Codes:**

| Code | Meaning |
|------|---------|
| 0 | Rollback successful |
| 1 | Conflict detected (use --force to override) |
| 2 | Session not found or no checkpoint |

### shannot checkpoint

Manage session checkpoints.

```bash
shannot checkpoint list           # List sessions with checkpoints
shannot checkpoint show <id>      # Show checkpoint details
```

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| `list` | List sessions with available checkpoints |
| `show <session_id>` | Show checkpoint details for a session |

## See Also

- [Usage Guide](../usage.md) - Comprehensive examples
- [Configuration](../configuration.md) - Profiles and remotes
- [MCP Integration](../mcp.md) - MCP setup
