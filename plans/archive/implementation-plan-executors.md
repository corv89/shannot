# Implementation Plan: SandboxExecutor Interface & SSH Support

## Overview

This document provides a detailed implementation plan for adding the `SandboxExecutor` abstraction and SSH-based remote execution to Shannot. This will enable macOS/Windows clients to execute sandboxed commands on remote Linux systems.

**Goals:**
1. Create abstract `SandboxExecutor` interface
2. Refactor existing code to use `LocalExecutor`
3. Implement `SSHExecutor` for remote execution
4. Support configuration-based executor selection
5. Maintain backward compatibility

**Non-Goals:**
- HTTP-based remote execution
- Nuitka compilation
- Windows/macOS as remote targets

---

## Phase 1: Executor Abstraction Layer

### 1.1 Create Executor Interface

**File:** `shannot/execution.py` (NEW)

```python
"""Executor abstraction for sandbox command execution."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from shannot.process import ProcessResult
from shannot.sandbox import SandboxProfile

ExecutorType = Literal["local", "ssh"]


class SandboxExecutor(ABC):
    """Abstract base class for all execution strategies.

    Executors are responsible for running sandboxed commands, either
    locally or on remote systems. All executors must implement the
    same interface to ensure tools/MCP code works unchanged.
    """

    @abstractmethod
    async def run_command(
        self,
        profile: SandboxProfile,
        command: list[str],
        timeout: int = 30
    ) -> ProcessResult:
        """Execute command in sandbox.

        Args:
            profile: Sandbox profile configuration
            command: Command to execute as list of strings
            timeout: Timeout in seconds

        Returns:
            ProcessResult with stdout, stderr, returncode, duration

        Raises:
            TimeoutError: Command exceeded timeout
            RuntimeError: Execution error (SSH connection, etc.)
        """
        ...

    async def read_file(
        self,
        profile: SandboxProfile,
        path: str
    ) -> str:
        """Read file from filesystem.

        Default implementation uses 'cat' via run_command.
        Subclasses can override for more efficient implementations.

        Args:
            profile: Sandbox profile
            path: Path to file

        Returns:
            File contents as string

        Raises:
            FileNotFoundError: File doesn't exist or can't be read
        """
        result = await self.run_command(profile, ["cat", path])
        if result.returncode != 0:
            raise FileNotFoundError(f"Cannot read {path}: {result.stderr}")
        return result.stdout

    async def cleanup(self):
        """Cleanup resources (connections, temp files, etc.).

        Called when executor is no longer needed. Subclasses should
        override to clean up resources like SSH connection pools.
        """
        pass
```

**Tests:** `tests/test_execution.py` (NEW)

```python
"""Tests for executor interface."""

import pytest
from shannot.execution import SandboxExecutor
from shannot.process import ProcessResult
from shannot.sandbox import SandboxProfile


class MockExecutor(SandboxExecutor):
    """Mock executor for testing interface."""

    def __init__(self):
        self.commands_run = []

    async def run_command(
        self,
        profile: SandboxProfile,
        command: list[str],
        timeout: int = 30
    ) -> ProcessResult:
        self.commands_run.append(command)
        return ProcessResult(
            command=tuple(command),
            returncode=0,
            stdout="mock output",
            stderr="",
            duration=0.1
        )


@pytest.mark.asyncio
async def test_executor_interface():
    """Test basic executor interface."""
    executor = MockExecutor()
    profile = SandboxProfile(name="test")

    result = await executor.run_command(profile, ["ls", "/"])

    assert result.returncode == 0
    assert result.stdout == "mock output"
    assert executor.commands_run == [["ls", "/"]]


@pytest.mark.asyncio
async def test_executor_read_file_default(minimal_profile):
    """Test default read_file implementation."""
    executor = MockExecutor()

    content = await executor.read_file(minimal_profile, "/etc/os-release")

    # Default implementation calls 'cat'
    assert executor.commands_run == [["cat", "/etc/os-release"]]


@pytest.mark.asyncio
async def test_executor_cleanup():
    """Test cleanup method."""
    executor = MockExecutor()
    await executor.cleanup()  # Should not raise
```

### 1.2 Create LocalExecutor

**File:** `shannot/executors/__init__.py` (NEW)

