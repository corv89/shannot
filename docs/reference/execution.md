# Execution Module

Session-based execution for sandboxed scripts.

## Overview

Shannot v0.4.0+ uses a session-based approval workflow instead of direct executors.

## Architecture

| Phase | Description |
|-------|-------------|
| Dry-run | Script runs in sandbox, operations captured |
| Review | User reviews captured operations via TUI |
| Checkpoint | Original file content saved before changes |
| Execute | Approved operations run on host system |
| Rollback | (Optional) Restore files to pre-execution state |

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
shannot setup remote add prod user@host

# Run on remote
shannot run script.py --target prod
```

The remote receives the session data and executes in its own PyPy sandbox.

## Key Modules

| Module | Purpose |
|--------|---------|
| `run_session.py` | Session execution orchestration |
| `session.py` | Session data structures |
| `checkpoint.py` | Checkpoint and rollback logic |
| `deploy.py` | Remote deployment |
| `ssh.py` | Zero-dependency SSH client |

## Checkpoint Creation

Before committing writes, Shannot creates a checkpoint:

1. **Blob storage**: Original file content saved as `{hash[:8]}.blob`
2. **Metadata**: Path mappings stored in `session.checkpoint`
3. **Post-exec hashes**: Recorded after writes for conflict detection

Directory structure:

```
~/.local/share/shannot/sessions/{session_id}/
  session.json
  checkpoint/
    a1b2c3d4.blob
    e5f6g7h8.blob
```

## Session Statuses

| Status | Description |
|--------|-------------|
| `pending` | Awaiting approval |
| `approved` | Ready for execution |
| `executed` | Completed successfully |
| `rolled_back` | Restored to pre-execution state |
| `expired` | TTL exceeded |

## See Also

- [Usage Guide](../usage.md) - Session workflow details
- [Deployment](../deployment.md) - Remote execution setup
- [Configuration](../configuration.md) - Remote targets
