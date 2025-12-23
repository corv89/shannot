"""MCP type definitions using Python dataclasses.

This module defines all the types needed for MCP protocol implementation
using pure Python stdlib (dataclasses + typing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# ============================================================================
# Content Types
# ============================================================================


@dataclass
class TextContent:
    """Text content in MCP responses."""

    type: Literal["text"] = "text"
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {"type": self.type, "text": self.text}


# ============================================================================
# Tool Types
# ============================================================================


@dataclass
class Tool:
    """MCP tool definition."""

    name: str
    description: str
    inputSchema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }


# ============================================================================
# Resource Types
# ============================================================================


@dataclass
class Resource:
    """MCP resource definition."""

    uri: str
    name: str
    description: str | None = None
    mimeType: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {
            "uri": self.uri,
            "name": self.name,
        }
        if self.description is not None:
            result["description"] = self.description
        if self.mimeType is not None:
            result["mimeType"] = self.mimeType
        return result


# ============================================================================
# Prompt Types
# ============================================================================


@dataclass
class PromptArgument:
    """Argument definition for a prompt."""

    name: str
    description: str | None = None
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {"name": self.name, "required": self.required}
        if self.description is not None:
            result["description"] = self.description
        return result


@dataclass
class PromptMessage:
    """Message in a prompt template."""

    role: Literal["user", "assistant"]
    content: TextContent

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "role": self.role,
            "content": self.content.to_dict(),
        }


@dataclass
class Prompt:
    """MCP prompt template definition."""

    name: str
    description: str | None = None
    arguments: list[PromptArgument] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {"name": self.name}
        if self.description is not None:
            result["description"] = self.description
        if self.arguments:
            result["arguments"] = [arg.to_dict() for arg in self.arguments]
        return result


@dataclass
class GetPromptResult:
    """Result of get_prompt request."""

    description: str | None = None
    messages: list[PromptMessage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {
            "messages": [msg.to_dict() for msg in self.messages],
        }
        if self.description is not None:
            result["description"] = self.description
        return result


# ============================================================================
# Capability Types
# ============================================================================


@dataclass
class ToolsCapability:
    """Server capability for tools."""

    listChanged: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {"listChanged": self.listChanged}


@dataclass
class ResourcesCapability:
    """Server capability for resources."""

    subscribe: bool = False
    listChanged: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {"subscribe": self.subscribe, "listChanged": self.listChanged}


@dataclass
class PromptsCapability:
    """Server capability for prompts."""

    listChanged: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {"listChanged": self.listChanged}


@dataclass
class ServerCapabilities:
    """Server capabilities declaration."""

    tools: ToolsCapability | None = None
    resources: ResourcesCapability | None = None
    prompts: PromptsCapability | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {}
        if self.tools is not None:
            result["tools"] = self.tools.to_dict()
        if self.resources is not None:
            result["resources"] = self.resources.to_dict()
        if self.prompts is not None:
            result["prompts"] = self.prompts.to_dict()
        return result


# ============================================================================
# Server Metadata
# ============================================================================


@dataclass
class ServerInfo:
    """Server information for initialization."""

    name: str
    version: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {"name": self.name, "version": self.version}


# MCP protocol version (spec date)
PROTOCOL_VERSION = "2024-11-05"


@dataclass
class InitializationOptions:
    """Server initialization options."""

    server_info: ServerInfo
    capabilities: ServerCapabilities
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "protocolVersion": self.protocol_version,
            "serverInfo": self.server_info.to_dict(),
            "capabilities": self.capabilities.to_dict(),
        }
