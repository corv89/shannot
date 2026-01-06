#!/usr/bin/env python3
"""
Re-execute an approved session through the sandbox.

Usage:
    python -m shannot.run_session <session_id>

This module is called by execute_session() to run a script with
pre-approved commands loaded into the sandbox's allowlist.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import Session

# ANSI color codes
GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"


def format_execution_summary(session: Session, *, use_color: bool = True) -> str:
    """
    Generate human-readable execution summary.

    Shows what commands executed and what files were written.
    """
    lines = []

    # Commands executed
    if session.executed_commands:
        lines.append(f"Executed {len(session.executed_commands)} command(s):")
        for cmd_info in session.executed_commands:
            cmd = cmd_info.get("cmd", "")
            exit_code = cmd_info.get("exit_code", 0)
            ok = exit_code == 0

            if use_color:
                mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
                code_str = f"{DIM}exit {exit_code}{RESET}"
            else:
                mark = "✓" if ok else "✗"
                code_str = f"exit {exit_code}"

            # Truncate long commands
            display_cmd = cmd[:50] + "..." if len(cmd) > 50 else cmd
            lines.append(f"  {mark} {display_cmd:<54} {code_str}")

    # Files written
    if session.completed_writes:
        if lines:
            lines.append("")
        lines.append(f"Wrote {len(session.completed_writes)} file(s):")
        for write_info in session.completed_writes:
            path = write_info.get("path", "")
            success = write_info.get("success", False)

            if use_color:
                mark = f"{GREEN}✓{RESET}" if success else f"{RED}✗{RESET}"
            else:
                mark = "✓" if success else "✗"

            if success:
                size = write_info.get("size", 0)
                size_str = _format_size(size)
                lines.append(f"  {mark} {path} ({size_str})")
            else:
                error = write_info.get("error", "unknown error")
                lines.append(f"  {mark} {path} ({error})")

    # Files/directories deleted
    if session.completed_deletions:
        if lines:
            lines.append("")
        # Count actual deletions (not skipped)
        actual = [d for d in session.completed_deletions if not d.get("skipped")]
        skipped = len(session.completed_deletions) - len(actual)
        skip_note = f" ({skipped} already removed)" if skipped else ""
        lines.append(f"Deleted {len(actual)} item(s){skip_note}:")
        for del_info in session.completed_deletions:
            path = del_info.get("path", "")
            success = del_info.get("success", False)
            skipped_item = del_info.get("skipped", False)
            target_type = del_info.get("target_type", "file")

            if skipped_item:
                continue  # Don't show skipped items

            if use_color:
                mark = f"{GREEN}✓{RESET}" if success else f"{RED}✗{RESET}"
            else:
                mark = "✓" if success else "✗"

            type_label = " [dir]" if target_type == "directory" else ""
            if success:
                lines.append(f"  {mark} {path}{type_label}")
            else:
                error = del_info.get("error", "unknown error")
                lines.append(f"  {mark} {path} ({error})")

    return "\n".join(lines)


def _format_size(size: int) -> str:
    """Format size in bytes to human-readable string."""
    if size < 1024:
        return f"{size} bytes"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def execute_session_direct(session) -> int:
    """
    Execute a session directly (called from execute_session).

    This is the main execution logic, extracted to work with both
    subprocess invocation and direct function calls (needed for Nuitka).

    Returns the exit code.
    """
    # Build argv for interact.main() from structured sandbox_args
    args = session.sandbox_args
    argv = []

    # Reconstruct sandbox options
    if args.get("lib_path"):
        argv.append(f"--lib-path={args['lib_path']}")
    if args.get("tmp"):
        argv.append(f"--tmp={args['tmp']}")
    if args.get("nocolor"):
        argv.append("--nocolor")
    if args.get("raw_stdout"):
        argv.append("--raw-stdout")

    # Pass session ID so interact can load pre-approved commands
    argv.extend(["--session-id", session.id])

    # Add PyPy executable
    pypy_exe = args.get("pypy_exe", "pypy3-c-sandbox")
    argv.append(pypy_exe)

    # Determine script to run
    script_content = session.load_script()
    temp_script = None

    if script_content:
        # Write to temp file in the sandbox's tmp dir if available
        tmp_dir = args.get("tmp")
        if tmp_dir and os.path.isdir(tmp_dir):
            # Write script to the sandbox's tmp directory
            temp_script = os.path.join(tmp_dir, f"session_{session.id[:8]}.py")
            with open(temp_script, "w") as f:
                f.write(script_content)
            # Use virtual path
            script_path = f"/tmp/{os.path.basename(temp_script)}"
        else:
            # Use a system temp file
            fd, temp_script = tempfile.mkstemp(suffix=".py")
            with os.fdopen(fd, "w") as f:
                f.write(script_content)
            script_path = temp_script
    else:
        # Use original script path
        script_path = session.script_path

    # Add -S flag and script path (PyPy convention)
    argv.extend(["-S", script_path])

    # Execute and capture output
    from .interact import main as interact_main

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            result = interact_main(argv)
    except Exception as e:
        result = {"exit_code": 1, "executed_commands": []}
        stderr_capture.write(str(e))
    finally:
        # Clean up temp script
        if temp_script and os.path.exists(temp_script):
            try:
                os.unlink(temp_script)
            except OSError:
                pass  # Best effort cleanup

    stdout = stdout_capture.getvalue()
    stderr = stderr_capture.getvalue()

    # Extract exit code and executed commands from result
    if isinstance(result, dict):
        exit_code = result.get("exit_code", 0)
        executed_commands = result.get("executed_commands", [])
    else:
        exit_code = result or 0
        executed_commands = []

    # Commit pending writes to filesystem
    completed_writes = session.commit_writes()

    # Commit pending deletions to filesystem
    completed_deletions = session.commit_deletions()

    # Update session with results
    session.stdout = stdout
    session.stderr = stderr
    session.exit_code = exit_code
    session.executed_at = datetime.now().isoformat()
    session.status = "executed" if exit_code == 0 else "failed"
    session.executed_commands = executed_commands
    session.completed_writes = completed_writes
    session.completed_deletions = completed_deletions
    session.save()

    # Print output
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)

    # Print execution summary
    use_color = not session.sandbox_args.get("nocolor", False)
    summary = format_execution_summary(session, use_color=use_color)
    if summary:
        sys.stderr.write("\n" + summary + "\n")

    return exit_code


def main():
    """Command-line entry point for running as a module."""
    if len(sys.argv) < 2:
        print("Usage: python -m shannot.run_session <session_id>", file=sys.stderr)
        sys.exit(1)

    session_id = sys.argv[1]

    from .session import Session

    try:
        session = Session.load(session_id)
    except FileNotFoundError:
        print(f"Session not found: {session_id}", file=sys.stderr)
        sys.exit(1)

    exit_code = execute_session_direct(session)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
