# Remote Execution - Planning Notes

**Status**: Phase 1 Complete (SSH Executor implemented)

## Overview

Enable Shannot execution on remote Linux systems from local macOS/Windows machines without deploying Python dependencies to remote systems.

## Implemented Solution: SSH-Based Execution

**Architecture**:
```
┌────────────────────────────────────┐
│  Local System (any OS)             │
│  - Full shannot with dependencies  │
│  - MCP server                      │
│  - SSH client                      │
└────────────────────────────────────┘
              ↓ SSH
┌────────────────────────────────────┐
│  Remote Linux System               │
│  Requirements:                     │
│  - bubblewrap only                 │
│  - SSH server                      │
│  - No Python/Shannot needed        │
└────────────────────────────────────┘
```

**How It Works**:
1. Local system builds bubblewrap command from profile
2. SSH transport sends command to remote
3. Remote executes `bwrap`, returns output
4. Local system processes results

## Implementation Status

### ✅ Phase 1: Executor Abstraction (COMPLETE)
- `SandboxExecutor` abstract interface
- `LocalExecutor` for Linux systems
- `SSHExecutor` for remote execution
- Connection pooling for performance
- Full backward compatibility
- Comprehensive tests

**Code**: `shannot/execution.py`, `shannot/executors/`

### 🔜 Phase 2: Configuration & CLI (NEXT)

**Needed**:
- Configuration file for multiple remotes
- CLI commands for remote management
- MCP integration with remote executors

**Config Example**:
```toml
# ~/.config/shannot/config.toml
default_executor = "local"

[executor.local]
type = "local"

[executor.prod]
type = "ssh"
host = "prod-server.example.com"
username = "admin"
key_file = "~/.ssh/id_ed25519"
port = 22

[executor.staging]
type = "ssh"
host = "staging.example.com"
username = "deploy"
```

**CLI Commands**:
```bash
shannot remote add prod --host prod.example.com --user admin
shannot remote list
shannot remote test prod
shannot --executor prod run ls /
```

**MCP Integration**:
```bash
shannot mcp install --executor prod
# Claude Desktop now executes on remote system
```

### 🔮 Phase 3: HTTP Agent (FUTURE - Optional)

Alternative to SSH for cloud environments:
- REST API on remote system
- Better for containerized deployments
- Token-based authentication
- Lower priority than SSH

## Security Considerations

### SSH Executor
- ✅ SSH encryption for transport
- ✅ Key-based authentication
- ⚠️ Host key validation (should be required)
- ⚠️ Key storage on filesystem
- ✅ Same sandbox constraints on remote

### Recommendations
- Use dedicated SSH keys for Shannot
- Configure `known_hosts` for host validation
- Use SSH users with minimal privileges
- Monitor SSH access logs
- Consider SSH agent integration

## Testing Notes

- Unit tests: Mock SSH connections
- Integration tests: Real SSH (docker-based)
- Platform tests: macOS → Linux, Windows → Linux

## Next Steps

1. Create `shannot/config.py` for TOML loading
2. Add `shannot remote` CLI commands
3. Update MCP server to accept executor config
4. Write integration tests for real SSH
5. Document SSH setup for users

---

**See Also**:
- Implementation details: `shannot/executors/ssh.py`
- Architecture: Executor abstraction in `shannot/execution.py`
- User guide: TBD (needs writing after Phase 2)