```python
"""Executor implementations for sandbox command execution."""

from shannot.executors.local import LocalExecutor

__all__ = ["LocalExecutor"]
```

**File:** `shannot/executors/local.py` (NEW)

```python
"""Local executor using bubblewrap on Linux."""

import platform
import shutil
from pathlib import Path
from typing import Optional

from shannot.execution import SandboxExecutor
from shannot.process import ProcessResult, run_process
from shannot.sandbox import BubblewrapCommandBuilder, SandboxProfile


class LocalExecutor(SandboxExecutor):
    """Execute commands on local Linux system using bubblewrap.

    This executor runs commands directly on the local system using
    bubblewrap for sandboxing. It's the fastest option but requires:
    - Linux operating system
    - bubblewrap installed and in PATH

    Example:
        executor = LocalExecutor()
        result = await executor.run_command(profile, ["ls", "/"])
    """

    def __init__(self, bwrap_path: Optional[Path] = None):
        """Initialize local executor.

        Args:
            bwrap_path: Optional explicit path to bwrap binary.
                       If None, searches PATH.

        Raises:
            RuntimeError: If bubblewrap not found or not on Linux
        """
        self._validate_platform()
        self.bwrap_path = bwrap_path or self._find_bwrap()

    def _validate_platform(self):
        """Check that we're on Linux."""
        if platform.system() != "Linux":
            raise RuntimeError(
                f"LocalExecutor requires Linux, but running on {platform.system()}. "
                f"Use SSHExecutor to execute on remote Linux systems."
            )

    def _find_bwrap(self) -> Path:
        """Locate bubblewrap executable in PATH."""
        path = shutil.which("bwrap")
        if not path:
            raise RuntimeError(
                "bubblewrap not found in PATH. "
                "Install with: sudo apt-get install bubblewrap"
            )
        return Path(path)

    async def run_command(
        self,
        profile: SandboxProfile,
        command: list[str],
        timeout: int = 30
    ) -> ProcessResult:
        """Execute command locally via bubblewrap.

        Builds bubblewrap command from profile and executes it
        using subprocess on the local system.
        """
        # Build bubblewrap command
        builder = BubblewrapCommandBuilder(profile)
        bwrap_cmd = builder.build(command)

        # Execute locally
        # Note: run_process is currently sync, we'll need to make it async
        # or use asyncio.to_thread() for now
        import asyncio
        result = await asyncio.to_thread(
            run_process,
            bwrap_cmd,
            timeout=timeout
        )

        return result
```

**Tests:** `tests/test_local_executor.py` (NEW)

```python
"""Tests for LocalExecutor."""

import platform
import pytest
from pathlib import Path

from shannot.executors.local import LocalExecutor
from shannot.sandbox import SandboxProfile


@pytest.mark.skipif(
    platform.system() != "Linux",
    reason="LocalExecutor requires Linux"
)
class TestLocalExecutor:
    """Tests for LocalExecutor (Linux only)."""

    def test_init_finds_bwrap(self):
        """Test that executor finds bwrap in PATH."""
        executor = LocalExecutor()
        assert executor.bwrap_path.exists()
        assert executor.bwrap_path.name == "bwrap"

    def test_init_with_explicit_path(self, tmp_path):
        """Test explicit bwrap path."""
        bwrap_path = tmp_path / "bwrap"
        bwrap_path.touch()
        bwrap_path.chmod(0o755)

        executor = LocalExecutor(bwrap_path=bwrap_path)
        assert executor.bwrap_path == bwrap_path

    @pytest.mark.asyncio
    @pytest.mark.requires_bwrap
    async def test_run_command(self, minimal_profile):
        """Test running a simple command."""
        executor = LocalExecutor()

        result = await executor.run_command(
            minimal_profile,
            ["echo", "hello"]
        )

        assert result.returncode == 0
        assert "hello" in result.stdout

    @pytest.mark.asyncio
    @pytest.mark.requires_bwrap
    async def test_run_command_timeout(self, minimal_profile):
        """Test timeout handling."""
        executor = LocalExecutor()

        with pytest.raises(TimeoutError):
            await executor.run_command(
                minimal_profile,
                ["sleep", "10"],
                timeout=1
            )


@pytest.mark.skipif(
    platform.system() == "Linux",
    reason="Test non-Linux rejection"
)
def test_local_executor_rejects_non_linux():
    """Test that LocalExecutor raises on non-Linux."""
    with pytest.raises(RuntimeError, match="requires Linux"):
        LocalExecutor()
```

