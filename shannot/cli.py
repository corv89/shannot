#!/usr/bin/env python3
"""
Simplified CLI for running commands in a read-only sandbox.

Usage:
    sandbox run -- COMMAND [ARGS...]              Run command in sandbox
    sandbox run cat /proc/meminfo                 Run with implicit command
    sandbox verify                                 Verify sandbox works
    sandbox export                                 Export profile config

Default profile: /etc/sandbox/readonly.json
Override with: --profile PATH or SANDBOX_PROFILE env var
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import shutil
import sys
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import cast

# TOML support: tomllib is built-in for Python 3.11+, else use tomli
try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]

# TOML writing support
try:
    import tomli_w
except ModuleNotFoundError:
    tomli_w = None  # type: ignore[assignment]

from . import (
    SandboxError,
    SandboxManager,
    SandboxProfile,
    __version__,
    load_profile_from_path,
)
from .process import ProcessResult, ensure_tool_available
from .validation import ValidationError, validate_port, validate_type

_LOGGER = logging.getLogger("shannot")

# Default profile locations (checked in order)
_DEFAULT_PROFILES = [
    Path.home() / ".config/shannot/minimal.json",  # User config first
    Path.home() / ".config/shannot/profile.json",  # Legacy user config
    Path(__file__).parent.parent / "profiles" / "minimal.json",  # Bundled profiles
    Path("/etc/shannot/minimal.json"),  # System-wide
    Path("/etc/shannot/profile.json"),  # Legacy system
]

_MCP_CLIENT_LABELS: dict[str, str] = {
    "claude-desktop": "Claude Desktop",
    "claude-code": "Claude Code",
    "codex": "Codex CLI",
    "lmstudio": "LM Studio",
}

_MCP_CLIENT_PATHS: dict[str, dict[str, tuple[tuple[str, ...], ...]]] = {
    "claude-desktop": {
        "Darwin": (("Library", "Application Support", "Claude", "claude_desktop_config.json"),),
        "Windows": (("AppData", "Roaming", "Claude", "claude_desktop_config.json"),),
    },
    "claude-code": {
        "Darwin": (
            ("Library", "Application Support", "Claude", "claude_code_config.json"),
            ("Library", "Application Support", "Claude", "claude_config.json"),
            (".claude", "config.json"),
            (".config", "claude", "config.json"),
        ),
        "Linux": (
            (".config", "Claude", "claude_code_config.json"),
            (".claude", "config.json"),
            (".config", "claude", "config.json"),
        ),
        "Windows": (
            ("AppData", "Roaming", "Claude", "claude_code_config.json"),
            ("AppData", "Roaming", "Claude", "claude_config.json"),
        ),
    },
    "codex": {
        "Darwin": (
            (".codex", "config.toml"),
            ("Library", "Application Support", "OpenAI", "Codex", "codex_cli_config.json"),
        ),
        "Linux": ((".codex", "config.toml"),),
        "Windows": (
            (".codex", "config.toml"),
            ("AppData", "Roaming", "OpenAI", "Codex", "codex_cli_config.json"),
        ),
    },
    "lmstudio": {
        "Darwin": ((".lmstudio", "mcp.json"),),
        "Linux": ((".lmstudio", "mcp.json"),),
        "Windows": ((".lmstudio", "mcp.json"),),
    },
}

_MCP_CLIENT_SUCCESS_HINTS: dict[str, str] = {
    "claude-desktop": "Restart Claude Desktop to use Shannot tools",
    "claude-code": "Restart Claude Code to use Shannot tools",
    "codex": "Restart Codex CLI sessions to use Shannot tools",
    "lmstudio": "Restart LM Studio to use Shannot tools",
}


def _claude_cli_config_path() -> Path:
    """Locate Claude Code CLI configuration file."""
    override_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    base_dir = Path(override_dir).expanduser() if override_dir else Path.home()

    alt_path = Path.home() / ".claude" / ".config.json"
    if alt_path.exists():
        return alt_path

    candidates = sorted(base_dir.glob(".claude*.json"))
    if candidates:
        return candidates[0]

    return base_dir / ".claude.json"


def _get_default_profile() -> Path:
    """Get default profile from env or standard locations."""
    env_profile = os.environ.get("SANDBOX_PROFILE")
    if env_profile:
        return Path(env_profile)

    for profile_path in _DEFAULT_PROFILES:
        if profile_path.exists():
            return profile_path

    raise SandboxError(
        "No default sandbox profile found. Set SANDBOX_PROFILE env var or specify --profile.\n"
        f"Searched: {', '.join(str(p) for p in _DEFAULT_PROFILES)}"
    )


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # Suppress noisy third-party loggers unless in verbose mode
    if not verbose:
        logging.getLogger("asyncssh").setLevel(logging.WARNING)


def _resolve_bubblewrap_path(candidate: str | None) -> Path:
    if candidate:
        return Path(candidate).expanduser()
    env_candidate = os.environ.get("BWRAP")
    if env_candidate:
        return Path(env_candidate).expanduser()

    try:
        resolved = ensure_tool_available("bwrap")
        return resolved
    except FileNotFoundError as e:
        # Provide helpful error message based on platform
        import platform

        if platform.system() == "Darwin":
            raise SandboxError(
                "bubblewrap is not available on macOS.\n\n"
                "Shannot requires Linux to run locally. You have two options:\n"
                "  1. Use a remote Linux system with --target:\n"
                "     shannot remote add myserver --host linux-server.local --user yourname\n"
                "     shannot --target myserver ls /\n"
                "  2. Run in a Linux VM or container\n\n"
                "See docs/configuration.md for remote setup instructions."
            ) from None
        elif platform.system() == "Windows":
            raise SandboxError(
                "bubblewrap is not available on Windows.\n\n"
                "Shannot requires Linux to run locally. You have two options:\n"
                "  1. Use a remote Linux system with --target:\n"
                "     shannot remote add myserver --host linux-server --user yourname\n"
                "     shannot --target myserver ls /\n"
                "  2. Use WSL2 (Windows Subsystem for Linux)\n\n"
                "See docs/configuration.md for remote setup instructions."
            ) from None
        else:
            # Linux but bwrap not installed
            raise SandboxError(
                "bubblewrap is not installed.\n\n"
                "Install bubblewrap:\n"
                "  Debian/Ubuntu: sudo apt install bubblewrap\n"
                "  Fedora/RHEL:   sudo dnf install bubblewrap\n"
                "  Arch:          sudo pacman -S bubblewrap\n\n"
                f"Original error: {e}"
            ) from e


def _load_profile(path: str) -> SandboxProfile:
    return load_profile_from_path(Path(path).expanduser())


def _profile_to_serializable(profile: SandboxProfile) -> dict[str, object]:
    data = asdict(profile)

    def _path_to_str(value: Path | None) -> str | None:
        if value is None:
            return None
        return str(value)

    def _convert_bind(bind: Mapping[str, object]) -> MutableMapping[str, object]:
        converted: MutableMapping[str, object] = dict(bind)
        converted["source"] = str(bind["source"])
        converted["target"] = str(bind["target"])
        return converted

    binds = [_convert_bind(cast(Mapping[str, object], bind)) for bind in data["binds"]]
    tmpfs_paths = [str(cast(Path, path)) for path in data["tmpfs_paths"]]
    environment = dict(cast(Mapping[str, str], data["environment"]))
    seccomp_profile = _path_to_str(cast(Path | None, data["seccomp_profile"]))
    additional_args = list(cast(Sequence[str], data["additional_args"]))

    return {
        "name": data["name"],
        "allowed_commands": list(data["allowed_commands"]),
        "binds": binds,
        "tmpfs_paths": tmpfs_paths,
        "environment": environment,
        "seccomp_profile": seccomp_profile,
        "network_isolation": data["network_isolation"],
        "additional_args": additional_args,
    }


def _detect_available_mcp_clients() -> list[tuple[str, Path]]:
    """
    Detect which MCP clients are installed on the system.

    Returns:
        List of tuples (client_name, config_path) for detected clients.
    """
    system_name = platform.system()
    detected: list[tuple[str, Path]] = []

    for client_name, platform_paths in _MCP_CLIENT_PATHS.items():
        # Special handling for Claude Code - use CLI config path
        if client_name == "claude-code":
            cli_path = _claude_cli_config_path()
            # Check if Claude Code is installed by looking for the parent directory
            if cli_path.parent.exists():
                detected.append((client_name, cli_path))
            continue

        candidates = platform_paths.get(system_name)
        if not candidates:
            continue

        for segments in candidates:
            candidate_path = Path.home().joinpath(*segments)
            if candidate_path.exists():
                detected.append((client_name, candidate_path))
                break
            # Also check parent directory exists as indicator of installation
            if candidate_path.parent.exists() and client_name not in [c[0] for c in detected]:
                detected.append((client_name, candidate_path))
                break

    return detected


def _resolve_mcp_config_path(client: str, override: str | None) -> Path:
    if override:
        return Path(override).expanduser()

    # Special handling for Claude Code - use CLI config path
    if client == "claude-code":
        return _claude_cli_config_path()

    system_name = platform.system()
    candidates = _MCP_CLIENT_PATHS.get(client, {}).get(system_name)
    if not candidates:
        friendly = _MCP_CLIENT_LABELS.get(client, client)
        raise ValueError(
            f"{friendly} config location unknown for platform '{system_name}'. "
            "Specify the location explicitly with --config-path.",
        )

    selected_path: Path | None = None
    for segments in candidates:
        candidate_path = Path.home().joinpath(*segments)
        if candidate_path.exists():
            selected_path = candidate_path
            break

    if selected_path is None:
        selected_path = Path.home().joinpath(*candidates[0])

    return selected_path


def _update_claude_cli_user_server(
    server_name: str,
    command: str,
    args: list[str],
    env: dict[str, str] | None,
) -> tuple[Path, bool] | None:
    """Write Claude Code CLI user-scope config (available across all projects)."""
    config_path = _claude_cli_config_path()
    try:
        if config_path.exists():
            with open(config_path, encoding="utf-8") as fh:
                config_data = json.load(fh)
        else:
            config_data = {}
    except json.JSONDecodeError as exc:
        _LOGGER.warning("Could not parse Claude Code config at %s: %s", config_path, exc)
        return None

    # User scope: top-level mcpServers (not under projects)
    mcp_servers = config_data.setdefault("mcpServers", {})

    cli_server_config: dict[str, object] = {
        "type": "stdio",
        "command": command,
        "args": list(args),
        "env": env or {},
    }

    changed = mcp_servers.get(server_name) != cli_server_config
    mcp_servers[server_name] = cli_server_config

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(config_data, fh, indent=2)
        fh.write("\n")

    return config_path, changed


def _execute_command(manager: SandboxManager, command: Sequence[str]) -> ProcessResult:
    _LOGGER.debug("Executing sandbox command: %s", " ".join(command))
    result = manager.run(command, check=False)
    _LOGGER.debug(
        "Command finished (exit=%s, duration=%.3fs)",
        result.returncode,
        result.duration,
    )
    return result


def _handle_run(args: argparse.Namespace) -> int:
    """Handle 'run' subcommand - execute command in sandbox."""
    import asyncio

    # Validate inputs
    try:
        # Validate profile path (argparse provides str or None)
        profile_path_arg = getattr(args, "profile", None)
        if profile_path_arg is not None:
            profile_path = validate_type(profile_path_arg, str, "profile")
        else:
            profile_path = _get_default_profile()
        profile = _load_profile(str(profile_path))

        # Validate command (argparse provides list)
        command_raw = getattr(args, "command", [])
        if not command_raw:
            raise ValidationError("No command specified", "command")

        # Validate command is list of strings
        from .validation import validate_list_of_strings

        command = validate_list_of_strings(list(command_raw), "command")

        # Validate target name if specified
        target_name_raw = getattr(args, "target", None)
        target_name = None
        if target_name_raw is not None:
            target_name = validate_type(target_name_raw, str, "target")
            if not target_name.strip():
                raise ValidationError("must be non-empty", "target")
    except ValidationError as e:
        _LOGGER.error(f"Invalid argument: {e}")
        return 1

    # Check if target flag is specified (after validation)

    if target_name:
        # Use executor from config
        from .config import create_executor, load_config

        try:
            config = load_config()
            executor = create_executor(config, target_name)
        except Exception as e:
            _LOGGER.error(f"Failed to create target executor '{target_name}': {e}")
            return 1

        # Execute async
        async def run():
            return await executor.run_command(profile, command, timeout=60)

        try:
            result = asyncio.run(run())
        except Exception as e:
            _LOGGER.error(f"Execution failed: {e}")
            return 1
    else:
        # Use local execution (legacy)
        bubblewrap_arg = getattr(args, "bubblewrap", None)
        bubblewrap = _resolve_bubblewrap_path(bubblewrap_arg)
        manager = SandboxManager(profile, bubblewrap)
        result = manager.run(command, check=False)

    # Handle output (argparse guarantees these are bool with defaults)
    print_stdout = getattr(args, "print_stdout", True)
    print_stderr = getattr(args, "print_stderr", True)
    check = getattr(args, "check", False)

    if print_stdout and result.stdout:
        print(result.stdout, end="")
    if print_stderr and result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    # Check exit code if requested
    if check and result.returncode != 0:
        return result.returncode

    return result.returncode


def _handle_export(args: argparse.Namespace) -> int:
    """Handle 'export' subcommand - export profile as JSON."""
    profile_path_arg = getattr(args, "profile", None)
    if profile_path_arg is not None:
        profile_path = profile_path_arg
    else:
        profile_path = _get_default_profile()
    profile = _load_profile(str(profile_path))
    serialized = _profile_to_serializable(profile)
    json_output = json.dumps(serialized, indent=2, sort_keys=True)
    print(json_output)
    return 0


def _handle_verify(args: argparse.Namespace) -> int:
    """Handle 'verify' subcommand - verify sandbox configuration."""
    try:
        # Validate profile path
        profile_path_arg = getattr(args, "profile", None)
        if profile_path_arg is not None:
            profile_path = profile_path_arg
        else:
            profile_path = _get_default_profile()
        profile = _load_profile(str(profile_path))

        # Validate bubblewrap path
        bubblewrap_arg = getattr(args, "bubblewrap", None)
        bubblewrap = _resolve_bubblewrap_path(bubblewrap_arg)
        manager = SandboxManager(profile, bubblewrap)

        # Validate command sequences
        from .validation import validate_list_of_strings

        allowed_command_arg = getattr(args, "allowed_command", None)
        if allowed_command_arg is not None:
            allowed_command = validate_list_of_strings(list(allowed_command_arg), "allowed_command")
        else:
            allowed_command = ["ls", "/"]

        disallowed_command_arg = getattr(args, "disallowed_command", None)
        if disallowed_command_arg is not None:
            disallowed_command = validate_list_of_strings(
                list(disallowed_command_arg), "disallowed_command"
            )
        else:
            disallowed_command = ["touch", "/tmp/probe"]
    except ValidationError as e:
        _LOGGER.error(f"Invalid argument: {e}")
        return 1

    _LOGGER.info("Verifying allowed command: %s", " ".join(allowed_command))
    allowed_result = _execute_command(manager, allowed_command)
    if allowed_result.returncode != 0:
        _LOGGER.error(
            "Allowed command failed with exit code %s:\n%s",
            allowed_result.returncode,
            allowed_result.stderr,
        )
        return 1

    _LOGGER.info("Verifying disallowed command is rejected: %s", " ".join(disallowed_command))
    disallowed_status = 0
    try:
        _ = manager.run(disallowed_command, check=True)
    except SandboxError:
        disallowed_status = 0
    else:
        _LOGGER.error("Disallowed command unexpectedly succeeded.")
        disallowed_status = 1

    return disallowed_status


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shannot",
        description="Run commands in a read-only sandbox.",
        epilog=(
            "Default profile: ~/.config/shannot/minimal.json or bundled profiles/minimal.json\n"
            "(override with --profile or $SANDBOX_PROFILE)\n"
            "Examples:\n"
            "  shannot ls /                   # Run command locally\n"
            "  shannot --target prod df -h    # Run on remote 'prod'\n"
            "  shannot remote list            # List configured targets"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _ = parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show version and exit.",
    )
    _ = parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )
    _ = parser.add_argument(
        "--profile",
        "-p",
        help="Path to sandbox profile (default: auto-detect).",
    )
    _ = parser.add_argument(
        "--target",
        "-t",
        help="Target system to run on (from config file, default: local).",
    )

    subparsers = parser.add_subparsers(dest="command_name", required=False)

    # run subcommand - main use case
    run_parser = subparsers.add_parser(
        "run",
        help="Run a command in the sandbox.",
    )
    _ = run_parser.add_argument(
        "--bubblewrap",
        help="Path to bubblewrap executable (default: auto-detect).",
    )
    _ = run_parser.add_argument(
        "--no-check",
        dest="check",
        action="store_false",
        help="Don't fail on non-zero exit codes.",
    )
    _ = run_parser.add_argument(
        "--no-stdout",
        dest="print_stdout",
        action="store_false",
        help="Suppress stdout output.",
    )
    _ = run_parser.add_argument(
        "--no-stderr",
        dest="print_stderr",
        action="store_false",
        help="Suppress stderr output.",
    )
    run_parser.set_defaults(check=True, print_stdout=True, print_stderr=True, handler=_handle_run)
    _ = run_parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command and arguments (use -- to separate from options).",
    )

    # export subcommand
    export_parser = subparsers.add_parser(
        "export",
        help="Export profile configuration as JSON.",
    )
    export_parser.set_defaults(handler=_handle_export)

    # verify subcommand
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify sandbox configuration.",
    )
    _ = verify_parser.add_argument(
        "--bubblewrap",
        help="Path to bubblewrap executable (default: auto-detect).",
    )
    _ = verify_parser.add_argument(
        "--allowed-command",
        nargs="+",
        help="Command that should succeed (default: ls /).",
    )
    _ = verify_parser.add_argument(
        "--disallowed-command",
        nargs="+",
        help="Command that should fail (default: touch /tmp/probe).",
    )
    verify_parser.set_defaults(handler=_handle_verify)

    # mcp subcommand
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="MCP server commands (install, test).",
    )
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_command", required=True)

    # mcp install
    mcp_install_parser = mcp_subparsers.add_parser(
        "install",
        help="Install MCP server config for supported clients.",
    )
    _ = mcp_install_parser.add_argument(
        "--target",
        "-t",
        help="Target system to use for MCP server (from config file).",
    )

    _ = mcp_install_parser.add_argument(
        "--client",
        choices=("claude-desktop", "claude-code", "codex", "lmstudio", "all", "auto"),
        help=(
            "MCP client to configure. Use 'auto' to detect and choose, 'all' to install to all "
            "detected clients, or specify: claude-desktop (macOS/Windows only), claude-code "
            "(all platforms), codex (all platforms), lmstudio (all platforms). "
            "Default: auto-detect."
        ),
    )
    _ = mcp_install_parser.add_argument(
        "--config-path",
        help="Override the MCP client config file path (only works with specific --client).",
    )
    _ = mcp_install_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompts and install to all detected clients.",
    )
    mcp_install_parser.set_defaults(handler=_handle_mcp_install)

    # mcp test
    mcp_test_parser = mcp_subparsers.add_parser(
        "test",
        help="Test MCP server with sample commands.",
    )
    mcp_test_parser.set_defaults(handler=_handle_mcp_test)

    # remote subcommand
    remote_parser = subparsers.add_parser(
        "remote",
        help="Manage remote targets.",
    )
    remote_subparsers = remote_parser.add_subparsers(dest="remote_command", required=True)

    # remote list
    remote_list_parser = remote_subparsers.add_parser(
        "list",
        help="List configured targets.",
    )
    remote_list_parser.set_defaults(handler=_handle_remote_list)

    # remote add
    remote_add_parser = remote_subparsers.add_parser(
        "add",
        help="Add a remote target.",
        epilog="Examples:\n"
        "  shannot remote add myserver example.com\n"
        "  shannot remote add vm localhost --profile diagnostic\n"
        "  shannot remote add prod prod.example.com --user admin --port 2222",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _ = remote_add_parser.add_argument(
        "name", help="Name for this remote (e.g., 'prod', 'staging')"
    )
    _ = remote_add_parser.add_argument("host", help="SSH hostname or IP address")
    _ = remote_add_parser.add_argument(
        "--user", "--username", dest="username", help="SSH username (default: current user)"
    )
    _ = remote_add_parser.add_argument(
        "--key", "--key-file", dest="key_file", help="SSH key file path (default: SSH config)"
    )
    _ = remote_add_parser.add_argument(
        "--port", type=int, default=22, help="SSH port (default: 22)"
    )
    _ = remote_add_parser.add_argument(
        "--profile",
        help="Default profile for this remote (name like 'minimal' or path to .json file)",
    )
    remote_add_parser.set_defaults(handler=_handle_remote_add)

    # remote remove
    remote_remove_parser = remote_subparsers.add_parser(
        "remove",
        aliases=["rm"],
        help="Remove a remote target.",
    )
    _ = remote_remove_parser.add_argument("name", help="Name of remote to remove")
    remote_remove_parser.set_defaults(handler=_handle_remote_remove)

    # remote test
    remote_test_parser = remote_subparsers.add_parser(
        "test",
        help="Test connection to a remote target.",
    )
    _ = remote_test_parser.add_argument("name", help="Name of remote to test")
    remote_test_parser.set_defaults(handler=_handle_remote_test)

    return parser


def _install_to_client(
    client: str,
    config_path: Path,
    target_name: str | None,
    resolved_command: str,
    command_args: list[str],
    env_vars: dict[str, str],
) -> bool:
    """Install MCP server config to a specific client. Returns True on success."""
    client_label = _MCP_CLIENT_LABELS.get(client, client)
    is_toml = config_path.suffix == ".toml"

    try:
        # For Claude Code, use the CLI config directly (available across all projects)
        if client == "claude-code":
            server_args = list(command_args)
            if target_name:
                server_args.extend(["--target", target_name])

            cli_result = _update_claude_cli_user_server(
                "shannot",
                resolved_command,
                server_args,
                env_vars if env_vars else None,
            )
            if cli_result is not None:
                path, changed = cli_result
                status = "Configured" if changed else "Already configured"
                _LOGGER.info(
                    "✓ %s %s at %s (available across all projects)", status, client_label, path
                )
                success_hint = _MCP_CLIENT_SUCCESS_HINTS.get(client)
                if success_hint:
                    _LOGGER.info("✓ %s", success_hint)
                return True
            else:
                return False

        # Check if TOML libraries are available when needed
        if is_toml and (tomllib is None or tomli_w is None):
            _LOGGER.error(
                f"TOML support required for {client_label} but not installed. "
                "Install with: pip install tomli tomli-w"
            )
            return False

        # Read existing config if present
        if config_path.exists():
            if is_toml:
                assert tomllib is not None  # Already checked above
                with open(config_path, "rb") as f:
                    config = tomllib.load(f)
            else:
                with open(config_path) as f:
                    config = json.load(f)
        else:
            config = {}

        server_args = list(command_args)
        if target_name:
            server_args.extend(["--target", target_name])

        # Handle different config formats
        if client == "codex" and is_toml:
            # Codex uses [mcp_servers.shannot] format in TOML
            mcp_servers = config.setdefault("mcp_servers", {})
            server_config = {
                "command": resolved_command,
                "args": server_args,
                "enabled": True,
            }
            if env_vars:
                server_config["env"] = env_vars
            mcp_servers["shannot"] = server_config
        else:
            # Claude Desktop, LM Studio use JSON with mcpServers
            config.setdefault("mcpServers", {})
            server_config = {"command": resolved_command, "args": server_args}
            if env_vars:
                server_config["env"] = env_vars
            config["mcpServers"]["shannot"] = server_config

        # Write config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if is_toml:
            assert tomli_w is not None  # Already checked above
            with open(config_path, "wb") as f:
                tomli_w.dump(config, f)
        else:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
                f.write("\n")

        _LOGGER.info("✓ Installed MCP server config for %s at %s", client_label, config_path)

        success_hint = _MCP_CLIENT_SUCCESS_HINTS.get(client)
        if success_hint:
            _LOGGER.info("✓ %s", success_hint)

        return True
    except Exception as e:
        _LOGGER.error(f"Failed to install to {client_label}: {e}")
        return False


def _handle_mcp_install(args: argparse.Namespace) -> int:
    """Install MCP server configuration for supported clients."""
    client_arg = cast(str | None, getattr(args, "client", None))
    config_override = cast(str | None, getattr(args, "config_path", None))
    target_name = cast(str | None, getattr(args, "target", None))
    auto_yes = cast(bool, getattr(args, "yes", False))

    # Validate target if specified
    if target_name:
        try:
            from .config import load_config

            config_obj = load_config()
            if target_name not in config_obj.executor:
                _LOGGER.error(f"Target '{target_name}' not found in config")
                _LOGGER.info("List targets with: shannot remote list")
                return 1
            _LOGGER.info(f"Using target: {target_name}")
        except Exception as e:
            _LOGGER.error(f"Failed to load config: {e}")
            return 1

    # Prepare command and environment
    command_args: list[str] = []
    resolved_command = shutil.which("shannot-mcp")
    if resolved_command is None:
        resolved_command = sys.executable
        command_args = ["-m", "shannot.mcp_main"]
        _LOGGER.info("shannot-mcp not found on PATH; using Python module fallback.")
    else:
        _LOGGER.info("Using MCP server binary at %s", resolved_command)

    # Pass through SSH agent environment so remote targets work when spawned by MCP clients.
    agent_env_keys = ["SSH_AUTH_SOCK", "SSH_AGENT_PID"]
    env_vars = {key: os.environ[key] for key in agent_env_keys if key in os.environ}

    # Auto-detection mode
    if client_arg is None or client_arg == "auto":
        detected = _detect_available_mcp_clients()

        if not detected:
            _LOGGER.error("No MCP clients detected on this system")
            _LOGGER.info("Supported clients: claude-desktop, claude-code, codex, lmstudio")
            _LOGGER.info("Specify a client manually with: shannot mcp install --client <name>")
            return 1

        _LOGGER.info(f"Detected {len(detected)} MCP client(s):")
        for client_name, client_path in detected:
            client_label = _MCP_CLIENT_LABELS.get(client_name, client_name)
            exists_msg = "✓" if client_path.exists() else "○"
            _LOGGER.info(f"  {exists_msg} {client_label}: {client_path}")

        # If only one detected, install to it
        if len(detected) == 1:
            client, config_path = detected[0]
            _LOGGER.info(f"\nInstalling to {_MCP_CLIENT_LABELS.get(client, client)}...")
        else:
            # Multiple detected, ask user
            if auto_yes:
                _LOGGER.info("\nInstalling to all detected clients...")
                success_count = 0
                for client, config_path in detected:
                    if _install_to_client(
                        client, config_path, target_name, resolved_command, command_args, env_vars
                    ):
                        success_count += 1

                if success_count > 0:
                    if target_name:
                        _LOGGER.info(f"\n✓ MCP server will use target: {target_name}")
                    return 0
                else:
                    return 1
            else:
                _LOGGER.info("\nWhich client(s) would you like to configure?")
                _LOGGER.info("  1) All detected clients")
                for idx, (client_name, _) in enumerate(detected, start=2):
                    client_label = _MCP_CLIENT_LABELS.get(client_name, client_name)
                    _LOGGER.info(f"  {idx}) {client_label}")

                try:
                    choice = input(f"\nEnter choice (1-{len(detected) + 1}, or comma-separated): ")
                    choice = choice.strip()

                    if choice == "1":
                        # Install to all
                        success_count = 0
                        for client, config_path in detected:
                            if _install_to_client(
                                client,
                                config_path,
                                target_name,
                                resolved_command,
                                command_args,
                                env_vars,
                            ):
                                success_count += 1

                        if success_count > 0:
                            if target_name:
                                _LOGGER.info(f"\n✓ MCP server will use target: {target_name}")
                            return 0
                        else:
                            return 1
                    else:
                        # Parse comma-separated choices
                        choices = [
                            int(c.strip()) - 2 for c in choice.split(",") if c.strip().isdigit()
                        ]
                        success_count = 0
                        for idx in choices:
                            if 0 <= idx < len(detected):
                                client, config_path = detected[idx]
                                if _install_to_client(
                                    client,
                                    config_path,
                                    target_name,
                                    resolved_command,
                                    command_args,
                                    env_vars,
                                ):
                                    success_count += 1

                        if success_count > 0:
                            if target_name:
                                _LOGGER.info(f"\n✓ MCP server will use target: {target_name}")
                            return 0
                        else:
                            return 1
                except (ValueError, KeyboardInterrupt):
                    _LOGGER.info("\nInstallation cancelled")
                    return 1

        # Single client installation
        if _install_to_client(
            client, config_path, target_name, resolved_command, command_args, env_vars
        ):
            if target_name:
                _LOGGER.info(f"\n✓ MCP server will use target: {target_name}")
            return 0
        else:
            return 1

    # Install to all detected clients
    elif client_arg == "all":
        detected = _detect_available_mcp_clients()

        if not detected:
            _LOGGER.error("No MCP clients detected on this system")
            return 1

        _LOGGER.info(f"Installing to {len(detected)} detected client(s)...")
        success_count = 0
        for client, config_path in detected:
            if _install_to_client(
                client, config_path, target_name, resolved_command, command_args, env_vars
            ):
                success_count += 1

        if success_count > 0:
            if target_name:
                _LOGGER.info(f"\n✓ MCP server will use target: {target_name}")
            return 0
        else:
            return 1

    # Install to specific client
    else:
        client = client_arg

        try:
            config_path = _resolve_mcp_config_path(client, config_override)
        except ValueError as exc:
            _LOGGER.error(str(exc))
            if not config_override:
                _LOGGER.info(
                    "Example: shannot mcp install --client %s --config-path /path/to/config", client
                )
            return 1

        if _install_to_client(
            client, config_path, target_name, resolved_command, command_args, env_vars
        ):
            if target_name:
                _LOGGER.info(f"\n✓ MCP server will use target: {target_name}")
            return 0
        else:
            return 1


def _handle_mcp_test(args: argparse.Namespace) -> int:
    """Test MCP server functionality."""
    try:
        # Check if MCP dependencies are installed
        from shannot.tools import CommandInput, SandboxDeps, run_command
    except ImportError:
        _LOGGER.error("MCP dependencies not installed")
        _LOGGER.info("Install with: pip install shannot[mcp]")
        return 1

    # Try to load a profile and test basic functionality
    try:
        deps = SandboxDeps(profile_name="minimal")
        _LOGGER.info(f"✓ Loaded profile: {deps.profile.name}")
        _LOGGER.info(f"  Allowed commands: {', '.join(deps.profile.allowed_commands[:5])}")

        # Test a simple command
        import asyncio

        result = asyncio.run(run_command(deps, CommandInput(command=["ls", "/"])))
        if result.succeeded:
            _LOGGER.info("✓ Test command succeeded")
            _LOGGER.info(f"  Output preview: {result.stdout[:100]}...")
            return 0
        else:
            _LOGGER.error("✗ Test command failed")
            _LOGGER.error(f"  Error: {result.stderr}")
            return 1
    except Exception as e:
        _LOGGER.error(f"✗ Test failed: {e}")
        return 1


def _handle_remote_list(args: argparse.Namespace) -> int:
    """List configured remote executors."""
    from .config import load_config

    try:
        config = load_config()
    except Exception as e:
        _LOGGER.error(f"Failed to load config: {e}")
        return 1

    if not config.executor:
        _LOGGER.info("No targets configured")
        _LOGGER.info("Add a remote with: shannot remote add NAME HOSTNAME")
        return 0

    _LOGGER.info("Configured targets:")
    for name, executor_config in config.executor.items():
        is_default = " (default)" if name == config.default_executor else ""
        if executor_config.type == "local":
            _LOGGER.info(f"  {name}: local{is_default}")
        elif executor_config.type == "ssh":
            host = executor_config.host
            user = f"{executor_config.username}@" if executor_config.username else ""
            port = f":{executor_config.port}" if executor_config.port != 22 else ""
            _LOGGER.info(f"  {name}: ssh → {user}{host}{port}{is_default}")

    return 0


def _handle_remote_add(args: argparse.Namespace) -> int:
    """Add a remote executor."""
    from .config import SSHExecutorConfig, load_config, save_config

    # Validate and extract arguments with proper error handling
    try:
        name = validate_type(args.name, str, "name")
        if not name or not name.strip():
            raise ValidationError("must be non-empty", "name")

        host = validate_type(args.host, str, "host")
        if not host or not host.strip():
            raise ValidationError("must be non-empty", "host")

        username = args.username
        if username is not None:
            username = validate_type(username, str, "username")

        key_file = args.key_file
        if key_file is not None:
            key_file = validate_type(key_file, str, "key_file")

        port = validate_port(args.port, "port")

        profile = args.profile
        if profile is not None:
            profile = validate_type(profile, str, "profile")
    except ValidationError as e:
        _LOGGER.error(f"Invalid argument: {e}")
        return 1

    # Reserved names
    if name in ("local", "default"):
        _LOGGER.error(f"Cannot use reserved name '{name}'")
        return 1

    try:
        config = load_config()
    except Exception:
        # Create default config if it doesn't exist
        from .config import LocalExecutorConfig, ShannotConfig

        config = ShannotConfig(
            default_executor="local",
            executor={"local": LocalExecutorConfig(type="local")},
        )

    # Check if name already exists
    if name in config.executor:
        _LOGGER.error(f"Target '{name}' already exists")
        _LOGGER.info(f"Remove it first with: shannot remote remove {name}")
        return 1

    # Validate and normalize profile if specified
    normalized_profile = None
    if profile:
        # Try to find the profile
        profile_locations = [
            Path(profile),  # Exact path
            Path(profile).with_suffix(".json")
            if not profile.endswith(".json")
            else None,  # Add .json
            Path.home() / ".config/shannot" / f"{profile}.json",  # User config by name
            Path.home() / ".config/shannot" / profile,  # User config exact
            Path(__file__).parent.parent / "profiles" / f"{profile}.json",  # Bundled by name
            Path(__file__).parent.parent / "profiles" / profile,  # Bundled exact
        ]

        profile_found = None
        for loc in profile_locations:
            if loc and loc.exists():
                profile_found = loc
                # Store just the name for bundled/standard profiles, full path for custom
                if loc.parent.name == "profiles" or loc.parent.name == "shannot":
                    normalized_profile = loc.stem  # Just the name without .json
                else:
                    normalized_profile = str(loc)  # Full path for custom locations
                _LOGGER.info(f"  Found profile: {loc}")
                break

        if not profile_found:
            _LOGGER.error(f"Profile '{profile}' not found")
            _LOGGER.info("Available profiles:")
            bundled = Path(__file__).parent.parent / "profiles"
            if bundled.exists():
                for p in bundled.glob("*.json"):
                    _LOGGER.info(f"  - {p.stem} (bundled)")
            user_config = Path.home() / ".config/shannot"
            if user_config.exists():
                for p in user_config.glob("*.json"):
                    _LOGGER.info(f"  - {p.stem} (user)")
            return 1

    # Create SSH executor config
    key_path = Path(key_file).expanduser() if key_file else None
    executor_config = SSHExecutorConfig(
        type="ssh",
        host=host,
        username=username,
        key_file=key_path,
        port=port,
        profile=normalized_profile,
    )

    # Add to config
    config.executor[name] = executor_config

    # Save config
    try:
        save_config(config)
        _LOGGER.info(f"✓ Added remote target '{name}'")
        _LOGGER.info(f"  Host: {host}")
        if username:
            _LOGGER.info(f"  User: {username}")
        if port != 22:
            _LOGGER.info(f"  Port: {port}")
        if key_file:
            _LOGGER.info(f"  Key: {key_file}")
        if normalized_profile:
            _LOGGER.info(f"  Profile: {normalized_profile}")
        _LOGGER.info(f"\nTest with: shannot remote test {name}")
        _LOGGER.info(f"Use with: shannot --target {name} ls /")
        return 0
    except Exception as e:
        _LOGGER.error(f"Failed to save config: {e}")
        return 1


def _handle_remote_remove(args: argparse.Namespace) -> int:
    """Remove a remote target."""
    from .config import load_config, save_config

    # Validate inputs
    try:
        name = validate_type(args.name, str, "name")
        if not name or not name.strip():
            raise ValidationError("must be non-empty", "name")
    except ValidationError as e:
        _LOGGER.error(f"Invalid argument: {e}")
        return 1

    # Prevent removing local
    if name == "local":
        _LOGGER.error("Cannot remove 'local' target")
        return 1

    try:
        config = load_config()
    except Exception as e:
        _LOGGER.error(f"Failed to load config: {e}")
        return 1

    if name not in config.executor:
        _LOGGER.error(f"Target '{name}' not found")
        _LOGGER.info("List targets with: shannot remote list")
        return 1

    # Remove from config
    del config.executor[name]

    # Update default if needed
    if config.default_executor == name:
        config.default_executor = "local"
        _LOGGER.info("Default target changed to 'local'")

    # Save config
    try:
        save_config(config)
        _LOGGER.info(f"✓ Removed remote target '{name}'")
        return 0
    except Exception as e:
        _LOGGER.error(f"Failed to save config: {e}")
        return 1


def _handle_remote_test(args: argparse.Namespace) -> int:
    """Test connection to a remote target."""
    import asyncio

    from .config import create_executor, load_config

    # Validate inputs
    try:
        name = validate_type(args.name, str, "name")
        if not name or not name.strip():
            raise ValidationError("must be non-empty", "name")
    except ValidationError as e:
        _LOGGER.error(f"Invalid argument: {e}")
        return 1

    try:
        config = load_config()
    except Exception as e:
        _LOGGER.error(f"Failed to load config: {e}")
        return 1

    if name not in config.executor:
        _LOGGER.error(f"Target '{name}' not found")
        _LOGGER.info("List targets with: shannot remote list")
        return 1

    executor_config = config.executor[name]

    # Only test SSH executors
    if executor_config.type != "ssh":
        _LOGGER.info(f"Target '{name}' is type '{executor_config.type}' (nothing to test)")
        return 0

    _LOGGER.info(f"Testing connection to '{name}'...")
    _LOGGER.info(f"  Host: {executor_config.host}")
    if executor_config.username:
        _LOGGER.info(f"  User: {executor_config.username}")

    try:
        # Create executor
        executor = create_executor(config, name)

        # Load profile using same logic as SandboxDeps
        profile_name = executor_config.profile or "minimal"

        # Check if it's a path or a name
        if "/" in profile_name or profile_name.endswith(".json"):
            # It's a path
            profile = _load_profile(profile_name)
        else:
            # It's a name - check standard locations
            user_profile = Path.home() / ".config" / "shannot" / f"{profile_name}.json"
            if user_profile.exists():
                profile = _load_profile(str(user_profile))
            else:
                # Fall back to bundled profiles
                bundled_profile = Path(__file__).parent.parent / "profiles" / f"{profile_name}.json"
                profile = _load_profile(str(bundled_profile))

        # Try to run a simple command
        async def test():
            result = await executor.run_command(profile, ["echo", "test"])
            return result

        result = asyncio.run(test())

        if result.succeeded():
            _LOGGER.info("✓ Connection successful")
            _LOGGER.info(f"  Test output: {result.stdout.strip()}")
            return 0
        else:
            _LOGGER.error("✗ Test command failed")
            _LOGGER.error(f"  Error: {result.stderr}")
            return 1

    except Exception as e:
        _LOGGER.error(f"✗ Connection failed: {e}")
        _LOGGER.info("\nTroubleshooting:")
        _LOGGER.info("  1. Check SSH key permissions (chmod 600 ~/.ssh/id_rsa)")
        _LOGGER.info("  2. Verify host is reachable (ping hostname)")
        _LOGGER.info("  3. Test SSH manually (ssh user@hostname)")
        _LOGGER.info(
            "  4. Check bubblewrap is installed on remote (ssh user@hostname bwrap --version)"
        )
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()

    # Special handling: if no subcommand specified, treat remaining args as command to run
    # This allows "shannot ls /" instead of requiring "shannot run ls /"
    if argv is None:
        argv = sys.argv[1:]

    # Check if a known subcommand is present (skip flag arguments and their values)
    known_subcommands = {"run", "verify", "export", "mcp", "remote"}
    flags_with_values = {"--profile", "-p", "--target", "-t", "--bubblewrap"}
    has_subcommand = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in flags_with_values:
            # Skip flag and its value
            i += 2
            continue
        elif arg.startswith("-"):
            # Skip standalone flag
            i += 1
            continue
        else:
            # Found non-flag argument - check if it's a subcommand
            if arg in known_subcommands:
                has_subcommand = True
            break

    # If no subcommand found, prepend 'run' to make it work
    if not has_subcommand and argv:
        # Find first non-flag argument and insert 'run' before it
        insert_pos = 0
        i = 0
        while i < len(argv):
            arg = argv[i]
            if arg in flags_with_values:
                i += 2
            elif arg.startswith("-"):
                i += 1
            else:
                insert_pos = i
                break

        if insert_pos > 0 or (insert_pos == 0 and not argv[0].startswith("-")):
            argv = list(argv[:insert_pos]) + ["run"] + list(argv[insert_pos:])

    args = parser.parse_args(argv)
    verbose = getattr(args, "verbose", False)
    _configure_logging(verbose)

    handler = getattr(args, "handler", None)
    if handler is None:
        # If still no handler, user probably gave only flags
        parser.print_help()
        return 0

    try:
        return handler(args)
    except SandboxError as exc:
        _LOGGER.error("Sandbox error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
