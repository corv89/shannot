# MCP Integration - Planning Notes

**Status**: Phase 1 MVP Complete ✅

## What Was Built

A complete MCP server implementation that allows Claude Desktop (and other MCP clients) to interact with Linux systems through Shannot's sandbox.

### Core Implementation

**Files Created**:
- `shannot/tools.py` - Pydantic-AI tool layer (reusable)
- `shannot/mcp_server.py` - MCP server wrapper
- `shannot/mcp_main.py` - Entry point
- CLI integration (`shannot mcp install/test`)
- Comprehensive test suite (112 tests)

**Features**:
- 7 Pydantic-AI tools: run_command, read_file, list_directory, check_disk_usage, check_memory, search_files, grep_content
- Auto-discovery of profiles from `~/.config/shannot/`
- Profile-based tool exposure
- Type-safe with Pydantic models
- Full test coverage

### Architecture

```
┌─────────────────────────────────────┐
│    MCP Interface (Claude Desktop)   │  ← User-facing
├─────────────────────────────────────┤
│    MCP Server (mcp_server.py)       │  ← Protocol layer
├─────────────────────────────────────┤
│    Pydantic-AI Tools (tools.py)     │  ← Reusable core
├─────────────────────────────────────┤
│    SandboxManager (sandbox.py)      │  ← Existing
├─────────────────────────────────────┤
│    bubblewrap + Linux namespaces    │  ← System
└─────────────────────────────────────┘
```

**Key Design**: Tools are independent of MCP protocol, can be reused for future Pydantic-AI agents.

## Current Status

### ✅ Phase 1: MCP Server MVP (COMPLETE)

- [x] Pydantic-AI tools layer
- [x] MCP server wrapper
- [x] Profile auto-discovery
- [x] CLI installation command
- [x] Testing command
- [x] Comprehensive test suite
- [x] Documentation

**Usage**:
```bash
pip install shannot[mcp]
shannot mcp install
# Restart Claude Desktop
# Ask: "Check my disk space"
```

## Roadmap

### 🔜 Phase 2: Enhanced Features (NEXT)

**Per-Command Tools** - Better UX
- Current: One tool per profile (`sandbox_minimal_run`)
- Future: One tool per command (`sandbox_ls`, `sandbox_df`, etc.)
- Impact: Much clearer for Claude what each tool does

**Security Enhancements**:
- Rate limiting (prevent abuse)
- Audit logging (track all tool calls)
- Input sanitization (validate paths, commands)
- Output filtering (redact sensitive data)

**MCP + Remote Execution**:
- Accept executor configuration
- `shannot mcp install --executor prod`
- Claude Desktop executes on remote Linux system
- Dependency: Needs config system (Phase 2 from REMOTE.md)

### 🔮 Phase 3: Distribution

- [ ] PyPI release
- [ ] Docker image with MCP server
- [ ] systemd service file
- [ ] Video tutorial
- [ ] Blog post announcement

### 🔮 Phase 4: Pydantic-AI Agent API

Expose tools as pre-configured Pydantic-AI agent for developers:

```python
from shannot.agent import create_diagnostics_agent

agent = create_diagnostics_agent(profile="diagnostics")
result = await agent.run("Check if disk is full and why")
```

**Use Cases**:
- FastAPI endpoints for monitoring
- CLI tools with AI assistance
- Cron jobs with intelligent diagnostics
- Multi-step workflows

## Testing Status

**Comprehensive test suite**: 112 tests, 100% pass rate

Files:
- `tests/test_tools.py` (25 tests) - Unit tests for Pydantic-AI tools
- `tests/test_mcp_server.py` (16 tests) - Unit tests for MCP server
- `tests/test_mcp_integration.py` (19 tests) - Integration tests
- `tests/test_mcp_security.py` (27 tests) - Security tests

Coverage: ~85% for MCP integration code

## Security Notes

### What's Protected
- ✅ Read-only filesystem
- ✅ Network isolation
- ✅ Ephemeral /tmp
- ✅ Command allowlist
- ✅ Namespace isolation

### What's Exposed
- ⚠️ File contents (Claude can read files)
- ⚠️ System info (processes, disk, memory)

**Use case**: Safe for LLM diagnostics, not a security boundary.

### Enhancements Needed (Phase 2)
- Rate limiting per tool
- Audit logging with timestamps
- Input validation (path traversal, command injection)
- Output filtering (sensitive data redaction)

## Key Design Decisions

### 1. Pydantic-AI from Day One
Build tools with Pydantic-AI even though starting with MCP.

**Rationale**: Reusability - same tools will power future Pydantic-AI agents (Phase 4).

### 2. Profile-Based Tools (Phase 1)
One tool per profile, not per command.

**Rationale**: Simpler MVP. Phase 2 will add per-command tools.

### 3. Auto-Discovery
Automatically load profiles from standard locations.

**Rationale**: Zero-config for most users.

### 4. Layered Architecture
MCP server is thin wrapper around reusable tools.

**Rationale**: Easy to add new interfaces (HTTP API, gRPC, etc.).

## Next Steps

1. **Per-command tools** (Phase 2) - Better Claude Desktop UX
2. **Rate limiting & audit logging** (Phase 2) - Production safety
3. **MCP + Remote execution** (Phase 2) - Depends on config system
4. **PyPI release** (Phase 3) - Easy installation
5. **Pydantic-AI agent** (Phase 4) - Developer API

---

**See Also**:
- Implementation: `shannot/tools.py`, `shannot/mcp_server.py`
- Tests: `tests/test_mcp_*.py`
- User guide: TBD (needs writing)
