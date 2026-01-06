"""Shared sandbox execution logic for CLI and MCP server."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


@dataclass
class ExecutionResult:
    """Result from sandbox execution."""

    exit_code: int
    stdout: str
    stderr: str


def execute_script(
    script: str,
    *,
    pypy_bin: Path | None = None,
    tmp_dir: Path | None = None,
    dry_run: bool = False,
    remote_target: str | None = None,
) -> ExecutionResult:
    """Execute a Python script in the PyPy sandbox.

    Used by both CLI and MCP server for direct execution.

    Parameters
    ----------
    script : str
        Python script content to execute.
    pypy_bin : Path | None
        Path to pypy-sandbox binary (auto-detected if None).
    tmp_dir : Path | None
        Temp directory for script file (uses system temp if None).
    dry_run : bool
        If True, queue commands for approval instead of executing.
    remote_target : str | None
        SSH target for remote execution (e.g., "user@host").

    Returns
    -------
    ExecutionResult
        Contains exit_code, stdout, stderr.

    Raises
    ------
    RuntimeError
        If pypy-sandbox not found or runtime not installed.
    """
    from .mix_accept_input import MixAcceptInput
    from .mix_dump_output import MixDumpOutput
    from .mix_pypy import MixPyPy
    from .mix_remote import MixRemote
    from .mix_subprocess import MixSubprocess
    from .mix_vfs import Dir, File, MixVFS, OverlayDir, RealDir
    from .runtime import find_pypy_sandbox, get_runtime_path
    from .stubs import get_stubs
    from .vfs_procfs import build_proc, build_sys
    from .virtualizedproc import VirtualizedProc

    # Find PyPy sandbox binary
    if pypy_bin is None:
        pypy_bin = find_pypy_sandbox()
    if pypy_bin is None:
        raise RuntimeError("pypy-sandbox binary not found")

    # Find runtime stdlib
    runtime_path = get_runtime_path()
    if not runtime_path:
        raise RuntimeError("PyPy runtime not installed. Run 'shannot setup'")

    # Write script to temp file with bootstrap imports
    # _bootlocale must be imported early for text I/O encoding to work correctly
    bootstrap = "import _bootlocale\n"
    temp_dir = tmp_dir or Path(tempfile.gettempdir())
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=temp_dir) as f:
        f.write(bootstrap + script)
        script_path = Path(f.name)

    try:
        # Build VFS with stubs overlaid
        stubs: dict[str, Any] = {name: File(content) for name, content in get_stubs().items()}

        # Define the sandboxed process class with all mixins
        class SandboxedProc(
            MixRemote,
            MixSubprocess,
            MixPyPy,
            MixVFS,
            MixDumpOutput,
            MixAcceptInput,
            VirtualizedProc,
        ):
            virtual_cwd = "/tmp"
            vfs_root = Dir(
                {
                    "tmp": RealDir(str(temp_dir)),
                    "lib": Dir(
                        {
                            "pypy": File(b"", mode=0o111),
                            "lib-python": RealDir(str(runtime_path / "lib-python")),
                            "lib_pypy": OverlayDir(str(runtime_path / "lib_pypy"), overrides=stubs),
                        }
                    ),
                }
            )
            # Centralize file_writes_pending to avoid conflicting definitions in base classes
            file_writes_pending: list = []

        # Configure dry-run and remote modes
        SandboxedProc.subprocess_dry_run = dry_run
        if dry_run:
            SandboxedProc.vfs_track_writes = True

        if remote_target:
            SandboxedProc.remote_target = remote_target

        # Add /proc and /sys
        SandboxedProc.vfs_root.entries["proc"] = build_proc(
            cmdline=["/lib/pypy", "-S", f"/tmp/{script_path.name}"],
            exe_path="/lib/pypy",
            cwd=SandboxedProc.virtual_cwd,
            pid=SandboxedProc.virtual_pid,
            uid=SandboxedProc.virtual_uid,
            gid=SandboxedProc.virtual_gid,
        )
        SandboxedProc.vfs_root.entries["sys"] = build_sys()

        # Spawn subprocess
        popen = subprocess.Popen(
            ["/lib/pypy", "-S", f"/tmp/{script_path.name}"],
            executable=str(pypy_bin),
            env={},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        # Create virtualized proc with output capture via MixDumpOutput
        proc = SandboxedProc(popen.stdin, popen.stdout)

        # Capture output via MixDumpOutput's dump_stdout/dump_stderr attributes
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        proc.dump_stdout = stdout_buffer  # type: ignore[misc]
        proc.dump_stderr = stderr_buffer  # type: ignore[misc]
        # Use default (sanitized) output for captured strings

        # Load security profile
        proc.load_profile()

        # Run the sandbox
        proc.run()

        # Wait for subprocess to finish
        popen.terminate()
        popen.wait()

        return ExecutionResult(
            exit_code=popen.returncode or 0,
            stdout=stdout_buffer.getvalue(),
            stderr=stderr_buffer.getvalue(),
        )

    finally:
        # Clean up temp script file
        script_path.unlink(missing_ok=True)
