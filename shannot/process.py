from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass
class ProcessResult:
    """Represents the outcome of a subprocess invocation."""

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration: float

    def succeeded(self) -> bool:
        """Return True when the underlying process exited with status 0."""
        return self.returncode == 0


def _decode_stream(stream: bytes | str | None) -> str:
    if stream is None:
        return ""
    if isinstance(stream, str):
        return stream
    return stream.decode("utf-8", errors="replace")


def run_process(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = False,
    capture_output: bool = True,
    timeout: float | None = None,
    print_command: bool = False,
) -> ProcessResult:
    """Execute ``args`` with ``subprocess.run`` and return a structured result.

    Args:
        args: Command and arguments to execute.
        cwd: Optional working directory.
        env: Optional environment overrides.
        check: When True, re-raises ``CalledProcessError`` on non-zero exit.
        capture_output: When True, captures stdout/stderr into the result.
        timeout: Optional timeout in seconds.
        print_command: When True, echoes the command before execution.

    Returns:
        ProcessResult with stdout/stderr always normalised to text.
    """
    if print_command:
        print("+", " ".join(str(part) for part in args))

    start = time.monotonic()
    cwd_param = str(cwd) if cwd is not None else None
    env_param = dict(env) if env is not None else None
    timeout_param = float(timeout) if timeout is not None else None
    try:
        if capture_output:
            completed = subprocess.run(
                list(args),
                cwd=cwd_param,
                env=env_param,
                check=check,
                capture_output=True,
                text=True,
                timeout=timeout_param,
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
        else:
            completed = subprocess.run(
                list(args),
                cwd=cwd_param,
                env=env_param,
                check=check,
                capture_output=False,
                timeout=timeout_param,
            )
            stdout = ""
            stderr = ""
        return ProcessResult(
            command=tuple(args),
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            duration=time.monotonic() - start,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _decode_stream(getattr(exc, "stdout", None))
        stderr = _decode_stream(getattr(exc, "stderr", None) or getattr(exc, "output", None))
        timeout_seconds = timeout_param
        timeout_message = (
            f"Command timed out after {timeout_seconds} seconds"
            if timeout_seconds is not None
            else "Command timed out"
        )
        return ProcessResult(
            command=tuple(args),
            returncode=124,
            stdout=stdout,
            stderr=stderr or timeout_message,
            duration=time.monotonic() - start,
        )
    except subprocess.CalledProcessError as exc:
        stdout_raw = cast(bytes | str | None, getattr(exc, "stdout", None))
        stderr_raw = cast(bytes | str | None, getattr(exc, "stderr", None))
        stdout = _decode_stream(stdout_raw)
        stderr = _decode_stream(stderr_raw)
        return ProcessResult(
            command=tuple(args),
            returncode=exc.returncode,
            stdout=stdout,
            stderr=stderr,
            duration=time.monotonic() - start,
        )


def ensure_tool_available(executable: str) -> Path:
    """Ensure the given executable is present on PATH and return its resolved Path."""
    resolved = shutil.which(executable)
    if resolved is None:
        raise FileNotFoundError(f"Required executable '{executable}' was not found in PATH")
    return Path(resolved)
