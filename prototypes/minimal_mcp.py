"""
Minimal Model Context Protocol (MCP) implementation using only Python stdlib.

This module provides a lightweight MCP server for stdio transport (stdin/stdout)
without any external dependencies. It implements the core MCP functionality needed
by Shannot: tools, resources, and prompts.

Protocol: JSON-RPC 2.0 over stdio
Spec: https://spec.modelcontextprotocol.io

Size: ~400 lines of stdlib code vs ~15,000+ lines + 11 dependencies in official SDK
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
class Prompt:
    """MCP Prompt definition"""

    name: str
    description: str | None = None
    arguments: list[dict[str, Any]] = field(default_factory=list)


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
class ServerCapabilities:
    """Server capability declarations"""

    tools: dict[str, Any] | None = None
    resources: dict[str, Any] | None = None
    prompts: dict[str, Any] | None = None
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
# Minimal MCP Server
# ============================================================================


class MinimalMCPServer:
    """
    Minimal MCP server implementation using only Python stdlib.

    Implements:
    - stdio transport (stdin/stdout)
    - Tools (list, call)
    - Resources (list, read)
    - Prompts (list, get)
    - Logging
    - Progress notifications

    Does NOT implement (not needed by Shannot):
    - HTTP/SSE/WebSocket transports
    - Sampling
    - OAuth authentication
    - Pagination (can be added easily if needed)
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

        # I/O
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

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
    # Main Server Loop
    # ------------------------------------------------------------------------

    async def run(
        self,
        read_stream: asyncio.StreamReader,
        write_stream: asyncio.StreamWriter,
        init_options: InitializationOptions,
    ) -> None:
        """
        Run the MCP server with provided read/write streams.

        This is the main entry point compatible with official SDK's Server.run()
        """
        self._reader = read_stream
        self._writer = write_stream

        try:
            while True:
                # Read one line (JSON-RPC message)
                line = await self._reader.readline()
                if not line:
                    break

                # Parse JSON
                try:
                    message = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {e}")
                    await self._send_error_response(
                        None, ErrorCode.PARSE_ERROR, "Parse error", str(e)
                    )
                    continue

                # Handle message
                await self._handle_message(message)

        except asyncio.CancelledError:
            logger.info("Server cancelled")
        except Exception as e:
            logger.exception(f"Server error: {e}")
        finally:
            if self._writer:
                self._writer.close()
                await self._writer.wait_closed()

    async def _handle_message(self, message: dict) -> None:
        """Route JSON-RPC message to appropriate handler"""
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        try:
            # Initialize
            if method == "initialize":
                result = await self._handle_initialize(params)
                await self._send_response(msg_id, result)

            # Initialized notification
            elif method == "initialized":
                # Client confirms initialization - just log
                logger.debug("Client sent initialized notification")

            # Tools
            elif method == "tools/list":
                if not self._tool_list_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Tools not supported")
                tools = await self._call_handler(self._tool_list_handler)
                # Convert dataclass list to dicts
                tools_data = [asdict(t) for t in tools] if tools else []
                await self._send_response(msg_id, {"tools": tools_data})

            elif method == "tools/call":
                if not self._tool_call_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Tools not supported")
                name = params.get("name")
                arguments = params.get("arguments", {})
                result = await self._call_handler(self._tool_call_handler, name, arguments)
                # Result should be list[TextContent]
                content_data = [asdict(c) for c in result] if result else []
                await self._send_response(msg_id, {"content": content_data})

            # Resources
            elif method == "resources/list":
                if not self._resource_list_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Resources not supported")
                resources = await self._call_handler(self._resource_list_handler)
                resources_data = [asdict(r) for r in resources] if resources else []
                await self._send_response(msg_id, {"resources": resources_data})

            elif method == "resources/read":
                if not self._resource_read_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Resources not supported")
                uri = params.get("uri")
                result = await self._call_handler(self._resource_read_handler, uri)
                await self._send_response(msg_id, result)

            # Prompts
            elif method == "prompts/list":
                if not self._prompt_list_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Prompts not supported")
                prompts = await self._call_handler(self._prompt_list_handler)
                prompts_data = [asdict(p) for p in prompts] if prompts else []
                await self._send_response(msg_id, {"prompts": prompts_data})

            elif method == "prompts/get":
                if not self._prompt_get_handler:
                    raise JSONRPCError(ErrorCode.METHOD_NOT_FOUND, "Prompts not supported")
                name = params.get("name")
                arguments = params.get("arguments")
                result = await self._call_handler(self._prompt_get_handler, name, arguments)
                # Convert GetPromptResult to dict
                result_data = asdict(result) if result else {}
                await self._send_response(msg_id, result_data)

            # Ping
            elif method == "ping":
                await self._send_response(msg_id, {})

            # Unknown method
            else:
                raise JSONRPCError(
                    ErrorCode.METHOD_NOT_FOUND, f"Unknown method: {method}"
                )

        except JSONRPCError as e:
            await self._send_error_response(msg_id, e.code, e.message, e.data)
        except Exception as e:
            logger.exception(f"Error handling {method}: {e}")
            await self._send_error_response(
                msg_id, ErrorCode.INTERNAL_ERROR, "Internal error", str(e)
            )

    async def _handle_initialize(self, params: dict) -> dict:
        """Handle initialize request"""
        # Extract client info
        protocol_version = params.get("protocolVersion", "2024-11-05")
        client_info = params.get("clientInfo", {})

        logger.info(
            f"Client connecting: {client_info.get('name', 'unknown')} "
            f"(protocol {protocol_version})"
        )

        # Build capabilities
        capabilities: dict[str, Any] = {}
        if self._has_tools:
            capabilities["tools"] = {}
        if self._has_resources:
            capabilities["resources"] = {}
        if self._has_prompts:
            capabilities["prompts"] = {}
        # Always support logging
        capabilities["logging"] = {}

        return {
            "protocolVersion": protocol_version,
            "capabilities": capabilities,
            "serverInfo": {"name": self.name, "version": self.version},
        }

    async def _call_handler(self, handler: Callable, *args: Any) -> Any:
        """Call a handler function (sync or async)"""
        if asyncio.iscoroutinefunction(handler):
            return await handler(*args)
        else:
            return handler(*args)

    # ------------------------------------------------------------------------
    # Response Helpers
    # ------------------------------------------------------------------------

    async def _send_response(self, msg_id: int | str | None, result: Any) -> None:
        """Send successful JSON-RPC response"""
        response = create_response(msg_id, result=result)
        await self._send_message(response)

    async def _send_error_response(
        self, msg_id: int | str | None, code: int, message: str, data: Any = None
    ) -> None:
        """Send error JSON-RPC response"""
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        response = create_response(msg_id, error=error)
        await self._send_message(response)

    async def _send_message(self, message: dict) -> None:
        """Send JSON-RPC message to stdout"""
        if not self._writer:
            raise RuntimeError("Writer not initialized")

        json_str = json.dumps(message, separators=(",", ":"))
        self._writer.write(json_str.encode("utf-8") + b"\n")
        await self._writer.drain()

    # ------------------------------------------------------------------------
    # Notification Helpers (for logging, progress)
    # ------------------------------------------------------------------------

    async def send_log(
        self, level: LogLevel | str, message: str, logger_name: str | None = None
    ) -> None:
        """Send a log notification to the client"""
        params: dict[str, Any] = {"level": level, "data": message}
        if logger_name:
            params["logger"] = logger_name

        notification = create_notification("notifications/message", params)
        await self._send_message(notification)

    async def send_progress(
        self, progress: float, total: float | None = None, message: str | None = None
    ) -> None:
        """Send a progress notification"""
        params: dict[str, Any] = {"progress": progress}
        if total is not None:
            params["total"] = total
        if message is not None:
            params["message"] = message

        notification = create_notification("notifications/progress", params)
        await self._send_message(notification)


