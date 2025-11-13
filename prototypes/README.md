# MCP Dependency Reduction Prototypes

This directory contains prototype implementations exploring how to reduce MCP-related dependencies.

## Files

### `minimal_mcp.py`

**A complete, working MCP server implementation using ONLY Python standard library.**

- **Size**: ~450 lines of stdlib code
- **Dependencies**: Zero (stdlib only)
- **Compares to**: Official `mcp` package (~15,000+ lines + 11 dependencies)

**Features Implemented**:
- ✅ stdio transport (stdin/stdout communication)
- ✅ Tools (list, call)
- ✅ Resources (list, read)
- ✅ Prompts (list, get)
- ✅ Logging notifications
- ✅ Progress notifications
- ✅ Proper JSON-RPC 2.0 message handling
- ✅ Error handling and validation
- ✅ Async/await support

**Features NOT Implemented** (not needed by Shannot):
- ❌ HTTP/SSE/WebSocket transports
- ❌ Sampling
- ❌ OAuth authentication
- ❌ Pagination (easily added if needed)

**API Compatibility**: Designed to be a drop-in replacement for the official SDK's stdio transport:

```python
# Works with both official SDK and minimal implementation
from shannot.minimal_mcp import MinimalMCPServer as Server, stdio_server

server = Server("my-server")

@server.list_tools()
async def list_tools():
    return [...]

@server.call_tool()
async def call_tool(name, arguments):
    return [...]

# Run server
read_stream, write_stream = await stdio_server()
await server.run(read_stream, write_stream, init_options)
```

## Testing the Prototype

```bash
# Run the example server
cd prototypes
python3 minimal_mcp.py

# In another terminal, test with MCP Inspector:
npx @modelcontextprotocol/inspector python3 minimal_mcp.py

# Or test with Claude Desktop by adding to config:
# {
#   "mcpServers": {
#     "minimal-test": {
#       "command": "python3",
#       "args": ["/path/to/prototypes/minimal_mcp.py"]
#     }
#   }
# }
```

## Implementation Notes

### Why This Works

The MCP protocol over stdio is fundamentally:
1. **JSON-RPC 2.0** messages over stdin/stdout
2. **Structured message types** (tools, resources, prompts)
3. **Simple async I/O** patterns

All of this can be implemented with stdlib:
- `json` module for serialization
- `asyncio` for async I/O and task management
- `dataclasses` for data structures (instead of Pydantic)
- `sys.stdin/stdout` for stdio transport

### What We Lose

Compared to the official SDK:
- No automatic Pydantic validation (we do manual validation)
- No JSON schema auto-generation from type hints (we define schemas manually)
- No HTTP/SSE/WebSocket transports (Shannot doesn't use these)
- Less sophisticated error messages (but still spec-compliant)

### What We Gain

- **Zero dependencies** for local MCP servers
- **~60MB smaller** installation
- **Easier to audit** and maintain
- **More portable** (no C extensions except in remote mode)
- **Faster installation** and startup

## Next Steps

If approved, this prototype can be:
1. Moved to `shannot/minimal_mcp.py`
2. Integrated into `shannot/mcp_server.py` as a fallback
3. Made the default with full `mcp` as optional `[mcp-full]` extra
4. Thoroughly tested against MCP specification
5. Documented and released

See `../MINIMAL_MCP_ANALYSIS.md` for full analysis.
