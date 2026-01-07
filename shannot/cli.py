#!/usr/bin/env python3
"""
shannot: Sandbox control for PyPy sandboxed processes.

Usage:
    shannot run             Dry-run a script, create session for review
    shannot approve         Review and execute pending sessions
    shannot status          Show system status
    shannot setup           Configure shannot (interactive menu or subcommands)
"""

from __future__ import annotations

import argparse
import sys


def cmd_setup_runtime(args: argparse.Namespace) -> int:
    """Handle 'shannot setup runtime' command."""
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


def cmd_setup(args: argparse.Namespace) -> int:
    """Handle 'shannot setup' command - dispatch to subcommands or interactive menu."""
    if args.setup_command is None:
        # No subcommand = interactive mode
        return run_setup_menu()
    elif args.setup_command == "runtime":
        return cmd_setup_runtime(args)
    elif args.setup_command == "remote":
        return cmd_setup_remote(args)
    elif args.setup_command == "mcp":
        return cmd_setup_mcp(args)
    else:
        return 1


def cmd_setup_remote(args: argparse.Namespace) -> int:
    """Handle 'shannot setup remote' - dispatch to remote subcommands or show help."""
    if args.remote_command is None:
        # No subcommand - show interactive remote menu
        return run_remote_menu()
    elif args.remote_command == "add":
        return cmd_remote_add(args)
    elif args.remote_command == "list":
        return cmd_remote_list(args)
    elif args.remote_command == "remove":
        return cmd_remote_remove(args)
    elif args.remote_command == "test":
        return cmd_remote_test(args)
    else:
        return 1


def cmd_setup_mcp(args: argparse.Namespace) -> int:
    """Handle 'shannot setup mcp' - dispatch to mcp subcommands or show help."""
    if args.mcp_command is None:
        # No subcommand - run MCP install interactively
        return run_mcp_menu()
    elif args.mcp_command == "install":
        return cmd_mcp_install(args)
    else:
        return 1


def run_setup_menu() -> int:
    """Interactive setup menu."""
    from .menu import clear_screen, select_menu

    while True:
        clear_screen()
        choice = select_menu(
            "Shannot Setup",
            ["Manage remotes", "Install MCP integration", "Exit"],
        )

        if choice is None or choice == 2:  # Exit
            return 0
        elif choice == 0:  # Manage remotes
            run_remote_menu()
        elif choice == 1:  # MCP
            run_mcp_menu()


def run_remote_menu() -> int:
    """Interactive remote management menu."""
    from .config import load_remotes
    from .menu import clear_screen, prompt_input, select_menu, wait_for_key

    while True:
        clear_screen()

        # Show current remotes status
        try:
            remotes = load_remotes()
            if remotes:
                print("Configured remotes:")
                for name, remote in sorted(remotes.items()):
                    print(f"  {name}: {remote.target_string}")
                print()
        except RuntimeError:
            remotes = {}

        choice = select_menu(
            "Remote Targets",
            ["Add remote", "Remove remote", "Test connection", "List remotes", "Back"],
        )

        if choice is None or choice == 4:  # Back
            return 0
        elif choice == 0:  # Add
            print()
            name = prompt_input("Remote name (e.g., 'prod')")
            if not name:
                continue
            host = prompt_input("Hostname or IP")
            if not host:
                continue
            user = prompt_input("SSH user", default=None)
            port_str = prompt_input("SSH port", default="22")
            port = int(port_str) if port_str and port_str.isdigit() else 22

            class AddArgs:
                pass

            add_args = AddArgs()
            add_args.name = name  # type: ignore[attr-defined]
            add_args.host = host  # type: ignore[attr-defined]
            add_args.user = user  # type: ignore[attr-defined]
            add_args.port = port  # type: ignore[attr-defined]
            cmd_remote_add(add_args)  # type: ignore[arg-type]
            wait_for_key()
        elif choice == 1:  # Remove
            try:
                remotes = load_remotes()
            except RuntimeError:
                remotes = {}
            if not remotes:
                print("\n  No remotes configured.")
                wait_for_key()
                continue
            remote_names = sorted(remotes.keys())
            idx = select_menu("Select remote to remove", remote_names + ["Back"])
            if idx is None or idx == len(remote_names):  # Back or quit
                continue
            name = remote_names[idx]

            class RemoveArgs:
                pass

            remove_args = RemoveArgs()
            remove_args.name = name  # type: ignore[attr-defined]
            cmd_remote_remove(remove_args)  # type: ignore[arg-type]
            wait_for_key()
        elif choice == 2:  # Test
            try:
                remotes = load_remotes()
            except RuntimeError:
                remotes = {}
            if not remotes:
                print("\n  No remotes configured. Add one first.")
                wait_for_key()
                continue
            remote_names = sorted(remotes.keys())
            idx = select_menu("Select remote to test", remote_names + ["Back"])
            if idx is None or idx == len(remote_names):  # Back or quit
                continue
            name = remote_names[idx]

            class TestArgs:
                timeout = 10

            test_args = TestArgs()
            test_args.name = name  # type: ignore[attr-defined]
            cmd_remote_test(test_args)  # type: ignore[arg-type]
            wait_for_key()
        elif choice == 3:  # List

            class ListArgs:
                pass

            cmd_remote_list(ListArgs())  # type: ignore[arg-type]
            wait_for_key()