### 1.3 Update SandboxManager

**File:** `shannot/sandbox.py` (MODIFY)

Add optional executor parameter to `SandboxManager` for backward compatibility:

```python
class SandboxManager:
    """Manages sandbox execution (backward compatible wrapper).

    This class maintains backward compatibility while using the new
    executor abstraction internally. New code should use executors directly.
    """

    def __init__(
        self,
        profile: SandboxProfile,
        bwrap_path: Optional[Path] = None,
        executor: Optional[SandboxExecutor] = None  # NEW
    ):
        self.profile = profile
        self.bwrap_path = bwrap_path

        # NEW: Use provided executor or create LocalExecutor
        if executor is not None:
            self.executor = executor
        else:
            from shannot.executors.local import LocalExecutor
            self.executor = LocalExecutor(bwrap_path=bwrap_path)

    async def run(
        self,
        command: list[str],
        check: bool = False,
        timeout: int = 30
    ) -> ProcessResult:
        """Execute command (delegates to executor).

        Backward compatible method that uses executor internally.
        """
        result = await self.executor.run_command(
            self.profile,
            command,
            timeout=timeout
        )

        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed: {result.stderr}")

        return result
```

---

## Phase 2: SSH Executor Implementation

### 2.1 Add asyncssh Dependency

**File:** `pyproject.toml` (MODIFY)

```toml
[project.optional-dependencies]
# ... existing groups ...

# Remote execution via SSH
remote = [
    "asyncssh>=2.14.0",
]

# All optional dependencies
all = [
    "mcp>=1.0.0",
    "pydantic-ai>=0.0.1",
    "pydantic>=2.0.0",
    "asyncssh>=2.14.0",  # NEW
]
```

### 2.2 Implement SSHExecutor

**File:** `shannot/executors/ssh.py` (NEW)

```python
"""SSH executor for remote Linux systems."""

import asyncio
import shlex
from pathlib import Path
from typing import Optional

try:
    import asyncssh
except ImportError:
    raise ImportError(
        "asyncssh required for SSH execution. "
        "Install with: pip install shannot[remote]"
    )

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

    Example:
        executor = SSHExecutor(
            host="prod.example.com",
            username="admin",
            key_file=Path("~/.ssh/id_ed25519")
        )
        result = await executor.run_command(profile, ["ls", "/"])
        await executor.cleanup()
    """

    def __init__(
        self,
        host: str,
        username: Optional[str] = None,
        key_file: Optional[Path] = None,
        port: int = 22,
        connection_pool_size: int = 5,
        known_hosts_file: Optional[Path] = None
    ):
        """Initialize SSH executor.

        Args:
            host: Remote hostname or IP address
            username: SSH username (None = use current user)
            key_file: Path to SSH private key (None = use SSH agent/config)
            port: SSH port
            connection_pool_size: Maximum pooled connections
            known_hosts_file: Path to known_hosts file (None = use default)
        """
        self.host = host
        self.username = username
        self.key_file = key_file
        self.port = port
        self._connection_pool: list[asyncssh.SSHClientConnection] = []
        self._pool_size = connection_pool_size
        self._lock = asyncio.Lock()
        self._known_hosts = known_hosts_file

    async def _get_connection(self) -> asyncssh.SSHClientConnection:
        """Get or create SSH connection from pool."""
        async with self._lock:
            # Try to reuse existing connection
            if self._connection_pool:
                return self._connection_pool.pop()

            # Create new connection
            try:
                conn = await asyncssh.connect(
                    self.host,
                    port=self.port,
                    username=self.username,
                    client_keys=[str(self.key_file)] if self.key_file else None,
                    known_hosts=str(self._known_hosts) if self._known_hosts else None,
                )
                return conn
            except asyncssh.Error as e:
                raise RuntimeError(f"Failed to connect to {self.host}: {e}") from e

    async def _release_connection(self, conn: asyncssh.SSHClientConnection):
        """Return connection to pool or close if pool full."""
        async with self._lock:
            if len(self._connection_pool) < self._pool_size:
                self._connection_pool.append(conn)
            else:
                conn.close()

    async def run_command(
        self,
        profile: SandboxProfile,
        command: list[str],
        timeout: int = 30
    ) -> ProcessResult:
        """Execute command on remote system via SSH.

        Builds bubblewrap command locally, then sends it via SSH
        to the remote system for execution.
        """
        # Build bubblewrap command locally
        builder = BubblewrapCommandBuilder(profile)
        bwrap_cmd = builder.build(command)

        # Convert to shell command
        shell_cmd = shlex.join(bwrap_cmd)

        # Execute via SSH
        conn = await self._get_connection()
        try:
            result = await conn.run(
                shell_cmd,
                timeout=timeout,
                check=False  # Don't raise on non-zero exit
            )

            return ProcessResult(
                command=tuple(command),
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.exit_status or 0,
                duration=0.0  # asyncssh doesn't track timing
            )
        except asyncssh.TimeoutError as e:
            raise TimeoutError(f"Command timed out after {timeout}s") from e
        except asyncssh.Error as e:
            raise RuntimeError(f"SSH execution error: {e}") from e
        finally:
            await self._release_connection(conn)

    async def cleanup(self):
        """Close all pooled SSH connections."""
        async with self._lock:
            for conn in self._connection_pool:
                conn.close()
            self._connection_pool.clear()
```

