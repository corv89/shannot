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
import sys
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Optional, cast

from . import (
    SandboxError,
    SandboxManager,
    SandboxProfile,
    load_profile_from_path,
)
from .process import ProcessResult, ensure_tool_available

_LOGGER = logging.getLogger("shannot")

# Default profile locations (checked in order)
_DEFAULT_PROFILES = [
    Path.home() / ".config/shannot/profile.json",
    Path("/etc/shannot/profile.json"),
    Path("/etc/sandbox/readonly.json"),
    Path("/usr/etc/sandbox/readonly.json"),
]


def _get_default_profile() -> Path:
    """Get default profile from env or standard locations."""
    env_profile = os.environ.get("SANDBOX_PROFILE")
    if env_profile:
        return Path(env_profile)

    for profile_path in _DEFAULT_PROFILES:
        if profile_path.exists():
            return profile_path

    raise SandboxError(
        "No default sandbox profile found. Set SANDBOX_PROFILE env var or specify --profile"
    )


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _resolve_bubblewrap_path(candidate: Optional[str]) -> Path:
    if candidate:
        return Path(candidate).expanduser()
    env_candidate = os.environ.get("BWRAP")
    if env_candidate:
        return Path(env_candidate).expanduser()
    resolved = ensure_tool_available("bwrap")
    return resolved


def _load_profile(path: str) -> SandboxProfile:
    return load_profile_from_path(Path(path).expanduser())


def _profile_to_serializable(profile: SandboxProfile) -> dict[str, object]:
    data = asdict(profile)

    def _path_to_str(value: Optional[Path]) -> Optional[str]:
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
    seccomp_profile = _path_to_str(cast(Optional[Path], data["seccomp_profile"]))
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
    profile_path = cast(Optional[str], args.profile) or _get_default_profile()
    profile = _load_profile(str(profile_path))
    bubblewrap = _resolve_bubblewrap_path(cast(Optional[str], args.bubblewrap))
    manager = SandboxManager(profile, bubblewrap)
    command = list(cast(Sequence[str], args.command))
    if not command:
        raise SandboxError("No command specified. Usage: sandbox run COMMAND [ARGS...]")
    result = manager.run(command, check=cast(bool, args.check))
    if cast(bool, args.print_stdout) and result.stdout:
        print(result.stdout, end="")
    if cast(bool, args.print_stderr) and result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def _handle_export(args: argparse.Namespace) -> int:
    """Handle 'export' subcommand - export profile as JSON."""
    profile_path = cast(Optional[str], args.profile) or _get_default_profile()
    profile = _load_profile(str(profile_path))
    serialized = _profile_to_serializable(profile)
    json_output = json.dumps(serialized, indent=2, sort_keys=True)
    print(json_output)
    return 0


def _handle_verify(args: argparse.Namespace) -> int:
    """Handle 'verify' subcommand - verify sandbox configuration."""
    profile_path = cast(Optional[str], args.profile) or _get_default_profile()
    profile = _load_profile(str(profile_path))
    bubblewrap = _resolve_bubblewrap_path(cast(Optional[str], args.bubblewrap))
    manager = SandboxManager(profile, bubblewrap)

    allowed_command = cast(Optional[Sequence[str]], args.allowed_command) or ["ls", "/"]
    disallowed_command = cast(Optional[Sequence[str]], args.disallowed_command) or [
        "touch",
        "/tmp/probe",
    ]

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
        prog="sandbox",
        description="Run commands in a read-only sandbox.",
        epilog=(
            "Default profile: /etc/sandbox/readonly.json "
            "(override with --profile or $SANDBOX_PROFILE)"
        ),
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

    subparsers = parser.add_subparsers(dest="command_name", required=True)

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

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(cast(bool, args.verbose))

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error("No handler associated with the selected subcommand.")
        # parser.error() calls sys.exit(), so this is unreachable but needed for type checking
        raise SystemExit(2)  # pragma: no cover  # type: ignore[reportUnreachable]
    try:
        return handler(args)
    except SandboxError as exc:
        _LOGGER.error("Sandbox error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
