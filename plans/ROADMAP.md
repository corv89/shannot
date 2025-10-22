# Shannot Development Roadmap

**Last Updated**: 2025-10-21
**Status**: Phase 1 Complete, Planning Phase 2

## Current Status

### ✅ Completed (October 2025)

**MCP Integration (Phase 1)**:
- Pydantic-AI tools layer (7 tools)
- MCP server with profile auto-discovery
- CLI integration (`shannot mcp install/test`)
- 112 comprehensive tests
- ~1,071 lines of code

**SSH/Remote Execution (Phase 1)**:
- Abstract `SandboxExecutor` interface
- `LocalExecutor` for Linux
- `SSHExecutor` with connection pooling
- Full backward compatibility
- ~1,025 lines of code

**Total**: ~2,100+ lines of production code, 126+ tests

---

## Roadmap Overview

### Tier 1: Immediate User Value (Next 4-6 weeks)
1. Configuration system for executors
2. MCP + SSH integration
3. Per-command MCP tools
4. PyPI release

### Tier 2: Production Readiness (6-12 weeks)
5. Rate limiting & audit logging
6. User documentation
7. Video tutorials
8. Community building

### Tier 3: Advanced Features (3-6 months)
9. Pydantic-AI agent API
10. HTTP agent (alternative to SSH)
11. Advanced monitoring features

---

## Tier 1: Immediate User Value

### 1. Configuration System for Executors
**Timeline**: Weeks 1-2
**Priority**: 🔥 CRITICAL
**Status**: Not started
**Depends on**: Nothing (ready to start)

**Why Critical**: Makes SSH executor actually usable. Without config, users can't define remotes.

**Deliverables**:
- `shannot/config.py` - TOML config loading (~200 lines)
- `shannot remote` CLI commands (~150 lines)
  - `shannot remote add/list/remove/test`
  - `shannot --target <name> run <cmd>`
- Configuration file format and loading
- Tests (~200 lines)

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

**CLI Usage**:
```bash
# Add a remote
shannot remote add prod --host prod.example.com --user admin

# List remotes
shannot remote list

# Test connection
shannot remote test prod

# Use remote
shannot --target prod run ls /
```

**Files to Create**:
- `shannot/config.py`
- Update `shannot/cli.py`
- `tests/test_config.py`
- `docs/configuration.md` (user guide)

**Success Criteria**:
- [ ] TOML config loads correctly
- [ ] Multiple executors can be defined
- [ ] CLI commands work end-to-end
- [ ] Tests cover all config scenarios
- [ ] Documentation clear for users

**Effort**: ~1-2 weeks

---

### 2. MCP + SSH Integration
**Timeline**: Weeks 2-3
**Priority**: 🔥 HIGH
**Status**: Not started
**Depends on**: #1 (Configuration system)

**Why High Priority**: Enables macOS/Windows users to use Claude Desktop with remote Linux systems.

**Deliverables**:
- MCP server accepts executor config
- `shannot mcp install --target <name>`
- MCP config includes executor settings
- Tests for MCP + SSH flow
- User documentation

**Usage**:
```bash
# Install MCP with remote executor
shannot mcp install --target prod

# Now Claude Desktop executes on prod server
```

**Files to Update**:
- `shannot/mcp_main.py` - Accept executor config
- `shannot/mcp_server.py` - Use configured executor
- `shannot/cli.py` - Update `mcp install` command
- `tests/test_mcp_remote.py` - Integration tests
- `docs/mcp.md` - Add remote section

**Success Criteria**:
- [ ] MCP server can use SSH executor
- [ ] `--target` flag works
- [ ] Claude Desktop executes on remote
- [ ] Clear error messages if SSH fails
- [ ] Documentation covers setup

