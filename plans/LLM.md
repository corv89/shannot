# LLM Integration - Planning Notes

**Status**: MCP Phase 1 Complete, Pydantic-AI Phase 4 Pending

## Overview

Two approaches for LLM integration with Shannot:
1. **MCP Server** - For end-user tools (Claude Desktop, etc.)
2. **Pydantic-AI Agent** - For developers building custom applications

## Approach 1: MCP Server (COMPLETE ✅)

### What It Is
MCP (Model Context Protocol) is Anthropic's standard for connecting Claude Desktop to external tools.

### Status: Phase 1 MVP Complete

**Implemented**:
- Pydantic-AI tools layer (reusable core)
- MCP server wrapper
- Profile auto-discovery
- CLI integration (`shannot mcp install/test`)
- 112 comprehensive tests

**Usage**:
```bash
pip install shannot[mcp]
shannot mcp install
# Restart Claude Desktop
# Ask: "Check my disk space"
```

### When to Use MCP
- ✅ End-users with Claude Desktop
- ✅ Quick diagnostics via chat
- ✅ Shared tools across organization
- ✅ No coding required
- ❌ NOT for automated workflows
- ❌ NOT for programmatic control

## Approach 2: Pydantic-AI Agent (PLANNED 🔮)

### What It Is
Pydantic-AI is a framework for building AI agents with structured outputs and type-safe tool calling.

### Status: Phase 4 (Not Started)

**Goal**: Expose Shannot's tools as a pre-configured Pydantic-AI agent that developers can use in custom applications.

**Example**:
```python
from shannot.agent import create_diagnostics_agent

# Create pre-configured agent
agent = create_diagnostics_agent(profile="diagnostics")

# Use in your application
result = await agent.run("Check if disk is full and why")
print(result.data)  # Structured output
```

### When to Use Pydantic-AI
- ✅ Building custom applications
- ✅ Automated monitoring/alerting
- ✅ Multi-step workflows
- ✅ Structured outputs needed
- ✅ Programmatic control
- ❌ NOT for end-user chat (use MCP)

## Use Case Comparison

### Use Case 1: End-User Chat → **MCP**
Developer wants Claude Desktop to check their Linux server.
```bash
shannot mcp install
# Ask Claude: "Is my disk full?"
```

### Use Case 2: Monitoring Dashboard → **Pydantic-AI**
Developer builds a web dashboard with AI-powered diagnostics.
```python
agent = create_diagnostics_agent()
result = await agent.run(user_query)
return {"diagnosis": result.data}
```

### Use Case 3: Shared Team Tools → **MCP**
Team wants everyone to use Claude Desktop for server diagnostics.
```bash
# Share config across team
shannot mcp install --profile diagnostics
```

### Use Case 4: Automated Alerting → **Pydantic-AI**
Cron job monitors disk space, alerts if issues found.
```python
async def check_and_alert():
    agent = create_diagnostics_agent()
    result = await agent.run("Check disk space")
    if result.data.usage > 90:
        send_alert(result.data)
```

### Use Case 5: Multi-Step Workflow → **Pydantic-AI**
Complex diagnostic workflow with multiple steps.
```python
async def diagnose_disk_full():
    agent = create_diagnostics_agent()

    # Step 1: Check disk
    disk = await agent.run("Check disk usage")

    # Step 2: If full, find largest files
    if disk.data.usage > 90:
        large_files = await agent.run("Find largest files in /var")

    # Step 3: Generate report
    return {"disk": disk.data, "large_files": large_files.data}
```

## Decision Tree

```
┌─────────────────────────────────────┐
│  Who will use this?                 │
└─────────────────────────────────────┘
           │
           ├─ End users (chat) ────────────────► MCP Server
           │
           └─ Developers (code) ───────────────► Pydantic-AI Agent
                      │
                      ├─ Interactive chat ─────► MCP Server
                      │
                      └─ Programmatic ─────────► Pydantic-AI Agent
                                 │
                                 ├─ One-off diagnostics ──► MCP Server
                                 │
                                 └─ Automated/complex ────► Pydantic-AI Agent
```

## Layered Architecture (Recommended)

**Current Reality**:
```
┌─────────────────────────────────────┐
│    MCP Interface (Claude Desktop)   │
├─────────────────────────────────────┤
│    MCP Server (mcp_server.py)       │
├─────────────────────────────────────┤
│    Pydantic-AI Tools (tools.py)     │  ← Reusable!
├─────────────────────────────────────┤
│    SandboxManager (sandbox.py)      │
└─────────────────────────────────────┘
```

**Future (Phase 4)**:
```
┌─────────────────┬───────────────────────────┐
│  MCP Interface  │  Pydantic-AI Agent API    │
├─────────────────┴───────────────────────────┤
│       Pydantic-AI Tools (tools.py)          │  ← Shared!
├─────────────────────────────────────────────┤
│       SandboxManager (sandbox.py)           │
└─────────────────────────────────────────────┘
```

**Benefit**: One tool implementation, multiple interfaces.

## Implementation Roadmap

