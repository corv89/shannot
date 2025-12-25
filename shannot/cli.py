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

from .config import VERSION


def cmd_setup(args: argparse.Namespace) -> int:
    """Handle 'shannot setup' command."""
    from .config import RUNTIME_DIR, SANDBOX_BINARY_PATH
    from .runtime import (
        SetupError,
        download_sandbox,
        is_runtime_installed,
        is_sandbox_installed,
        remove_runtime,
        setup_runtime,
    )

    verbose = not args.quiet

    # --status: show installation status
    if args.status:
        if is_runtime_installed():
            print(f"✓ Stdlib: {RUNTIME_DIR}")
        else:
            print("✗ Stdlib not installed")

        if is_sandbox_installed():
            print(f"✓ Sandbox: {SANDBOX_BINARY_PATH}")
        else:
            print("✗ Sandbox binary not installed")

        return 0 if (is_runtime_installed() and is_sandbox_installed()) else 1

    # --remove: remove both
    if args.remove:
        return 0 if remove_runtime(verbose=verbose) else 1

    # Default: install both stdlib and sandbox
    # 1. Install stdlib
    try:
        setup_runtime(force=args.force, verbose=verbose)
    except SetupError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # 2. Install sandbox binary (graceful failure)
    if verbose:
        print()  # Blank line between components
    try:
        download_sandbox(force=args.force, verbose=verbose)
    except SetupError as e:
        if verbose:
            print(f"⚠ {e}")
            print("Setup complete (stdlib only).")
        # Don't fail - sandbox binary might not be available yet
        return 0

    if verbose:
        print("\nSetup complete!")

    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Handle 'shannot run' command."""
    # If target specified, use remote execution path
    if args.target:
        return cmd_run_remote(args)

    # Local execution
    from .config import RUNTIME_DIR
    from .interact import main as interact_main
    from .runtime import SetupError, find_pypy_sandbox, get_runtime_path, setup_runtime

    argv = []

    # Step 1: Auto-detect lib-path and setup runtime if needed
    # (Do this first so runtime can download even if binary is missing)
    if args.lib_path:
        argv.append(f"--lib-path={args.lib_path}")
    else:
        runtime_path = get_runtime_path()
        if runtime_path:
            argv.append(f"--lib-path={runtime_path}")
        else:
            # Runtime not installed - set up automatically for local runs
            print("Runtime not installed. Setting up automatically...", file=sys.stderr)
            print("", file=sys.stderr)

            try:
                success = setup_runtime(verbose=True)
                if not success:
                    print("", file=sys.stderr)
                    print("Error: Automatic setup failed.", file=sys.stderr)
                    print("Try running manually: shannot setup --verbose", file=sys.stderr)
                    return 1
            except SetupError as e:
                print("", file=sys.stderr)
                print(f"Error: Setup failed: {e}", file=sys.stderr)
                print("Try running manually: shannot setup --verbose", file=sys.stderr)
                return 1

            # Setup succeeded - get runtime path
            runtime_path = get_runtime_path()
            if not runtime_path:
                print("", file=sys.stderr)
                print("Error: Setup completed but runtime path not found.", file=sys.stderr)
                msg = "This is unexpected. Try: shannot setup --remove && shannot setup"
                print(msg, file=sys.stderr)
                return 1

            argv.append(f"--lib-path={runtime_path}")
            print("", file=sys.stderr)
            print("Setup complete! Running script...", file=sys.stderr)
            print("", file=sys.stderr)

    # Step 2: Auto-detect pypy-sandbox executable
    # (Check this after runtime setup, so both can be auto-downloaded in future)
    if args.executable:
        executable = args.executable
    else:
        executable = find_pypy_sandbox()
        if not executable:
            print("Error: pypy-sandbox not found.", file=sys.stderr)
            print("", file=sys.stderr)
            print("You can:", file=sys.stderr)
            print("  1. Run 'shannot setup' to download pre-built binary", file=sys.stderr)
            print("  2. Build from source: https://github.com/corv89/pypy", file=sys.stderr)
            print(f"  3. Place manually at {RUNTIME_DIR}/pypy-sandbox", file=sys.stderr)
            print("  4. Specify with --pypy-sandbox <path>", file=sys.stderr)
            print("", file=sys.stderr)
            print("Run 'shannot status' to check current status.", file=sys.stderr)
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

    # Add executable and script with args
    argv.append(str(executable))
    argv.append("-S")  # Suppress site module import (not useful in sandbox)
    argv.append(args.script)
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
        with open(script_path) as f:
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


def cmd_remote_add(args: argparse.Namespace) -> int:
    """Handle 'shannot remote add' command."""
    import getpass

    from .config import add_remote

    try:
        user = args.user or getpass.getuser()
        remote = add_remote(
            name=args.name,
            host=args.host,
            user=user,
            port=args.port,
        )
        print(f"Added remote '{args.name}': {remote.user}@{remote.host}:{remote.port}")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_remote_list(args: argparse.Namespace) -> int:
    """Handle 'shannot remote list' command."""
    from .config import load_remotes

    try:
        remotes = load_remotes()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not remotes:
        print("No remotes configured.")
        print("Use 'shannot remote add <name> <host>' to add one.")
        return 0

    # Calculate column widths
    name_width = max(len(name) for name in remotes.keys())
    name_width = max(name_width, 4)  # Minimum "NAME" header width

    print(f"{'NAME':<{name_width}}  TARGET")
    print(f"{'-' * name_width}  {'-' * 30}")

    for name, remote in sorted(remotes.items()):
        target = f"{remote.user}@{remote.host}"
        if remote.port != 22:
            target += f":{remote.port}"
        print(f"{name:<{name_width}}  {target}")

    return 0


def cmd_remote_test(args: argparse.Namespace) -> int:
    """Handle 'shannot remote test' command."""
    from .config import resolve_target
    from .ssh import SSHConfig, SSHConnection

    try:
        user, host, port = resolve_target(args.name)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    target = f"{user}@{host}"
    print(f"Testing connection to {target}:{port}...")

    # Create SSHConfig with resolved values
    config = SSHConfig(target=target, port=port, connect_timeout=args.timeout)

    with SSHConnection(config) as ssh:
        if not ssh.connect():
            print(f"FAILED: Could not connect to {target}:{port}")
            return 1

        # Run a simple command to verify
        result = ssh.run("echo OK")
        if result.returncode == 0 and b"OK" in result.stdout:
            print(f"SUCCESS: Connected to {target}:{port}")
            # Get remote hostname for verification
            hostname_result = ssh.run("hostname")
            if hostname_result.returncode == 0:
                hostname = hostname_result.stdout.decode().strip()
                print(f"  Remote hostname: {hostname}")
            return 0
        else:
            print("FAILED: Connection succeeded but test command failed")
            if result.stderr:
                print(f"  Error: {result.stderr.decode()}")
            return 1


def cmd_remote_remove(args: argparse.Namespace) -> int:
    """Handle 'shannot remote remove' command."""
    from .config import remove_remote

    if remove_remote(args.name):
        print(f"Removed remote '{args.name}'")
        return 0
    else:
        print(f"Error: Remote '{args.name}' not found", file=sys.stderr)
        return 1


def cmd_mcp_install(args: argparse.Namespace) -> int:
    """Handle 'shannot mcp install' command."""
    import json
    import os
    from pathlib import Path

    client = args.client

    if client == "claude-desktop":
        # Determine config path based on platform
        if sys.platform == "darwin":
            config_path = Path(
                "~/Library/Application Support/Claude/claude_desktop_config.json"
            ).expanduser()
        elif sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            if not appdata:
                print("Error: APPDATA environment variable not set", file=sys.stderr)
                return 1
            config_path = Path(appdata) / "Claude" / "claude_desktop_config.json"
        else:
            print(
                "Error: Claude Desktop not supported on Linux (use claude-code)",
                file=sys.stderr,
            )
            return 1

        # Load existing config or create new
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
        else:
            config = {}

        # Ensure mcpServers key exists
        if "mcpServers" not in config:
            config["mcpServers"] = {}

        # Add shannot-mcp server
        config["mcpServers"]["shannot"] = {
            "command": "shannot-mcp",
            "args": [],
            "env": {},
        }

        # Write back config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            f.write("\n")

        print(f"✓ Updated {config_path}")
        print()
        print("Restart Claude Desktop to see Shannot MCP server.")

    elif client == "claude-code":
        # Output .mcp.json snippet for project
        snippet = {"mcpServers": {"shannot": {"command": "shannot-mcp", "args": [], "env": {}}}}

        print("Add this to your project's .mcp.json file:")
        print()
        print(json.dumps(snippet, indent=2))
        print()
        print("Or add to user config at:")
        if sys.platform == "darwin":
            print("  ~/Library/Application Support/Claude/claude_code_config.json")
        elif sys.platform == "win32":
            print("  %APPDATA%\\Claude\\claude_code_config.json")
        else:
            print("  ~/.config/Claude/claude_code_config.json")

    else:
        print(f"Error: Unknown client '{client}'", file=sys.stderr)
        print("Supported clients: claude-desktop, claude-code", file=sys.stderr)
        return 1

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Handle 'shannot status' command."""
    # Determine what to show
    show_all = not args.runtime and not args.targets
    show_runtime = args.runtime or show_all
    show_targets = args.targets or show_all
    show_sessions = show_all

    # Runtime status
    if show_runtime:
        from .config import RUNTIME_DIR
        from .runtime import find_pypy_sandbox, is_runtime_installed

        print("Runtime:")
        if is_runtime_installed():
            print(f"  ✓ Stdlib: {RUNTIME_DIR}")
        else:
            print("  ✗ Stdlib not installed (run 'shannot setup')")

        # Check for pypy-sandbox binary
        sandbox_path = find_pypy_sandbox()
        if sandbox_path:
            print(f"  ✓ Sandbox binary: {sandbox_path}")
        else:
            print("  ✗ Sandbox binary not found")
            print("    Build pypy-sandbox from PyPy source and add to PATH,")
            print(f"    or place in {RUNTIME_DIR}/pypy-sandbox")

        if show_all:
            print()

    # Targets status
    if show_targets:
        from .config import load_remotes, resolve_target
        from .ssh import SSHConfig, SSHConnection

        print("Targets:")
        try:
            remotes = load_remotes()
        except RuntimeError as e:
            print(f"  ✗ Error loading remotes: {e}")
            remotes = {}

        if not remotes:
            print("  No remotes configured")
        else:
            for name, remote in sorted(remotes.items()):
                user, host, port = resolve_target(name)
                target_str = remote.target_string
                if remote.port != 22:
                    target_str += f":{remote.port}"

                # Test connection with short timeout
                config = SSHConfig(target=f"{user}@{host}", port=port, connect_timeout=5)
                try:
                    with SSHConnection(config) as ssh:
                        if ssh.connect():
                            result = ssh.run("echo OK", timeout=5)
                            if result.returncode == 0:
                                print(f"  ✓ {name} ({target_str}) — connected")
                            else:
                                print(f"  ✗ {name} ({target_str}) — command failed")
                        else:
                            print(f"  ✗ {name} ({target_str}) — connection failed")
                except Exception as e:
                    print(f"  ✗ {name} ({target_str}) — {e}")
        if show_all:
            print()

    # Sessions status
    if show_sessions:
        from .session import Session

        print("Sessions:")
        try:
            pending = Session.list_pending()
            count = len(pending)
            if count > 0:
                print(f"  {count} pending (shannot approve to review)")
            else:
                print("  No pending sessions")
        except Exception as e:
            print(f"  ✗ Error: {e}")

        # Audit status (only in show_all mode)
        from .audit import get_today_event_count, load_audit_config

        audit_config = load_audit_config()
        if audit_config.enabled:
            event_count = get_today_event_count()
            print(f"  Audit: enabled ({event_count} events today)")
        else:
            print("  Audit: disabled")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="shannot",
        description="Sandbox control for PyPy sandboxed processes",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"shannot {VERSION}",
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
        description="Execute a PyPy sandbox with auto-detected pypy-sandbox binary and runtime",
    )
    run_parser.add_argument(
        "script",
        help="Python script to execute in the sandbox",
    )
    run_parser.add_argument(
        "script_args",
        nargs="*",
        help="Arguments to pass to the script",
    )
    run_parser.add_argument(
        "--pypy-sandbox",
        dest="executable",
        help="Path to pypy-sandbox executable (auto-detected if not specified)",
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

    # ===== remote subcommand (with sub-subcommands) =====
    remote_parser = subparsers.add_parser(
        "remote",
        help="Manage SSH remote targets",
        description="Add, list, test, and remove named SSH targets",
    )
    remote_subparsers = remote_parser.add_subparsers(dest="remote_command", help="Remote commands")

    # remote add
    remote_add_parser = remote_subparsers.add_parser(
        "add",
        help="Add a new remote target",
        description="Save a named SSH target for easy reuse",
    )
    remote_add_parser.add_argument(
        "name",
        help="Unique name for the remote (e.g., 'prod', 'staging')",
    )
    remote_add_parser.add_argument(
        "host",
        help="Hostname or IP address",
    )
    remote_add_parser.add_argument(
        "--user",
        "-u",
        help="SSH username (defaults to current user)",
    )
    remote_add_parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=22,
        help="SSH port (default: 22)",
    )
    remote_add_parser.set_defaults(func=cmd_remote_add)

    # remote list
    remote_list_parser = remote_subparsers.add_parser(
        "list",
        help="List configured remotes",
        description="Show all saved SSH targets",
    )
    remote_list_parser.set_defaults(func=cmd_remote_list)

    # remote test
    remote_test_parser = remote_subparsers.add_parser(
        "test",
        help="Test connection to a remote",
        description="Verify SSH connectivity to a saved or ad-hoc target",
    )
    remote_test_parser.add_argument(
        "name",
        help="Remote name or user@host target",
    )
    remote_test_parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=10,
        help="Connection timeout in seconds (default: 10)",
    )
    remote_test_parser.set_defaults(func=cmd_remote_test)

    # remote remove
    remote_remove_parser = remote_subparsers.add_parser(
        "remove",
        help="Remove a remote target",
        description="Delete a saved SSH target",
    )
    remote_remove_parser.add_argument(
        "name",
        help="Name of remote to remove",
    )
    remote_remove_parser.set_defaults(func=cmd_remote_remove)

    # Handle 'shannot remote' with no subcommand
    def print_remote_help(args: argparse.Namespace) -> int:
        remote_parser.print_help()
        return 0

    remote_parser.set_defaults(func=print_remote_help)

    # ===== status subcommand =====
    status_parser = subparsers.add_parser(
        "status",
        help="Show system status",
        description="Display runtime, targets, and session status",
    )
    status_parser.add_argument(
        "--runtime",
        action="store_true",
        help="Check runtime installation only",
    )
    status_parser.add_argument(
        "--targets",
        action="store_true",
        help="Test target connections only",
    )
    status_parser.set_defaults(func=cmd_status)

    # ===== mcp subcommand (with sub-subcommands) =====
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="MCP server installation and management",
        description="Install/manage MCP server for Claude Desktop/Code",
    )
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_command", help="MCP commands")

    # mcp install
    mcp_install_parser = mcp_subparsers.add_parser(
        "install",
        help="Install MCP server configuration",
        description="Configure Claude Desktop or Claude Code to use Shannot MCP server",
    )
    mcp_install_parser.add_argument(
        "--client",
        "-c",
        choices=["claude-desktop", "claude-code"],
        default="claude-desktop",
        help="MCP client to configure (default: claude-desktop)",
    )
    mcp_install_parser.set_defaults(func=cmd_mcp_install)

    # Handle 'shannot mcp' with no subcommand
    def print_mcp_help(args: argparse.Namespace) -> int:
        mcp_parser.print_help()
        return 0

    mcp_parser.set_defaults(func=print_mcp_help)

    # Parse and execute
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
