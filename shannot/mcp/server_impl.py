"""Shannot MCP server implementation with PyPy sandbox integration."""

from __future__ import annotations

import ast
import json
import logging
import time
from pathlib import Path
from typing import Any

from ..config import get_version, load_remotes
from ..deploy import ensure_deployed
from ..execute import execute_script
from ..remote import run_remote_dry_run
from ..runtime import find_pypy_sandbox, get_runtime_path
from ..session import Session, create_session
from ..ssh import SSHConfig, SSHConnection
from .server import MCPServer
from .types import TextContent

logger = logging.getLogger(__name__)


def find_runtime() -> dict[str, Path] | None:
    """Find PyPy sandbox runtime paths.

    Returns
    -------
    dict[str, Path] | None
        Dictionary with 'pypy_sandbox', 'lib_python', 'lib_pypy' paths,
        or None if runtime not found.
    """
    runtime_path = get_runtime_path()
    if not runtime_path:
        return None

    pypy_sandbox = find_pypy_sandbox()
    if not pypy_sandbox:
        return None

    lib_python = runtime_path / "lib-python" / "3"
    lib_pypy = runtime_path / "lib_pypy"

    if not lib_python.exists() or not lib_pypy.exists():
        return None

    return {
        "pypy_sandbox": pypy_sandbox,
        "lib_python": lib_python,
        "lib_pypy": lib_pypy,
    }


