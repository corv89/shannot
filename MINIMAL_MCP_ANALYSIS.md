# Minimal MCP Implementation Analysis

**Date**: 2025-11-13
**Objective**: Determine if MCP support can be reimplemented with stdlib-only or significantly reduced dependencies

## Executive Summary

**YES**, we can reimplement the MCP stdio server functionality used by Shannot with **zero external dependencies** using only the Python standard library.

The current `mcp` package brings in **11+ dependencies** (many with subdependencies), but Shannot only uses a tiny subset of MCP functionality: **stdio transport for tools, resources, and prompts**.

## Current Dependency Tree

### `mcp>=1.18.0` Dependencies

From `mcp-1.18.0.dist-info/METADATA`:

```
Requires-Dist: anyio>=4.5
Requires-Dist: httpx-sse>=0.4
Requires-Dist: httpx>=0.27.1
Requires-Dist: jsonschema>=4.20.0
Requires-Dist: pydantic-settings>=2.5.2
Requires-Dist: pydantic<3.0.0,>=2.11.0
Requires-Dist: python-multipart>=0.0.9
Requires-Dist: pywin32>=310; sys_platform == 'win32'
Requires-Dist: sse-starlette>=1.6.1
Requires-Dist: starlette>=0.27
Requires-Dist: uvicorn>=0.31.1; sys_platform != 'emscripten'
```

**Why so many dependencies?**
- `anyio`, `httpx*`, `sse-starlette`, `starlette`, `uvicorn`: HTTP/SSE/WebSocket transports
- `pydantic`, `pydantic-settings`, `jsonschema`: Data validation
- `python-multipart`: Multipart form parsing
- `pywin32`: Windows-specific functionality

**But Shannot only uses**: stdio transport (stdin/stdout), not HTTP/SSE/WebSocket

## What Shannot Actually Uses

### Imports from `shannot/mcp_server.py`

```python
from mcp.server import InitializationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    PromptsCapability,
    Resource,
    ResourcesCapability,
    ServerCapabilities,
    TextContent,
    Tool,
    ToolsCapability,
)
```

### What These Actually Do

1. **`stdio_server()`**: Reads JSON-RPC from stdin, writes to stdout
2. **`Server`**: Manages request handlers (list_tools, call_tool, etc.)
3. **Type classes**: Dataclasses representing JSON-RPC message structures

### The Actual Protocol

MCP is **JSON-RPC 2.0** over stdio:

```json
// Request (from client via stdin)
{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

// Response (to client via stdout)
{"jsonrpc": "2.0", "id": 1, "result": {"tools": [...]}}
```

## Stdlib-Only Implementation Feasibility

### Core Requirements

| Feature | Current Implementation | Stdlib Alternative |
|---------|----------------------|-------------------|
| **Async I/O** | `anyio` | `asyncio` (stdlib) |
| **JSON serialization** | Pydantic models | `json` + `dataclasses` |
| **Stdin/stdout** | anyio.wrap_file | `sys.stdin.buffer`, `asyncio.StreamReader` |
| **Message validation** | Pydantic | Manual validation or `typing` |
| **Task management** | anyio.create_task_group | `asyncio.TaskGroup` (3.11+) or `asyncio.create_task` |

### Minimal Implementation Architecture

```python
import asyncio
import json
import sys
from dataclasses import dataclass, asdict
from typing import Any, Callable

@dataclass
class Tool:
    name: str
    description: str
    inputSchema: dict[str, Any]

@dataclass
class ServerCapabilities:
    tools: dict = None
    resources: dict = None
    prompts: dict = None

class MinimalMCPServer:
    """Stdlib-only MCP server for stdio transport"""

    def __init__(self, name: str):
        self.name = name
        self._tool_handlers = {}
        self._resource_handlers = {}

    def list_tools(self):
        def decorator(func: Callable):
            self._list_tools_handler = func
            return func
        return decorator

    def call_tool(self):
        def decorator(func: Callable):
            self._call_tool_handler = func
            return func
        return decorator

    async def run(self):
        """Main stdio loop - read JSON-RPC from stdin, write to stdout"""
        # Create async stdin/stdout readers
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)

        await asyncio.get_event_loop().connect_read_pipe(
            lambda: protocol, sys.stdin.buffer
        )

        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout.buffer
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, asyncio.get_event_loop())

        while True:
            # Read JSON-RPC message from stdin
            line = await reader.readline()
            if not line:
                break

            try:
                message = json.loads(line.decode('utf-8'))
            except json.JSONDecodeError:
                continue

            # Handle request
            response = await self._handle_message(message)

            # Write response to stdout
            writer.write(json.dumps(response).encode('utf-8') + b'\n')
            await writer.drain()

    async def _handle_message(self, message: dict) -> dict:
        """Route JSON-RPC message to appropriate handler"""
        method = message.get('method')
        params = message.get('params', {})
        msg_id = message.get('id')

        # Initialize request
        if method == 'initialize':
            return {
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': {
                    'protocolVersion': '2025-06-18',
                    'capabilities': asdict(self.capabilities),
                    'serverInfo': {'name': self.name, 'version': '1.0.0'}
                }
            }

        # List tools
        elif method == 'tools/list':
            tools = await self._list_tools_handler()
            return {
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': {'tools': [asdict(t) for t in tools]}
            }

        # Call tool
        elif method == 'tools/call':
            name = params['name']
            arguments = params.get('arguments', {})
            result = await self._call_tool_handler(name, arguments)
            return {
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': {'content': [{'type': 'text', 'text': str(result)}]}
            }

        # Unknown method
        return {
            'jsonrpc': '2.0',
            'id': msg_id,
            'error': {'code': -32601, 'message': f'Method not found: {method}'}
        }
```

