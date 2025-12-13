#!/usr/bin/env python3
"""
Re-execute an approved session through the sandbox.

Usage:
    python -m sandboxlib.run_session <session_id>

This module is called by execute_session() to run a script with
pre-approved commands loaded into the sandbox's allowlist.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


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

    # Build interact.py command from structured sandbox_args
    args = session.sandbox_args
    interact_path = Path(__file__).parent.parent / "interact.py"

    cmd = [sys.executable, str(interact_path)]

    # Reconstruct sandbox options
    if args.get("lib_path"):
        cmd.append(f"--lib-path={args['lib_path']}")
    if args.get("tmp"):
        cmd.append(f"--tmp={args['tmp']}")
    if args.get("nocolor"):
        cmd.append("--nocolor")
    if args.get("raw_stdout"):
        cmd.append("--raw-stdout")

    # Add pre-approved commands to allowlist
    for approved_cmd in session.commands:
        cmd.extend(["--allow-cmd", approved_cmd])

    # Add PyPy executable
    pypy_exe = args.get("pypy_exe", "pypy3-c-sandbox")
    cmd.append(pypy_exe)

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
    cmd.extend(["-S", script_path])

    # Execute and capture output
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except Exception as e:
        exit_code = 1
        stdout = ""
        stderr = str(e)
    finally:
        # Clean up temp script
        if temp_script and os.path.exists(temp_script):
            try:
                os.unlink(temp_script)
            except Exception:
                pass

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