class ShannotMCPServer(MCPServer):
    """MCP server exposing Shannot PyPy sandbox capabilities.

    Provides a single sandbox_run tool that executes commands in PyPy sandbox
    with profile-based allowlisting. Per-connection trust model - commands
    execute immediately if allowed by profile.

    Attributes
    ----------
    profiles : dict[str, dict[str, Any]]
        Loaded approval profiles (profile_name -> profile_dict).
    runtime : dict[str, Path] | None
        PyPy runtime paths (lib_python, lib_pypy, pypy_sandbox).
    """

    def __init__(
        self,
        profile_paths: list[Path] | None = None,
        verbose: bool = False,
    ):
        """Initialize Shannot MCP server.

        Parameters
        ----------
        profile_paths : list[Path] | None
            Optional list of profile paths to load.
            If None, discovers profiles from config directories.
        verbose : bool
            Enable verbose logging.
        """
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        # Load profiles
        self.profiles = self._load_profiles(profile_paths)

        # Load PyPy runtime
        try:
            self.runtime = find_runtime()
            if self.runtime:
                logger.info(f"Found PyPy runtime at: {self.runtime.get('pypy_sandbox')}")
            else:
                logger.warning("PyPy runtime not found")
        except RuntimeError as e:
            logger.warning(f"PyPy runtime not found: {e}")
            self.runtime = None

        # Initialize base server
        super().__init__(name="shannot", version=get_version())

    def _load_profiles(self, profile_paths: list[Path] | None) -> dict[str, dict[str, Any]]:
        """Load approval profiles from paths or defaults.

        Parameters
        ----------
        profile_paths : list[Path] | None
            Paths to profile JSON files, or None for discovery.

        Returns
        -------
        dict[str, dict[str, Any]]
            Loaded profiles keyed by profile name.
        """
        profiles: dict[str, dict[str, Any]] = {}

        if profile_paths:
            # Load specified profiles
            for path in profile_paths:
                try:
                    # Load profile from specific path
                    data = json.loads(path.read_text())
                    profile = {
                        "auto_approve": data.get("auto_approve", []),
                        "always_deny": data.get("always_deny", []),
                    }
                    # Use filename (without .json) as profile name
                    name = path.stem
                    profiles[name] = profile
                    logger.info(f"Loaded profile '{name}' from {path}")
                except Exception as e:
                    logger.warning(f"Failed to load profile {path}: {e}")

        if not profiles:
            # Use default profiles
            profiles = self._get_default_profiles()
            logger.info(f"Using {len(profiles)} default profiles")

        return profiles

    def _get_default_profiles(self) -> dict[str, dict[str, Any]]:
        """Get default approval profiles.

        Returns
        -------
        dict[str, dict[str, Any]]
            Default profiles (minimal, readonly, diagnostics).
        """
        return {
            "minimal": {
                "auto_approve": ["ls", "cat", "grep", "find"],
                "always_deny": [
                    "rm -rf /",
                    "dd if=/dev/zero",
                    ":(){ :|:& };:",
                ],
            },
            "readonly": {
                "auto_approve": [
                    "ls",
                    "cat",
                    "grep",
                    "find",
                    "head",
                    "tail",
                    "file",
                    "stat",
                    "wc",
                    "du",
                ],
                "always_deny": [
                    "rm -rf /",
                    "dd if=/dev/zero",
                    ":(){ :|:& };:",
                ],
            },
            "diagnostics": {
                "auto_approve": [
                    "ls",
                    "cat",
                    "grep",
                    "find",
                    "head",
                    "tail",
                    "file",
                    "stat",
                    "wc",
                    "du",
                    "df",
                    "free",
                    "ps",
                    "uptime",
                    "hostname",
                    "uname",
                    "env",
                    "id",
                ],
                "always_deny": [
                    "rm -rf /",
                    "dd if=/dev/zero",
                    ":(){ :|:& };:",
                ],
            },
        }

    def _register_tools(self) -> None:
        """Register MCP tools (sandbox_run, session_result)."""
        self.register_tool(
            name="sandbox_run",
            description=(
                "Execute a Python script in PyPy sandbox with profile-based approval. "
                "**IMPORTANT**: Use Python 3.6 syntax only (PyPy sandbox limitation). "
                "Script may execute immediately (fast path), require approval (creates session), "
                "or be denied based on detected operations and profile."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": (
                            "Python 3.6 script to execute. Avoid f-strings, async/await, "
                            "walrus operators, and other modern syntax."
                        ),
                    },
                    "profile": {
                        "type": "string",
                        "description": (
                            "Approval profile for operation allowlisting. "
                            f"Available: {', '.join(self.profiles.keys())}"
                        ),
                        "default": "minimal",
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional human-readable name for session tracking",
                        "default": "mcp-request",
                    },
                    "target": {
                        "type": "string",
                        "description": (
                            "Named remote target for SSH execution (e.g., 'prod', 'staging'). "
                            "Must be configured via 'shannot remote add'. "
                            "If omitted, executes locally."
                        ),
                    },
                },
                "required": ["script"],
            },
            handler=self._handle_sandbox_run,
        )

        self.register_tool(
            name="session_result",
            description=(
                "Poll result of a pending session created by sandbox_run. "
                "Use this after receiving status='pending_approval' to check if "
                "user has approved and executed the session."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned by sandbox_run",
                    },
                },
                "required": ["session_id"],
            },
            handler=self._handle_session_result,
        )

    def _register_resources(self) -> None:
        """Register MCP resources for profile/status inspection."""
        # Resource: List of available profiles
        self.register_resource(
            uri="sandbox://profiles",
            name="Available Profiles",
            description="List of available approval profiles",
            mime_type="application/json",
            handler=self._handle_list_profiles,
        )

        # Resource: Each profile's configuration
        for profile_name in self.profiles.keys():
            self.register_resource(
                uri=f"sandbox://profiles/{profile_name}",
                name=f"Profile: {profile_name}",
                description=f"Configuration for {profile_name} profile",
                mime_type="application/json",
                handler=lambda pname=profile_name: self._handle_get_profile(pname),
            )

        # Resource: Runtime status
        self.register_resource(
            uri="sandbox://status",
            name="Runtime Status",
            description="PyPy sandbox runtime status and configuration",
            mime_type="application/json",
            handler=self._handle_status,
        )

        # Resource: Configured SSH remotes
        self.register_resource(
            uri="sandbox://remotes",
            name="SSH Remotes",
            description="List of configured SSH remote targets for sandbox_run",
            mime_type="application/json",
            handler=self._handle_list_remotes,
        )

    def _handle_sandbox_run(self, arguments: dict[str, Any]) -> TextContent:
        """Execute Python script in PyPy sandbox with hybrid approval workflow.

        Three possible execution paths:
        1. Fast path: All detected operations allowed → execute immediately
        2. Review path: Some operations need approval → create session
        3. Blocked: Denied operations detected → reject immediately

        Parameters
        ----------
        arguments : dict[str, Any]
            Tool arguments with 'script', optional 'profile', optional 'name'.

        Returns
        -------
        TextContent
            JSON response with status and results/session info.
        """
        # Get script
        script = arguments.get("script")
        if not script or not isinstance(script, str):
            return TextContent(
                text=json.dumps(
                    {"status": "error", "error": "Missing or invalid 'script' parameter"}
                )
            )

        # Get profile (default to minimal)
        profile_name = arguments.get("profile", "minimal")
        if profile_name not in self.profiles:
            return TextContent(
                text=json.dumps({"status": "error", "error": f"Unknown profile '{profile_name}'"})
            )

        profile = self.profiles[profile_name]
        session_name = arguments.get("name", "mcp-request")
        target = arguments.get("target")

        # Route to remote execution if target specified
        if target:
            return self._handle_remote_sandbox_run(
                script=script,
                profile=profile,
                profile_name=profile_name,
                session_name=session_name,
                target=target,
            )

        # AST analysis - best-effort operation detection (UX optimization, NOT security!)
        # Security is enforced at runtime by PyPy sandbox subprocess virtualization.
        # This analysis helps provide fast feedback but may miss dynamic operations.
        try:
            detected_ops = self._analyze_script_best_effort(script)
        except Exception as e:
            logger.warning(f"AST analysis failed: {e}")
            detected_ops = []

        # Check for denied operations (blocked path)
        always_deny = profile.get("always_deny", [])
        for op in detected_ops:
            for pattern in always_deny:
                if pattern in op:
                    return TextContent(
                        text=json.dumps(
                            {
                                "status": "denied",
                                "reason": f"Script contains denied operation: '{pattern}'",
                                "detected_operations": detected_ops,
                            }
                        )
                    )

        # Check if all operations are in allowlist (fast path)
        auto_approve = profile.get("auto_approve", [])
        all_allowed = (
            all(any(pattern in op for pattern in auto_approve) for op in detected_ops)
            if detected_ops
            else True
        )

        if all_allowed and detected_ops:
            # Fast path: execute immediately
            logger.info(f"Fast path: all {len(detected_ops)} operations allowed")
            return self._execute_script_fast_path(script, profile_name)

        # Review path: create session for user approval
        logger.info(f"Review path: creating session for {len(detected_ops)} operations")
        return self._create_approval_session(
            script=script,
            detected_ops=detected_ops,
            profile_name=profile_name,
            session_name=session_name,
        )

    def _analyze_script_best_effort(self, script: str) -> list[str]:
        """Analyze Python script to detect subprocess calls (best-effort, UX only).

        **IMPORTANT**: This is NOT a security boundary! It's a UX optimization to
        provide fast feedback. Security is enforced at runtime by PyPy sandbox
        subprocess virtualization. This analysis may miss:
        - Dynamic subprocess calls (eval, exec, getattr, etc.)
        - Obfuscated code
        - Operations hidden in imported modules

        Parameters
        ----------
        script : str
            Python script to analyze.

        Returns
        -------
        list[str]
            List of detected subprocess operations (e.g., ["ls /tmp", "cat file.txt"]).
        """
        detected = []

        try:
            tree = ast.parse(script)
        except SyntaxError:
            # Can't parse - return empty, will be caught at runtime
            return detected

        for node in ast.walk(tree):
            # Detect subprocess.call/run/check_output with literal arguments
            if isinstance(node, ast.Call):
                # Check for subprocess.call(['ls', '/'])
                if isinstance(node.func, ast.Attribute):
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "subprocess"
                        and node.func.attr in ("call", "run", "check_output", "Popen")
                    ):
                        # Try to extract command from first arg
                        if node.args:
                            cmd = self._extract_command_from_ast(node.args[0])
                            if cmd:
                                detected.append(cmd)

        return detected

    def _extract_command_from_ast(self, node: ast.AST) -> str | None:
        """Extract command string from AST node (best-effort).

        Parameters
        ----------
        node : ast.AST
            AST node potentially containing command.

        Returns
        -------
        str | None
            Extracted command string, or None if not extractable.
        """
        # Handle list literal: ['ls', '/tmp'] → "ls /tmp"
        if isinstance(node, ast.List):
            parts = []
            for elt in node.elts:
                if isinstance(elt, ast.Constant):
                    parts.append(str(elt.value))
                else:
                    # Non-literal element, can't extract
                    return None
            return " ".join(parts) if parts else None

        # Handle string literal: "ls /tmp" → "ls /tmp"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value

        # Can't extract (variable, function call, etc.)
        return None

    def _execute_script_fast_path(self, script: str, profile_name: str) -> TextContent:
        """Execute script immediately (all operations pre-approved).

        Parameters
        ----------
        script : str
            Python script to execute.
        profile_name : str
            Profile name (for logging/debugging).

        Returns
        -------
        TextContent
            JSON response with execution results.
        """
        # Check runtime availability
        if not self.runtime:
            return TextContent(
                text=json.dumps(
                    {
                        "status": "error",
                        "error": "PyPy sandbox runtime not found. Run 'shannot setup' to install.",
                    }
                )
            )

        try:
            start_time = time.time()

            # Execute script in PyPy sandbox using shared execution function
            result = execute_script(
                script,
                pypy_bin=self.runtime["pypy_sandbox"],
                dry_run=False,  # MCP fast-path executes directly
            )

            duration = time.time() - start_time

            # Format response
            return TextContent(
                text=json.dumps(
                    {
                        "status": "success",
                        "exit_code": result.exit_code,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "duration": duration,
                        "profile": profile_name,
                    }
                )
            )

        except RuntimeError as e:
            logger.error(f"Fast path execution failed: {e}", exc_info=True)
            return TextContent(text=json.dumps({"status": "error", "error": str(e)}))
        except Exception as e:
            logger.error(f"Fast path execution failed: {e}", exc_info=True)
            return TextContent(
                text=json.dumps({"status": "error", "error": f"Execution failed: {e}"})
            )

    def _create_approval_session(
        self,
        script: str,
        detected_ops: list[str],
        profile_name: str,
        session_name: str,
    ) -> TextContent:
        """Create session for user approval (review path).

        Parameters
        ----------
        script : str
            Python script to execute.
        detected_ops : list[str]
            Operations detected by AST analysis.
        profile_name : str
            Profile name.
        session_name : str
            Human-readable session name.

        Returns
        -------
        TextContent
            JSON response with session ID and instructions.
        """
        try:
            # Create session using existing infrastructure
            session = create_session(
                script_path="<mcp>",
                commands=detected_ops,
                script_content=script,
                name=session_name,
                analysis=f"MCP request with profile '{profile_name}'",
                sandbox_args={"profile": profile_name},
            )

            return TextContent(
                text=json.dumps(
                    {
                        "status": "pending_approval",
                        "session_id": session.id,
                        "detected_operations": detected_ops,
                        "instructions": [
                            f"Session created: {session.id}",
                            f"Review with: shannot approve show {session.id}",
                            f"Approve and execute: shannot approve --execute {session.id}",
                            "Or use session_result tool to poll status",
                        ],
                    }
                )
            )

        except Exception as e:
            logger.error(f"Session creation failed: {e}", exc_info=True)
            return TextContent(
                text=json.dumps({"status": "error", "error": f"Failed to create session: {e}"})
            )

    def _handle_remote_sandbox_run(
        self,
        script: str,
        profile: dict[str, Any],
        profile_name: str,
        session_name: str,
        target: str,
    ) -> TextContent:
        """Execute Python script on a remote SSH target.

        Security: Only named remotes from config.toml are allowed.
        Arbitrary user@host:port format is rejected.

        Parameters
        ----------
        script : str
            Python script to execute.
        profile : dict[str, Any]
            Loaded profile configuration.
        profile_name : str
            Profile name.
        session_name : str
            Human-readable session name.
        target : str
            Named remote target (e.g., 'prod', 'staging').

        Returns
        -------
        TextContent
            JSON response with status and results/session info.
        """
        # Security: Only allow named remotes, reject arbitrary user@host:port
        try:
            remotes = load_remotes()
        except Exception as e:
            logger.warning(f"Failed to load remotes: {e}")
            remotes = {}

        if target not in remotes:
            # Check if it looks like user@host format (disallowed)
            if "@" in target or ":" in target:
                return TextContent(
                    text=json.dumps(
                        {
                            "status": "error",
                            "error": (
                                f"Arbitrary SSH targets are not allowed. "
                                f"Configure '{target.split('@')[-1].split(':')[0]}' with: "
                                f"shannot remote add <name> <host> --user <user>"
                            ),
                        }
                    )
                )
            return TextContent(
                text=json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"Unknown remote target '{target}'. "
                            f"Available remotes: {', '.join(remotes.keys()) or 'none configured'}. "
                            f"Add with: shannot remote add {target} <host> --user <user>"
                        ),
                    }
                )
            )

        remote = remotes[target]
        resolved_target = remote.target_string

        # AST analysis for fast-path detection (UX optimization, NOT security)
        try:
            detected_ops = self._analyze_script_best_effort(script)
        except Exception as e:
            logger.warning(f"AST analysis failed: {e}")
            detected_ops = []

        # Check for denied operations (blocked path)
        always_deny = profile.get("always_deny", [])
        for op in detected_ops:
            for pattern in always_deny:
                if pattern in op:
                    return TextContent(
                        text=json.dumps(
                            {
                                "status": "denied",
                                "reason": f"Script contains denied operation: '{pattern}'",
                                "detected_operations": detected_ops,
                                "target": target,
                            }
                        )
                    )

        # Check if all operations are in allowlist (fast path)
        auto_approve = profile.get("auto_approve", [])
        all_allowed = (
            all(any(pattern in op for pattern in auto_approve) for op in detected_ops)
            if detected_ops
            else True
        )

        try:
            # Connect to remote
            ssh_config = SSHConfig(target=resolved_target, port=remote.port)
            with SSHConnection(ssh_config) as ssh:
                # Ensure shannot is deployed (fast check, only deploys if missing)
                if not ensure_deployed(ssh):
                    return TextContent(
                        text=json.dumps(
                            {
                                "status": "error",
                                "error": f"Failed to deploy shannot to {target}",
                                "target": target,
                            }
                        )
                    )

                if all_allowed and detected_ops:
                    # Fast path: execute immediately on remote
                    logger.info(
                        f"Remote fast path: all {len(detected_ops)} operations allowed on {target}"
                    )
                    return self._execute_remote_fast_path(
                        ssh=ssh,
                        script=script,
                        profile_name=profile_name,
                        target=target,
                    )

                # Review path: create session with remote metadata
                logger.info(f"Remote review path: {len(detected_ops)} operations on {target}")
                return self._create_remote_approval_session(
                    script=script,
                    detected_ops=detected_ops,
                    profile_name=profile_name,
                    session_name=session_name,
                    target=target,
                )

        except Exception as e:
            logger.error(f"Remote execution failed: {e}", exc_info=True)
            return TextContent(
                text=json.dumps(
                    {
                        "status": "error",
                        "error": f"Remote execution failed: {e}",
                        "target": target,
                    }
                )
            )

    def _execute_remote_fast_path(
        self,
        ssh: SSHConnection,
        script: str,
        profile_name: str,
        target: str,
    ) -> TextContent:
        """Execute script immediately on remote (all operations pre-approved).

        Parameters
        ----------
        ssh : SSHConnection
            Connected SSH session.
        script : str
            Python script to execute.
        profile_name : str
            Profile name (for logging).
        target : str
            Remote target name.

        Returns
        -------
        TextContent
            JSON response with execution results.
        """
        from ..remote import run_remote_fast_path

        try:
            start_time = time.time()

            result = run_remote_fast_path(
                ssh=ssh,
                script_content=script,
            )

            duration = time.time() - start_time

            return TextContent(
                text=json.dumps(
                    {
                        "status": "success",
                        "exit_code": result.get("exit_code", 0),
                        "stdout": result.get("stdout", ""),
                        "stderr": result.get("stderr", ""),
                        "duration": duration,
                        "profile": profile_name,
                        "target": target,
                    }
                )
            )

        except Exception as e:
            logger.error(f"Remote fast path execution failed: {e}", exc_info=True)
            return TextContent(
                text=json.dumps(
                    {
                        "status": "error",
                        "error": f"Remote execution failed: {e}",
                        "target": target,
                    }
                )
            )

    def _create_remote_approval_session(
        self,
        script: str,
        detected_ops: list[str],
        profile_name: str,
        session_name: str,
        target: str,
    ) -> TextContent:
        """Create session for remote execution requiring user approval.

        Parameters
        ----------
        script : str
            Python script to execute.
        detected_ops : list[str]
            Operations detected by AST analysis.
        profile_name : str
            Profile name.
        session_name : str
            Human-readable session name.
        target : str
            Remote target name.

        Returns
        -------
        TextContent
            JSON response with session ID and instructions.
        """
        try:
            # Use run_remote_dry_run to create session with remote metadata
            session = run_remote_dry_run(
                target=target,
                script_path="<mcp>",
                script_content=script,
                name=session_name,
                analysis=f"MCP request with profile '{profile_name}' on {target}",
            )

            if session is None:
                # No operations queued - script is pure Python with no subprocess calls
                return TextContent(
                    text=json.dumps(
                        {
                            "status": "success",
                            "message": "Script executed (no operations requiring approval)",
                            "target": target,
                        }
                    )
                )

            return TextContent(
                text=json.dumps(
                    {
                        "status": "pending_approval",
                        "session_id": session.id,
                        "detected_operations": detected_ops,
                        "target": target,
                        "instructions": [
                            f"Session created: {session.id}",
                            f"Target: {target}",
                            f"Review with: shannot approve show {session.id}",
                            f"Approve and execute: shannot approve --execute {session.id}",
                            "Or use session_result tool to poll status",
                        ],
                    }
                )
            )

        except Exception as e:
            logger.error(f"Remote session creation failed: {e}", exc_info=True)
            return TextContent(
                text=json.dumps(
                    {
                        "status": "error",
                        "error": f"Failed to create remote session: {e}",
                        "target": target,
                    }
                )
            )

    def _handle_session_result(self, arguments: dict[str, Any]) -> TextContent:
        """Poll result of a pending session.

        Parameters
        ----------
        arguments : dict[str, Any]
            Tool arguments with 'session_id'.

        Returns
        -------
        TextContent
            JSON response with session status and results if executed.
        """
        session_id = arguments.get("session_id")
        if not session_id:
            return TextContent(text=json.dumps({"status": "error", "error": "Missing session_id"}))

        try:
            session = Session.load(session_id)
        except FileNotFoundError:
            return TextContent(
                text=json.dumps({"status": "error", "error": f"Session not found: {session_id}"})
            )
        except Exception as e:
            return TextContent(
                text=json.dumps({"status": "error", "error": f"Failed to load session: {e}"})
            )

        # Check if session is expired
        if session.is_expired() and session.status == "pending":
            session.status = "expired"
            session.save()

        # Return session status
        result: dict[str, Any] = {
            "session_id": session.id,
            "status": session.status,
            "created_at": session.created_at,
        }

        # Include target if this is a remote session
        if session.target:
            result["target"] = session.target

        if session.status == "executed":
            result["exit_code"] = session.exit_code
            result["stdout"] = session.stdout
            result["stderr"] = session.stderr
            result["executed_at"] = session.executed_at
        elif session.status == "failed":
            result["error"] = session.error
        elif session.status == "pending":
            result["expires_at"] = session.expires_at
            instructions = [
                f"Review with: shannot approve show {session.id}",
                f"Approve and execute: shannot approve --execute {session.id}",
            ]
            if session.target:
                instructions.insert(0, f"Target: {session.target}")
            result["instructions"] = instructions
        elif session.status == "expired":
            result["message"] = "Session expired (1 hour TTL)"
        elif session.status == "cancelled":
            result["message"] = "Session was cancelled"
        elif session.status == "rejected":
            result["message"] = "Session was rejected"

        return TextContent(text=json.dumps(result))

    def _handle_list_profiles(self) -> str:
        """Resource handler: list available profiles."""
        profile_names = list(self.profiles.keys())
        return json.dumps(profile_names, indent=2)

    def _handle_get_profile(self, profile_name: str) -> str:
        """Resource handler: get profile configuration."""
        if profile_name not in self.profiles:
            return json.dumps({"error": f"Unknown profile: {profile_name}"})

        return json.dumps(self.profiles[profile_name], indent=2)

    def _handle_status(self) -> str:
        """Resource handler: get runtime status."""
        status = {
            "version": get_version(),
            "runtime_available": self.runtime is not None,
            "profiles": list(self.profiles.keys()),
        }

        if self.runtime:
            status["runtime"] = {
                "pypy_sandbox": str(self.runtime["pypy_sandbox"]),
                "lib_python": str(self.runtime["lib_python"]),
                "lib_pypy": str(self.runtime["lib_pypy"]),
            }

        return json.dumps(status, indent=2)

    def _handle_list_remotes(self) -> str:
        """Resource handler: list configured SSH remotes."""
        try:
            remotes = load_remotes()
        except Exception as e:
            logger.warning(f"Failed to load remotes: {e}")
            return json.dumps({"remotes": {}, "error": str(e)}, indent=2)

        remotes_dict = {}
        for name, remote in remotes.items():
            remotes_dict[name] = {
                "host": remote.host,
                "user": remote.user,
                "port": remote.port,
            }

        return json.dumps({"remotes": remotes_dict}, indent=2)
