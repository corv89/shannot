"""MCP (Model Context Protocol) server implementation for Shannot.

This package provides a pure stdlib implementation of MCP for exposing
Shannot's PyPy sandbox capabilities to Claude Desktop, Claude Code, and
other MCP clients.

Key components:
- protocol: JSON-RPC 2.0 over stdin/stdout (synchronous)
- types: MCP type definitions using dataclasses
- server: Base MCP server infrastructure
- server_impl: Shannot-specific MCP server with sandbox_run tool
"""

from __future__ import annotations

__all__ = ["MCPServer", "ShannotMCPServer", "serve"]

from .protocol import serve
from .server import MCPServer
from .server_impl import ShannotMCPServer