### 2.3 SSH Executor Tests

**File:** `tests/test_ssh_executor.py` (NEW)

```python
"""Tests for SSHExecutor."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from shannot.executors.ssh import SSHExecutor
from shannot.sandbox import SandboxProfile


@pytest.fixture
def mock_ssh_connection():
    """Mock asyncssh connection."""
    conn = AsyncMock()
    result = MagicMock()
    result.stdout = "test output"
    result.stderr = ""
    result.exit_status = 0
    conn.run = AsyncMock(return_value=result)
    conn.close = MagicMock()
    return conn


@pytest.mark.asyncio
async def test_ssh_executor_init():
    """Test SSHExecutor initialization."""
    executor = SSHExecutor(
        host="test.example.com",
        username="testuser",
        key_file=Path("/tmp/test_key"),
        port=2222
    )

    assert executor.host == "test.example.com"
    assert executor.username == "testuser"
    assert executor.port == 2222


@pytest.mark.asyncio
async def test_ssh_run_command(minimal_profile, mock_ssh_connection):
    """Test SSH command execution with mocked connection."""
    executor = SSHExecutor(host="test.example.com")

    with patch('asyncssh.connect', return_value=mock_ssh_connection):
        result = await executor.run_command(
            minimal_profile,
            ["echo", "hello"]
        )

    assert result.stdout == "test output"
    assert result.returncode == 0
    assert result.command == ("echo", "hello")
    mock_ssh_connection.run.assert_called_once()


@pytest.mark.asyncio
async def test_ssh_connection_pooling(minimal_profile, mock_ssh_connection):
    """Test that connections are reused from pool."""
    executor = SSHExecutor(host="test.example.com", connection_pool_size=2)

    with patch('asyncssh.connect', return_value=mock_ssh_connection) as mock_connect:
        # Run multiple commands
        for i in range(5):
            await executor.run_command(minimal_profile, ["echo", str(i)])

        # Should only connect once (pool reuse)
        assert mock_connect.call_count <= 2  # Pool size

    await executor.cleanup()


@pytest.mark.asyncio
async def test_ssh_timeout_handling(minimal_profile):
    """Test SSH timeout handling."""
    executor = SSHExecutor(host="test.example.com")

    mock_conn = AsyncMock()
    import asyncssh
    mock_conn.run = AsyncMock(side_effect=asyncssh.TimeoutError("Timeout"))

    with patch('asyncssh.connect', return_value=mock_conn):
        with pytest.raises(TimeoutError, match="timed out"):
            await executor.run_command(
                minimal_profile,
                ["sleep", "100"],
                timeout=1
            )


@pytest.mark.asyncio
async def test_ssh_cleanup(mock_ssh_connection):
    """Test cleanup closes all connections."""
    executor = SSHExecutor(host="test.example.com")

    with patch('asyncssh.connect', return_value=mock_ssh_connection):
        # Create some connections
        await executor._get_connection()
        await executor._get_connection()

    # Cleanup should close all
    await executor.cleanup()
    assert len(executor._connection_pool) == 0
```