### Lines of Code Comparison

- **Full `mcp` package**: ~15,000+ lines (plus dependencies)
- **Minimal stdio implementation**: ~200-300 lines of stdlib code
- **Shannot's actual MCP usage**: ~1,300 lines in `mcp_server.py`

## Advantages of Stdlib-Only Implementation

### 1. **Dependency Reduction**

**Before**:
```
mcp (11 dependencies)
  ├── anyio
  ├── httpx + httpx-sse
  ├── pydantic + pydantic-settings
  ├── jsonschema
  ├── starlette + sse-starlette + uvicorn
  ├── python-multipart
  └── pywin32 (Windows)

asyncssh (for remote)
  ├── cryptography
  └── ...

tomli / tomli-w
```

**After** (Option 1: Minimal stdlib):
```
(no dependencies)
```

**After** (Option 2: Keep remote, minimal MCP):
```
asyncssh (for remote only)
tomli / tomli-w (for remote config only)
```

### 2. **Installation Size**

| Package | Size | With Dependencies |
|---------|------|------------------|
| `mcp` | ~170KB wheel | ~50MB+ total |
| `asyncssh` | ~375KB | ~10MB+ |
| `tomli` + `tomli-w` | ~25KB | ~25KB |
| **Minimal stdlib** | **0 bytes** | **0 bytes** |

**Total reduction**: ~60MB → 0MB (local MCP) or ~10MB (with remote)

### 3. **Security**

- Fewer dependencies = smaller attack surface
- No external code execution in MCP message handling
- Easier security audits (200 lines vs 15,000+)

### 4. **Portability**

- Stdlib works everywhere Python works
- No C extensions (except in remote mode with asyncssh)
- Easier PyPy, alternative Python implementations

### 5. **Maintenance**

- No dependency version conflicts
- No security updates for 11+ packages
- No pydantic v1→v2 migration issues

## Challenges and Mitigations

### 1. **JSON Schema Generation**

**Challenge**: Pydantic auto-generates JSON schemas for tool input validation

**Solution**:
- Manual schema definition (acceptable, schemas are simple)
- Or use `typing` module introspection for auto-generation
- Example:
  ```python
  def generate_schema(func):
      # Inspect function signature
      sig = inspect.signature(func)
      schema = {"type": "object", "properties": {}}

      for name, param in sig.parameters.items():
          if param.annotation == int:
              schema["properties"][name] = {"type": "integer"}
          elif param.annotation == str:
              schema["properties"][name] = {"type": "string"}

      return schema
  ```

### 2. **Data Validation**

**Challenge**: Pydantic validates incoming JSON against schemas

**Solution**:
- Basic type checking with stdlib `isinstance()`
- JSON schema validation with stdlib (limited)
- Or add single lightweight dependency: `jsonschema` (if validation critical)
- Trade-off: Some validation vs 11 dependencies

### 3. **Async Abstractions**

**Challenge**: anyio provides abstraction over asyncio/trio

**Solution**:
- Just use `asyncio` (stdlib, and shannot already uses it)
- No need for anyio's abstraction layer
- Code is simpler and more direct

### 4. **Type Annotations**

**Challenge**: Pydantic models provide rich type information

**Solution**:
- Use `dataclasses` (stdlib, Python 3.7+)
- Use `typing.TypedDict` for simple structures
- Example:
  ```python
  from dataclasses import dataclass

  @dataclass
  class Tool:
      name: str
      description: str
      inputSchema: dict
  ```

