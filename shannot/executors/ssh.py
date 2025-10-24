"""SSH executor for remote Linux systems.

This module provides the SSHExecutor class for running sandboxed
commands on remote Linux systems via SSH.

This executor allows Shannot to work from any platform (Linux, macOS,
Windows) by executing commands on remote Linux systems that have
bubblewrap installed.

Requirements:
    - asyncssh package (install with: pip install shannot[remote])
    - SSH access to remote Linux system
    - bubblewrap installed on remote system
    - No Python or Shannot needed on remote

Example:
    >>> executor = SSHExecutor(
    ...     host="prod.example.com",
    ...     username="admin",
    ...     key_file=Path("~/.ssh/id_ed25519")
    ... )
    >>> result = await executor.run_command(profile, ["ls", "/"])
    >>> await executor.cleanup()
"""

import asyncio
import shlex
from pathlib import Path

try:
    import asyncssh
except ImportError:
    raise ImportError(
        "asyncssh required for SSH execution. Install with: pip install shannot[remote]"
    ) from None

from shannot.execution import SandboxExecutor
from shannot.process import ProcessResult
from shannot.sandbox import BubblewrapCommandBuilder, SandboxProfile


class SSHExecutor(SandboxExecutor):
    """Execute commands on remote Linux system via SSH.

    This executor builds bubblewrap commands locally, then executes
    them on a remote Linux system via SSH. The remote system only
    needs bubblewrap and sshd - no Python or Shannot installation.

    Features:
        - Connection pooling for performance
        - SSH key authentication
        - Timeout handling
        - Works from any platform (Linux, macOS, Windows)

    The executor maintains a pool of SSH connections to avoid the
    overhead of establishing new connections for each command.

    Attributes:
        host: Remote hostname or IP address
        username: SSH username
        key_file: Path to SSH private key
        port: SSH port

    Example:
        >>> # From macOS, execute on remote Linux server
        >>> executor = SSHExecutor(
        ...     host="prod-server.example.com",
        ...     username="admin",
        ...     key_file=Path.home() / ".ssh" / "id_ed25519"
        ... )
        >>> try:
        ...     profile = SandboxProfile.load("minimal.json")
        ...     result = await executor.run_command(profile, ["ls", "/"])
        ...     print(result.stdout)
        ... finally:
        ...     await executor.cleanup()
    """

    def __init__(
        self,
        host: str,
        username: str | None = None,
        key_file: Path | None = None,
        port: int = 22,
        connection_pool_size: int = 5,
        known_hosts: Path | None = None,
        strict_host_key: bool = True,
    ):
        """Initialize SSH executor.

        Args:
            host: Remote hostname or IP address
            username: SSH username (None = use current user)
            key_file: Path to SSH private key (None = use SSH agent/config)
            port: SSH port (default: 22)
            connection_pool_size: Maximum pooled connections (default: 5)
            known_hosts: Path to known_hosts file (default: SSH config)
            strict_host_key: Enforce host key validation (default: True).
                             Set to False to disable validation (insecure).

        Example:
            >>> # Use SSH config defaults
            >>> executor = SSHExecutor(host="example.com")

            >>> # Explicit configuration
            >>> executor = SSHExecutor(
            ...     host="192.168.1.100",
            ...     username="deploy",
            ...     key_file=Path("/path/to/key"),
            ...     port=2222
            ... )
        """
        self.host: str = host
        self.username: str | None = username
        self.key_file: Path | None = key_file
        self.port: int = port
        self._connection_pool: list[asyncssh.SSHClientConnection] = []
        self._pool_size: int = connection_pool_size
        self._lock: asyncio.Lock = asyncio.Lock()
        self._known_hosts: Path | None = known_hosts
        self._strict_host_key: bool = strict_host_key

    async def _get_connection(self) -> asyncssh.SSHClientConnection:
        """Get or create SSH connection from pool.

        Returns:
            Active SSH connection

        Raises:
            RuntimeError: If SSH connection fails
        """
        async with self._lock:
            # Try to reuse existing connection
            if self._connection_pool:
                conn = self._connection_pool.pop()
                # Verify connection is still alive
                if not conn.is_closed():
                    return conn
                # Connection was closed, discard it

            # Create new connection
            try:
                # Prepare connection options
                connect_kwargs: dict[str, str | int | None | list[str]] = {
                    "host": self.host,
                    "port": self.port,
                    "username": self.username,
                }

                if self._known_hosts is not None:
                    connect_kwargs["known_hosts"] = str(self._known_hosts)
                elif not self._strict_host_key:
                    connect_kwargs["known_hosts"] = None

                # Configure authentication
                if self.key_file:
                    # Use specific key file
                    connect_kwargs["client_keys"] = [str(self.key_file)]
                # If no key_file specified, asyncssh will use default keys and agent

                conn = await asyncssh.connect(**connect_kwargs)
                return conn
            except Exception as e:
                raise RuntimeError(f"Failed to connect to {self.host}:{self.port}: {e}") from e

    async def _release_connection(self, conn: asyncssh.SSHClientConnection):
        """Return connection to pool or close if pool full.

        Args:
            conn: SSH connection to release
        """
        async with self._lock:
            if len(self._connection_pool) < self._pool_size:
                # Return to pool
                self._connection_pool.append(conn)
            else:
                # Pool is full, close connection
                conn.close()

    async def run_command(
        self, profile: SandboxProfile, command: list[str], timeout: int = 30
    ) -> ProcessResult:
        """Execute command on remote system via SSH.

        Builds bubblewrap command locally, then sends it via SSH
        to the remote system for execution.

        Args:
            profile: Sandbox profile configuration
            command: Command to execute as list of strings
            timeout: Timeout in seconds

        Returns:
            ProcessResult with stdout, stderr, returncode, duration

        Raises:
            TimeoutError: Command exceeded timeout
            RuntimeError: SSH connection or execution error

        Example:
            >>> executor = SSHExecutor(host="example.com")
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

        # Build bubblewrap command locally (disable path validation for remote execution)
        builder = BubblewrapCommandBuilder(profile, command, validate_paths=False)
        bwrap_args = builder.build()

        # Prepend 'bwrap' command (assumes bwrap is in PATH on remote)
        full_command = ["bwrap"] + bwrap_args

        # Convert to shell command string
        # Use shlex.join for safe shell escaping
        shell_cmd = shlex.join(full_command)

        # Execute via SSH
        conn = await self._get_connection()
        try:
            result = await conn.run(
                shell_cmd,
                timeout=timeout,
                check=False,  # Don't raise on non-zero exit
            )

            # Convert stdout/stderr to strings (asyncssh can return bytes or None)
            stdout_str = ""
            if result.stdout is not None:
                stdout_str = (
                    result.stdout
                    if isinstance(result.stdout, str)
                    else result.stdout.decode("utf-8")
                )

            stderr_str = ""
            if result.stderr is not None:
                stderr_str = (
                    result.stderr
                    if isinstance(result.stderr, str)
                    else result.stderr.decode("utf-8")
                )

            return ProcessResult(
                command=tuple(command),
                stdout=stdout_str,
                stderr=stderr_str,
                returncode=result.exit_status or 0,
                duration=0.0,  # asyncssh doesn't track timing
            )
        except asyncssh.TimeoutError as e:
            raise TimeoutError(f"Command timed out after {timeout}s: {' '.join(command)}") from e
        except asyncssh.Error as e:
            raise RuntimeError(f"SSH execution error on {self.host}: {e}") from e
        finally:
            await self._release_connection(conn)

    async def cleanup(self):
        """Close all pooled SSH connections.

        Should be called when the executor is no longer needed to
        ensure all SSH connections are properly closed.

        Example:
            >>> executor = SSHExecutor(host="example.com")
            >>> try:
            ...     result = await executor.run_command(...)
            ... finally:
            ...     await executor.cleanup()
        """
        async with self._lock:
            for conn in self._connection_pool:
                conn.close()
            self._connection_pool.clear()
