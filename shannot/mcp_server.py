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

        bwrap_errors = 0
        for spec in profile_paths:
            try:
                deps = self._create_deps_from_spec(spec, executor)
                self.deps_by_profile[deps.profile.name] = deps
                logger.info(f"Loaded profile: {deps.profile.name}")
            except Exception as e:
                logger.error(f"Failed to load profile {spec}: {e}")
                if "Bubblewrap executable not found" in str(e):
                    bwrap_errors += 1

        # Warn if no profiles loaded due to missing bubblewrap
        if len(self.deps_by_profile) == 0 and bwrap_errors > 0:
            import platform

            if platform.system() == "Darwin":
                logger.warning(
                    "No profiles loaded: Bubblewrap is not available on macOS. "
                    "To use Shannot tools, configure remote execution with --target. "
                    "See: https://corv89.github.io/shannot/usage/#remote-execution"
                )
            else:
                logger.warning(
                    "No profiles loaded: Bubblewrap not found. "
                    "Install bubblewrap or configure remote execution with --target. "
                    "See: https://corv89.github.io/shannot/installation/"
                )

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

        # Register handlers once for all profiles
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
                Prompt(
                    name="check-kernel-logs",
                    description=(
                        "Access and analyze kernel logs using journalctl for hardware, "
                        "driver, and low-level system diagnostics"
                    ),
                    arguments=[
                        PromptArgument(
                            name="timeframe",
                            description="Time period to analyze (e.g., 'last hour', 'since boot')",
                            required=False,
                        ),
                        PromptArgument(
                            name="priority",
                            description="Log priority filter (e.g., 'err', 'warning', 'info')",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="list-running-services",
                    description=(
                        "Discover active systemd services using filesystem-based methods "
                        "(cgroup parsing) without requiring D-Bus access"
                    ),
                    arguments=[],
                ),
                Prompt(
                    name="check-service-resources",
                    description=(
                        "Check resource usage (memory, CPU, I/O) of a specific service "
                        "using cgroup statistics"
                    ),
                    arguments=[
                        PromptArgument(
                            name="service_name",
                            description="Name of the service (e.g., 'nginx', 'postgresql')",
                            required=True,
                        ),
                    ],
                ),
                Prompt(
                    name="discover-failed-services",
                    description=(
                        "Find services that failed recently by analyzing journal logs "
                        "for error messages"
                    ),
                    arguments=[
                        PromptArgument(
                            name="timeframe",
                            description="Time period to check (e.g., 'today', '1 hour ago')",
                            required=False,
                        ),
                        PromptArgument(
                            name="priority",
                            description="Log priority level (default: 'err')",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="analyze-service-logs",
                    description=(
                        "Deep analysis of a specific service's logs to diagnose issues, "
                        "find errors, and track restart events"
                    ),
                    arguments=[
                        PromptArgument(
                            name="service_name",
                            description="Name of the service to analyze",
                            required=True,
                        ),
                        PromptArgument(
                            name="timeframe",
                            description="Time period to analyze (default: '1 hour ago')",
                            required=False,
                        ),
                        PromptArgument(
                            name="priority",
                            description="Minimum log priority (default: 'info')",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="monitor-service-health",
                    description=(
                        "Comprehensive health check for a service combining cgroup stats, "
                        "process info, and log analysis"
                    ),
                    arguments=[
                        PromptArgument(
                            name="service_name",
                            description="Name of the service to monitor",
                            required=True,
                        ),
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
            elif name == "check-kernel-logs":
                return self._generate_kernel_logs_prompt(args)
            elif name == "list-running-services":
                return self._generate_list_running_services_prompt(args)
            elif name == "check-service-resources":
                return self._generate_check_service_resources_prompt(args)
            elif name == "discover-failed-services":
                return self._generate_discover_failed_services_prompt(args)
            elif name == "analyze-service-logs":
                return self._generate_analyze_service_logs_prompt(args)
            elif name == "monitor-service-health":
                return self._generate_monitor_service_health_prompt(args)
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

    def _generate_kernel_logs_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate kernel log analysis prompt."""
        timeframe = args.get("timeframe", "recent entries")
        priority = args.get("priority", "all priorities")
        tool_name = self._get_systemd_tool_name()

        prompt_text = f"""Please analyze kernel logs for {timeframe} ({priority}).
Use the {tool_name} tool with the systemd profile:

1. **Access Kernel Ring Buffer via journalctl**:
   - Run: `journalctl -k` (kernel messages only)
   - Or: `journalctl --dmesg` (equivalent to -k)
   - For time filtering: `journalctl -k --since "1 hour ago"`
   - For specific boot: `journalctl -k -b 0` (current boot)

2. **Filter by Priority** (if {priority} != 'all priorities'):
   - Errors only: `journalctl -k -p err`
   - Warnings: `journalctl -k -p warning`
   - Info and above: `journalctl -k -p info`
   - All messages: `journalctl -k` (default)

3. **Common Kernel Log Diagnostic Patterns**:
   - Hardware errors: `journalctl -k | grep -i "error\\|fail"`
   - Driver issues: `journalctl -k | grep -i "driver"`
   - Disk problems: `journalctl -k | grep -i "ata\\|scsi\\|disk\\|sda\\|nvme"`
   - Memory issues: `journalctl -k | grep -i "oom\\|memory\\|killed process"`
   - Network hardware: `journalctl -k | grep -i "eth\\|wlan\\|network"`
   - USB devices: `journalctl -k | grep -i "usb"`
   - Firmware: `journalctl -k | grep -i "firmware"`

4. **Time-Based Analysis**:
   - Current boot: `journalctl -k -b 0`
   - Previous boot: `journalctl -k -b -1`
   - Last hour: `journalctl -k --since "1 hour ago"`
   - Last 24h: `journalctl -k --since "24 hours ago"`
   - Since specific time: `journalctl -k --since "2024-01-01 00:00:00"`

5. **Combined Filters** (examples):
   - Recent errors: `journalctl -k -p err --since "1 hour ago"`
   - Boot errors: `journalctl -k -b 0 -p err`
   - Hardware warnings: `journalctl -k -p warning | grep -i "hardware"`

**Important Notes**:
- `journalctl -k` and `journalctl --dmesg` access the same kernel ring buffer data
- Traditional `dmesg` command may require CAP_SYSLOG capability (restricted)
- journalctl reads from /var/log/journal and /run/log/journal (accessible via systemd profile)
- User must be in `systemd-journal` group for full access to historical logs
- Requires systemd profile with journal bind mounts enabled

**Limitations**:
- Live following (`journalctl -kf`) won't work in read-only sandbox
- Some very early boot messages may not be captured in journal

Provide comprehensive analysis including:
- **Critical Issues**: Any hardware errors, driver failures, or system crashes
- **Warnings**: Important warnings that need attention
- **Patterns**: Recurring messages or error sequences
- **Hardware Health**: Assessment of hardware-level problems (disk, memory, network)
- **Driver Status**: Any driver loading failures or incompatibilities
- **Recommendations**: Suggested actions based on kernel messages found
- **Timeline**: When issues occurred (if time-based patterns exist)"""

        return GetPromptResult(
            description=f"Kernel log analysis ({timeframe}, {priority})",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    def _generate_list_running_services_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate prompt for listing running services without D-Bus."""
        tool_name = self._get_systemd_tool_name()

        prompt_text = f"""Please discover active systemd services using filesystem-based methods.
Use the {tool_name} tool with the systemd profile:

**Important**: This profile does NOT have D-Bus access, so `systemctl` commands won't work.
Instead, use filesystem-based service discovery methods:

1. **List Running Services via cgroup Filesystem**:
   - Run: `ls -1 /sys/fs/cgroup/system.slice/ | grep '\\.service$'`
   - This shows all services with active cgroups
   - Each directory represents a running service

2. **Verify Services Have Active Processes**:
   - For each service, check: `cat /sys/fs/cgroup/system.slice/<service>/cgroup.procs`
   - Non-empty file = service has running processes
   - Example: `cat /sys/fs/cgroup/system.slice/nginx.service/cgroup.procs`

3. **Use systemd-cgls for Tree View**:
   - Run: `systemd-cgls /sys/fs/cgroup/system.slice`
   - Shows hierarchical view of services and processes
   - No D-Bus required for this operation

4. **Cross-Reference with Journal** (optional):
   - Run: `journalctl -F _SYSTEMD_UNIT | grep '\\.service$'`
   - Shows services that have logged (may include stopped services)
   - Combine with cgroup listing for comprehensive view

5. **Count Processes per Service**:
   - For each service: `cat /sys/fs/cgroup/system.slice/<service>/cgroup.procs | wc -l`
   - Shows how many processes the service has

**Limitations**:
- Cannot show service state (active/inactive/failed) like `systemctl list-units`
- Only shows services with active cgroup directories
- User services require checking `/sys/fs/cgroup/user.slice/` separately
- Service state must be inferred from cgroup existence + log analysis

**What This Method Provides**:
- ✅ List of running services
- ✅ Process count per service
- ✅ Service hierarchy (via systemd-cgls)
- ❌ Service state (active/failed/inactive) - use logs to infer
- ❌ Service dependencies - parse unit files if needed

Provide a summary including:
- **Running Services**: List of active services found
- **Process Count**: How many processes each service has
- **Health Indicators**: Any services with unusual characteristics
- **Next Steps**: Suggestions for specific services to investigate further"""

        return GetPromptResult(
            description="List running services (filesystem-based discovery)",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    def _generate_check_service_resources_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate prompt for checking service resource usage via cgroups."""
        service_name = args.get("service_name", "")
        if not service_name:
            raise ValueError("service_name argument is required")

        # Add .service suffix if not present
        if not service_name.endswith(".service"):
            service_name = f"{service_name}.service"

        tool_name = self._get_systemd_tool_name()

        prompt_text = f"""Please analyze resource usage for {service_name} using cgroup statistics.
Use the {tool_name} tool with the systemd profile:

**Important**: No D-Bus access available - using cgroup v2 filesystem instead.

1. **Check if Service is Running**:
   - Run: `test -d /sys/fs/cgroup/system.slice/{service_name} && echo "Running" \\
     || echo "Not Running"`
   - Or: `ls -la /sys/fs/cgroup/system.slice/{service_name}/`

2. **Get Process Information**:
   - List PIDs: `cat /sys/fs/cgroup/system.slice/{service_name}/cgroup.procs`
   - Process details: `ps -p $(cat /sys/fs/cgroup/system.slice/{service_name}/cgroup.procs) \\
     -o pid,user,comm,%cpu,%mem,vsz,rss,start,time,args`

3. **Memory Usage**:
   - Current memory: `cat /sys/fs/cgroup/system.slice/{service_name}/memory.current`
   - Memory limit: `cat /sys/fs/cgroup/system.slice/{service_name}/memory.max`
   - Peak memory: `cat /sys/fs/cgroup/system.slice/{service_name}/memory.peak`
   - Detailed stats: `cat /sys/fs/cgroup/system.slice/{service_name}/memory.stat`
   - **Note**: Values are in bytes. Divide by 1048576 for MB, 1073741824 for GB.

4. **CPU Statistics**:
   - CPU stats: `cat /sys/fs/cgroup/system.slice/{service_name}/cpu.stat`
   - Shows `usage_usec` (total CPU time in microseconds)
   - Shows `user_usec` and `system_usec` (user vs kernel CPU time)
   - **Note**: These are cumulative values since service start

5. **I/O Statistics** (if available):
   - I/O stats: `cat /sys/fs/cgroup/system.slice/{service_name}/io.stat`
   - Shows read/write bytes and operations per device

6. **Live Monitoring with systemd-cgtop**:
   - Run: `systemd-cgtop --depth=3 -n 1 | grep {service_name}`
   - Shows formatted CPU%, memory usage, and tasks

7. **Check Recent Logs for Context**:
   - Last 20 lines: `journalctl -u {service_name} -n 20 --no-pager`
   - Recent errors: `journalctl -u {service_name} -p err --since "1 hour ago"`

**Interpreting cgroup Values**:
- `memory.current`: Current memory usage in bytes
- `memory.max`: Memory limit (may be "max" for unlimited)
- `cpu.stat usage_usec`: Total CPU microseconds consumed
- `cgroup.procs`: One PID per line

**Limitations**:
- Cannot get service uptime from cgroups (check journal start time instead)
- CPU usage is cumulative time, not current percentage
- systemd-cgtop provides percentage but is a snapshot
- No service state information (use logs to infer health)

Provide analysis including:
- **Status**: Running or Not Running
- **Resource Usage**: Memory (in MB/GB), CPU time
- **Process Count**: Number of active processes
- **Health Assessment**: Based on resource consumption and logs
- **Recommendations**: If memory/CPU usage seems unusual"""

        return GetPromptResult(
            description=f"Resource usage analysis for {service_name}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    def _generate_discover_failed_services_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate prompt for discovering failed services via journal analysis."""
        timeframe = args.get("timeframe", "today")
        priority = args.get("priority", "err")
        tool_name = self._get_systemd_tool_name()

        prompt_text = f"""Please find services that failed recently by analyzing journal logs.
Use the {tool_name} tool with the systemd profile:

**Important**: Without D-Bus access, cannot query `systemctl --failed`.
Instead, analyze journal logs to infer service failures.

1. **Find Error-Level Messages from systemd**:
   - Run: `journalctl -p {priority} --since "{timeframe}" | grep -E '\\.service|Failed|failed'`
   - Look for patterns like "Failed to start", "Main process exited"

2. **Extract Units with Errors**:
   - Run: `journalctl -p {priority} --since "{timeframe}" --no-pager | \\
     grep -oP '[a-zA-Z0-9_-]+\\.service' | sort -u`
   - Lists unique service names that appeared in error logs

3. **Search for Specific Failure Patterns**:
   - Failed starts: `journalctl --since "{timeframe}" | grep -i "failed to start"`
   - Service exits: `journalctl --since "{timeframe}" | grep -i "main process exited"`
   - Core dumps: `journalctl --since "{timeframe}" | grep -i "core dump"`
   - Timeouts: `journalctl --since "{timeframe}" | grep -i "timeout"`

4. **Analyze Each Failed Service**:
   - For each service found, get detailed logs:
   - Run: `journalctl -u <service_name> -p {priority} --since "{timeframe}" --no-pager`
   - Look for error messages, exit codes, and stack traces

5. **Check for Restart Loops**:
   - Run: `journalctl --since "{timeframe}" | grep -E "Started|Stopped" | grep <service_name>`
   - Multiple start/stop cycles indicate instability

6. **Cross-Reference with Running Services**:
   - Check if failed service is currently running:
   - Run: `test -d /sys/fs/cgroup/system.slice/<service>.service && \\
     echo "Now Running" || echo "Still Failed"`

**Common Failure Indicators**:
- "code=exited, status=1" - Service exited with error
- "code=killed, signal=KILL" - Service was killed (OOM?)
- "code=killed, signal=TERM" - Service was terminated
- "Start request repeated too quickly" - Restart loop
- "Failed with result 'timeout'" - Service took too long to start
- "Failed with result 'exit-code'" - Service crashed on startup

**Limitations**:
- Relies on journal entries (may miss silent failures)
- Cannot query systemd manager state directly
- Some services may fail without logging to journal
- Requires systemd-journal group for full log access

Provide summary including:
- **Failed Services**: List of services with errors in timeframe
- **Failure Types**: Exit codes, signals, timeout, etc.
- **Error Messages**: Key error messages for each service
- **Current Status**: Whether services are now running
- **Recommendations**: Actions to diagnose or fix issues"""

        return GetPromptResult(
            description=f"Discover failed services ({timeframe}, priority={priority})",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    def _generate_analyze_service_logs_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate prompt for deep service log analysis."""
        service_name = args.get("service_name", "")
        if not service_name:
            raise ValueError("service_name argument is required")

        # Add .service suffix if not present
        if not service_name.endswith(".service"):
            service_name = f"{service_name}.service"

        timeframe = args.get("timeframe", "1 hour ago")
        priority = args.get("priority", "info")
        tool_name = self._get_systemd_tool_name()

        prompt_text = f"""Please perform deep analysis of {service_name} logs to diagnose issues.
Use the {tool_name} tool with the systemd profile:

1. **Get Recent Logs**:
   - Run: `journalctl -u {service_name} --since "{timeframe}" -p {priority} --no-pager`
   - Shows all messages at {priority} level and above

2. **Search for Error Patterns**:
   - Errors: `journalctl -u {service_name} --since "{timeframe}" | \\
     grep -iE "error|fail|exception|timeout"`
   - Refused connections: `journalctl -u {service_name} --since "{timeframe}" | \\
     grep -i "refused\\|denied"`
   - Crashes: `journalctl -u {service_name} --since "{timeframe}" | \\
     grep -iE "crash|segfault|core dump"`

3. **Track Service Lifecycle Events**:
   - Start/stop events: `journalctl -u {service_name} --since "{timeframe}" | \\
     grep -iE "start|stop|restart|reload"`
   - Count restarts: `journalctl -u {service_name} --since "{timeframe}" | \\
     grep -c "Started"`
   - Last start: `journalctl -u {service_name} | grep "Started" | tail -1`

4. **Analyze Log Volume**:
   - Total entries: `journalctl -u {service_name} --since "{timeframe}" | wc -l`
   - By priority:
     - Errors: `journalctl -u {service_name} --since "{timeframe}" -p err | wc -l`
     - Warnings: `journalctl -u {service_name} --since "{timeframe}" -p warning | wc -l`
     - Info: `journalctl -u {service_name} --since "{timeframe}" -p info | wc -l`

5. **Boot History** (if available):
   - List boots: `journalctl -u {service_name} --list-boots | tail -5`
   - Previous boot logs: `journalctl -u {service_name} -b -1 -n 50 --no-pager`
   - Compare with current boot

6. **Time-Based Pattern Analysis**:
   - Last hour: `journalctl -u {service_name} --since "1 hour ago" -n 100`
   - Specific time range: `journalctl -u {service_name} \\
     --since "2024-01-01 10:00" --until "2024-01-01 11:00"`
   - Follow live (limited in sandbox): `journalctl -u {service_name} -f -n 20`

7. **Extract Specific Information**:
   - Exit codes: `journalctl -u {service_name} | grep "code=exited"`
   - Signals: `journalctl -u {service_name} | grep "code=killed"`
   - Configuration changes: `journalctl -u {service_name} | grep -i "config\\|reload"`

**journalctl Pro Tips**:
- `-o json`: Output as JSON for parsing
- `-o verbose`: Show all metadata fields
- `-p <priority>`: Filter by syslog priority (emerg/alert/crit/err/warning/notice/info/debug)
- `--since` and `--until`: Time ranges
- `-n <number>`: Limit output lines
- `--no-pager`: Don't use less/more (better for scripting)

**Limitations**:
- No live following in read-only sandbox
- Boot logs require persistent journal (journald configuration)
- Full access requires systemd-journal group membership

Provide comprehensive analysis:
- **Summary**: Overall service health and activity level
- **Error Analysis**: Types and frequency of errors
- **Lifecycle**: Start/stop/restart patterns and timestamps
- **Anomalies**: Unusual log patterns or error spikes
- **Timeline**: Key events in chronological order
- **Root Cause**: Likely cause of any issues found
- **Recommendations**: Specific actions to resolve problems"""

        return GetPromptResult(
            description=f"Deep log analysis for {service_name} ({timeframe})",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    def _generate_monitor_service_health_prompt(self, args: dict[str, str]) -> GetPromptResult:
        """Generate comprehensive service health monitoring prompt."""
        service_name = args.get("service_name", "")
        if not service_name:
            raise ValueError("service_name argument is required")

        # Add .service suffix if not present
        if not service_name.endswith(".service"):
            service_name = f"{service_name}.service"

        tool_name = self._get_systemd_tool_name()

        prompt_text = f"""Please perform a comprehensive health check for {service_name}.
Use the {tool_name} tool with the systemd profile:

**This combines cgroup statistics, process information, and log analysis for \\
complete service health assessment.**

1. **Check Running Status** (cgroup-based):
   - Run: `test -d /sys/fs/cgroup/system.slice/{service_name} && \\
     echo "RUNNING" || echo "NOT RUNNING"`
   - If running, continue with detailed checks

2. **Process Information**:
   - List PIDs: `cat /sys/fs/cgroup/system.slice/{service_name}/cgroup.procs`
   - Full process details:
     ```
     ps -p $(cat /sys/fs/cgroup/system.slice/{service_name}/cgroup.procs \\
       2>/dev/null || echo 1) \\
       -o pid,ppid,user,%cpu,%mem,vsz,rss,stat,start,time,comm,args 2>/dev/null
     ```

3. **Resource Usage**:
   - Memory: `cat /sys/fs/cgroup/system.slice/{service_name}/memory.current`
   - CPU stats: `cat /sys/fs/cgroup/system.slice/{service_name}/cpu.stat`
   - Live view: `systemd-cgtop --depth=3 -n 1 | grep {service_name}`
   - Convert memory bytes to MB: divide by 1048576

4. **Recent Log Analysis**:
   - Last 50 lines: `journalctl -u {service_name} -n 50 --no-pager`
   - Recent errors: `journalctl -u {service_name} -p err \\
     --since "1 hour ago"`
   - Count errors today: `journalctl -u {service_name} -p err \\
     --since today | wc -l`

5. **Restart Analysis** (last 24 hours):
   - Count restarts: `journalctl -u {service_name} --since "24 hours ago" | \\
     grep -c "Started\\|Stopped"`
   - Last start time: `journalctl -u {service_name} | \\
     grep "Started" | tail -1`
   - Any crashes: `journalctl -u {service_name} --since "24 hours ago" | \\
     grep -i "core dump\\|segfault"`

6. **Port/Network Status** (if ss is available):
   - Listening ports: `ss -tlnp 2>/dev/null | \\
     grep -i {service_name.replace(".service", "")}`
   - Or: `ps -p $(cat /sys/fs/cgroup/system.slice/{service_name}/cgroup.procs) \\
     -o pid | tail -n +2 | xargs -I {{}} ss -tlnp | grep {{}}`

7. **Configuration File Check** (common locations):
   - Service unit: `cat /lib/systemd/system/{service_name} 2>/dev/null || \\
     cat /etc/systemd/system/{service_name}`
   - Check for MemoryMax, CPUQuota limits
   - App config: `ls -l /etc/{service_name.replace(".service", "")}/ 2>/dev/null`

8. **Health Score Indicators**:
   - ✅ Running with processes: Healthy
   - ⚠️ Running but errors in logs: Degraded
   - ⚠️ Running but frequent restarts: Unstable
   - ⚠️ High memory usage (>80% of limit): Resource pressure
   - ❌ Not running + recent errors: Failed
   - ❌ Not running + crash logs: Crashed

**Determine Health Status**:
- **Healthy**: Running, no errors, stable, normal resource usage
- **Degraded**: Running but errors/warnings in logs
- **Unstable**: Frequent restarts, intermittent errors
- **Resource-Constrained**: High memory/CPU usage approaching limits
- **Failed**: Not running with recent error logs
- **Unknown**: Cannot determine (insufficient data)

**Limitations**:
- Cannot query systemd state directly (no D-Bus)
- Service uptime must be inferred from journal start time
- systemctl-specific fields unavailable (SubState, LoadState, etc.)

Provide comprehensive health report:
- **Status**: RUNNING or NOT RUNNING
- **Health**: Healthy/Degraded/Unstable/Failed/Unknown
- **Process Count**: Number of active processes
- **Resource Usage**: Memory (MB), CPU time
- **Recent Errors**: Count and summary of recent errors
- **Restart Count**: Times restarted in last 24h
- **Listening Ports**: If applicable
- **Issues Found**: Any problems detected
- **Recommendations**: Specific actions based on findings
- **Overall Assessment**: Summary and severity level"""

        return GetPromptResult(
            description=f"Comprehensive health check for {service_name}",
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

    def _get_systemd_tool_name(self) -> str:
        """Get the name of the systemd sandbox tool."""
        # Find systemd profile or fall back to diagnostics
        for pname in self.deps_by_profile.keys():
            if "systemd" in pname.lower():
                return self._make_tool_name(pname)

        # Fallback to diagnostics if systemd not found
        return self._get_diagnostics_tool_name()

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
