#!/usr/bin/env python3
"""
shannot: Sandbox control for PyPy sandboxed processes.

Usage:
    shannot setup           Install PyPy stdlib for sandboxing
    shannot run [options]   Run a script in the sandbox
    shannot approve         Interactive session approval (TUI)
"""
from __future__ import annotations

import argparse
import sys


def cmd_setup(args: argparse.Namespace) -> int:
    """Handle 'shannot setup' command."""
    from .config import RUNTIME_DIR
    from .runtime import SetupError, is_runtime_installed, remove_runtime, setup_runtime

    if args.status:
        if is_runtime_installed():
            print(f"Runtime installed at {RUNTIME_DIR}")
            return 0
        else:
            print("Runtime not installed. Run 'shannot setup' to install.")
            return 1

    if args.remove:
        return 0 if remove_runtime(verbose=not args.quiet) else 1

    try:
        success = setup_runtime(
            force=args.force,
            verbose=not args.quiet,
        )
        return 0 if success else 1
    except SetupError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Handle 'shannot run' command."""
    # If target specified, use remote execution path
    if args.target:
        return cmd_run_remote(args)

    # Local execution
    from .interact import main as interact_main
    from .runtime import get_runtime_path

    argv = []

    # Auto-detect lib-path if not specified
    if args.lib_path:
        argv.append(f"--lib-path={args.lib_path}")
    else:
        runtime_path = get_runtime_path()
        if runtime_path:
            argv.append(f"--lib-path={runtime_path}")
        else:
            print(
                "Error: No --lib-path specified and runtime not installed.",
                file=sys.stderr,
            )
            print("Run 'shannot setup' to install the runtime.", file=sys.stderr)
            return 1

    # Pass through other options
    if args.tmp:
        argv.append(f"--tmp={args.tmp}")
    if args.nocolor:
        argv.append("--nocolor")
    if args.raw_stdout:
        argv.append("--raw-stdout")
    if args.debug:
        argv.append("--debug")
    if args.dry_run:
        argv.append("--dry-run")
    if args.script_name:
        argv.append(f"--script-name={args.script_name}")
    if args.analysis:
        argv.append(f"--analysis={args.analysis}")

    # Add executable and script args
    argv.append(args.executable)
    argv.extend(args.script_args)

    # Execute directly
    return interact_main(argv)


def cmd_run_remote(args: argparse.Namespace) -> int:
    """Handle 'shannot run --target' for remote execution."""
    from .remote import RemoteExecutionError, run_remote_dry_run

    # Get script path from args - look for .py files in script_args
    script_args = [a for a in args.script_args if a.endswith(".py")]
    if not script_args:
        print("Error: No .py script specified in arguments", file=sys.stderr)
        return 1

    script_path = script_args[0]

    # Read script content
    try:
        with open(script_path, "r") as f:
            script_content = f.read()
    except FileNotFoundError:
        print(f"Error: Script not found: {script_path}", file=sys.stderr)
        return 1

    try:
        session = run_remote_dry_run(
            target=args.target,
            script_path=script_path,
            script_content=script_content,
            name=args.script_name,
            analysis=args.analysis or "",
        )

        if session:
            print(f"\n*** Remote session created: {session.id} ***")
            print(f"    Target: {args.target}")
            print(f"    Commands queued: {len(session.commands)}")
            print(f"    File writes queued: {len(session.pending_writes)}")
            print("    Run 'shannot approve' to review and execute.")
            return 0
        else:
            print("\n*** No commands or writes were queued. ***")
            return 0

    except RemoteExecutionError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_approve(args: argparse.Namespace) -> int:
    """Handle 'shannot approve' - delegate to approve module."""
    from .approve import main as approve_main

    # Reconstruct sys.argv for approve module
    sys.argv = ["shannot approve"] + (args.approve_args or [])
    return approve_main()


def cmd_execute(args: argparse.Namespace) -> int:
    """Handle 'shannot execute' - execute a session directly."""
    import json

    from .config import VERSION
    from .session import Session, execute_session

    try:
        session = Session.load(args.session_id)
    except FileNotFoundError:
        if args.json_output:
            print(json.dumps({"error": f"Session not found: {args.session_id}"}))
        else:
            print(f"Error: Session not found: {args.session_id}", file=sys.stderr)
        return 1

    # Mark as approved and execute
    session.status = "approved"
    session.save()

    exit_code = execute_session(session)

    # Reload to get updated fields
    session = Session.load(args.session_id)

    if args.json_output:
        output = {
            "version": VERSION,
            "status": session.status,
            "exit_code": session.exit_code,
            "stdout": session.stdout or "",
            "stderr": session.stderr or "",
        }
        print(json.dumps(output))
    else:
        if exit_code == 0:
            print(f"Session {session.id} executed successfully")
        else:
            print(f"Session {session.id} failed with exit code {exit_code}")

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="shannot",
        description="Sandbox control for PyPy sandboxed processes",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # ===== setup subcommand =====
    setup_parser = subparsers.add_parser(
        "setup",
        help="Install PyPy stdlib for sandboxing",
        description="Download and install PyPy 3.6 stdlib to ~/.local/share/shannot/runtime/",
    )
    setup_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force reinstall even if already installed",
    )
    setup_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )
    setup_parser.add_argument(
        "--status",
        "-s",
        action="store_true",
        help="Check if runtime is installed",
    )
    setup_parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove installed runtime",
    )
    setup_parser.set_defaults(func=cmd_setup)

    # ===== run subcommand =====
    run_parser = subparsers.add_parser(
        "run",
        help="Run a script in the sandbox",
        description="Execute a PyPy sandbox with optional auto-detected runtime",
    )
    run_parser.add_argument(
        "executable",
        help="Path to pypy-c-sandbox executable",
    )
    run_parser.add_argument(
        "script_args",
        nargs="*",
        help="Arguments to pass to the sandbox (e.g., -S script.py)",
    )
    run_parser.add_argument(
        "--lib-path",
        help="Path to lib-python and lib_pypy (auto-detected if not specified)",
    )
    run_parser.add_argument(
        "--tmp",
        help="Real directory mapped to virtual /tmp",
    )
    run_parser.add_argument(
        "--nocolor",
        action="store_true",
        help="Disable ANSI coloring",
    )
    run_parser.add_argument(
        "--raw-stdout",
        action="store_true",
        help="Disable output sanitization",
    )
    run_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log commands without executing",
    )
    run_parser.add_argument(
        "--script-name",
        help="Human-readable session name",
    )
    run_parser.add_argument(
        "--analysis",
        help="Description of script purpose",
    )
    run_parser.add_argument(
        "--target",
        help="SSH target for remote execution (user@host)",
    )
    run_parser.set_defaults(func=cmd_run)

    # ===== approve subcommand (delegates to existing approve module) =====
    approve_parser = subparsers.add_parser(
        "approve",
        help="Interactive session approval",
        description="Launch TUI for reviewing and approving pending sessions",
    )
    approve_parser.add_argument(
        "approve_args",
        nargs="*",
        help="Arguments passed to approval system",
    )
    approve_parser.set_defaults(func=cmd_approve)

    # ===== execute subcommand =====
    execute_parser = subparsers.add_parser(
        "execute",
        help="Execute a session directly",
        description="Execute an approved session without TUI (used by remote protocol)",
    )
    execute_parser.add_argument(
        "--session-id",
        required=True,
        help="Session ID to execute",
    )
    execute_parser.add_argument(
        "--json-output",
        action="store_true",
        help="Output results as JSON",
    )
    execute_parser.set_defaults(func=cmd_execute)

    # Parse and execute
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