# ============================================================================
# Stdio Transport (compatible with official SDK)
# ============================================================================


async def stdio_server():
    """
    Create stdio transport for MCP server.

    Returns read_stream and write_stream compatible with Server.run()

    This is a simplified version of official mcp.server.stdio.stdio_server()
    using only stdlib.
    """
    loop = asyncio.get_event_loop()

    # Create reader for stdin
    reader = asyncio.StreamReader(loop=loop)
    reader_protocol = asyncio.StreamReaderProtocol(reader)

    # Connect stdin to reader
    await loop.connect_read_pipe(lambda: reader_protocol, sys.stdin.buffer)

    # Create writer for stdout
    writer_transport, writer_protocol = await loop.connect_write_pipe(
        lambda: asyncio.streams.FlowControlMixin(), sys.stdout.buffer
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, loop)

    return reader, writer


# ============================================================================
# Example Usage
# ============================================================================


async def example():
    """Example MCP server using minimal implementation"""

    # Create server
    server = MinimalMCPServer("example-server", "1.0.0")

    # Register tools
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="add",
                description="Add two numbers",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                    "required": ["a", "b"],
                },
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "add":
            result = arguments["a"] + arguments["b"]
            return [TextContent(type="text", text=str(result))]
        raise JSONRPCError(ErrorCode.INVALID_PARAMS, f"Unknown tool: {name}")

    # Register resources
    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="file://example.txt",
                name="Example File",
                description="An example resource",
                mimeType="text/plain",
            )
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        if uri == "file://example.txt":
            return "This is example content"
        raise JSONRPCError(ErrorCode.INVALID_PARAMS, f"Unknown resource: {uri}")

    # Register prompts
    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="greeting",
                description="Generate a greeting",
                arguments=[{"name": "name", "description": "Name to greet", "required": True}],
            )
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
        if name == "greeting":
            user_name = arguments.get("name", "World") if arguments else "World"
            return GetPromptResult(
                description="A greeting prompt",
                messages=[PromptMessage(role="user", content=TextContent(text=f"Hello, {user_name}!"))]
            )
        raise JSONRPCError(ErrorCode.INVALID_PARAMS, f"Unknown prompt: {name}")

    # Run server
    read_stream, write_stream = await stdio_server()
    init_options = InitializationOptions(
        server_name="example",
        server_version="1.0.0",
        capabilities=ServerCapabilities(tools={}, resources={}, prompts={}),
    )

    await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    asyncio.run(example())
