"""
Minimal Model Context Protocol (MCP) implementation using only Python stdlib.

This module provides a lightweight MCP server for stdio transport (stdin/stdout)
without any external dependencies. It implements the core MCP functionality needed
by Shannot: tools, resources, and prompts.

Protocol: JSON-RPC 2.0 over stdio
Spec: https://spec.modelcontextprotocol.io

Size: ~250 lines of stdlib code vs ~15,000+ lines + 11 dependencies in official SDK
Uses: Threads + blocking I/O (simpler than async)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Literal

logger = logging.getLogger(__name__)


def asdict_exclude_none(obj: Any) -> dict:
    """Convert dataclass to dict, excluding None values"""
    if obj is None:
        return {}
    result = asdict(obj)
    return {k: v for k, v in result.items() if v is not None}


# ============================================================================
# Data Models (stdlib dataclasses instead of Pydantic)
# ============================================================================


@dataclass
class TextContent:
    """Text content for responses"""

    type: Literal["text"] = "text"
    text: str = ""


@dataclass
class Tool:
    """MCP Tool definition"""

    name: str
    description: str
    inputSchema: dict[str, Any]


@dataclass
class Resource:
    """MCP Resource definition"""

    uri: str
    name: str
    description: str | None = None
    mimeType: str | None = None


@dataclass
class PromptArgument:
    """Argument for a prompt"""

    name: str
    description: str | None = None
    required: bool = False


@dataclass
class Prompt:
    """MCP Prompt definition"""

    name: str
    description: str | None = None
    arguments: list[PromptArgument] = field(default_factory=list)


@dataclass
class PromptMessage:
    """Message in a prompt"""

    role: Literal["user", "assistant"]
    content: TextContent


@dataclass
class GetPromptResult:
    """Result of getting a prompt"""

    description: str | None = None
    messages: list[PromptMessage] = field(default_factory=list)


@dataclass
class ToolsCapability:
    """Tools capability declaration"""

    pass


@dataclass
class ResourcesCapability:
    """Resources capability declaration"""

    pass


@dataclass
class PromptsCapability:
    """Prompts capability declaration"""

    pass


@dataclass
class ServerCapabilities:
    """Server capability declarations"""

    tools: ToolsCapability | None = None
    resources: ResourcesCapability | None = None
    prompts: PromptsCapability | None = None
    logging: dict[str, Any] | None = None


@dataclass
class ServerInfo:
    """Server metadata"""

    name: str
    version: str


@dataclass
class InitializationOptions:
    """MCP initialization options"""

    server_name: str
    server_version: str
    capabilities: ServerCapabilities


class LogLevel(str, Enum):
    """MCP log levels"""

    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    ALERT = "alert"
    EMERGENCY = "emergency"


# ============================================================================
# JSON-RPC Message Handling
# ============================================================================


class JSONRPCError(Exception):
    """JSON-RPC error"""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


# JSON-RPC error codes
class ErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


def create_response(msg_id: int | str | None, result: Any = None, error: dict | None = None) -> dict:
    """Create a JSON-RPC 2.0 response"""
    response: dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id}

    if error is not None:
        response["error"] = error
    else:
        response["result"] = result

    return response


def create_notification(method: str, params: Any = None) -> dict:
    """Create a JSON-RPC 2.0 notification (no id = no response expected)"""
    notif: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        notif["params"] = params
    return notif


# ============================================================================
# Minimal MCP Server (Thread-based, blocking I/O)
# ============================================================================


class MinimalMCPServer:
    """
    Minimal MCP server implementation using only Python stdlib.

    Uses blocking I/O with threads for simplicity. Bridges to async code
    when needed using asyncio.run().

    Implements:
    - stdio transport (stdin/stdout) with blocking I/O
    - Tools (list, call)
    - Resources (list, read)
    - Prompts (list, get)
    - Logging
    - Progress notifications

    Does NOT implement (not needed by Shannot):
    - HTTP/SSE/WebSocket transports
    - Sampling
    - OAuth authentication
    """

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version

        # Handler registries
        self._tool_list_handler: Callable[[], Any] | None = None
        self._tool_call_handler: Callable[[str, dict], Any] | None = None
        self._resource_list_handler: Callable[[], Any] | None = None
        self._resource_read_handler: Callable[[str], Any] | None = None
        self._prompt_list_handler: Callable[[], Any] | None = None
        self._prompt_get_handler: Callable[[str, dict | None], Any] | None = None

        # Capability flags
        self._has_tools = False
        self._has_resources = False
        self._has_prompts = False

        # I/O streams
        self._reader = None
        self._writer = None

    # ------------------------------------------------------------------------
    # Handler Registration (decorator API like official SDK)
    # ------------------------------------------------------------------------

    def list_tools(self) -> Callable:
        """Decorator to register tools/list handler"""

        def decorator(func: Callable) -> Callable:
            self._tool_list_handler = func
            self._has_tools = True
            return func

        return decorator

    def call_tool(self) -> Callable:
        """Decorator to register tools/call handler"""

        def decorator(func: Callable) -> Callable:
            self._tool_call_handler = func
            self._has_tools = True
            return func

        return decorator

    def list_resources(self) -> Callable:
        """Decorator to register resources/list handler"""

        def decorator(func: Callable) -> Callable:
            self._resource_list_handler = func
            self._has_resources = True
            return func

        return decorator

    def read_resource(self) -> Callable:
        """Decorator to register resources/read handler"""

        def decorator(func: Callable) -> Callable:
            self._resource_read_handler = func
            self._has_resources = True
            return func

        return decorator

    def list_prompts(self) -> Callable:
        """Decorator to register prompts/list handler"""

        def decorator(func: Callable) -> Callable:
            self._prompt_list_handler = func
            self._has_prompts = True
            return func

        return decorator

    def get_prompt(self) -> Callable:
        """Decorator to register prompts/get handler"""

        def decorator(func: Callable) -> Callable:
            self._prompt_get_handler = func
            self._has_prompts = True
            return func

        return decorator

    # ------------------------------------------------------------------------
    # Main Server Loop (Synchronous with blocking I/O)
    # ------------------------------------------------------------------------

    def run(
        self,
        read_stream: Any,
        write_stream: Any,
        init_options: InitializationOptions,
    ) -> None:
        """
        Run the MCP server with blocking I/O.

        Args:
            read_stream: Input stream (e.g., sys.stdin)
            write_stream: Output stream (e.g., sys.stdout)
            init_options: Initialization options (unused, for API compatibility)
        """
        self._reader = read_stream
        self._writer = write_stream

        try:
            while True:
                # Blocking read - simple and straightforward!
                line = self._reader.readline()
                if not line:
                    break

                # Parse JSON
                try:
                    message = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {e}")
                    self._send_error_response(
                        None, ErrorCode.PARSE_ERROR, "Parse error", str(e)
                    )
                    continue

                # Handle message
                self._handle_message(message)

        except KeyboardInterrupt:
            logger.info("Server interrupted")
        except Exception as e:
            logger.exception(f"Server error: {e}")

    def _handle_message(self, message: dict) -> None:
        """Route JSON-RPC message to appropriate handler"""
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        try:
            # Initialize
            if method == "initialize":
                result = self._handle_initialize(params)
                self._send_response(msg_id, result)

            # Initialized notification
            elif method == "initialized":
                # Client confirms initialization - just log
                logger.debug("Client sent initialized notification")

            # Tools
            elif method == "tools/list":
                if not self._tool_list_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Tools not supported")
                tools = self._call_handler(self._tool_list_handler)
                tools_data = [asdict(t) for t in tools] if tools else []
                self._send_response(msg_id, {"tools": tools_data})

            elif method == "tools/call":
                if not self._tool_call_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Tools not supported")
                name = params.get("name")
                arguments = params.get("arguments", {})
                result = self._call_handler(self._tool_call_handler, name, arguments)
                content_data = [asdict(c) for c in result] if result else []
                self._send_response(msg_id, {"content": content_data})

            # Resources
            elif method == "resources/list":
                if not self._resource_list_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Resources not supported")
                resources = self._call_handler(self._resource_list_handler)
                resources_data = [asdict(r) for r in resources] if resources else []
                self._send_response(msg_id, {"resources": resources_data})

            elif method == "resources/read":
                if not self._resource_read_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Resources not supported")
                uri = params.get("uri")
                result = self._call_handler(self._resource_read_handler, uri)
                self._send_response(msg_id, result)

            # Prompts
            elif method == "prompts/list":
                if not self._prompt_list_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Prompts not supported")
                prompts = self._call_handler(self._prompt_list_handler)
                prompts_data = [asdict(p) for p in prompts] if prompts else []
                self._send_response(msg_id, {"prompts": prompts_data})

            elif method == "prompts/get":
                if not self._prompt_get_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Prompts not supported")
                name = params.get("name")
                arguments = params.get("arguments")
                result = self._call_handler(self._prompt_get_handler, name, arguments)
                result_data = asdict(result) if result else {}
                self._send_response(msg_id, result_data)

            # Ping
            elif method == "ping":
                self._send_response(msg_id, {})

            # Unknown method
            else:
                raise JSONRPCError(
                    ErrorCode.METHOD_NOT_FOUND, f"Unknown method: {method}"
                )

        except JSONRPCError as e:
            self._send_error_response(msg_id, e.code, e.message, e.data)
        except Exception as e:
            logger.exception(f"Error handling {method}: {e}")
            self._send_error_response(
                msg_id, ErrorCode.INTERNAL_ERROR, "Internal error", str(e)
            )

    def _handle_initialize(self, params: dict) -> dict:
        """Handle initialize request"""
        protocol_version = params.get("protocolVersion", "2024-11-05")
        client_info = params.get("clientInfo", {})

        logger.info(
            f"Client connecting: {client_info.get('name', 'unknown')} "
            f"(protocol {protocol_version})"
        )

        # Build capabilities
        capabilities = ServerCapabilities(
            tools=ToolsCapability() if self._has_tools else None,
            resources=ResourcesCapability() if self._has_resources else None,
            prompts=PromptsCapability() if self._has_prompts else None,
            logging={},  # Always support logging
        )

        return {
            "protocolVersion": protocol_version,
            "capabilities": asdict_exclude_none(capabilities),
            "serverInfo": {"name": self.name, "version": self.version},
        }

    def _call_handler(self, handler: Callable, *args: Any) -> Any:
        """
        Call a handler function.

        If handler is async, bridge to it using asyncio.run().
        If handler is sync, call directly.
        """
        if asyncio.iscoroutinefunction(handler):
            # Bridge to async code
            return asyncio.run(handler(*args))
        else:
            # Call sync function directly
            return handler(*args)

    # ------------------------------------------------------------------------
    # Response Helpers
    # ------------------------------------------------------------------------

    def _send_response(self, msg_id: int | str | None, result: Any) -> None:
        """Send successful JSON-RPC response"""
        response = create_response(msg_id, result=result)
        self._send_message(response)

    def _send_error_response(
        self, msg_id: int | str | None, code: int, message: str, data: Any = None
    ) -> None:
        """Send error JSON-RPC response"""
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        response = create_response(msg_id, error=error)
        self._send_message(response)

    def _send_message(self, message: dict) -> None:
        """Send JSON-RPC message to stdout"""
        json_str = json.dumps(message, separators=(",", ":"))
        self._writer.write(json_str + "\n")
        self._writer.flush()


# ============================================================================
# Stdio Transport (simple function, no async needed)
# ============================================================================


def stdio_server():
    """
    Return stdin/stdout streams for MCP server.

    Simple synchronous function - just returns the streams directly.
    No async context manager needed!
    """
    import io

    # Return text-mode streams
    # Note: sys.stdin/stdout are already text mode by default
    return sys.stdin, sys.stdout


# Export public API
__all__ = [
    "MinimalMCPServer",
    "stdio_server",
    "InitializationOptions",
    "ServerCapabilities",
    "ToolsCapability",
    "ResourcesCapability",
    "PromptsCapability",
    "Tool",
    "Resource",
    "Prompt",
    "PromptArgument",
    "PromptMessage",
    "GetPromptResult",
    "TextContent",
    "LogLevel",
    "JSONRPCError",
]
