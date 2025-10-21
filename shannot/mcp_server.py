"""MCP server implementation for Shannot sandbox.

This module exposes Shannot sandbox capabilities as MCP tools, allowing
Claude Desktop and other MCP clients to interact with the sandbox.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool

from shannot.tools import (
    CommandInput,
    DirectoryListInput,
    FileReadInput,
    SandboxDeps,
    check_disk_usage,
    check_memory,
    list_directory,
    read_file,
    run_command,
)

logger = logging.getLogger(__name__)


class ShannotMCPServer:
    """MCP server exposing sandbox profiles as tools."""

    def __init__(self, profile_paths: list[Path] | None = None):
        """Initialize the MCP server.

        Args:
            profile_paths: List of profile paths to load. If None, loads from default locations.
        """
        self.server = Server("shannot-sandbox")
        self.deps_by_profile: dict[str, SandboxDeps] = {}

        # Load profiles
        if profile_paths is None:
            profile_paths = self._discover_profiles()

        for path in profile_paths:
            try:
                deps = SandboxDeps(profile_path=path)
                self.deps_by_profile[deps.profile.name] = deps
                logger.info(f"Loaded profile: {deps.profile.name} from {path}")
            except Exception as e:
                logger.error(f"Failed to load profile from {path}: {e}")

        # Register handlers
        self._register_tools()
        self._register_resources()

    def _discover_profiles(self) -> list[Path]:
        """Discover profiles from default locations."""
        paths: list[Path] = []

        # User config directory
        user_config = Path.home() / ".config" / "shannot"
        if user_config.exists():
            paths.extend(user_config.glob("*.json"))

        # Bundled profiles
        bundled_dir = Path(__file__).parent.parent / "profiles"
        if bundled_dir.exists():
            paths.extend(bundled_dir.glob("*.json"))

        return paths

    def _register_tools(self) -> None:
        """Register MCP tools for each profile."""

        # Register a generic tool for each profile
        for profile_name in self.deps_by_profile.keys():
            self._register_profile_tools(profile_name)

    def _register_profile_tools(self, profile_name: str) -> None:
        """Register tools for a specific profile."""

        # Generic command execution tool
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available MCP tools."""
            tools: list[Tool] = []

            for pname, pdeps in self.deps_by_profile.items():
                # Main command tool
                tools.append(
                    Tool(
                        name=f"sandbox_{pname}",
                        description=self._generate_tool_description(pdeps),
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "command": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Command and arguments to execute",
                                }
                            },
                            "required": ["command"],
                        },
                    )
                )

                # Specialized tools
                tools.extend(
                    [
                        Tool(
                            name=f"sandbox_{pname}_read_file",
                            description=f"Read a file using {pname} sandbox (read-only)",
                            inputSchema={
                                "type": "object",
                                "properties": {
                                    "path": {
                                        "type": "string",
                                        "description": "Absolute path to file",
                                    }
                                },
                                "required": ["path"],
                            },
                        ),
                        Tool(
                            name=f"sandbox_{pname}_list_directory",
                            description=f"List directory contents using {pname} sandbox",
                            inputSchema={
                                "type": "object",
                                "properties": {
                                    "path": {
                                        "type": "string",
                                        "description": "Directory path",
                                    },
                                    "long_format": {
                                        "type": "boolean",
                                        "description": "Show detailed info (ls -l)",
                                        "default": False,
                                    },
                                    "show_hidden": {
                                        "type": "boolean",
                                        "description": "Show hidden files (ls -a)",
                                        "default": False,
                                    },
                                },
                                "required": ["path"],
                            },
                        ),
                        Tool(
                            name=f"sandbox_{pname}_check_disk",
                            description=f"Check disk usage using {pname} sandbox",
                            inputSchema={"type": "object", "properties": {}},
                        ),
                        Tool(
                            name=f"sandbox_{pname}_check_memory",
                            description=f"Check memory usage using {pname} sandbox",
                            inputSchema={"type": "object", "properties": {}},
                        ),
                    ]
                )

            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Handle MCP tool calls."""
            # Parse tool name to extract profile and action
            if not name.startswith("sandbox_"):
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            parts = name.split("_", 2)  # ['sandbox', 'profilename', 'action']
            if len(parts) < 2:
                return [TextContent(type="text", text=f"Invalid tool name format: {name}")]

            pname = parts[1]
            action = parts[2] if len(parts) > 2 else "command"

            if pname not in self.deps_by_profile:
                return [TextContent(type="text", text=f"Unknown profile: {pname}")]

            pdeps = self.deps_by_profile[pname]

            try:
                # Route to appropriate tool
                if action == "command":
                    cmd_input = CommandInput(**arguments)
                    result = await run_command(pdeps, cmd_input)
                    return [
                        TextContent(
                            type="text",
                            text=self._format_command_output(result),
                        )
                    ]
                elif action == "read" and len(parts) > 3 and parts[3] == "file":
                    file_input = FileReadInput(**arguments)
                    content = await read_file(pdeps, file_input)
                    return [TextContent(type="text", text=content)]
                elif action == "list" and len(parts) > 3 and parts[3] == "directory":
                    dir_input = DirectoryListInput(**arguments)
                    listing = await list_directory(pdeps, dir_input)
                    return [TextContent(type="text", text=listing)]
                elif action == "check" and len(parts) > 3 and parts[3] == "disk":
                    usage = await check_disk_usage(pdeps)
                    return [TextContent(type="text", text=usage)]
                elif action == "check" and len(parts) > 3 and parts[3] == "memory":
                    usage = await check_memory(pdeps)
                    return [TextContent(type="text", text=usage)]
                else:
                    return [TextContent(type="text", text=f"Unknown action: {action}")]

            except Exception as e:
                logger.error(f"Tool execution failed: {e}", exc_info=True)
                return [TextContent(type="text", text=f"Error executing tool: {str(e)}")]

    def _register_resources(self) -> None:
        """Register MCP resources for profile inspection."""

        @self.server.list_resources()
        async def list_resources() -> list[Resource]:
            """List available resources."""
            resources: list[Resource] = []

            # Profile resources
            for name in self.deps_by_profile.keys():
                resources.append(
                    Resource(
                        uri=f"sandbox://profiles/{name}",  # type: ignore[arg-type]
                        name=f"Sandbox Profile: {name}",
                        mimeType="application/json",
                        description=f"Configuration for {name} sandbox profile",
                    )
                )

            return resources

        @self.server.read_resource()  # type: ignore[arg-type]
        async def read_resource(uri: str) -> str:
            """Read resource content."""
            if uri.startswith("sandbox://profiles/"):
                profile_name = uri.split("/")[-1]
                if profile_name in self.deps_by_profile:
                    deps = self.deps_by_profile[profile_name]
                    return json.dumps(
                        {
                            "name": deps.profile.name,
                            "allowed_commands": deps.profile.allowed_commands,
                            "network_isolation": deps.profile.network_isolation,
                            "tmpfs_paths": deps.profile.tmpfs_paths,
                            "environment": deps.profile.environment,
                        },
                        indent=2,
                    )
                else:
                    return json.dumps({"error": f"Profile not found: {profile_name}"})
            else:
                return json.dumps({"error": f"Unknown resource: {uri}"})

    def _generate_tool_description(self, deps: SandboxDeps) -> str:
        """Generate a description for a profile's tool."""
        commands = ", ".join(deps.profile.allowed_commands[:5])
        if len(deps.profile.allowed_commands) > 5:
            commands += f", ... ({len(deps.profile.allowed_commands)} total)"

        return (
            f"Execute commands in read-only '{deps.profile.name}' sandbox. "
            f"Allowed commands: {commands}. "
            f"Network isolation: {deps.profile.network_isolation}. "
            f"All file modifications are ephemeral (tmpfs)."
        )

    def _format_command_output(self, result: Any) -> str:
        """Format command output for MCP response."""
        output = f"Exit code: {result.returncode}\n"
        output += f"Duration: {result.duration:.2f}s\n\n"

        if result.stdout:
            output += "--- stdout ---\n"
            output += result.stdout
            output += "\n"

        if result.stderr:
            output += "--- stderr ---\n"
            output += result.stderr
            output += "\n"

        if not result.succeeded:
            output += "\n⚠️  Command failed"

        return output

    async def run(self) -> None:
        """Run the MCP server."""
        await self.server.run()  # type: ignore[call-arg]


# Export
__all__ = ["ShannotMCPServer"]