**Effort**: ~1 week (depends on #1)

---

### 3. Per-Command MCP Tools
**Timeline**: Weeks 3-4
**Priority**: 🟡 MEDIUM
**Status**: Not started
**Depends on**: Nothing (can start now)

**Why Medium Priority**: Improves Claude Desktop UX significantly but not blocking.

**Current State**:
- One tool per profile: `sandbox_diagnostics_run`
- Claude must specify command each time
- Less clear what tools can do

**Future State**:
- One tool per command: `sandbox_ls`, `sandbox_df`, `sandbox_cat`
- Claude knows exactly what each tool does
- Better autocomplete/discovery

**Implementation**:
```python
# Current (profile-level)
@tool
async def sandbox_diagnostics_run(
    deps: SandboxDeps,
    input: CommandInput
) -> CommandOutput:
    """Run a command in diagnostics sandbox"""
    ...

# Future (command-level)
@tool
async def sandbox_df(deps: SandboxDeps) -> CommandOutput:
    """Check disk space with df -h"""
    return await run_command(deps, CommandInput(command=["df", "-h"]))

@tool
async def sandbox_ps(deps: SandboxDeps) -> CommandOutput:
    """List processes with ps aux"""
    return await run_command(deps, CommandInput(command=["ps", "aux"]))
```

**Files to Update**:
- `shannot/mcp_server.py` - Generate per-command tools
- `tests/test_mcp_server.py` - Test tool generation
- `docs/mcp.md` - Update available tools

**Success Criteria**:
- [ ] Each allowed command gets a tool
- [ ] Tool descriptions are clear
- [ ] Backward compatibility maintained
- [ ] Tests pass
- [ ] Claude Desktop UX improves

**Effort**: ~1 week

---

### 4. PyPI Release
**Timeline**: Week 4-5
**Priority**: 🟡 MEDIUM
**Status**: Not started
**Depends on**: #1, #2 (want features ready first)

**Why Medium Priority**: Makes installation easier but not blocking development.

**Deliverables**:
- Polish `pyproject.toml`
- Add long_description from README
- Set up GitHub Actions for releases
- Tag release (v0.1.0)
- Publish to PyPI
- Update docs with `pip install shannot`

**Files to Update**:
- `pyproject.toml` - Polish metadata
- `.github/workflows/release.yml` - Automated releases
- `README.md` - Installation instructions
- `docs/installation.md` - Update

**Success Criteria**:
- [ ] `pip install shannot` works
- [ ] `pip install shannot[mcp]` works
- [ ] `pip install shannot[remote]` works
- [ ] `pip install shannot[all]` works
- [ ] Version numbers automated
- [ ] Release notes generated

**Effort**: ~3-5 days

---

## Tier 2: Production Readiness

### 5. Rate Limiting & Audit Logging
**Timeline**: Weeks 5-7
**Priority**: 🟡 MEDIUM
**Status**: Not started

**Why**: Production deployments need abuse prevention and security auditing.

**Deliverables**:
- Rate limiter per tool/user
- Audit logger for all tool calls
- Configuration for limits
- Log rotation
- Alerting on abuse

**Implementation**:
```python
# Rate limiting
class RateLimiter:
    def __init__(self, max_calls: int, window: int):
        self.max_calls = max_calls
        self.window = window  # seconds

    async def check(self, key: str) -> bool:
        # Token bucket or sliding window
        ...

# Audit logging
class AuditLogger:
    def log_tool_call(
        self,
        tool_name: str,
        input: dict,
        output: dict,
        user: str,
        timestamp: datetime
    ):
        # Log to file/database
        ...
```

**Files to Create**:
- `shannot/ratelimit.py`
- `shannot/audit.py`
- Update `shannot/mcp_server.py`
- `tests/test_ratelimit.py`
- `tests/test_audit.py`

**Success Criteria**:
- [ ] Rate limiting prevents abuse
- [ ] All tool calls logged
- [ ] Logs include timestamp, user, input, output
- [ ] Configurable limits
- [ ] Tests cover edge cases

**Effort**: ~1-2 weeks

---

### 6. User Documentation
**Timeline**: Weeks 6-8
**Priority**: 🟢 LOW
**Status**: Partial (basic docs exist)

**Why**: Users need clear guides, not planning docs.

**Deliverables**:
- `docs/remote-execution-guide.md` - How to use SSH executor
- `docs/mcp-guide.md` - Complete MCP setup
- `docs/configuration.md` - Config file reference
- `docs/troubleshooting.md` - Common issues
- Update `README.md` with new features

**Topics to Cover**:
- SSH setup (keys, known_hosts, etc.)
- Remote executor configuration
- MCP + remote integration
- Security best practices
- Common errors and fixes

**Success Criteria**:
- [ ] New user can setup SSH in <15 min
- [ ] MCP + remote works first try
- [ ] Troubleshooting covers 90% of issues
- [ ] Examples are copy-pasteable
- [ ] Screenshots where helpful

**Effort**: ~1-2 weeks

---

### 7. Video Tutorials & Community
**Timeline**: Weeks 8-10
**Priority**: 🟢 LOW
**Status**: Not started

**Why**: Grow user base and get feedback.

**Deliverables**:
- 5-10 min video: "Getting Started with Shannot MCP"
- 5-10 min video: "Remote Execution with SSH"
- Blog post announcement
- Post on Reddit/HackerNews
- GitHub Discussions setup

**Success Criteria**:
- [ ] Videos uploaded to YouTube
- [ ] Blog post published
- [ ] Community channels active
- [ ] Feedback collected
- [ ] Issues filed by users

**Effort**: ~1-2 weeks

---

## Tier 3: Advanced Features

### 8. Pydantic-AI Agent API
**Timeline**: Weeks 11-14 (3+ months out)
**Priority**: 🟢 LOW
**Status**: Not started

**Why**: Enables developers to build custom applications with Shannot.

**Deliverables**:
- `shannot/agent.py` - Pre-configured agent factory
- Example applications:
  - FastAPI monitoring endpoint
  - CLI diagnostic tool
  - Cron job monitor
- Developer documentation
- Structured output models

**Implementation**:
```python
from shannot.agent import create_diagnostics_agent

# Create agent
agent = create_diagnostics_agent(profile="diagnostics")

# Use in app
result = await agent.run("Check if disk is full and why")
print(result.data)  # Structured output
```

**Files to Create**:
- `shannot/agent.py`
- `examples/fastapi_monitor.py`
- `examples/cli_diagnose.py`
- `examples/cron_monitor.py`
- `docs/pydantic-ai-guide.md`
- `tests/test_agent.py`

**Success Criteria**:
- [ ] Agent creation in <10 lines
- [ ] Example apps work out-of-box
- [ ] Structured outputs validate
- [ ] Developer docs clear
- [ ] Community adoption

**Effort**: ~3-4 weeks

---

### 9. HTTP Agent (Alternative to SSH)
**Timeline**: Weeks 15-18 (4+ months out)
**Priority**: 🟢 LOW
**Status**: Not started

**Why**: Better for cloud/containerized deployments than SSH.

**Architecture**:
```
┌──────────────────────┐
│  Local System        │
│  - MCP/Agent         │
│  - HTTP client       │
└──────────────────────┘
         ↓ HTTPS
┌──────────────────────┐
│  Remote Container    │
│  - shannot-agent     │
│  - REST API          │
│  - bubblewrap        │
└──────────────────────┘
```

**Deliverables**:
- `HTTPExecutor` implementation
- `shannot-agent` HTTP server
- Token-based authentication
- Docker image
- Kubernetes deployment example

**Files to Create**:
- `shannot/executors/http.py`
- `shannot/agent_server.py`
- `Dockerfile`
- `k8s/deployment.yaml`
- `tests/test_http_executor.py`

**Success Criteria**:
- [ ] HTTP executor works like SSH
- [ ] Token auth secure
- [ ] Docker image <100MB
- [ ] K8s deployment works
- [ ] Documentation complete

**Effort**: ~3-4 weeks

---

### 10. Advanced Monitoring Features
**Timeline**: Months 5-6
**Priority**: 🟢 LOW
**Status**: Not started

**Why**: Power user features for production deployments.

**Ideas**:
- Streaming output for long commands
- Progress indicators
- Multi-step workflows
- Agent memory/history
- Custom tool registration
- Metrics collection
- Prometheus exporter

**Details**: TBD (collect user feedback first)

---

## Prioritization Framework

### Must Have (Before v1.0)
1. ✅ MCP integration
2. ✅ SSH executor
3. 🔥 Configuration system
4. 🔥 MCP + SSH integration
5. 🟡 PyPI release
6. 🟡 Basic documentation

### Should Have (v1.1-1.2)
7. 🟡 Per-command tools
8. 🟡 Rate limiting
9. 🟡 Audit logging
10. 🟡 User guides

### Nice to Have (v2.0+)
11. 🟢 Pydantic-AI agent
12. 🟢 HTTP executor
13. 🟢 Advanced features

---

## Next Steps (This Week)

### Immediate Actions
1. **Start configuration system** (#1)
   - Create `shannot/config.py`
   - Implement TOML loading
   - Add `shannot remote` CLI commands

2. **Test SSH executor manually**
   - Verify it works on real systems
   - Document setup steps
   - Identify pain points

3. **Plan MCP + SSH integration** (#2)
   - Design executor config in MCP
   - Plan CLI flags
   - Write integration tests

### This Sprint (Next 2 Weeks)
- [ ] Complete configuration system (#1)
- [ ] Start MCP + SSH integration (#2)
- [ ] Write user guide for SSH setup (#6 partial)

### This Month (Next 4 Weeks)
- [ ] Finish MCP + SSH integration (#2)
- [ ] Implement per-command tools (#3)
- [ ] Prepare PyPI release (#4)

---

## Success Metrics

### Phase 1 (Complete ✅)
- [x] MCP server works with Claude Desktop
- [x] SSH executor implemented
- [x] 100% test coverage
- [x] <5min setup for MCP

### Phase 2 (In Progress)
- [ ] Users can configure remotes easily
- [ ] macOS users can use Claude with Linux servers
- [ ] `pip install shannot` works
- [ ] Documentation covers 90% of use cases

### Phase 3 (Future)
- [ ] Developers build apps with Pydantic-AI
- [ ] Community contributions active
- [ ] Production deployments running
- [ ] 1000+ PyPI downloads

---

## Questions & Decisions

### Open Questions
1. Should we support Windows SSH client? (Currently Unix-only)
2. Do we need SSH agent support? (Currently key files only)
3. What's the right rate limit default? (TBD)
4. Should config be TOML or YAML? (Current: TOML)
5. Do we need HTTP executor or is SSH enough? (Defer to user feedback)

### Decisions Made
- ✅ Use TOML for config (more Pythonic)
- ✅ Configuration system before PyPI release
- ✅ Per-command tools as enhancement, not blocker
- ✅ Pydantic-AI agent deferred to Phase 3
- ✅ Focus on SSH before HTTP executor

---

## Resources

### Planning Docs
- `plans/REMOTE.md` - Remote execution notes
- `plans/MCP.md` - MCP integration notes
- `plans/LLM.md` - LLM integration notes
- `plans/archive/` - Completed implementation plans

### Implementation
- `shannot/execution.py` - Executor interface
- `shannot/executors/` - Executor implementations
- `shannot/tools.py` - Pydantic-AI tools
- `shannot/mcp_server.py` - MCP server

### Tests
- `tests/test_executors.py` - Executor tests
- `tests/test_mcp_*.py` - MCP tests
- `tests/test_tools.py` - Tool tests

---

**Maintained by**: Shannot Team
**Review Cadence**: Weekly
**Next Review**: 2025-10-28
