"""MCP server implementation for Shannot sandbox.

This module exposes Shannot sandbox capabilities as MCP tools, allowing
Claude Desktop and other MCP clients to interact with the sandbox.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path

from mcp.server import InitializationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, ServerCapabilities, TextContent, Tool

from shannot import __version__
from shannot.execution import SandboxExecutor
from shannot.tools import CommandInput, CommandOutput, SandboxDeps, run_command

logger = logging.getLogger(__name__)


class ShannotMCPServer:
    """MCP server exposing sandbox profiles as tools."""

    def __init__(
        self,
        profile_paths: Sequence[Path | str] | None = None,
        executor: SandboxExecutor | None = None,
        executor_label: str | None = None,
    ):
        """Initialize the MCP server.

        Args:
            profile_paths: List of profile paths to load. If None, loads from default locations.
            executor: Optional executor used to run sandbox commands (local or remote).
        """
        self.server: Server = Server("shannot-sandbox")
        self.deps_by_profile: dict[str, SandboxDeps] = {}
        self._executor_label: str | None = executor_label

        # Load profiles
        if profile_paths is None:
            profile_paths = self._discover_profiles()

        for spec in profile_paths:
            try:
                deps = self._create_deps_from_spec(spec, executor)
                self.deps_by_profile[deps.profile.name] = deps
                logger.info(f"Loaded profile: {deps.profile.name}")
            except Exception as e:
                logger.error(f"Failed to load profile {spec}: {e}")

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

    def _create_deps_from_spec(
        self,
        spec: Path | str,
        executor: SandboxExecutor | None,
    ) -> SandboxDeps:
        """Create SandboxDeps from a profile specification.

        Args:
            spec: Path to profile JSON or profile name string.
            executor: Optional executor to attach.

        Returns:
            SandboxDeps configured for the requested profile.
        """
        if isinstance(spec, Path):
            return SandboxDeps(profile_path=spec, executor=executor)

        # Accept either path-like strings or profile names
        possible_path = Path(spec).expanduser()
        if possible_path.exists() or "/" in spec or spec.endswith(".json") or "\\" in spec:
            return SandboxDeps(profile_path=possible_path, executor=executor)

        # Treat as profile name.
        return SandboxDeps(profile_name=spec, executor=executor)

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
                tool_name = self._make_tool_name(pname)
                # Main command tool
                tools.append(
                    Tool(
                        name=tool_name,
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

            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, object]) -> list[TextContent]:  # type: ignore[misc]
            """Handle MCP tool calls."""
            # Parse tool name to extract profile and action
            profile_name = None
            for pname in self.deps_by_profile.keys():
                if name == self._make_tool_name(pname):
                    profile_name = pname
                    break

            if profile_name is None:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            pdeps = self.deps_by_profile[profile_name]

            try:
                cmd_input = CommandInput(**arguments)  # type: ignore[arg-type]
                result = await run_command(pdeps, cmd_input)
                return [
                    TextContent(
                        type="text",
                        text=self._format_command_output(result),
                    )
                ]

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

        @self.server.read_resource()
        async def read_resource(uri: object) -> str:  # type: ignore[misc]
            """Read resource content."""
            uri_str = str(uri)
            if uri_str.startswith("sandbox://profiles/"):
                profile_name = uri_str.split("/")[-1]
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
        commands_list = deps.profile.allowed_commands[:5]
        commands = ", ".join(commands_list)
        if len(deps.profile.allowed_commands) > 5:
            commands += f", ... ({len(deps.profile.allowed_commands)} total)"
        if not commands:
            commands = "commands permitted by the profile rules"

        executor = getattr(deps, "executor", None)
        if executor is None:
            host_info = "local sandbox"
        else:
            host = getattr(executor, "host", None)
            if host:
                host_info = f"remote host {host}"
            else:
                host_info = f"{executor.__class__.__name__}"

        network_note = (
            "network isolated" if deps.profile.network_isolation else "network access allowed"
        )

        return (
            f"Execute read-only commands in '{deps.profile.name}' sandbox on {host_info}. "
            f"Allowed commands include: {commands}. "
            f'{network_note}. Provide arguments as {{"command": ["ls", "/"]}}.'
        )

    def _make_tool_name(self, profile_name: str) -> str:
        """Create deterministic tool names optionally including executor label."""
        if self._executor_label:
            return f"sandbox_{self._executor_label}_{profile_name}"
        return f"sandbox_{profile_name}"

    def _format_command_output(self, result: CommandOutput) -> str:
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
        options = InitializationOptions(
            server_name="shannot-sandbox",
            server_version=__version__,
            capabilities=ServerCapabilities(),
        )

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, options)

    async def cleanup(self) -> None:
        """Cleanup resources associated with the server."""
        for deps in self.deps_by_profile.values():
            try:
                await deps.cleanup()
            except Exception as exc:
                logger.debug("Failed to cleanup sandbox dependencies: %s", exc)


# Export
__all__ = ["ShannotMCPServer"]