### ✅ Phase 1: MCP Server MVP (COMPLETE)
- [x] Pydantic-AI tools layer
- [x] MCP server wrapper
- [x] Profile auto-discovery
- [x] CLI integration
- [x] Tests

### 🔜 Phase 2: Enhanced MCP (NEXT - 2-3 weeks)
- [ ] Per-command tools (better UX)
- [ ] Rate limiting
- [ ] Audit logging
- [ ] MCP + Remote execution
- [ ] Input sanitization
- [ ] Output filtering

### 📦 Phase 3: Distribution (3-4 weeks)
- [ ] PyPI release
- [ ] Docker image
- [ ] systemd service
- [ ] Video tutorial
- [ ] Blog post

### 🔧 Phase 4: Pydantic-AI Agent API (6-8 weeks)

**Deliverables**:
1. `shannot/agent.py` - Pre-configured agent factory
2. Example applications:
   - FastAPI monitoring endpoint
   - CLI diagnostic tool
   - Cron job monitor
3. Developer documentation
4. Structured output models

**Implementation**:
```python
# shannot/agent.py
from pydantic_ai import Agent
from .tools import (
    run_command, read_file, list_directory,
    check_disk_usage, check_memory, search_files, grep_content
)

def create_diagnostics_agent(
    profile_name: str = "diagnostics",
    executor: Optional[SandboxExecutor] = None
) -> Agent:
    """Create pre-configured diagnostics agent"""

    deps = SandboxDeps(profile_name, executor=executor)

    agent = Agent(
        "openai:gpt-4",
        deps_type=SandboxDeps,
        system_prompt="""You are a Linux system diagnostics assistant.
        You can check disk space, memory, processes, and read files.
        Always provide clear explanations with your findings."""
    )

    # Register all tools
    agent.tool(run_command)
    agent.tool(read_file)
    agent.tool(list_directory)
    agent.tool(check_disk_usage)
    agent.tool(check_memory)
    agent.tool(search_files)
    agent.tool(grep_content)

    return agent
```

**Example Applications**:
```python
# examples/fastapi_monitor.py
from fastapi import FastAPI
from shannot.agent import create_diagnostics_agent

app = FastAPI()
agent = create_diagnostics_agent()

@app.post("/diagnose")
async def diagnose(query: str):
    result = await agent.run(query)
    return {"diagnosis": result.data}


# examples/cli_diagnose.py
import asyncio
from shannot.agent import create_diagnostics_agent

async def main():
    agent = create_diagnostics_agent()

    while True:
        query = input("Ask> ")
        if query.lower() == "quit":
            break
        result = await agent.run(query)
        print(result.data)

asyncio.run(main())


# examples/cron_monitor.py
import asyncio
from shannot.agent import create_diagnostics_agent

async def check_and_alert():
    agent = create_diagnostics_agent()
    result = await agent.run("Check disk space and memory")

    if result.data.disk_usage > 90:
        send_alert(f"Disk at {result.data.disk_usage}%")
    if result.data.memory_usage > 95:
        send_alert(f"Memory at {result.data.memory_usage}%")

asyncio.run(check_and_alert())
```

### 🏭 Phase 5: Advanced Features (Future)

- Streaming outputs for long commands
- Multi-profile workflows
- Agent memory/history
- Custom tool registration
- Agent composition (multiple agents)

## Security Considerations

### MCP Server
- ⚠️ Rate limiting needed (Phase 2)
- ⚠️ Audit logging needed (Phase 2)
- ✅ Read-only sandbox (enforced)
- ✅ Network isolation (enforced)

### Pydantic-AI Agent
- Same security as MCP (uses same tools)
- Developer responsible for rate limiting
- Developer responsible for audit logging
- Structured outputs easier to validate

### Recommendations
- Always use read-only profiles
- Enable audit logging in production
- Rate limit API endpoints
- Validate structured outputs
- Monitor for abuse patterns

## Success Metrics

### MCP Integration (Phase 1)
- [x] Claude Desktop can execute commands ✅
- [x] Profile auto-discovery works ✅
- [x] 100% test coverage ✅
- [x] <5min setup time ✅

### Enhanced MCP (Phase 2)
- [ ] Per-command tools improve UX
- [ ] Rate limiting prevents abuse
- [ ] Audit logging tracks all calls
- [ ] Works with remote executors

### Pydantic-AI Agent (Phase 4)
- [ ] Developer can create agent in <10 lines
- [ ] Example apps work out-of-box
- [ ] Structured outputs validate correctly
- [ ] Documentation covers common use cases

## Next Steps

1. **Phase 2: Enhanced MCP** (NEXT)
   - Per-command tools
   - Rate limiting
   - Audit logging
   - Remote execution integration

2. **Phase 3: Distribution**
   - PyPI release
   - Docker image
   - Documentation

3. **Phase 4: Pydantic-AI Agent**
   - Agent factory
   - Example applications
   - Developer docs

---

**See Also**:
- MCP implementation: `plans/MCP.md`
- Remote execution: `plans/REMOTE.md`
- Code: `shannot/tools.py`, `shannot/mcp_server.py`
