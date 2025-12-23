# Execution Module

Session-based execution for sandboxed scripts.

## Overview

Shannot v0.4.0+ uses a session-based approval workflow instead of direct executors.

## Architecture

| Phase | Description |
|-------|-------------|
| Dry-run | Script runs in sandbox, operations captured |
| Review | User reviews captured operations via TUI |
| Execute | Approved operations run on host system |

## Session Workflow

```bash
# 1. Run script (creates session)
shannot run script.py

# 2. Review and approve operations
shannot approve

# 3. Execute approved session
# (done via TUI or shannot execute)
```

## Remote Execution

Remote execution uses SSH with auto-deployment:

```bash
# Add remote target
shannot remote add prod user@host

# Run on remote
shannot run script.py --target prod
```

The remote receives the session data and executes in its own PyPy sandbox.

## Key Modules

| Module | Purpose |
|--------|---------|
| `run_session.py` | Session execution orchestration |
| `session.py` | Session data structures |
| `deploy.py` | Remote deployment |
| `ssh.py` | Zero-dependency SSH client |

## See Also

- [Usage Guide](../usage.md) - Session workflow details
- [Deployment](../deployment.md) - Remote execution setup
- [Configuration](../configuration.md) - Remote targets
