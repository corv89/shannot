"""Executor abstraction for sandbox command execution.

This module provides the abstract base class for all execution strategies.
Executors are responsible for running sandboxed commands, either locally
or on remote systems. All executors implement the same interface to ensure
tools and MCP code works unchanged.

Example:
    Local execution on Linux:
        >>> executor = LocalExecutor()
        >>> result = await executor.run_command(profile, ["ls", "/"])

    Remote execution via SSH:
        >>> executor = SSHExecutor(host="prod.example.com")
        >>> result = await executor.run_command(profile, ["ls", "/"])
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal

from shannot.process import ProcessResult

if TYPE_CHECKING:
    from shannot.sandbox import SandboxProfile

# Type for executor configuration
ExecutorType = Literal["local", "ssh"]


class SandboxExecutor(ABC):
    """Abstract base class for all execution strategies.

    Executors are responsible for running sandboxed commands, either
    locally or on remote systems. All executors must implement the
    same interface to ensure tools/MCP code works unchanged.

    The executor abstraction allows Shannot to work on any platform:
    - Linux: Use LocalExecutor for native bubblewrap execution
    - macOS/Windows: Use SSHExecutor to execute on remote Linux systems

    Subclasses must implement:
        - run_command(): Execute command in sandbox

    Subclasses may override:
        - read_file(): Read file from filesystem (default uses cat)
        - cleanup(): Clean up resources like connections
    """

    @abstractmethod
    async def run_command(
        self, profile: SandboxProfile, command: list[str], timeout: int = 30
    ) -> ProcessResult:
        """Execute command in sandbox.

        This is the core method all executors must implement. It takes
        a sandbox profile (which defines allowed commands, mounts, etc.)
        and executes the command in that sandbox environment.

        Args:
            profile: Sandbox profile configuration
            command: Command to execute as list of strings
                    Example: ["ls", "-la", "/tmp"]
            timeout: Timeout in seconds (default: 30)

        Returns:
            ProcessResult with:
                - command: The command that was executed (tuple)
                - stdout: Standard output as string
                - stderr: Standard error as string
                - returncode: Exit code (0 = success)
                - duration: Execution time in seconds

        Raises:
            TimeoutError: Command exceeded timeout
            RuntimeError: Execution error (SSH connection failure, etc.)

        Example:
            >>> result = await executor.run_command(
            ...     profile,
            ...     ["echo", "hello"],
            ...     timeout=10
            ... )
            >>> assert result.returncode == 0
            >>> assert "hello" in result.stdout
        """
        raise NotImplementedError("Subclasses must implement run_command")

    async def read_file(self, profile: SandboxProfile, path: str) -> str:
        """Read file from filesystem.

        Default implementation uses 'cat' command via run_command.
        Subclasses can override for more efficient implementations
        (e.g., SSH executor could use SFTP).

        Args:
            profile: Sandbox profile (must allow 'cat' command)
            path: Absolute path to file to read

        Returns:
            File contents as string

        Raises:
            FileNotFoundError: File doesn't exist or can't be read

        Example:
            >>> content = await executor.read_file(
            ...     profile,
            ...     "/etc/os-release"
            ... )
            >>> assert "Linux" in content
        """
        result = await self.run_command(profile, ["cat", path])
        if result.returncode != 0:
            raise FileNotFoundError(f"Cannot read {path}: {result.stderr}")
        return result.stdout

    async def cleanup(self):
        """Cleanup resources (connections, temp files, etc.).

        Called when executor is no longer needed. Subclasses should
        override to clean up resources like:
        - SSH connection pools
        - Temporary files
        - Background processes

        Default implementation does nothing.

        Example:
            >>> executor = SSHExecutor(host="example.com")
            >>> try:
            ...     result = await executor.run_command(...)
            ... finally:
            ...     await executor.cleanup()  # Close SSH connections
        """
        # Default implementation: no cleanup needed
        return None
