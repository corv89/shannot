"""Base MCP server infrastructure with request routing and dispatch.

This module provides the core MCPServer class that handles JSON-RPC
request routing, method dispatch, and error handling.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from .types import (
    InitializationOptions,
    Resource,
    ServerCapabilities,
    ServerInfo,
    TextContent,
    Tool,
)

logger = logging.getLogger(__name__)


class MCPServer:
    """Base MCP server with request routing and handler registration.

    Subclasses should override _register_* methods to add tools/resources.

    Attributes
    ----------
    server_info : ServerInfo
        Server name and version metadata.
    capabilities : ServerCapabilities
        Declared server capabilities.
    tools : dict[str, Tool]
        Registered tool definitions.
    tool_handlers : dict[str, Callable]
        Tool execution handlers.
    resources : dict[str, Resource]
        Registered resource definitions.
    resource_handlers : dict[str, Callable]
        Resource read handlers.
    """

    def __init__(self, name: str, version: str):
        """Initialize MCP server.

        Parameters
        ----------
        name : str
            Server name (e.g., "shannot").
        version : str
            Server version (e.g., "0.5.0").
        """
        self.server_info = ServerInfo(name=name, version=version)
        self.capabilities = ServerCapabilities()

        # Tool registry
        self.tools: dict[str, Tool] = {}
        self.tool_handlers: dict[str, Callable[[dict[str, Any]], TextContent]] = {}

        # Resource registry
        self.resources: dict[str, Resource] = {}
        self.resource_handlers: dict[str, Callable[[], str]] = {}

        # Register tools and resources
        self._register_tools()
        self._register_resources()

    def _register_tools(self) -> None:
        """Register tools. Override in subclasses."""
        pass

    def _register_resources(self) -> None:
        """Register resources. Override in subclasses."""
        pass

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[[dict[str, Any]], TextContent],
    ) -> None:
        """Register a tool with handler.

        Parameters
        ----------
        name : str
            Tool name (must be unique).
        description : str
            Human-readable tool description.
        input_schema : dict[str, Any]
            JSON Schema for tool input.
        handler : Callable[[dict[str, Any]], TextContent]
            Function that executes the tool.
        """
        tool = Tool(name=name, description=description, inputSchema=input_schema)
        self.tools[name] = tool
        self.tool_handlers[name] = handler

    def register_resource(
        self,
        uri: str,
        name: str,
        description: str | None,
        mime_type: str | None,
        handler: Callable[[], str],
    ) -> None:
        """Register a resource with handler.

        Parameters
        ----------
        uri : str
            Resource URI (must be unique).
        name : str
            Human-readable resource name.
        description : str | None
            Optional description.
        mime_type : str | None
            Optional MIME type.
        handler : Callable[[], str]
            Function that reads the resource content.
        """
        resource = Resource(
            uri=uri,
            name=name,
            description=description,
            mimeType=mime_type,
        )
        self.resources[uri] = resource
        self.resource_handlers[uri] = handler

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle incoming JSON-RPC request.

        Parameters
        ----------
        request : dict[str, Any]
            JSON-RPC request message.

        Returns
        -------
        dict[str, Any] | None
            JSON-RPC response, or None for notifications.
        """
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params", {})

        logger.debug(f"Received request: method={method}, id={request_id}")

        # Dispatch to appropriate handler
        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = self._handle_list_tools()
            elif method == "tools/call":
                result = self._handle_call_tool(params)
            elif method == "resources/list":
                result = self._handle_list_resources()
            elif method == "resources/read":
                result = self._handle_read_resource(params)
            else:
                raise ValueError(f"Unknown method: {method}")

            # Return response for requests (have id)
            if request_id is not None:
                return {
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id,
                }
            return None

        except Exception as e:
            logger.error(f"Error handling {method}: {e}", exc_info=True)
            if request_id is not None:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": str(e),
                    },
                    "id": request_id,
                }
            return None

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize request.

        Parameters
        ----------
        params : dict[str, Any]
            Initialize params (client capabilities, etc.).

        Returns
        -------
        dict[str, Any]
            Initialization result with server info and capabilities.
        """
        # Update capabilities based on what we have registered
        if self.tools:
            from .types import ToolsCapability

            self.capabilities.tools = ToolsCapability(listChanged=False)

        if self.resources:
            from .types import ResourcesCapability

            self.capabilities.resources = ResourcesCapability(subscribe=False, listChanged=False)

        init_options = InitializationOptions(
            server_info=self.server_info,
            capabilities=self.capabilities,
        )

        return init_options.to_dict()

    def _handle_list_tools(self) -> dict[str, Any]:
        """Handle tools/list request."""
        return {"tools": [tool.to_dict() for tool in self.tools.values()]}

    def _handle_call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tool_handlers:
            raise ValueError(f"Unknown tool: {tool_name}")

        handler = self.tool_handlers[tool_name]
        result = handler(arguments)

        return {"content": [result.to_dict()]}

    def _handle_list_resources(self) -> dict[str, Any]:
        """Handle resources/list request."""
        return {"resources": [res.to_dict() for res in self.resources.values()]}

    def _handle_read_resource(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri")

        if uri not in self.resource_handlers:
            raise ValueError(f"Unknown resource: {uri}")

        handler = self.resource_handlers[uri]
        content = handler()

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": self.resources[uri].mimeType or "text/plain",
                    "text": content,
                }
            ]
        }
