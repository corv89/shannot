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

from shannot import __version__
from shannot.execution import SandboxExecutor
from shannot.tools import CommandInput, CommandOutput, SandboxDeps, run_command
from shannot.validation import ValidationError

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
        self._register_prompts()

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
                cmd_input = CommandInput.from_dict(arguments)  # type: ignore[arg-type]
                result = await run_command(pdeps, cmd_input)
                return [
                    TextContent(
                        type="text",
                        text=self._format_command_output(result),
                    )
                ]

            except ValidationError as e:
                logger.error(f"Tool validation failed: {e}", exc_info=True)
                return [TextContent(type="text", text=f"Invalid input: {str(e)}")]
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

    def _register_prompts(self) -> None:
        """Register MCP prompts for diagnostic workflows."""

        @self.server.list_prompts()
        async def list_prompts() -> list[Prompt]:
            """List available diagnostic prompt templates."""
            return [
                Prompt(
                    name="system-health-check",
                    description=(
                        "Perform a comprehensive system health assessment checking "
                        "disk space, memory, CPU, processes, and uptime"
                    ),
                    arguments=[
                        PromptArgument(
                            name="target",
                            description=(
                                "Target environment for context (e.g., 'production', 'staging')"
                            ),
                            required=False,
                        )
                    ],
                ),
                Prompt(
                    name="investigate-performance",
                    description=(
                        "Diagnose performance issues by checking resource consumption "
                        "and identifying bottlenecks"
                    ),
                    arguments=[
                        PromptArgument(
                            name="symptom",
                            description=(
                                "Observed symptom "
                                "(e.g., 'slow response', 'high load', 'memory exhaustion')"
                            ),
                            required=False,
                        )
                    ],
                ),
                Prompt(
                    name="analyze-logs",
                    description=(
                        "Search and analyze system logs to identify errors, warnings, and anomalies"
                    ),
                    arguments=[
                        PromptArgument(
                            name="log_path",
                            description=(
                                "Specific log file path to analyze (e.g., '/var/log/syslog')"
                            ),
                            required=False,
                        ),
                        PromptArgument(
                            name="timeframe",
                            description="Time period to analyze (e.g., 'last hour', 'today')",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="disk-usage-audit",
                    description=(
                        "Audit disk space usage to identify what's consuming storage "
                        "and potential cleanup targets"
                    ),
                    arguments=[
                        PromptArgument(
                            name="threshold",
                            description="Alert if disk usage exceeds this percentage (e.g., '80')",
                            required=False,
                        )
                    ],
                ),
                Prompt(
                    name="monitor-processes",
                    description=(
                        "Monitor and analyze running processes to identify "
                        "resource-intensive or unusual activity"
                    ),
                    arguments=[
                        PromptArgument(
                            name="sort_by",
                            description="Sort criteria: 'cpu', 'memory', or 'time'",
                            required=False,
                        )
                    ],
                ),
                Prompt(
                    name="check-service-status",
                    description="Check the status and health of a specific system service",
                    arguments=[
                        PromptArgument(
                            name="service_name",
                            description=(
                                "Name of the service to check (e.g., 'nginx', 'postgresql')"
                            ),
                            required=True,
                        )
                    ],
                ),
            ]

        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
            """Generate prompt content based on name and arguments."""
            args = arguments or {}

            if name == "system-health-check":
                return self._generate_health_check_prompt(args)
            elif name == "investigate-performance":
                return self._generate_performance_prompt(args)
            elif name == "analyze-logs":
                return self._generate_log_analysis_prompt(args)
            elif name == "disk-usage-audit":
                return self._generate_disk_audit_prompt(args)
            elif name == "monitor-processes":
                return self._generate_process_monitoring_prompt(args)
            elif name == "check-service-status":
                return self._generate_service_check_prompt(args)
            else:
                raise ValueError(f"Unknown prompt: {name}")

    def _generate_health_check_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate system health check prompt."""
        target = args.get("target", "the system")
        tool_name = self._get_diagnostics_tool_name()

        prompt_text = f"""Please perform a comprehensive health check of {target}.
Use the {tool_name} tool to:

1. **Disk Space**: Check available disk space across all mounted filesystems
   - Run: `df -h`
   - Alert if any filesystem is >80% full

2. **Memory Usage**: Check RAM and swap utilization
   - Run: `free -h`
   - Note if swap is being heavily used

3. **CPU Load**: Check system load averages
   - Run: `uptime`
   - Compare load to number of CPU cores

4. **Running Processes**: Identify resource-intensive processes
   - Run: `ps aux --sort=-%cpu | head -20` for top CPU consumers
   - Run: `ps aux --sort=-%mem | head -20` for top memory consumers

5. **System Information**: Get basic system info
   - Run: `cat /etc/os-release` for OS version
   - Run: `env` to check environment

After gathering this information, provide a summary with:
- Overall health status (healthy/warning/critical)
- Any issues requiring attention
- Recommendations for improvement"""

        return GetPromptResult(
            description=f"System health check for {target}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    def _generate_performance_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate performance investigation prompt."""
        symptom = args.get("symptom", "performance issues")
        tool_name = self._get_diagnostics_tool_name()

        prompt_text = f"""The system is experiencing {symptom}.
Please investigate using the {tool_name} tool:

1. **Identify Top Resource Consumers**:
   - CPU: `ps aux --sort=-%cpu | head -20`
   - Memory: `ps aux --sort=-%mem | head -20`
   - Look for processes consuming excessive resources

2. **Check System Load**:
   - Run: `uptime`
   - Compare 1-min, 5-min, 15-min load averages

3. **Memory Pressure**:
   - Run: `free -h`
   - Check if swap is active (indicates memory pressure)

4. **Disk I/O** (if supported):
   - Run: `df -h` to check disk space
   - Full disks can cause performance issues

5. **Recent Errors**:
   - Check: `tail -100 /var/log/syslog` or `/var/log/messages`
   - Look for errors correlating with performance issues

Provide a diagnosis with:
- Most likely cause of {symptom}
- Which resources are constrained
- Recommended actions to resolve the issue"""

        return GetPromptResult(
            description=f"Performance investigation for: {symptom}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    def _generate_log_analysis_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate log analysis prompt."""
        log_path = args.get("log_path", "/var/log/syslog or /var/log/messages")
        timeframe = args.get("timeframe", "recent entries")
        tool_name = self._get_diagnostics_tool_name()

        prompt_text = f"""Please analyze system logs for {timeframe}. Use the {tool_name} tool:

1. **Identify Available Logs**:
   - Run: `ls -lh /var/log/`
   - Target: {log_path}

2. **Check for Errors**:
   - Run: `grep -i error {log_path} | tail -50`
   - Run: `grep -i fail {log_path} | tail -50`
   - Run: `grep -i critical {log_path} | tail -50`

3. **Check for Warnings**:
   - Run: `grep -i warn {log_path} | tail -50`

4. **Recent Activity**:
   - Run: `tail -100 {log_path}`

5. **Pattern Analysis**:
   - Look for repeated error messages
   - Identify any error spikes or patterns
   - Check timestamps for correlation with issues

Provide a summary including:
- Most significant errors or warnings found
- Any patterns or trends
- Recommended actions based on log findings"""

        return GetPromptResult(
            description=f"Log analysis for {log_path} ({timeframe})",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    def _generate_disk_audit_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate disk usage audit prompt."""
        threshold = args.get("threshold", "80")
        tool_name = self._get_diagnostics_tool_name()

        prompt_text = f"""Please audit disk space usage and identify storage consumption.
Use the {tool_name} tool:

1. **Overall Disk Usage**:
   - Run: `df -h`
   - Alert if any filesystem exceeds {threshold}% capacity

2. **Largest Directories** (if find is available):
   - Run: `find /var -type f -size +100M 2>/dev/null | head -20`
   - Run: `find /usr -type f -size +100M 2>/dev/null | head -20`
   - Run: `find /tmp -type f -size +100M 2>/dev/null | head -20`

3. **Log File Sizes**:
   - Run: `ls -lhS /var/log/ | head -20`
   - Identify large log files that could be rotated

4. **Check Cache Directories**:
   - Run: `ls -lh /var/cache/` if accessible

Provide a report with:
- Filesystems exceeding {threshold}% capacity
- Largest files and directories found
- Recommendations for cleanup (old logs, caches, tmp files)
- Estimated space that could be reclaimed"""

        return GetPromptResult(
            description=f"Disk usage audit (threshold: {threshold}%)",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    def _generate_process_monitoring_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate process monitoring prompt."""
        sort_by = args.get("sort_by", "cpu")
        tool_name = self._get_diagnostics_tool_name()

        sort_options = {
            "cpu": ("-%cpu", "CPU usage"),
            "memory": ("-%mem", "memory usage"),
            "time": ("-time", "running time"),
        }
        sort_flag, sort_desc = sort_options.get(sort_by, ("-%cpu", "CPU usage"))

        prompt_text = f"""Please monitor and analyze running processes sorted by {sort_desc}.
Use the {tool_name} tool:

1. **Top Processes by {sort_desc.title()}**:
   - Run: `ps aux --sort={sort_flag} | head -20`
   - Identify highest resource consumers

2. **Process Count**:
   - Run: `ps aux | wc -l`
   - Count total running processes

3. **System Load**:
   - Run: `uptime`
   - Check load averages

4. **Unusual Processes**:
   - Look for unexpected or unknown processes
   - Check for processes with unusual resource patterns
   - Identify any zombie or defunct processes

5. **User Context**:
   - Run: `ps aux` to see which users own processes
   - Identify if specific users/services are problematic

Provide analysis including:
- Top 10 processes by {sort_desc}
- Any unusual or suspicious processes
- Recommendations for optimization
- Whether process count is healthy for the system"""

        return GetPromptResult(
            description=f"Process monitoring (sorted by: {sort_by})",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    def _generate_service_check_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate service status check prompt."""
        service_name = args.get("service_name", "")
        if not service_name:
            raise ValueError("service_name argument is required")

        tool_name = self._get_diagnostics_tool_name()

        prompt_text = f"""Please check the status and health of the '{service_name}' service.
Use the {tool_name} tool:

1. **Check if Service Process is Running**:
   - Run: `ps aux | grep -i {service_name}`
   - Look for active {service_name} processes

2. **Check Service Logs**:
   - Run: `grep -i {service_name} /var/log/syslog | tail -50` (or /var/log/messages)
   - Look for recent errors or warnings

3. **Check Service-Specific Logs** (if accessible):
   - Common paths: `/var/log/{service_name}/`
   - Try: `ls -la /var/log/{service_name}/` or `ls -la /var/log/ | grep -i {service_name}`
   - Read recent entries if log files found

4. **Resource Usage**:
   - Run: `ps aux | grep -i {service_name}`
   - Note CPU and memory usage of service processes

5. **Port Listening** (if netstat-like tools available):
   - Check if service is listening on expected ports

Provide a status report with:
- Is {service_name} running? (yes/no)
- Resource consumption (CPU, memory)
- Any recent errors in logs
- Overall health assessment (healthy/degraded/down)
- Recommended actions if issues found"""

        return GetPromptResult(
            description=f"Service status check for: {service_name}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    def _get_diagnostics_tool_name(self) -> str:
        """Get the name of the diagnostics sandbox tool."""
        # Find diagnostics profile or any available profile
        for pname in self.deps_by_profile.keys():
            if "diagnostics" in pname.lower():
                return self._make_tool_name(pname)

        # Fallback to any available profile
        if self.deps_by_profile:
            return self._make_tool_name(next(iter(self.deps_by_profile.keys())))

        return "sandbox_diagnostics"

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
            capabilities=ServerCapabilities(
                tools=ToolsCapability(),  # We provide tools
                resources=ResourcesCapability(),  # We provide resources
                prompts=PromptsCapability(),  # We provide prompts
            ),
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