def run_mcp_menu() -> int:
    """Interactive MCP setup menu."""
    from .menu import clear_screen, select_menu, wait_for_key

    clear_screen()
    choice = select_menu(
        "MCP Integration",
        ["Install for Claude Desktop", "Install for Claude Code", "Back"],
    )

    if choice is None or choice == 2:  # Back
        return 0
    elif choice == 0:  # Claude Desktop

        class InstallArgs:
            client = "claude-desktop"

        result = cmd_mcp_install(InstallArgs())  # type: ignore[arg-type]
        wait_for_key()
        return result
    elif choice == 1:  # Claude Code

        class InstallArgs2:
            client = "claude-code"

        result = cmd_mcp_install(InstallArgs2())  # type: ignore[arg-type]
        wait_for_key()
        return result

    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Handle 'shannot run' command."""
    # Validate: --session is mutually exclusive with script/-c
    if args.session and (args.script or args.code):
        print("Error: --session cannot be used with script or -c", file=sys.stderr)
        return 1

    # Session execution mode
    if args.session:
        return cmd_run_session(args)

    # Script mode: validate we have script or -c
    if not args.script and not args.code:
        print("Error: Provide script, -c CODE, or --session ID", file=sys.stderr)
        return 1
    if args.script and args.code:
        print("Error: Cannot specify both script and -c", file=sys.stderr)
        return 1

    # If target specified, use remote execution path
    if args.target:
        return cmd_run_remote(args)

    # Local execution
    from .config import RUNTIME_DIR
    from .interact import main as interact_main
    from .runtime import (
        SetupError,
        download_sandbox,
        find_pypy_sandbox,
        get_runtime_path,
        setup_runtime,
    )

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

            # Also try to download sandbox binary (graceful failure)
            try:
                download_sandbox(verbose=True)
            except SetupError as e:
                # Graceful: continue without binary, user will get instructions later
                print(f"Note: Could not download sandbox binary: {e}", file=sys.stderr)
                print("You can download it manually with: shannot setup runtime", file=sys.stderr)

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
    # run script.py is always dry-run (capture commands/writes for approval)
    # use --session to execute an approved session
    argv.append("--dry-run")
    if args.script_name:
        argv.append(f"--script-name={args.script_name}")
    if args.analysis:
        argv.append(f"--analysis={args.analysis}")
    if args.json_output:
        argv.append("--json-output")

    # Pass --code before executable (getopt stops at first positional)
    if args.code:
        argv.append(f"--code={args.code}")

    # Add executable
    argv.append(str(executable))
    argv.append("-S")  # Suppress site module import (not useful in sandbox)

    # Script file: pass path (interact will read and inject into VFS)
    if not args.code:
        argv.append(args.script)
        argv.extend(args.script_args)

    # Execute directly
    result = interact_main(argv)
    if isinstance(result, dict):
        return result.get("exit_code", 0)
    return result


def cmd_run_remote(args: argparse.Namespace) -> int:
    """Handle 'shannot run --target' for remote execution."""
    from .remote import RemoteExecutionError, run_remote_dry_run

    # Get script path from args.script (not script_args which are passed to script)
    script_path = args.script
    if not script_path:
        print("Error: No script specified", file=sys.stderr)
        return 1

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
            print(f"    Deletions queued: {len(session.pending_deletions)}")
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


def cmd_run_session(args: argparse.Namespace) -> int:
    """Handle 'shannot run --session' - execute an approved session."""
    import json

    from .config import get_version
    from .session import Session, execute_session

    session_id = args.session

    try:
        session = Session.load(session_id)
    except FileNotFoundError:
        if args.json_output:
            print(json.dumps({"error": f"Session not found: {session_id}"}))
        else:
            print(f"Error: Session not found: {session_id}", file=sys.stderr)
        return 1

    # Mark as approved and execute
    session.status = "approved"
    session.save()

    exit_code = execute_session(session)

    # Reload to get updated fields
    session = Session.load(session_id)

    if args.json_output:
        output = {
            "version": get_version(),
            "status": session.status,
            "exit_code": session.exit_code,
            "stdout": session.stdout or "",
            "stderr": session.stderr or "",
            "completed_writes": session.completed_writes or [],
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
        print("Use 'shannot setup remote add <name> <host>' to add one.")
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
    from .deploy import ensure_deployed, is_deployed
    from .selftest import run_remote_self_test
    from .ssh import SSHConfig, SSHConnection

    try:
        user, host, port = resolve_target(args.name)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    target = f"{user}@{host}"
    target_display = f"{target}:{port}" if port != 22 else target
    print(f"Testing {args.name} ({target_display})...")

    # Create SSHConfig with resolved values
    config = SSHConfig(target=target, port=port, connect_timeout=args.timeout)

    with SSHConnection(config) as ssh:
        # Step 1: Test SSH connection
        if not ssh.connect():
            print("  ✗ SSH connection failed")
            return 1
        print("  ✓ SSH connection")

        # Step 2: Check/deploy shannot
        try:
            if is_deployed(ssh):
                print("  ✓ Shannot deployed")
            else:
                print("  ⟳ Deploying runtime...", end="", flush=True)
                ensure_deployed(ssh)
                print(" done")
        except Exception as e:
            print(f"\n  ✗ Deployment failed: {e}")
            return 1

        # Step 3: Run sandbox self-test
        result = run_remote_self_test(user, host, port, deploy_if_missing=False)
        if result.success:
            print(f"  ✓ Sandbox execution ({result.elapsed_ms:.0f}ms)")
            print(f"    Output: {result.output!r}")
        else:
            print("  ✗ Sandbox execution failed")
            print(f"    Error: {result.error}")
            return 1

    print(f"\nRemote '{args.name}' is ready.")
    return 0


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
    import shutil
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

        # Find the full path to shannot-mcp executable
        # Claude Desktop doesn't inherit shell PATH, so we need the absolute path
        mcp_command = shutil.which("shannot-mcp")
        if not mcp_command:
            print("Error: shannot-mcp not found in PATH", file=sys.stderr)
            print("Make sure shannot is installed: pip install shannot", file=sys.stderr)
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

        # Add shannot-mcp server with absolute path
        config["mcpServers"]["shannot"] = {
            "command": mcp_command,
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
        import subprocess

        # Find claude CLI - check PATH first, then common install location
        claude_path = shutil.which("claude")
        if not claude_path:
            local_claude = Path.home() / ".claude" / "local" / "claude"
            if local_claude.exists():
                claude_path = str(local_claude)

        if claude_path:
            result = subprocess.run(
                [claude_path, "mcp", "add", "--transport", "stdio", "shannot", "--", "shannot-mcp"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("✓ Added shannot MCP server to Claude Code")
                return 0
            elif "already exists" in result.stderr.lower():
                print("✓ shannot MCP server already configured")
                return 0
            else:
                print(f"Failed: {result.stderr.strip()}")
                print("\nManual installation:")
                # Fall through to instructions

        # Fallback: print manual command
        print("Run: claude mcp add --transport stdio shannot -- shannot-mcp")

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
            print("    Build pypy-sandbox from PyPy source and add pypy3-c to PATH,")
            print(f"    or place pypy3-c binary in {RUNTIME_DIR}/")

        # Run self-test if both runtime and sandbox are available
        if is_runtime_installed() and sandbox_path:
            from .selftest import run_local_self_test

            result = run_local_self_test()
            if result.success:
                print(f"  ✓ Self-test: passed ({result.elapsed_ms:.0f}ms)")
            else:
                print("  ✗ Self-test: FAILED")
                if result.error:
                    print(f"    Error: {result.error}")
                if result.output:
                    print(f"    Output: {result.output!r}")

        if show_all:
            print()

    # Targets status
    if show_targets:
        from .config import load_remotes

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
                target_str = remote.target_string
                if remote.port != 22:
                    target_str += f":{remote.port}"
                print(f"  {name}: {target_str}")
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


class _VersionAction(argparse.Action):
    """Lazy version action that defers importlib.metadata lookup until --version is used."""

    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help="show program's version number and exit",
    ):
        super().__init__(
            option_strings=option_strings, dest=dest, default=default, nargs=0, help=help
        )

    def __call__(self, parser, namespace, values, option_string=None):
        from .config import get_version

        parser._print_message(f"shannot {get_version()}\n", sys.stdout)
        parser.exit()


def main() -> int:
    import textwrap

    parser = argparse.ArgumentParser(
        prog="shannot",
        description="Run Python in a sandbox. Commands execute only after your approval.",
        epilog=textwrap.dedent("""\
            Quick start:
              shannot run script.py                Run script, queue commands for review
              shannot run --code "print('hi')"     Run inline code
              shannot approve                      Review and execute queued commands

            See 'shannot <command> --help' for more details.
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action=_VersionAction,
    )
    subparsers = parser.add_subparsers(
        dest="command",
        help="Commands",
        metavar="{run,approve,status,setup}",
    )

    # ===== setup subcommand (with sub-subcommands) =====
    setup_parser = subparsers.add_parser(
        "setup",
        help="Configure shannot (interactive menu or subcommands)",
        description="Interactive setup or manage runtime, remotes, and MCP integration",
    )
    setup_subparsers = setup_parser.add_subparsers(dest="setup_command", help="Setup commands")

    # setup runtime
    setup_runtime_parser = setup_subparsers.add_parser(
        "runtime",
        help="Install PyPy sandbox runtime",
        description="Download and install PyPy 3.6 stdlib to ~/.local/share/shannot/runtime/",
    )
    setup_runtime_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force reinstall even if already installed",
    )
    setup_runtime_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )
    setup_runtime_parser.add_argument(
        "--status",
        "-s",
        action="store_true",
        help="Check if runtime is installed",
    )
    setup_runtime_parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove installed runtime",
    )

    # setup remote (with sub-subcommands)
    setup_remote_parser = setup_subparsers.add_parser(
        "remote",
        help="Manage SSH remote targets",
        description="Add, list, test, and remove named SSH targets",
    )
    remote_subparsers = setup_remote_parser.add_subparsers(
        dest="remote_command", help="Remote commands"
    )

    # setup remote add
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

    # setup remote list
    remote_subparsers.add_parser(
        "list",
        help="List configured remotes",
        description="Show all saved SSH targets",
    )

    # setup remote test
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

    # setup remote remove
    remote_remove_parser = remote_subparsers.add_parser(
        "remove",
        help="Remove a remote target",
        description="Delete a saved SSH target",
    )
    remote_remove_parser.add_argument(
        "name",
        help="Name of remote to remove",
    )

    # setup mcp (with sub-subcommands)
    setup_mcp_parser = setup_subparsers.add_parser(
        "mcp",
        help="MCP server installation and management",
        description="Install/manage MCP server for Claude Desktop/Code",
    )
    mcp_subparsers = setup_mcp_parser.add_subparsers(dest="mcp_command", help="MCP commands")

    # setup mcp install
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

    setup_parser.set_defaults(func=cmd_setup)

    # ===== run subcommand =====
    run_parser = subparsers.add_parser(
        "run",
        help="Run a script in the sandbox",
        description="Execute a PyPy sandbox with auto-detected pypy-sandbox binary and runtime",
    )
    run_parser.add_argument(
        "script",
        nargs="?",
        help="Python script to execute in the sandbox",
    )
    run_parser.add_argument(
        "--code",
        dest="code",
        metavar="CODE",
        help="Execute inline Python code",
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
    run_parser.add_argument(
        "--session",
        metavar="ID",
        help="Execute an approved session instead of dry-running a script",
    )
    run_parser.add_argument(
        "--json-output",
        action="store_true",
        dest="json_output",
        help="Output results as JSON (for automation)",
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

    # Parse and execute
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
