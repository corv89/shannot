#!/usr/bin/env python3
"""
Re-execute an approved session through the sandbox.

Usage:
    python -m sandboxlib.run_session <session_id>

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


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m sandboxlib.run_session <session_id>", file=sys.stderr)
        sys.exit(1)

    session_id = sys.argv[1]

    from .session import Session

    try:
        session = Session.load(session_id)
    except FileNotFoundError:
        print(f"Session not found: {session_id}", file=sys.stderr)
        sys.exit(1)

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
            exit_code = interact_main(argv) or 0
    except Exception as e:
        exit_code = 1
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

    # Update session with results
    session.stdout = stdout
    session.stderr = stderr
    session.exit_code = exit_code
    session.executed_at = datetime.now().isoformat()
    session.status = "executed" if exit_code == 0 else "failed"
    session.save()

    # Print output for debugging (will be captured by execute_session)
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