---

## Phase 3: Configuration & CLI

### 3.1 Configuration Module

**File:** `shannot/config.py` (NEW)

```python
"""Configuration loading and executor factory."""

import os
from pathlib import Path
from typing import Dict, Optional

try:
    import tomli
except ImportError:
    import tomllib as tomli  # Python 3.11+

from shannot.execution import SandboxExecutor, ExecutorType
from shannot.executors.local import LocalExecutor


def load_config() -> Dict:
    """Load configuration from standard locations.

    Searches in order:
    1. $SHANNOT_CONFIG environment variable
    2. ~/.config/shannot/config.toml
    3. /etc/shannot/config.toml

    Returns:
        Configuration dictionary, or empty dict if no config found
    """
    config_paths = []

    # Environment variable
    if "SHANNOT_CONFIG" in os.environ:
        config_paths.append(Path(os.environ["SHANNOT_CONFIG"]))

    # User config
    config_paths.append(Path.home() / ".config" / "shannot" / "config.toml")

    # System config
    config_paths.append(Path("/etc/shannot/config.toml"))

    for path in config_paths:
        if path.exists():
            with open(path, "rb") as f:
                return tomli.load(f)

    return {}


def create_executor(
    executor_type: ExecutorType,
    **kwargs
) -> SandboxExecutor:
    """Create executor from type and parameters.

    Args:
        executor_type: Type of executor ("local" or "ssh")
        **kwargs: Executor-specific parameters

    Returns:
        Configured executor instance

    Raises:
        ValueError: Unknown executor type
        RuntimeError: Executor requirements not met
    """
    if executor_type == "local":
        return LocalExecutor(
            bwrap_path=kwargs.get("bwrap_path")
        )
    elif executor_type == "ssh":
        # Import here to avoid requiring asyncssh for local-only use
        from shannot.executors.ssh import SSHExecutor

        return SSHExecutor(
            host=kwargs["host"],
            username=kwargs.get("username"),
            key_file=Path(kwargs["key_file"]).expanduser()
                if "key_file" in kwargs else None,
            port=kwargs.get("port", 22),
            connection_pool_size=kwargs.get("connection_pool_size", 5)
        )
    else:
        raise ValueError(f"Unknown executor type: {executor_type}")


def create_executor_from_config(name: str) -> SandboxExecutor:
    """Create executor from configuration.

    Args:
        name: Executor name from config (e.g., "prod", "staging")

    Returns:
        Configured executor

    Raises:
        ValueError: Executor not found in config
    """
    config = load_config()
    executor_configs = config.get("executor", {})

    if name not in executor_configs:
        raise ValueError(
            f"Executor '{name}' not found in config. "
            f"Available: {', '.join(executor_configs.keys())}"
        )

    executor_config = executor_configs[name]
    executor_type = executor_config.pop("type")

    return create_executor(executor_type, **executor_config)


def get_default_executor() -> Optional[SandboxExecutor]:
    """Get default executor from configuration.

    Returns:
        Default executor, or None if not configured
    """
    config = load_config()
    default_name = config.get("default_executor")

    if default_name:
        return create_executor_from_config(default_name)

    return None
```

### 3.2 Update CLI for Remote Commands

**File:** `shannot/cli.py` (MODIFY)

Add remote subcommands:

```python
@click.group()
def remote():
    """Manage remote executors."""
    pass


@remote.command("list")
def remote_list():
    """List configured remote executors."""
    from shannot.config import load_config

    config = load_config()
    executors = config.get("executor", {})

    if not executors:
        click.echo("No executors configured")
        return

    for name, config in executors.items():
        executor_type = config.get("type", "unknown")
        click.echo(f"{name}: {executor_type}")

        if executor_type == "ssh":
            click.echo(f"  host: {config.get('host')}")
            click.echo(f"  user: {config.get('username', 'default')}")


@remote.command("test")
@click.argument("name")
def remote_test(name: str):
    """Test connection to remote executor."""
    import asyncio
    from shannot.config import create_executor_from_config, load_config
    from shannot.sandbox import SandboxProfile

    async def test_connection():
        try:
            executor = create_executor_from_config(name)
            profile = SandboxProfile(name="minimal", allowed_commands=["echo"])

            click.echo(f"Testing connection to '{name}'...")
            result = await executor.run_command(profile, ["echo", "test"])

            if result.returncode == 0:
                click.echo(f"✓ Connection successful")
            else:
                click.echo(f"✗ Command failed: {result.stderr}")

            await executor.cleanup()
        except Exception as e:
            click.echo(f"✗ Error: {e}")

    asyncio.run(test_connection())


# Add remote subcommand to main CLI
cli.add_command(remote)
```