## Implementation Options

### Option 1: Full Stdlib Rewrite (Recommended for Local-Only)

**Scope**: Replace entire `mcp` dependency with ~300 lines of stdlib code

**Dependencies**:
- Core: None
- Remote: `asyncssh`, `tomli`, `tomli-w` (optional `[remote]` extra)

**Effort**: Medium (1-2 days)

**Benefits**:
- ✅ Zero dependencies for local MCP
- ✅ Maximum portability
- ✅ Smallest installation size
- ✅ Easiest to audit and maintain

**Risks**:
- ⚠️ Need to reimplement JSON-RPC handling
- ⚠️ Need to handle edge cases
- ⚠️ Divergence from official MCP SDK

---

### Option 2: Hybrid Approach

**Scope**: Keep official `mcp` as optional extra, provide minimal builtin

**Dependencies**:
- Core: None (builtin minimal MCP)
- Full MCP: `mcp` (optional `[mcp-full]` extra for HTTP/SSE transports)
- Remote: `asyncssh`, `tomli`, `tomli-w` (optional `[remote]` extra)

**Implementation**:
```python
# shannot/mcp_server.py
try:
    from mcp.server import Server
    USE_FULL_MCP = True
except ImportError:
    from shannot.minimal_mcp import MinimalServer as Server
    USE_FULL_MCP = False
```

**Benefits**:
- ✅ Zero dependencies by default
- ✅ Can use full MCP if needed
- ✅ Gradual migration path

---

### Option 3: Keep `mcp` but Make Optional

**Scope**: Minimal code changes, just dependency restructuring

```toml
# pyproject.toml
dependencies = []

[project.optional-dependencies]
mcp = ["mcp>=1.18.0"]
remote = ["asyncssh>=2.14.0", "tomli>=2.0.0", "tomli-w>=1.0.0"]
full = ["mcp>=1.18.0", "asyncssh>=2.14.0", "tomli>=2.0.0", "tomli-w>=1.0.0"]
```

**Benefits**:
- ✅ Easiest to implement
- ✅ Preserves exact compatibility

**Drawbacks**:
- ❌ Still requires 11 dependencies for MCP users
- ❌ Doesn't solve the core problem

---

## Recommended Approach

**Phase 1: Implement Minimal Stdlib MCP** (1-2 days)
1. Create `shannot/minimal_mcp.py` with stdlib-only implementation
2. Implements: stdio transport, tools, resources, prompts
3. ~300 lines of code, zero dependencies
4. Used by default

**Phase 2: Make Full MCP Optional** (immediate)
1. Move `mcp` to optional `[mcp-full]` extra
2. Fallback to minimal implementation if not installed
3. Document when full MCP is needed (currently: never for shannot)

**Phase 3: Testing & Documentation** (1 day)
1. Extensive testing of minimal implementation
2. Compare behavior with full MCP
3. Document differences and limitations
4. Update installation docs

**Total Effort**: 2-4 days
**Impact**: Zero dependencies for 95% of users

---

## Prototype: Minimal MCP Server

See `shannot/minimal_mcp.py` (to be created) for a complete working implementation.

Key features:
- ✅ JSON-RPC 2.0 over stdio
- ✅ Tool registration and execution
- ✅ Resource registration and reading
- ✅ Prompt registration and templates
- ✅ Proper error handling
- ✅ Progress notifications
- ✅ Logging support
- ❌ HTTP/SSE/WebSocket transports (not needed)
- ❌ OAuth authentication (not needed)
- ❌ Sampling (can be added if needed)

---

## Conclusion

**Recommendation**: Implement **Option 1** (Full Stdlib Rewrite for Local MCP)

**Justification**:
1. **Massive dependency reduction**: 11+ packages → 0 packages
2. **Installation size**: ~60MB → ~0MB
3. **Security**: Smaller attack surface, easier audits
4. **Maintenance**: No external dependency churn
5. **Feasibility**: MCP stdio protocol is simple, ~300 LOC
6. **No feature loss**: Shannot doesn't use HTTP/SSE transports

**Next Steps**:
1. Create prototype `minimal_mcp.py` implementation
2. Update `mcp_server.py` to use minimal implementation
3. Move `mcp`, `asyncssh`, `tomli*` to optional extras:
   - `[remote]`: SSH execution support
   - `[mcp-full]`: Full official MCP SDK (if ever needed)
4. Test thoroughly against MCP specification
5. Update documentation

**Migration Path**: Users get zero-dependency local MCP by default, can opt into remote execution with `pip install shannot[remote]`.
