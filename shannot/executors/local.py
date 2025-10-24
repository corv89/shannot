"""Local executor using bubblewrap on Linux.

This module provides the LocalExecutor class for running sandboxed
commands directly on the local Linux system using bubblewrap.

This is the fastest execution method but requires:
- Linux operating system
- bubblewrap installed and in PATH

For macOS/Windows, use SSHExecutor instead to execute on remote Linux systems.
"""

import asyncio
import platform
import shutil
import subprocess
from pathlib import Path

from shannot.execution import SandboxExecutor
from shannot.process import ProcessResult, run_process
from shannot.sandbox import BubblewrapCommandBuilder, SandboxProfile


class LocalExecutor(SandboxExecutor):
    """Execute commands on local Linux system using bubblewrap.

    This executor runs commands directly on the local system using
    bubblewrap for sandboxing. It's the fastest option but requires
    Linux with bubblewrap installed.

    The LocalExecutor is essentially a refactored version of the logic
    from SandboxManager, but implementing the SandboxExecutor interface
    to allow interchangeability with other executors (like SSHExecutor).

    Attributes:
        bwrap_path: Path to bubblewrap executable

    Example:
        >>> # On Linux with bubblewrap installed
        >>> executor = LocalExecutor()
        >>> profile = SandboxProfile.load("minimal.json")
        >>> result = await executor.run_command(profile, ["ls", "/"])
        >>> print(result.stdout)

    Raises:
        RuntimeError: If not on Linux or bubblewrap not found
    """

    def __init__(self, bwrap_path: Path | None = None):
        """Initialize local executor.

        Args:
            bwrap_path: Optional explicit path to bwrap binary.
                       If None, searches PATH automatically.

        Raises:
            RuntimeError: If not on Linux
            RuntimeError: If bubblewrap not found in PATH
        """
        self._validate_platform()
        self.bwrap_path: Path = bwrap_path or self._find_bwrap()

        # Validate bwrap_path exists and is executable
        if not self.bwrap_path.exists():
            raise RuntimeError(
                f"Bubblewrap not found at {self.bwrap_path}. "
                f"Install with: sudo apt-get install bubblewrap"
            )

    def _validate_platform(self) -> None:
        """Check that we're running on Linux.

        Raises:
            RuntimeError: If not on Linux
        """
        if platform.system() != "Linux":
            raise RuntimeError(
                f"LocalExecutor requires Linux, but running on {platform.system()}. "
                f"Use SSHExecutor to execute on remote Linux systems from "
                f"macOS/Windows. See REMOTE.md for configuration."
            )

    def _find_bwrap(self) -> Path:
        """Locate bubblewrap executable in PATH.

        Returns:
            Path to bubblewrap executable

        Raises:
            RuntimeError: If bubblewrap not found
        """
        bwrap = shutil.which("bwrap")
        if not bwrap:
            raise RuntimeError(
                "bubblewrap not found in PATH. Install with: sudo apt-get install bubblewrap"
            )
        return Path(bwrap)

    async def run_command(
        self, profile: SandboxProfile, command: list[str], timeout: int = 30
    ) -> ProcessResult:
        """Execute command locally via bubblewrap.

        Builds bubblewrap command from profile and executes it
        using subprocess on the local system.

        Args:
            profile: Sandbox profile configuration
            command: Command to execute as list of strings
            timeout: Timeout in seconds

        Returns:
            ProcessResult with stdout, stderr, returncode, duration

        Raises:
            TimeoutError: Command exceeded timeout
            RuntimeError: Execution error

        Example:
            >>> executor = LocalExecutor()
            >>> profile = SandboxProfile(
            ...     name="test",
            ...     allowed_commands=["echo"]
            ... )
            >>> result = await executor.run_command(
            ...     profile,
            ...     ["echo", "hello"],
            ...     timeout=10
            ... )
            >>> assert result.returncode == 0
            >>> assert "hello" in result.stdout
        """
        # Validate profile before building command
        profile.validate()

        # Build bubblewrap command
        builder = BubblewrapCommandBuilder(profile, command)
        bwrap_args = builder.build()

        # Prepend bwrap executable path
        full_command = [str(self.bwrap_path)] + bwrap_args

        # Execute locally using asyncio.to_thread to avoid blocking
        # Note: run_process is currently synchronous, so we run it in a thread
        try:
            result = await asyncio.to_thread(run_process, full_command, timeout=timeout)
            return result
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(f"Command timed out after {timeout}s: {' '.join(command)}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to execute command: {e}") from e