---

## Phase 4: MCP Integration

### 4.1 Update SandboxDeps

**File:** `shannot/tools.py` (MODIFY)

```python
class SandboxDeps:
    """Dependencies for sandbox tools.

    Supports both local and remote execution via executor abstraction.
    """

    def __init__(
        self,
        profile_path: Path,
        executor: Optional[SandboxExecutor] = None,
        executor_name: Optional[str] = None
    ):
        """Initialize dependencies.

        Args:
            profile_path: Path to sandbox profile
            executor: Explicit executor instance (optional)
            executor_name: Name of executor from config (optional)

        If neither executor nor executor_name is provided, uses
        LocalExecutor by default.
        """
        self.profile = SandboxProfile.load(profile_path)

        if executor is not None:
            self.executor = executor
        elif executor_name is not None:
            from shannot.config import create_executor_from_config
            self.executor = create_executor_from_config(executor_name)
        else:
            from shannot.executors.local import LocalExecutor
            self.executor = LocalExecutor()

    async def cleanup(self):
        """Cleanup executor resources."""
        await self.executor.cleanup()
```

### 4.2 Update MCP Server

**File:** `shannot/mcp_server.py` (MODIFY)

```python
class ShannotMCPServer:
    """MCP server for Shannot sandbox execution.

    Supports both local and remote execution via executor configuration.
    """

    def __init__(
        self,
        profiles: list[Path],
        executor_name: Optional[str] = None
    ):
        """Initialize MCP server.

        Args:
            profiles: List of profile paths
            executor_name: Name of executor from config (optional)
                          If not provided, uses default or LocalExecutor
        """
        self.profiles = profiles
        self.executor_name = executor_name

        if executor_name:
            from shannot.config import create_executor_from_config
            self.executor = create_executor_from_config(executor_name)
        else:
            from shannot.config import get_default_executor
            self.executor = get_default_executor()
            if self.executor is None:
                from shannot.executors.local import LocalExecutor
                self.executor = LocalExecutor()
```

---

## Testing Strategy

### Unit Tests
- Mock SSH connections using unittest.mock
- Test executor interface compliance
- Test configuration loading
- Test error handling

### Integration Tests
- Require SSH server (mark with `@pytest.mark.integration`)
- Test real SSH connections to localhost
- Test connection pooling
- Test timeout handling

### Platform Tests
- Linux: Test both local and SSH executors
- macOS/Windows: Test SSH executor only
- Use `@pytest.mark.skipif` for platform-specific tests

---

## Backward Compatibility Checklist

- [ ] `SandboxManager` still works with existing code
- [ ] Existing profiles load unchanged
- [ ] CLI commands work as before
- [ ] MCP server works with default (local) executor
- [ ] Tests pass on Linux with bubblewrap

---

## Documentation Updates

1. Update `README.md` with executor overview
2. Create `docs/remote-execution.md` guide
3. Add SSH setup instructions
4. Document configuration file format
5. Add macOS/Windows quick start guide

---

## Migration Path

**For existing users (Linux with bubblewrap):**
- No changes required
- Everything works as before
- Can optionally add SSH executors for remote systems

**For new users (macOS/Windows):**
- Install Shannot: `pip install shannot[remote]`
- Configure SSH executor in `~/.config/shannot/config.toml`
- Use `shannot remote test <name>` to verify connection
- Use with MCP/Claude Desktop

---

## Success Criteria

- [ ] LocalExecutor works on Linux (backward compatible)
- [ ] SSHExecutor works from macOS → Linux
- [ ] SSHExecutor works from Windows → Linux
- [ ] Configuration loads from TOML files
- [ ] CLI supports remote management
- [ ] MCP server works with remote executors
- [ ] All tests pass
- [ ] Documentation complete
